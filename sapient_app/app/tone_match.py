from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass

import anthropic
import praw
import prawcore
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

log = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-opus-4-7"
TOP_COMMENTS = 10
MAX_COMMENT_CHARS = 600
MAX_POST_CHARS = 1500


SYSTEM_PROMPT = """You are an editor helping a user adapt a Reddit reply to fit
a specific subreddit's culture, without altering what the user is saying.

You will receive:
- The user's draft reply.
- The parent post the user is replying to.
- The top comments from the same subreddit, as a tone sample.

Hard rules — never break these:
1. Preserve the user's facts, opinions, claims, and any product mention exactly
   as written. You may move them around or re-word the surrounding language, but
   the substance and the product name must survive unchanged.
2. Adjust only register, length, vocabulary, and structure to fit the sub's tone
   (e.g. concise + dry, long + earnest, casual + jargon-heavy, etc.).
3. Never invent biographical details about the user (job, location, history,
   relationships, credentials) or new claims about the product (features,
   pricing, comparisons) that are not already in the draft.
4. Do not add disclaimers, hedges, or compliments that change the user's stance.
5. If the draft reads as promotional in a subreddit whose top comments punish
   promotion (downvoted promo, mod warnings, "no self-promo" norms visible in
   the sample), flag it and suggest a reframing as personal experience or a
   genuine question — but still leave the product mention intact in the
   revised draft. The user decides whether to use your reframing.

Output ONLY a JSON object of this exact shape, no markdown fences:
{
  "revised_draft": "<the rewritten reply, ready to paste>",
  "promo_risk": "low" | "med" | "high",
  "promo_reasoning": "<1-3 sentences citing specific tone cues from the sample>",
  "tone_notes": "<1-3 sentences on what you adjusted and why>",
  "reframe_suggestion": "<optional: only if promo_risk is med/high — a single
                         paragraph alternative framing as personal experience or
                         genuine question, still preserving the product mention>"
}
"""


@dataclass
class SubredditSample:
    subreddit: str
    parent_title: str
    parent_body: str
    parent_score: int
    comments: list["CommentSample"]


@dataclass
class CommentSample:
    body: str
    score: int


@dataclass
class ToneMatchResult:
    revised_draft: str
    promo_risk: str
    promo_reasoning: str
    tone_notes: str
    reframe_suggestion: str | None


_REDDIT_RETRYABLE = (
    prawcore.exceptions.ServerError,
    prawcore.exceptions.RequestException,
    prawcore.exceptions.ResponseException,
)

_ANTHROPIC_RETRYABLE = (
    anthropic.APIConnectionError,
    anthropic.APITimeoutError,
    anthropic.RateLimitError,
    anthropic.InternalServerError,
)


def _truncate(text: str, limit: int) -> str:
    text = text or ""
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _make_reddit() -> praw.Reddit:
    return praw.Reddit(
        client_id=os.environ["REDDIT_CLIENT_ID"],
        client_secret=os.environ["REDDIT_CLIENT_SECRET"],
        user_agent=os.environ.get(
            "REDDIT_USER_AGENT", "tone-match-cli/0.1 by u/anon"
        ),
        check_for_async=False,
    )


@retry(
    reraise=True,
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type(_REDDIT_RETRYABLE),
)
def fetch_sample(post_url: str, subreddit: str) -> SubredditSample:
    reddit = _make_reddit()
    submission = reddit.submission(url=post_url)
    submission.comment_sort = "top"
    submission.comments.replace_more(limit=0)

    top = sorted(
        submission.comments.list(),
        key=lambda c: getattr(c, "score", 0),
        reverse=True,
    )[:TOP_COMMENTS]

    comments = [
        CommentSample(
            body=_truncate(getattr(c, "body", ""), MAX_COMMENT_CHARS),
            score=int(getattr(c, "score", 0)),
        )
        for c in top
        if getattr(c, "body", None)
    ]

    sub_name = str(submission.subreddit)
    if sub_name.lower() != subreddit.lower():
        log.warning(
            "post is in r/%s but user said r/%s — using actual r/%s",
            sub_name,
            subreddit,
            sub_name,
        )

    return SubredditSample(
        subreddit=sub_name,
        parent_title=submission.title or "",
        parent_body=_truncate(submission.selftext or "", MAX_POST_CHARS),
        parent_score=int(submission.score or 0),
        comments=comments,
    )


def _format_sample(sample: SubredditSample) -> str:
    parts = [
        f"Subreddit: r/{sample.subreddit}",
        f"Parent post (score {sample.parent_score}):",
        f"  Title: {sample.parent_title}",
    ]
    if sample.parent_body:
        parts.append(f"  Body: {sample.parent_body}")
    parts.append("")
    parts.append("Top comments (in score order — note what gets upvoted):")
    for i, c in enumerate(sample.comments, 1):
        parts.append(f"  [{i}] (score {c.score}) {c.body}")
    return "\n".join(parts)


_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse_response(text: str) -> ToneMatchResult:
    match = _JSON_RE.search(text)
    if not match:
        raise ValueError(f"no JSON object in model response: {text!r}")
    data = json.loads(match.group(0))
    risk = str(data.get("promo_risk", "low")).lower().strip()
    if risk not in {"low", "med", "high"}:
        risk = "low"
    reframe = data.get("reframe_suggestion")
    return ToneMatchResult(
        revised_draft=str(data.get("revised_draft", "")).strip(),
        promo_risk=risk,
        promo_reasoning=str(data.get("promo_reasoning", "")).strip(),
        tone_notes=str(data.get("tone_notes", "")).strip(),
        reframe_suggestion=str(reframe).strip() if reframe else None,
    )


@retry(
    reraise=True,
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=2, max=60),
    retry=retry_if_exception_type(_ANTHROPIC_RETRYABLE),
)
def revise(
    draft: str,
    sample: SubredditSample,
    model: str = DEFAULT_MODEL,
) -> ToneMatchResult:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    user_content = (
        "Tone sample from the target subreddit:\n"
        f"{_format_sample(sample)}\n\n"
        "---\n\n"
        "User's draft reply (preserve facts, opinions, and product mention exactly):\n"
        f"{draft}"
    )
    message = client.messages.create(
        model=model,
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )
    text = "".join(
        b.text for b in message.content if getattr(b, "type", None) == "text"
    )
    return _parse_response(text)

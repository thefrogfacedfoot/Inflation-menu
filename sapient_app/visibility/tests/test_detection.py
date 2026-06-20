from __future__ import annotations

from dataclasses import dataclass

import pytest

from visibility.detect import (
    SentimentClassifier,
    detect_mentions,
    find_mention_positions,
)


@dataclass
class _E:
    id: int
    name: str
    aliases: list[str]


def test_alias_word_boundary_no_macme_false_positive():
    e = _E(id=1, name="Acme", aliases=["acmewidget.com"])
    matches = find_mention_positions("the macme protocol is unrelated", [e])
    assert matches == []


@pytest.mark.parametrize("text", ["acme_dev", "acme_v2", "_acme_", "_acme", "acme_"])
def test_alias_matches_across_underscore_boundaries(text):
    e = _E(id=1, name="acme", aliases=[])
    matches = find_mention_positions(text, [e])
    assert len(matches) == 1, f"expected 1 match in {text!r}, got {matches}"


@pytest.mark.parametrize("text", ["macme", "acmewidget", "acme123", "123acme"])
def test_alias_still_rejects_letter_or_digit_neighbors(text):
    e = _E(id=1, name="acme", aliases=[])
    assert find_mention_positions(text, [e]) == []


def test_boundary_parity_with_js_detector():
    """The Python detector must agree with the dashboard's JS detector for
    every row in the ported fixture. If this test fails, the two engines
    have drifted and the cross-service guarantees no longer hold."""
    import json
    from pathlib import Path

    fixture = Path(__file__).parent / "_fixtures" / "boundary_parity.json"
    cases = json.loads(fixture.read_text())
    mismatches: list[str] = []
    for i, case in enumerate(cases):
        e = _E(id=i + 1, name=case["alias"], aliases=[])
        actual = bool(find_mention_positions(case["text"], [e]))
        if actual != case["expected"]:
            mismatches.append(
                f"  [{i}] text={case['text']!r} alias={case['alias']!r} "
                f"expected={case['expected']} got={actual} ({case.get('note','')})"
            )
    assert not mismatches, "boundary parity drift:\n" + "\n".join(mismatches)


def test_alias_matches_case_insensitive_at_string_boundaries():
    e = _E(id=1, name="Acme", aliases=[])
    matches = find_mention_positions("ACME is great", [e])
    assert len(matches) == 1
    assert matches[0].entity_id == 1
    assert matches[0].matched.lower() == "acme"


def test_alias_regex_specials_escaped_cpp():
    e = _E(id=2, name="C++", aliases=[])
    assert len(find_mention_positions("I write C++ daily", [e])) == 1
    assert find_mention_positions("I write CPlusPlus daily", [e]) == []


def test_alias_regex_specials_escaped_dotnet():
    e = _E(id=3, name=".NET", aliases=[])
    assert len(find_mention_positions("Working in .NET today", [e])) == 1
    # ASP.NET: "p" before "." is a word char → no match for the .NET alias.
    assert find_mention_positions("Working in ASP.NET today", [e]) == []


def test_alias_unicode_boundary():
    e = _E(id=4, name="fe", aliases=[])
    # "café" — "é" is a Unicode letter, so "fe" should not match inside it.
    matches = find_mention_positions("I drink café every morning", [e])
    assert matches == []


def test_context_window_clamps_to_text():
    e = _E(id=5, name="Acme", aliases=[])
    # "-" is not a word character, so the alias boundary still passes.
    text = "-" * 50 + " Acme " + "-" * 50
    matches = find_mention_positions(text, [e])
    assert len(matches) == 1
    # Padding is clamped to the string length: 50 + 1 + 4 + 1 + 50 = 106.
    assert len(matches[0].context) == 106
    assert "Acme" in matches[0].context


class _RecordingLLM:
    def __init__(self, response='{"sentiment":"positive","is_recommendation":true}'):
        self.response = response
        self.calls: list[str] = []

    async def classify(self, prompt: str) -> str:
        self.calls.append(prompt)
        return self.response


@pytest.mark.asyncio
async def test_sentiment_classifier_caches_on_second_call(session):
    from visibility.models import Entity

    e = Entity(name="Acme", type="brand", aliases=[])
    session.add(e)
    session.commit()

    llm = _RecordingLLM()
    classifier = SentimentClassifier(session, llm)

    r1 = await classifier.classify("Acme is amazing", entity_id=e.id, entity_name="Acme")
    session.commit()
    r2 = await classifier.classify("Acme is amazing", entity_id=e.id, entity_name="Acme")

    assert r1.sentiment == "positive"
    assert r1.is_recommendation is True
    assert r2 == r1
    # Second call must have hit the cache, not the LLM.
    assert len(llm.calls) == 1


@pytest.mark.asyncio
async def test_sentiment_cache_keyed_by_text_and_entity(session):
    from visibility.models import Entity

    a = Entity(name="Acme", type="brand", aliases=[])
    b = Entity(name="Beta", type="competitor", aliases=[])
    session.add_all([a, b])
    session.commit()

    llm = _RecordingLLM()
    classifier = SentimentClassifier(session, llm)

    await classifier.classify("same text", entity_id=a.id, entity_name="Acme")
    await classifier.classify("same text", entity_id=b.id, entity_name="Beta")
    session.commit()
    # Different entity → different cache key → second call still hits LLM.
    assert len(llm.calls) == 2


@pytest.mark.asyncio
async def test_detect_mentions_wires_classifier_results(session):
    from visibility.models import Entity

    e = Entity(name="Acme", type="brand", aliases=[])
    session.add(e)
    session.commit()

    llm = _RecordingLLM('{"sentiment":"negative","is_recommendation":false}')
    classifier = SentimentClassifier(session, llm)

    out = await detect_mentions("I tried Acme and it broke", [e], classifier)
    assert len(out) == 1
    assert out[0].entity_id == e.id
    assert out[0].sentiment == "negative"
    assert out[0].is_recommendation is False

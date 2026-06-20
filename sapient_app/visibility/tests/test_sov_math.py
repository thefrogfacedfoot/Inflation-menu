from visibility.sov import MentionRow, share_of_voice, summarize


def test_share_of_voice_basic():
    assert share_of_voice(3, 10) == 0.3
    assert share_of_voice(0, 0) == 0.0
    assert share_of_voice(5, 5) == 1.0


def test_summarize_per_source_per_entity():
    rows = [
        MentionRow("chatgpt", 1, "brand", True, None),
        MentionRow("chatgpt", 1, "brand", False, None),
        MentionRow("chatgpt", 2, "competitor", True, None),
        MentionRow("chatgpt", 2, "competitor", True, None),
        MentionRow("claude", 1, "brand", False, None),
    ]
    summaries = {(s.source, s.entity_id): s for s in summarize(rows)}

    # chatgpt: 4 total mentions, brand=2 → 50%
    assert summaries[("chatgpt", 1)].mention_count == 2
    assert summaries[("chatgpt", 1)].recommendation_count == 1
    assert summaries[("chatgpt", 1)].share_of_voice == 0.5
    # competitor share is 50% too
    assert summaries[("chatgpt", 2)].share_of_voice == 0.5
    assert summaries[("chatgpt", 2)].recommendation_count == 2

    # claude: 1 total → brand SoV = 100%
    assert summaries[("claude", 1)].share_of_voice == 1.0


def test_summarize_avg_rank_for_serp():
    rows = [
        MentionRow("serp", 1, "brand", False, 1),
        MentionRow("serp", 1, "brand", True, 3),
        MentionRow("serp", 1, "brand", False, None),
        MentionRow("serp", 2, "competitor", False, 2),
    ]
    out = {(s.source, s.entity_id): s for s in summarize(rows)}

    # Two ranked mentions for brand (1 and 3); the None doesn't count.
    assert out[("serp", 1)].avg_rank_when_mentioned == 2.0
    assert out[("serp", 2)].avg_rank_when_mentioned == 2.0


def test_summarize_no_rank_returns_none():
    rows = [MentionRow("claude", 1, "brand", False, None)]
    out = summarize(rows)
    assert out[0].avg_rank_when_mentioned is None


def test_summarize_empty():
    assert summarize([]) == []

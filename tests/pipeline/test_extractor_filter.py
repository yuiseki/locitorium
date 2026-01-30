from locitorium.pipeline.extractor import _filter_mentions


def test_filter_mentions_requires_verbatim_or_casefold_match():
    text = "FOSS4G 2026 開催概要 広島国際会議場"
    mentions = ["Hiroshima", "広島", "広島国際会議場", "Japan"]
    filtered = _filter_mentions(text, mentions)
    assert "広島" in filtered
    assert "広島国際会議場" in filtered
    assert "Hiroshima" not in filtered
    assert "Japan" not in filtered

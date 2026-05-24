from comps.search.retrieve import HybridRow, _band, dedupe_by_deal


def test_dedupe_keeps_best_score_per_deal_and_preserves_order():
    rows = [
        HybridRow(chunk_id=1, deal_id=10, score=0.5),
        HybridRow(chunk_id=2, deal_id=20, score=0.4),
        HybridRow(chunk_id=3, deal_id=10, score=0.9),  # better score for deal 10
        HybridRow(chunk_id=4, deal_id=30, score=0.1),
    ]
    out = dedupe_by_deal(rows)
    assert [r.deal_id for r in out] == [10, 20, 30]
    assert out[0].score == 0.9


def test_band_extracts_pair():
    assert _band({"revenue_band": [10, 20]}, "revenue_band") == (10, 20)
    assert _band({}, "revenue_band") == (None, None)
    assert _band({"revenue_band": "junk"}, "revenue_band") == (None, None)

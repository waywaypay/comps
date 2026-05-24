from datetime import date

from comps.search.rerank import Candidate


def test_candidate_snippet_compose():
    c = Candidate(
        deal_id=1,
        score=0.5,
        deal={
            "target_name": "Acme",
            "announced_on": date(2023, 5, 1),
            "thesis": "Buyout to consolidate vertical SaaS.",
        },
        top_chunk_text="Recurring revenue 95%.",
    )
    s = c.snippet()
    assert "Acme" in s
    assert "(2023)" in s
    assert "Buyout" in s
    assert "Recurring revenue" in s


def test_candidate_snippet_handles_missing_pieces():
    c = Candidate(deal_id=1, score=0.5, deal={"target_name": "X"}, top_chunk_text=None)
    s = c.snippet()
    assert "X" in s

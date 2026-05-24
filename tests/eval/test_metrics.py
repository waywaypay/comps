from comps.eval.metrics import mrr, ndcg, recall


def test_ndcg_perfect_order():
    judged = {1: 3, 2: 2, 3: 1}
    retrieved = [1, 2, 3]
    assert ndcg(retrieved, judged, k=3) == 1.0


def test_ndcg_reversed_order_below_one():
    judged = {1: 3, 2: 2, 3: 1}
    score = ndcg([3, 2, 1], judged, k=3)
    assert 0.0 < score < 1.0


def test_ndcg_no_judgments():
    assert ndcg([1, 2], {}, k=5) == 0.0


def test_recall_basic():
    judged = {1: 3, 2: 2, 3: 0, 4: 3}
    # Relevant = {1, 2, 4} since grade >= 2
    assert recall([1, 2, 5, 6], judged, k=4) == 2 / 3
    assert recall([1, 2, 4], judged, k=3) == 1.0
    assert recall([5, 6, 7], judged, k=3) == 0.0


def test_recall_no_relevant():
    assert recall([1, 2], {1: 0, 2: 1}, k=5) == 0.0


def test_mrr():
    judged = {1: 0, 2: 3, 3: 1}
    assert mrr([1, 2, 3], judged) == 0.5
    assert mrr([3, 2, 1], judged) == 0.5
    assert mrr([1, 3], judged) == 0.0

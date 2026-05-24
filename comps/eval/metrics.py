"""Retrieval metrics: nDCG@k and recall@k.

Grade scale: 0 irrelevant, 1 weakly related, 2 good, 3 perfect.
"""

from __future__ import annotations

from collections.abc import Sequence
from math import log2


def ndcg(retrieved_deal_ids: Sequence[int], judged: dict[int, int], k: int = 10) -> float:
    gains = [(2 ** judged.get(d, 0) - 1) for d in retrieved_deal_ids[:k]]
    dcg = sum(g / log2(i + 2) for i, g in enumerate(gains))
    ideal_grades = sorted(judged.values(), reverse=True)[:k]
    idcg = sum((2**g - 1) / log2(i + 2) for i, g in enumerate(ideal_grades))
    return dcg / idcg if idcg else 0.0


def recall(retrieved_deal_ids: Sequence[int], judged: dict[int, int], k: int = 20) -> float:
    relevant = {d for d, g in judged.items() if g >= 2}
    if not relevant:
        return 0.0
    hits = relevant.intersection(retrieved_deal_ids[:k])
    return len(hits) / len(relevant)


def mrr(retrieved_deal_ids: Sequence[int], judged: dict[int, int]) -> float:
    for i, d in enumerate(retrieved_deal_ids, 1):
        if judged.get(d, 0) >= 2:
            return 1.0 / i
    return 0.0

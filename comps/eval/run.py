"""Eval harness: run a search function over the golden set, score it.

Separates "vibes-driven" from "actually improving". CI uses this with a gate
that blocks PRs dropping nDCG@10 by more than 1 point.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from statistics import mean
from typing import Any

from pydantic import BaseModel

from comps.eval.dataset import EvalQuery, judgments_for, load_queries
from comps.eval.metrics import mrr, ndcg, recall

SearchFn = Callable[[str], Awaitable[list[dict[str, Any]]]]


class EvalRow(BaseModel):
    query: str
    ndcg_at_10: float
    recall_at_20: float
    mrr: float
    n_judged: int


class EvalReport(BaseModel):
    rows: list[EvalRow]
    mean_ndcg: float
    mean_recall: float
    mean_mrr: float


async def evaluate(system_under_test: SearchFn, k_ndcg: int = 10, k_recall: int = 20) -> EvalReport:
    eval_queries: list[EvalQuery] = await load_queries()
    rows: list[EvalRow] = []
    for q in eval_queries:
        retrieved = await system_under_test(q.query)
        retrieved_ids = [int(r["deal_id"]) for r in retrieved]
        judged = await judgments_for(q.id)
        rows.append(
            EvalRow(
                query=q.query,
                ndcg_at_10=ndcg(retrieved_ids, judged, k_ndcg),
                recall_at_20=recall(retrieved_ids, judged, k_recall),
                mrr=mrr(retrieved_ids, judged),
                n_judged=len(judged),
            )
        )
    if not rows:
        return EvalReport(rows=[], mean_ndcg=0.0, mean_recall=0.0, mean_mrr=0.0)
    return EvalReport(
        rows=rows,
        mean_ndcg=mean(r.ndcg_at_10 for r in rows),
        mean_recall=mean(r.recall_at_20 for r in rows),
        mean_mrr=mean(r.mrr for r in rows),
    )


async def evaluate_default() -> EvalReport:
    """Default system-under-test: the live search pipeline."""
    from comps.search.service import _search_core

    async def _sut(q: str) -> list[dict[str, Any]]:
        results = await _search_core(q, limit=20)
        return [r.model_dump() for r in results]

    return await evaluate(_sut)


def main() -> None:
    import argparse
    import json

    p = argparse.ArgumentParser()
    p.add_argument("--out", default=None)
    args = p.parse_args()
    report = asyncio.run(evaluate_default())
    if args.out:
        with open(args.out, "w") as f:
            json.dump(report.model_dump(), f, indent=2, default=str)
    print(
        f"nDCG@10={report.mean_ndcg:.3f} "
        f"recall@20={report.mean_recall:.3f} "
        f"MRR={report.mean_mrr:.3f} "
        f"n={len(report.rows)}"
    )


if __name__ == "__main__":
    main()

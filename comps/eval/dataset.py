"""Eval dataset loader. Queries + per-deal graded judgments.

Golden-set construction: pair each end user with 20 queries from their actual
workflow, have them grade the top 20 results from a baseline run (BM25-only
is fine) on a 0-3 scale. ~30 min per user. Refresh quarterly.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from comps.db import queries


@dataclass
class EvalQuery:
    id: int
    query: str
    filters: dict[str, Any]


async def load_queries() -> list[EvalQuery]:
    rows = await queries.load_eval_queries()
    return [EvalQuery(id=int(r["id"]), query=r["query"], filters=r["filters"] or {}) for r in rows]


async def judgments_for(query_id: int) -> dict[int, int]:
    return await queries.load_judgments(query_id)


async def load_from_file(path: Path) -> int:
    """Load a JSON file like:
        [
          {"query": "...", "filters": {...}, "judgments": [{"deal_id": 1, "grade": 3}, ...]}
        ]
    Returns the number of queries loaded.
    """
    data = json.loads(path.read_text())
    count = 0
    for entry in data:
        qid = await queries.insert_eval_query(entry["query"], entry.get("filters", {}))
        for j in entry.get("judgments", []):
            await queries.insert_judgment(qid, int(j["deal_id"]), int(j["grade"]))
        count += 1
    return count

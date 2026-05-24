"""Voyage embeddings. Asymmetric — use document for chunks, query at search time.

Voyage's asymmetric encoder gives ~3-5 nDCG points over symmetric use.
"""

from __future__ import annotations

from collections.abc import Iterable
from itertools import islice

import voyageai

from comps.core.config import settings
from comps.core.models import Chunk


def _batched[T](iterable: Iterable[T], n: int) -> Iterable[list[T]]:
    it = iter(iterable)
    while True:
        batch = list(islice(it, n))
        if not batch:
            return
        yield batch


def _client() -> voyageai.Client:
    return voyageai.Client(api_key=settings().voyage_api_key or None)


def embed_chunks(chunks: list[Chunk]) -> list[list[float]]:
    cfg = settings()
    if not chunks:
        return []
    vo = _client()
    out: list[list[float]] = []
    for batch in _batched(chunks, cfg.ingest_embed_batch):
        r = vo.embed(
            [c.text for c in batch],
            model=cfg.voyage_embed_model,
            input_type="document",
        )
        out.extend(r.embeddings)
    return out


def embed_query(text: str) -> list[float]:
    cfg = settings()
    r = _client().embed([text], model=cfg.voyage_embed_model, input_type="query")
    return r.embeddings[0]

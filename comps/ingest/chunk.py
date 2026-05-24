"""Section-aware chunking.

Sectioning matters more than the splitter. A bad splitter on good sections
still works; a great splitter on undifferentiated text does not.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from functools import lru_cache

from comps.core.config import settings
from comps.core.models import Chunk, Section
from comps.ingest.parse import ParsedDoc


@lru_cache(maxsize=1)
def _enc():
    """Lazy tiktoken loader; falls back to a whitespace counter if unavailable."""
    try:
        import tiktoken

        return tiktoken.get_encoding("cl100k_base")
    except Exception:
        return None


SECTION_PATTERNS: dict[Section, list[str]] = {
    "thesis": [
        r"transaction\s+rationale",
        r"investment\s+thesis",
        r"strategic\s+rationale",
        r"business\s+overview",
    ],
    "mdna": [
        r"management.{0,5}discussion",
        r"md&a",
        r"management's\s+discussion",
    ],
    "risks": [r"risk\s+factors"],
    "financials": [
        r"consolidated\s+statements",
        r"financial\s+highlights",
        r"selected\s+financial\s+data",
    ],
}


_HEADING = re.compile(r"^(#{1,6}\s+.+|[A-Z][A-Z0-9 \-&,/]{4,}\s*)$", re.MULTILINE)


def _classify(heading: str) -> Section:
    h = heading.lower()
    for sec, patterns in SECTION_PATTERNS.items():
        for p in patterns:
            if re.search(p, h):
                return sec
    return "other"


def split_by_headings(md: str) -> list[tuple[Section, str]]:
    """Split markdown by detected headings, tagging each block with a section."""
    matches = list(_HEADING.finditer(md))
    if not matches:
        return [("other", md.strip())]

    out: list[tuple[Section, str]] = []
    for i, m in enumerate(matches):
        heading = m.group(0).lstrip("#").strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(md)
        body = md[start:end].strip()
        if not body:
            continue
        out.append((_classify(heading), body))

    # Preamble before first heading falls into 'other'.
    head_text = md[: matches[0].start()].strip()
    if head_text:
        out.insert(0, ("other", head_text))
    return out


def _count_tokens(text: str) -> int:
    enc = _enc()
    if enc is None:
        # ~4 chars/token average. Crude but stable across environments.
        return max(1, len(text) // 4)
    return len(enc.encode(text, disallowed_special=()))


def recursive_split(
    text: str,
    target: int,
    overlap: int,
) -> Iterable[str]:
    """Recursive paragraph -> sentence split, target tokens with overlap.

    Greedy pack: walk paragraphs, accumulate until target hit, emit. Overlap
    is implemented by carrying the last `overlap` tokens worth of text into
    the next chunk.
    """
    if not text.strip():
        return

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]

    buf: list[str] = []
    buf_tokens = 0

    def flush() -> str:
        return "\n\n".join(buf).strip()

    for para in paragraphs:
        ptok = _count_tokens(para)
        if ptok > target:
            # Sentence-split oversized paragraphs.
            sentences = re.split(r"(?<=[.!?])\s+", para)
            for sent in sentences:
                stok = _count_tokens(sent)
                if buf_tokens + stok > target and buf:
                    yield flush()
                    # Carry tail for overlap.
                    tail = _carry_overlap(buf, overlap)
                    buf = [tail] if tail else []
                    buf_tokens = _count_tokens(tail) if tail else 0
                buf.append(sent)
                buf_tokens += stok
        else:
            if buf_tokens + ptok > target and buf:
                yield flush()
                tail = _carry_overlap(buf, overlap)
                buf = [tail] if tail else []
                buf_tokens = _count_tokens(tail) if tail else 0
            buf.append(para)
            buf_tokens += ptok

    if buf:
        yield flush()


def _carry_overlap(buf: list[str], overlap: int) -> str:
    if overlap <= 0:
        return ""
    text = "\n\n".join(buf)
    enc = _enc()
    if enc is None:
        # Approximate: keep ~4 chars per overlap token.
        chars = overlap * 4
        return text[-chars:] if len(text) > chars else text
    tokens = enc.encode(text, disallowed_special=())
    if len(tokens) <= overlap:
        return text
    return enc.decode(tokens[-overlap:])


def chunk(doc: ParsedDoc) -> list[Chunk]:
    cfg = settings()
    sections = split_by_headings(doc.markdown)
    out: list[Chunk] = []
    for sec_name, sec_text in sections:
        for ord_, piece in enumerate(
            recursive_split(
                sec_text,
                target=cfg.ingest_chunk_target_tokens,
                overlap=cfg.ingest_chunk_overlap_tokens,
            )
        ):
            out.append(
                Chunk(
                    section=sec_name,
                    ord=ord_,
                    text=piece,
                    tokens=_count_tokens(piece),
                )
            )
    return out

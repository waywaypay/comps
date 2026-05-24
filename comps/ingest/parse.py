"""Document parsing. Docling for PDFs, trafilatura for HTML, plain reads for .md/.txt.

Tables come out structured — keep them, that's where the numbers live.
"""

from __future__ import annotations

import contextlib
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import httpx
import trafilatura


@dataclass
class ParsedDoc:
    markdown: str
    tables: list[dict] = field(default_factory=list)
    pages: int = 0
    sha256: str = ""
    source_uri: str = ""
    kind: str = "other"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _kind_from_uri(uri: str) -> str:
    lower = uri.lower()
    if lower.endswith(".pdf"):
        return "pdf"
    if lower.endswith((".html", ".htm")):
        return "html"
    if lower.endswith((".md", ".markdown")):
        return "md"
    if lower.endswith(".txt"):
        return "txt"
    return "other"


def _fetch_bytes(uri: str) -> bytes:
    parsed = urlparse(uri)
    if parsed.scheme in ("http", "https"):
        with httpx.Client(timeout=60.0, follow_redirects=True) as c:
            r = c.get(uri)
            r.raise_for_status()
            return r.content
    if parsed.scheme in ("", "file"):
        return Path(parsed.path or uri).read_bytes()
    raise ValueError(f"unsupported scheme for {uri}")


def _parse_pdf(uri: str) -> ParsedDoc:
    # Lazy import so test envs without docling can still load this module.
    from docling.document_converter import DocumentConverter

    result = DocumentConverter().convert(uri)
    md = result.document.export_to_markdown()
    tables = []
    for t in getattr(result.document, "tables", []) or []:
        with contextlib.suppress(AttributeError):
            tables.append(t.export_to_dict())
    pages = len(getattr(result.document, "pages", []) or [])
    return ParsedDoc(markdown=md, tables=tables, pages=pages, kind="pdf")


def _parse_html(raw: bytes, uri: str) -> ParsedDoc:
    text = (
        trafilatura.extract(
            raw.decode("utf-8", errors="replace"),
            output_format="markdown",
            include_tables=True,
            include_comments=False,
            url=uri,
        )
        or ""
    )
    return ParsedDoc(markdown=text, kind="html")


def _parse_plain(raw: bytes) -> ParsedDoc:
    text = raw.decode("utf-8", errors="replace")
    return ParsedDoc(markdown=text, kind="md")


def parse(source_uri: str) -> ParsedDoc:
    """Parse a document URI into markdown + tables + sha256 of source bytes."""
    kind = _kind_from_uri(source_uri)
    if kind == "pdf":
        doc = _parse_pdf(source_uri)
        doc.sha256 = _sha256(doc.markdown)
    else:
        raw = _fetch_bytes(source_uri)
        doc = _parse_html(raw, source_uri) if kind == "html" else _parse_plain(raw)
        doc.sha256 = _sha256(raw.decode("utf-8", errors="replace"))
    doc.source_uri = source_uri
    if not doc.kind:
        doc.kind = kind
    return doc

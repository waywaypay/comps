"""CLI formatters. Numbers in a way analysts can read at a glance."""

from __future__ import annotations


def fmt_usd(v: float | None) -> str:
    if v is None:
        return "—"
    if v >= 1e9:
        return f"${v / 1e9:.2f}B"
    if v >= 1e6:
        return f"${v / 1e6:.1f}M"
    if v >= 1e3:
        return f"${v / 1e3:.0f}K"
    return f"${v:.0f}"


def fmt_mult(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v:.1f}x"


def fmt_pct(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v * 100:.0f}%"


def truncate(text: str | None, n: int = 80) -> str:
    if not text:
        return "—"
    text = text.replace("\n", " ").strip()
    return text if len(text) <= n else text[: n - 1] + "…"

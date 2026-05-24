from comps.cli.format import fmt_mult, fmt_pct, fmt_usd, truncate


def test_fmt_usd_scales():
    assert fmt_usd(None) == "—"
    assert fmt_usd(500) == "$500"
    assert fmt_usd(2_500) == "$2K"
    assert fmt_usd(1_500_000) == "$1.5M"
    assert fmt_usd(2_300_000_000) == "$2.30B"


def test_fmt_mult():
    assert fmt_mult(None) == "—"
    assert fmt_mult(5.25) == "5.2x"


def test_fmt_pct():
    assert fmt_pct(None) == "—"
    assert fmt_pct(0.15) == "15%"


def test_truncate():
    assert truncate(None) == "—"
    assert truncate("abc") == "abc"
    assert truncate("a" * 100, n=10).endswith("…")

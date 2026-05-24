from pathlib import Path

import pytest

from comps.ingest import parse as parse_mod


def test_parse_plain_text(tmp_path: Path):
    p = tmp_path / "doc.txt"
    p.write_text("hello world")
    doc = parse_mod.parse(str(p))
    assert "hello world" in doc.markdown
    assert doc.sha256


def test_parse_markdown(tmp_path: Path):
    p = tmp_path / "doc.md"
    p.write_text("# Title\n\nbody")
    doc = parse_mod.parse(str(p))
    assert "Title" in doc.markdown


def test_kind_from_uri():
    assert parse_mod._kind_from_uri("foo.pdf") == "pdf"
    assert parse_mod._kind_from_uri("foo.html") == "html"
    assert parse_mod._kind_from_uri("foo.md") == "md"
    assert parse_mod._kind_from_uri("foo.txt") == "txt"
    assert parse_mod._kind_from_uri("foo.bin") == "other"


def test_sha256_deterministic():
    a = parse_mod._sha256("abc")
    b = parse_mod._sha256("abc")
    assert a == b


def test_parse_unknown_scheme_raises():
    with pytest.raises(ValueError):
        parse_mod._fetch_bytes("ftp://example.com/x.txt")

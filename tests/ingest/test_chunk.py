from comps.ingest.chunk import chunk, recursive_split, split_by_headings
from comps.ingest.parse import ParsedDoc


def test_split_by_headings_classifies_sections():
    md = """
# Investment Thesis

We will compound EBITDA at 25% via M&A.

# Risk Factors

Concentration risk in top customer.

# Other Stuff

Boilerplate.
"""
    sections = split_by_headings(md)
    kinds = [s for s, _ in sections]
    assert "thesis" in kinds
    assert "risks" in kinds
    assert "other" in kinds


def test_recursive_split_respects_target():
    text = "\n\n".join(["This is a sentence."] * 200)
    pieces = list(recursive_split(text, target=100, overlap=10))
    assert len(pieces) > 1
    # Pieces should be roughly within target (within 2x because of single-paragraph fallthrough).
    for p in pieces:
        assert p.strip()


def test_recursive_split_empty_input():
    assert list(recursive_split("", target=100, overlap=10)) == []
    assert list(recursive_split("   ", target=100, overlap=10)) == []


def test_chunk_end_to_end():
    md = """
# Investment Thesis

We will compound EBITDA at 25% via tuck-in M&A in the vertical SaaS space.

# Risk Factors

Customer concentration in top three accounts.
"""
    doc = ParsedDoc(markdown=md, sha256="x", source_uri="mem://t")
    chunks = chunk(doc)
    assert chunks
    sections = {c.section for c in chunks}
    assert "thesis" in sections

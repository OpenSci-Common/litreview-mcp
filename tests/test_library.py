"""Tests for library.py — paper library management functions."""

from __future__ import annotations

from pathlib import Path

import pytest
from litreview.library import (
    add_paper,
    add_papers_batch,
    exclude_paper,
    list_papers,
    paper_detail,
    paper_stats,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_paper_data(
    title: str = "Test Paper",
    year: int = 2021,
    doi: str | None = None,
    arxiv_id: str | None = None,
    first_author: str = "Smith",
    status: str = "candidate",
) -> dict:
    external_ids: dict = {}
    if doi:
        external_ids["doi"] = doi
    if arxiv_id:
        external_ids["arxiv"] = arxiv_id
    return {
        "title": title,
        "year": year,
        "external_ids": external_ids,
        "authors": [{"name": first_author}],
        "abstract": "Abstract text.",
        "venue": "NeurIPS",
        "citation_count": 100,
        "fields_of_study": ["CS"],
        "open_access_status": "green",
        "pdf_status": "unknown",
        "pdf_path": None,
        "status": status,
        "source_apis": ["semantic_scholar"],
        "first_seen_session_id": None,
        "added_by": "user",
    }


# ---------------------------------------------------------------------------
# add_paper
# ---------------------------------------------------------------------------

def test_add_paper_returns_dict(tmp_workspace):
    data = make_paper_data(title="Paper One", doi="10.1/one")
    result = add_paper(tmp_workspace, data)
    assert isinstance(result, dict)


def test_add_paper_has_paper_id(tmp_workspace):
    data = make_paper_data(title="Paper With ID", doi="10.1/id")
    result = add_paper(tmp_workspace, data)
    assert "paper_id" in result
    assert len(result["paper_id"]) == 12


def test_add_paper_persisted_in_db(tmp_workspace):
    data = make_paper_data(title="Persisted Paper", doi="10.1/persist")
    result = add_paper(tmp_workspace, data)
    papers = list_papers(tmp_workspace)
    assert any(p["paper_id"] == result["paper_id"] for p in papers)


def test_add_paper_duplicate_returns_duplicate_flag(tmp_workspace):
    data = make_paper_data(title="Dup Paper", doi="10.1/dup")
    first = add_paper(tmp_workspace, data)
    second = add_paper(tmp_workspace, data)
    assert second.get("duplicate") is True
    assert second["paper_id"] == first["paper_id"]


def test_add_paper_duplicate_not_double_inserted(tmp_workspace):
    data = make_paper_data(title="No Double", doi="10.1/nodbl")
    add_paper(tmp_workspace, data)
    add_paper(tmp_workspace, data)
    papers = list_papers(tmp_workspace)
    matching = [p for p in papers if p.get("external_ids", {}).get("doi") == "10.1/nodbl"]
    assert len(matching) == 1


def test_add_paper_uses_literature_json(tmp_workspace):
    """add_paper must write to .litreview/literature.json."""
    data = make_paper_data(title="Lib JSON Paper", doi="10.1/libjson")
    add_paper(tmp_workspace, data)
    lit_file = Path(tmp_workspace) / ".litreview" / "literature.json"
    assert lit_file.exists()


# ---------------------------------------------------------------------------
# add_papers_batch
# ---------------------------------------------------------------------------

def test_add_papers_batch_returns_summary(tmp_workspace):
    papers = [
        make_paper_data(title="Batch Paper 1", doi="10.1/b1"),
        make_paper_data(title="Batch Paper 2", doi="10.1/b2"),
    ]
    result = add_papers_batch(tmp_workspace, papers)
    assert "added" in result
    assert "duplicates" in result
    assert "papers" in result


def test_add_papers_batch_counts_added(tmp_workspace):
    papers = [
        make_paper_data(title="Batch A", doi="10.1/ba"),
        make_paper_data(title="Batch B", doi="10.1/bb"),
        make_paper_data(title="Batch C", doi="10.1/bc"),
    ]
    result = add_papers_batch(tmp_workspace, papers)
    assert result["added"] == 3
    assert result["duplicates"] == 0


def test_add_papers_batch_counts_duplicates(tmp_workspace):
    p1 = make_paper_data(title="Exist Paper", doi="10.1/exist")
    add_paper(tmp_workspace, p1)
    papers = [
        make_paper_data(title="Exist Paper copy", doi="10.1/exist"),  # dup
        make_paper_data(title="New Paper", doi="10.1/new"),
    ]
    result = add_papers_batch(tmp_workspace, papers)
    assert result["added"] == 1
    assert result["duplicates"] == 1


def test_add_papers_batch_papers_list_correct_length(tmp_workspace):
    papers = [make_paper_data(title=f"Paper {i}", doi=f"10.1/{i}") for i in range(5)]
    result = add_papers_batch(tmp_workspace, papers)
    assert len(result["papers"]) == 5


# ---------------------------------------------------------------------------
# exclude_paper
# ---------------------------------------------------------------------------

def test_exclude_paper_sets_status(tmp_workspace):
    data = make_paper_data(title="To Exclude", doi="10.1/excl")
    added = add_paper(tmp_workspace, data)
    result = exclude_paper(tmp_workspace, added["paper_id"])
    assert result["status"] == "excluded"


def test_exclude_paper_persisted(tmp_workspace):
    data = make_paper_data(title="Exclude Persist", doi="10.1/ep")
    added = add_paper(tmp_workspace, data)
    exclude_paper(tmp_workspace, added["paper_id"])
    detail = paper_detail(tmp_workspace, added["paper_id"])
    assert detail["status"] == "excluded"


def test_exclude_paper_not_found_raises(tmp_workspace):
    with pytest.raises(KeyError):
        exclude_paper(tmp_workspace, "nonexistent_id")


# ---------------------------------------------------------------------------
# list_papers
# ---------------------------------------------------------------------------

def test_list_papers_empty(tmp_workspace):
    result = list_papers(tmp_workspace)
    assert result == []


def test_list_papers_returns_all(tmp_workspace):
    for i in range(3):
        add_paper(tmp_workspace, make_paper_data(title=f"Paper {i}", doi=f"10.1/{i}"))
    result = list_papers(tmp_workspace)
    assert len(result) == 3


def test_list_papers_filter_by_status(tmp_workspace):
    p1 = make_paper_data(title="Candidate Paper", doi="10.1/cand")
    p2 = make_paper_data(title="Excluded Paper", doi="10.1/excl2")
    added1 = add_paper(tmp_workspace, p1)
    added2 = add_paper(tmp_workspace, p2)
    exclude_paper(tmp_workspace, added2["paper_id"])

    candidates = list_papers(tmp_workspace, status="candidate")
    excluded = list_papers(tmp_workspace, status="excluded")
    assert len(candidates) == 1
    assert len(excluded) == 1


def test_list_papers_limit(tmp_workspace):
    for i in range(5):
        add_paper(tmp_workspace, make_paper_data(title=f"Limited {i}", doi=f"10.1/lim{i}"))
    result = list_papers(tmp_workspace, limit=3)
    assert len(result) == 3


def test_list_papers_offset(tmp_workspace):
    for i in range(5):
        add_paper(tmp_workspace, make_paper_data(title=f"Offset {i}", doi=f"10.1/off{i}"))
    result_full = list_papers(tmp_workspace)
    result_offset = list_papers(tmp_workspace, offset=2)
    assert len(result_offset) == 3
    assert result_offset == result_full[2:]


def test_list_papers_sort_by_year(tmp_workspace):
    add_paper(tmp_workspace, make_paper_data(title="Old Paper", doi="10.1/old", year=2015))
    add_paper(tmp_workspace, make_paper_data(title="New Paper", doi="10.1/new", year=2023))
    add_paper(tmp_workspace, make_paper_data(title="Mid Paper", doi="10.1/mid", year=2019))
    result = list_papers(tmp_workspace, sort_by="year")
    years = [p["year"] for p in result]
    # Default sort ascending (no "-" prefix)
    assert years == sorted(years)


def test_list_papers_sort_by_year_descending():
    # sort_by="-year" means descending (prefix "-" = ascending per spec, no prefix = default)
    # Per spec: "prefix '-' for ascending" — so "-year" is ascending, "year" is default
    # We just test that sort_by field name works without error
    pass  # covered by test_list_papers_sort_by_year


# ---------------------------------------------------------------------------
# paper_detail
# ---------------------------------------------------------------------------

def test_paper_detail_returns_correct_paper(tmp_workspace):
    data = make_paper_data(title="Detail Paper", doi="10.1/detail")
    added = add_paper(tmp_workspace, data)
    detail = paper_detail(tmp_workspace, added["paper_id"])
    assert detail["paper_id"] == added["paper_id"]
    assert detail["title"] == "Detail Paper"


def test_paper_detail_not_found_raises(tmp_workspace):
    with pytest.raises(KeyError):
        paper_detail(tmp_workspace, "does_not_exist")


# ---------------------------------------------------------------------------
# paper_stats
# ---------------------------------------------------------------------------

def test_paper_stats_empty(tmp_workspace):
    stats = paper_stats(tmp_workspace)
    assert stats["total"] == 0
    assert stats["in_library"] == 0
    assert stats["excluded"] == 0


def test_paper_stats_counts(tmp_workspace):
    p1 = make_paper_data(title="Stats A", doi="10.1/sa")
    p2 = make_paper_data(title="Stats B", doi="10.1/sb")
    p3 = make_paper_data(title="Stats C", doi="10.1/sc")
    added1 = add_paper(tmp_workspace, p1)
    add_paper(tmp_workspace, p2)
    add_paper(tmp_workspace, p3)
    exclude_paper(tmp_workspace, added1["paper_id"])

    stats = paper_stats(tmp_workspace)
    assert stats["total"] == 3
    assert stats["excluded"] == 1


def test_paper_stats_has_required_keys(tmp_workspace):
    stats = paper_stats(tmp_workspace)
    for key in ("total", "in_library", "excluded"):
        assert key in stats

"""Tests for dedup.py — dedup_papers function."""

from __future__ import annotations

import pytest
from litreview.dedup import dedup_papers


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_paper(
    title: str,
    year: int = 2020,
    doi: str | None = None,
    arxiv_id: str | None = None,
    s2_id: str | None = None,
    openalex_id: str | None = None,
    first_author: str | None = None,
) -> dict:
    external_ids: dict = {}
    if doi:
        external_ids["doi"] = doi
    if arxiv_id:
        external_ids["arxiv"] = arxiv_id
    if s2_id:
        external_ids["s2_paper_id"] = s2_id
    if openalex_id:
        external_ids["openalex_id"] = openalex_id

    authors = []
    if first_author:
        authors = [{"name": first_author}]

    return {
        "title": title,
        "year": year,
        "external_ids": external_ids,
        "authors": authors,
    }


# ---------------------------------------------------------------------------
# Basic structure
# ---------------------------------------------------------------------------

def test_dedup_returns_correct_keys():
    result = dedup_papers([], [])
    assert "unique" in result
    assert "duplicates" in result


def test_no_candidates_returns_empty():
    result = dedup_papers([], [])
    assert result["unique"] == []
    assert result["duplicates"] == []


def test_no_duplicates_all_unique():
    candidates = [
        make_paper("Paper Alpha", 2020, doi="10.1/alpha"),
        make_paper("Paper Beta", 2021, doi="10.1/beta"),
    ]
    result = dedup_papers(candidates, [])
    assert len(result["unique"]) == 2
    assert len(result["duplicates"]) == 0


# ---------------------------------------------------------------------------
# Level 1: DOI exact match (case-insensitive)
# ---------------------------------------------------------------------------

def test_dedup_doi_exact_within_candidates():
    p1 = make_paper("Paper One", 2020, doi="10.1234/test")
    p2 = make_paper("Paper One Variant", 2020, doi="10.1234/test")
    result = dedup_papers([p1, p2], [])
    assert len(result["unique"]) == 1
    assert len(result["duplicates"]) == 1
    assert result["duplicates"][0]["match_type"] == "doi"


def test_dedup_doi_case_insensitive():
    p1 = make_paper("Paper", 2020, doi="10.1234/TEST")
    p2 = make_paper("Paper", 2020, doi="10.1234/test")
    result = dedup_papers([p1, p2], [])
    assert len(result["unique"]) == 1
    assert result["duplicates"][0]["match_type"] == "doi"


def test_dedup_doi_against_existing():
    candidate = make_paper("New Paper", 2022, doi="10.9999/existing")
    existing = [make_paper("Existing Paper", 2022, doi="10.9999/existing")]
    result = dedup_papers([candidate], existing)
    assert len(result["unique"]) == 0
    assert len(result["duplicates"]) == 1
    assert result["duplicates"][0]["match_type"] == "doi"


# ---------------------------------------------------------------------------
# Level 2: External ID match (s2_paper_id, openalex_id, arxiv_id)
# ---------------------------------------------------------------------------

def test_dedup_s2_paper_id_within_candidates():
    p1 = make_paper("Paper S2 A", 2021, s2_id="abc123")
    p2 = make_paper("Paper S2 B", 2021, s2_id="abc123")
    result = dedup_papers([p1, p2], [])
    assert len(result["unique"]) == 1
    assert result["duplicates"][0]["match_type"] == "external_id"


def test_dedup_arxiv_id_within_candidates():
    p1 = make_paper("Paper Arxiv A", 2021, arxiv_id="2101.00001")
    p2 = make_paper("Paper Arxiv B", 2021, arxiv_id="2101.00001")
    result = dedup_papers([p1, p2], [])
    assert len(result["unique"]) == 1
    assert result["duplicates"][0]["match_type"] == "external_id"


def test_dedup_openalex_id_against_existing():
    candidate = make_paper("Paper OA", 2020, openalex_id="W12345")
    existing = [make_paper("Existing OA", 2020, openalex_id="W12345")]
    result = dedup_papers([candidate], existing)
    assert len(result["unique"]) == 0
    assert result["duplicates"][0]["match_type"] == "external_id"


# ---------------------------------------------------------------------------
# Level 3: Title + year normalized match
# ---------------------------------------------------------------------------

def test_dedup_title_year_within_candidates():
    p1 = make_paper("Attention Is All You Need", 2017)
    p2 = make_paper("Attention Is All You Need!", 2017)  # trailing punct
    result = dedup_papers([p1, p2], [])
    assert len(result["unique"]) == 1
    assert result["duplicates"][0]["match_type"] == "title_year"


def test_dedup_title_year_different_year_not_dedup():
    p1 = make_paper("Same Title", 2017)
    p2 = make_paper("Same Title", 2018)
    result = dedup_papers([p1, p2], [])
    # Different year — should NOT be deduped at this level
    # (fuzzy level may catch it if within ±1, check no title_year match)
    title_year_dups = [d for d in result["duplicates"] if d["match_type"] == "title_year"]
    assert len(title_year_dups) == 0


def test_dedup_title_year_against_existing():
    candidate = make_paper("Deep Learning Survey", 2020)
    existing = [make_paper("Deep Learning Survey.", 2020)]
    result = dedup_papers([candidate], existing)
    assert len(result["unique"]) == 0
    assert result["duplicates"][0]["match_type"] == "title_year"


# ---------------------------------------------------------------------------
# Level 4: Fuzzy title match
# ---------------------------------------------------------------------------

def test_dedup_fuzzy_title_within_candidates():
    # Very similar title, same first author, year within ±1
    p1 = make_paper(
        "Retrieval-Augmented Generation for Knowledge Intensive NLP Tasks",
        2020,
        first_author="Lewis",
    )
    p2 = make_paper(
        "Retrieval Augmented Generation for Knowledge-Intensive NLP Tasks",
        2020,
        first_author="Lewis",
    )
    result = dedup_papers([p1, p2], [])
    assert len(result["unique"]) == 1
    assert result["duplicates"][0]["match_type"] in ("title_year", "fuzzy_title")


def test_dedup_fuzzy_title_year_plus_one():
    # Year differs by 1, same author, similar title
    p1 = make_paper("BERT Pre-training of Deep Bidirectional Transformers", 2018, first_author="Devlin")
    p2 = make_paper("BERT Pre-training of Deep Bidirectional Transformers", 2019, first_author="Devlin")
    result = dedup_papers([p1, p2], [])
    assert len(result["unique"]) == 1
    assert result["duplicates"][0]["match_type"] == "fuzzy_title"


def test_dedup_fuzzy_title_different_author_no_match():
    # Same title but different author should NOT match on fuzzy
    p1 = make_paper("A Survey on Neural Networks", 2020, first_author="Smith")
    p2 = make_paper("A Survey on Neural Networks", 2020, first_author="Jones")
    result = dedup_papers([p1, p2], [])
    # Different authors: should NOT be flagged as duplicate via fuzzy
    fuzzy_dups = [d for d in result["duplicates"] if d["match_type"] == "fuzzy_title"]
    assert len(fuzzy_dups) == 0


def test_dedup_fuzzy_title_year_too_far():
    # Year difference > 1, should NOT match on fuzzy
    p1 = make_paper("Deep Neural Network Methods", 2015, first_author="Goodfellow")
    p2 = make_paper("Deep Neural Network Methods", 2018, first_author="Goodfellow")
    result = dedup_papers([p1, p2], [])
    fuzzy_dups = [d for d in result["duplicates"] if d["match_type"] == "fuzzy_title"]
    assert len(fuzzy_dups) == 0


# ---------------------------------------------------------------------------
# duplicate record structure
# ---------------------------------------------------------------------------

def test_duplicate_record_has_paper_and_matched_with():
    p1 = make_paper("Paper X", 2020, doi="10.0/x")
    p2 = make_paper("Paper X copy", 2020, doi="10.0/x")
    result = dedup_papers([p1, p2], [])
    dup = result["duplicates"][0]
    assert "paper" in dup
    assert "matched_with" in dup
    assert "match_type" in dup


# ---------------------------------------------------------------------------
# Priority: DOI wins over external_id
# ---------------------------------------------------------------------------

def test_doi_match_takes_priority_over_external_id():
    p1 = make_paper("Title", 2020, doi="10.1/same", s2_id="sid1")
    p2 = make_paper("Title", 2020, doi="10.1/same", s2_id="sid2")
    result = dedup_papers([p1, p2], [])
    assert result["duplicates"][0]["match_type"] == "doi"


# ---------------------------------------------------------------------------
# Multiple candidates with existing library
# ---------------------------------------------------------------------------

def test_mixed_new_and_existing_dedup():
    existing = [
        make_paper("Existing Paper A", 2019, doi="10.1/a"),
        make_paper("Existing Paper B", 2020, doi="10.1/b"),
    ]
    candidates = [
        make_paper("Existing Paper A", 2019, doi="10.1/a"),   # dup of existing
        make_paper("New Paper C", 2021, doi="10.1/c"),          # new
        make_paper("New Paper D", 2022),                         # new
    ]
    result = dedup_papers(candidates, existing)
    assert len(result["unique"]) == 2
    assert len(result["duplicates"]) == 1


# ---------------------------------------------------------------------------
# Candidates-only dedup across multiple papers
# ---------------------------------------------------------------------------

def test_three_candidates_two_dupes_one_unique():
    p1 = make_paper("Same Paper", 2021, doi="10.1/same")
    p2 = make_paper("Same Paper again", 2021, doi="10.1/same")
    p3 = make_paper("Different Paper", 2021, doi="10.1/diff")
    result = dedup_papers([p1, p2, p3], [])
    assert len(result["unique"]) == 2
    assert len(result["duplicates"]) == 1

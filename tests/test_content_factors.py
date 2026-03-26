"""Tests for content factor library (Task 10)."""

from __future__ import annotations

from pathlib import Path

import pytest

from litreview.workspace import init_workspace
from litreview.content_factors import (
    extract_content_factors,
    query_content_factors,
    promote_content_factor,
)
from litreview.factors import list_factors


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _workspace(tmp_path: Path) -> Path:
    init_workspace(tmp_path)
    return tmp_path


SAMPLE_PAPER = {
    "paper_id": "abc123def456",
    "title": "Attention Is All You Need",
    "year": 2017,
    "authors": [
        {"name": "Ashish Vaswani", "authorId": "1234"},
        {"name": "Noam Shazeer", "authorId": "5678"},
        {"name": "Niki Parmar"},
    ],
    "venue": "NeurIPS",
    "fields_of_study": ["Computer Science", "Artificial Intelligence"],
}

PAPER_NO_OPTIONAL = {
    "paper_id": "xyz789",
    "title": "Minimal Paper",
    "authors": [],
    "venue": None,
    "fields_of_study": [],
}


# ---------------------------------------------------------------------------
# extract_content_factors
# ---------------------------------------------------------------------------

class TestExtractContentFactors:
    def test_returns_dict_with_expected_keys(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        result = extract_content_factors(ws, SAMPLE_PAPER)
        assert "paper_id" in result
        assert "extracted_count" in result
        assert "factors" in result

    def test_paper_id_matches(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        result = extract_content_factors(ws, SAMPLE_PAPER)
        assert result["paper_id"] == "abc123def456"

    def test_extracts_authors(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        result = extract_content_factors(ws, SAMPLE_PAPER)
        author_factors = [f for f in result["factors"] if f["type"] == "author"]
        assert len(author_factors) == 3

    def test_first_author_role(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        result = extract_content_factors(ws, SAMPLE_PAPER)
        author_factors = [f for f in result["factors"] if f["type"] == "author"]
        # Sort by value to find "Ashish Vaswani" (first in list)
        first = next(f for f in author_factors if f["value"] == "Ashish Vaswani")
        assert first["role"] == "first_author"

    def test_co_author_role(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        result = extract_content_factors(ws, SAMPLE_PAPER)
        author_factors = [f for f in result["factors"] if f["type"] == "author"]
        co_authors = [f for f in author_factors if f["role"] == "co_author"]
        assert len(co_authors) == 2
        co_names = {f["value"] for f in co_authors}
        assert "Noam Shazeer" in co_names
        assert "Niki Parmar" in co_names

    def test_author_api_ids_extracted(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        result = extract_content_factors(ws, SAMPLE_PAPER)
        author_factors = [f for f in result["factors"] if f["type"] == "author"]
        vaswani = next(f for f in author_factors if f["value"] == "Ashish Vaswani")
        assert vaswani["api_ids"].get("s2_author_id") == "1234"

    def test_author_without_id_has_empty_api_ids(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        result = extract_content_factors(ws, SAMPLE_PAPER)
        author_factors = [f for f in result["factors"] if f["type"] == "author"]
        parmar = next(f for f in author_factors if f["value"] == "Niki Parmar")
        assert parmar["api_ids"] == {}

    def test_extracts_venue(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        result = extract_content_factors(ws, SAMPLE_PAPER)
        venue_factors = [f for f in result["factors"] if f["type"] == "venue"]
        assert len(venue_factors) == 1
        assert venue_factors[0]["value"] == "NeurIPS"

    def test_no_venue_skipped(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        result = extract_content_factors(ws, PAPER_NO_OPTIONAL)
        venue_factors = [f for f in result["factors"] if f["type"] == "venue"]
        assert len(venue_factors) == 0

    def test_extracts_fields(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        result = extract_content_factors(ws, SAMPLE_PAPER)
        field_factors = [f for f in result["factors"] if f["type"] == "field"]
        assert len(field_factors) == 2
        field_values = {f["value"] for f in field_factors}
        assert "Computer Science" in field_values
        assert "Artificial Intelligence" in field_values

    def test_extracted_count_matches_factors_length(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        result = extract_content_factors(ws, SAMPLE_PAPER)
        assert result["extracted_count"] == len(result["factors"])

    def test_factors_have_cf_ids(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        result = extract_content_factors(ws, SAMPLE_PAPER)
        for f in result["factors"]:
            assert f["id"].startswith("cf_")

    def test_factors_have_paper_id(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        result = extract_content_factors(ws, SAMPLE_PAPER)
        for f in result["factors"]:
            assert f["paper_id"] == "abc123def456"

    def test_empty_paper_no_factors(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        result = extract_content_factors(ws, PAPER_NO_OPTIONAL)
        assert result["extracted_count"] == 0
        assert result["factors"] == []

    def test_factors_persisted_in_db(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        extract_content_factors(ws, SAMPLE_PAPER)
        # Query should return persisted factors
        all_factors = query_content_factors(ws)
        assert len(all_factors) > 0


# ---------------------------------------------------------------------------
# query_content_factors
# ---------------------------------------------------------------------------

class TestQueryContentFactors:
    def _setup(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        extract_content_factors(ws, SAMPLE_PAPER)
        return ws

    def test_query_all_returns_list(self, tmp_path: Path):
        ws = self._setup(tmp_path)
        result = query_content_factors(ws)
        assert isinstance(result, list)
        assert len(result) > 0

    def test_query_by_type_author(self, tmp_path: Path):
        ws = self._setup(tmp_path)
        result = query_content_factors(ws, type="author")
        assert all(f["type"] == "author" for f in result)
        assert len(result) == 3

    def test_query_by_type_venue(self, tmp_path: Path):
        ws = self._setup(tmp_path)
        result = query_content_factors(ws, type="venue")
        assert len(result) == 1
        assert result[0]["value"] == "NeurIPS"

    def test_query_by_paper_id(self, tmp_path: Path):
        ws = self._setup(tmp_path)
        result = query_content_factors(ws, paper_id="abc123def456")
        assert all(f["paper_id"] == "abc123def456" for f in result)
        # 3 authors + 1 venue + 2 fields = 6
        assert len(result) == 6

    def test_query_by_type_and_paper_id(self, tmp_path: Path):
        ws = self._setup(tmp_path)
        result = query_content_factors(ws, type="field", paper_id="abc123def456")
        assert len(result) == 2
        assert all(f["type"] == "field" for f in result)

    def test_query_wrong_paper_id_returns_empty(self, tmp_path: Path):
        ws = self._setup(tmp_path)
        result = query_content_factors(ws, paper_id="nonexistent")
        assert result == []

    def test_aggregate_count(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        # Extract same field from two different papers
        paper2 = {
            "paper_id": "paper2",
            "title": "Another Paper",
            "authors": [{"name": "Ashish Vaswani", "authorId": "1234"}],
            "venue": "ICML",
            "fields_of_study": ["Computer Science"],
        }
        extract_content_factors(ws, SAMPLE_PAPER)
        extract_content_factors(ws, paper2)

        result = query_content_factors(ws, type="author", aggregate="count")
        assert isinstance(result, list)
        # Each item has value, count, type
        for item in result:
            assert "value" in item
            assert "count" in item
            assert "type" in item

    def test_aggregate_count_sorted_desc(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        paper2 = {
            "paper_id": "paper2",
            "title": "Another Paper",
            "authors": [{"name": "Ashish Vaswani", "authorId": "1234"}],
            "venue": "ICML",
            "fields_of_study": ["Computer Science"],
        }
        extract_content_factors(ws, SAMPLE_PAPER)
        extract_content_factors(ws, paper2)

        result = query_content_factors(ws, type="author", aggregate="count")
        counts = [item["count"] for item in result]
        assert counts == sorted(counts, reverse=True)

    def test_aggregate_count_vaswani_appears_twice(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        paper2 = {
            "paper_id": "paper2",
            "title": "Another Paper",
            "authors": [{"name": "Ashish Vaswani", "authorId": "1234"}],
            "venue": "ICML",
            "fields_of_study": [],
        }
        extract_content_factors(ws, SAMPLE_PAPER)
        extract_content_factors(ws, paper2)

        result = query_content_factors(ws, type="author", aggregate="count")
        vaswani_entry = next((r for r in result if r["value"] == "Ashish Vaswani"), None)
        assert vaswani_entry is not None
        assert vaswani_entry["count"] == 2

    def test_aggregate_min_count_filter(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        paper2 = {
            "paper_id": "paper2",
            "title": "Another Paper",
            "authors": [{"name": "Ashish Vaswani", "authorId": "1234"}],
            "venue": "ICML",
            "fields_of_study": [],
        }
        extract_content_factors(ws, SAMPLE_PAPER)
        extract_content_factors(ws, paper2)

        result = query_content_factors(ws, type="author", aggregate="count", min_count=2)
        # Only Ashish Vaswani appears twice
        assert all(item["count"] >= 2 for item in result)
        assert any(item["value"] == "Ashish Vaswani" for item in result)
        # Noam Shazeer only once — should be excluded
        assert not any(item["value"] == "Noam Shazeer" for item in result)


# ---------------------------------------------------------------------------
# promote_content_factor
# ---------------------------------------------------------------------------

class TestPromoteContentFactor:
    def test_promote_returns_dict_with_factor_and_marked_count(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        extract_content_factors(ws, SAMPLE_PAPER)
        result = promote_content_factor(ws, type="venue", value="NeurIPS")
        assert "factor" in result
        assert "content_factors_marked" in result

    def test_promote_creates_search_factor(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        extract_content_factors(ws, SAMPLE_PAPER)
        result = promote_content_factor(ws, type="venue", value="NeurIPS")
        factor = result["factor"]
        assert factor["type"] == "venue"
        assert factor["value"] == "NeurIPS"
        assert factor["id"].startswith("sf_")

    def test_promote_sets_provenance(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        extract_content_factors(ws, SAMPLE_PAPER)
        result = promote_content_factor(ws, type="venue", value="NeurIPS")
        assert result["factor"]["provenance"] == "promoted_from_content"

    def test_promote_sets_promoted_from(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        extract_content_factors(ws, SAMPLE_PAPER)
        result = promote_content_factor(ws, type="venue", value="NeurIPS")
        assert result["factor"]["promoted_from"] == "venue:NeurIPS"

    def test_promote_marks_content_factors(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        extract_content_factors(ws, SAMPLE_PAPER)
        result = promote_content_factor(ws, type="venue", value="NeurIPS")
        assert result["content_factors_marked"] == 1

    def test_promote_marks_multiple_matches(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        paper2 = {
            "paper_id": "paper2",
            "title": "Another Paper",
            "authors": [{"name": "Ashish Vaswani", "authorId": "1234"}],
            "venue": "NeurIPS",
            "fields_of_study": [],
        }
        extract_content_factors(ws, SAMPLE_PAPER)
        extract_content_factors(ws, paper2)
        result = promote_content_factor(ws, type="venue", value="NeurIPS")
        assert result["content_factors_marked"] == 2

    def test_promoted_content_factors_flagged_in_db(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        extract_content_factors(ws, SAMPLE_PAPER)
        promote_content_factor(ws, type="venue", value="NeurIPS")
        # Query content factors and verify promoted flag
        cf_list = query_content_factors(ws, type="venue")
        neurips = [f for f in cf_list if f["value"] == "NeurIPS"]
        assert all(f["promoted"] is True for f in neurips)

    def test_promote_search_factor_persisted(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        extract_content_factors(ws, SAMPLE_PAPER)
        promote_content_factor(ws, type="author", value="Ashish Vaswani")
        search_factors = list_factors(ws, type="author")
        assert len(search_factors) >= 1
        assert any(f["value"] == "Ashish Vaswani" for f in search_factors)

    def test_promote_collects_api_ids(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        extract_content_factors(ws, SAMPLE_PAPER)
        result = promote_content_factor(ws, type="author", value="Ashish Vaswani")
        # api_ids from content factor should be passed along
        factor = result["factor"]
        assert factor["api_ids"].get("s2_author_id") == "1234"

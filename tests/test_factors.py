"""Tests for search factor library (Task 5)."""

from __future__ import annotations

from pathlib import Path

import pytest

from litreview.workspace import init_workspace
from litreview.factors import (
    add_factor,
    compose_query,
    list_factors,
    remove_factor,
    toggle_factor,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _workspace(tmp_path: Path) -> Path:
    init_workspace(tmp_path)
    return tmp_path


# ---------------------------------------------------------------------------
# add_factor
# ---------------------------------------------------------------------------

class TestAddFactor:
    def test_add_returns_dict_with_id(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        result = add_factor(ws, type="keyword", value="transformer", query_role="must")
        assert "id" in result
        assert result["id"].startswith("sf_")

    def test_add_stores_type_and_value(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        result = add_factor(ws, type="author", value="Vaswani", query_role="must")
        assert result["type"] == "author"
        assert result["value"] == "Vaswani"

    def test_add_stores_query_role(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        result = add_factor(ws, type="keyword", value="attention", query_role="should")
        assert result["query_role"] == "should"

    def test_add_optional_fields(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        result = add_factor(
            ws,
            type="keyword",
            value="NLP",
            query_role="must",
            sub_type="concept",
            provenance="user",
            created_by="tester",
        )
        assert result["sub_type"] == "concept"
        assert result["provenance"] == "user"
        assert result["created_by"] == "tester"

    def test_add_duplicate_returns_duplicate_flag(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        add_factor(ws, type="keyword", value="transformer", query_role="must")
        result2 = add_factor(ws, type="keyword", value="transformer", query_role="should")
        assert result2.get("duplicate") is True

    def test_add_duplicate_does_not_insert_second_record(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        add_factor(ws, type="keyword", value="transformer", query_role="must")
        add_factor(ws, type="keyword", value="transformer", query_role="should")
        factors = list_factors(ws)
        assert len(factors) == 1

    def test_add_different_type_same_value_is_not_duplicate(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        add_factor(ws, type="keyword", value="attention", query_role="must")
        result2 = add_factor(ws, type="concept", value="attention", query_role="must")
        assert result2.get("duplicate") is not True
        factors = list_factors(ws)
        assert len(factors) == 2

    def test_add_does_not_infer_api_support(self, tmp_path: Path):
        """api_support is no longer auto-inferred; Skill layer decides search sources."""
        ws = _workspace(tmp_path)
        result = add_factor(ws, type="keyword", value="deep learning", query_role="must")
        assert result["api_support"] == []

    def test_add_with_api_ids(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        result = add_factor(
            ws,
            type="author",
            value="Hinton",
            query_role="must",
            api_ids={"semantic_scholar": "s2:abc"},
        )
        assert result["api_ids"]["semantic_scholar"] == "s2:abc"


# ---------------------------------------------------------------------------
# list_factors
# ---------------------------------------------------------------------------

class TestListFactors:
    def test_empty_list_when_no_factors(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        assert list_factors(ws) == []

    def test_list_returns_all_factors(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        add_factor(ws, type="keyword", value="a", query_role="must")
        add_factor(ws, type="author", value="b", query_role="must")
        factors = list_factors(ws)
        assert len(factors) == 2

    def test_list_filter_by_type(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        add_factor(ws, type="keyword", value="a", query_role="must")
        add_factor(ws, type="author", value="b", query_role="must")
        keywords = list_factors(ws, type="keyword")
        assert len(keywords) == 1
        assert keywords[0]["type"] == "keyword"

    def test_list_active_only_excludes_inactive(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        r1 = add_factor(ws, type="keyword", value="active_one", query_role="must")
        r2 = add_factor(ws, type="keyword", value="inactive_one", query_role="must")
        # Deactivate r2
        toggle_factor(ws, r2["id"], active=False)
        active = list_factors(ws, active_only=True)
        assert len(active) == 1
        assert active[0]["value"] == "active_one"

    def test_list_active_only_false_returns_all(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        r1 = add_factor(ws, type="keyword", value="a", query_role="must")
        toggle_factor(ws, r1["id"], active=False)
        all_factors = list_factors(ws, active_only=False)
        assert len(all_factors) == 1

    def test_list_combined_type_and_active_only(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        r1 = add_factor(ws, type="keyword", value="active_kw", query_role="must")
        r2 = add_factor(ws, type="keyword", value="inactive_kw", query_role="must")
        r3 = add_factor(ws, type="author", value="auth", query_role="must")
        toggle_factor(ws, r2["id"], active=False)
        result = list_factors(ws, type="keyword", active_only=True)
        assert len(result) == 1
        assert result[0]["value"] == "active_kw"


# ---------------------------------------------------------------------------
# toggle_factor
# ---------------------------------------------------------------------------

class TestToggleFactor:
    def test_toggle_deactivates_factor(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        r = add_factor(ws, type="keyword", value="x", query_role="must")
        updated = toggle_factor(ws, r["id"], active=False)
        assert updated["active"] is False

    def test_toggle_activates_factor(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        r = add_factor(ws, type="keyword", value="x", query_role="must")
        toggle_factor(ws, r["id"], active=False)
        updated = toggle_factor(ws, r["id"], active=True)
        assert updated["active"] is True

    def test_toggle_returns_updated_dict(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        r = add_factor(ws, type="keyword", value="x", query_role="must")
        result = toggle_factor(ws, r["id"], active=False)
        assert isinstance(result, dict)
        assert result["id"] == r["id"]

    def test_toggle_nonexistent_raises(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        with pytest.raises(KeyError):
            toggle_factor(ws, "sf_nonexistent", active=False)


# ---------------------------------------------------------------------------
# remove_factor
# ---------------------------------------------------------------------------

class TestRemoveFactor:
    def test_remove_deletes_factor(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        r = add_factor(ws, type="keyword", value="x", query_role="must")
        remove_factor(ws, r["id"])
        assert list_factors(ws) == []

    def test_remove_returns_removed_dict(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        r = add_factor(ws, type="keyword", value="x", query_role="must")
        result = remove_factor(ws, r["id"])
        assert isinstance(result, dict)
        assert result["id"] == r["id"]

    def test_remove_nonexistent_raises(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        with pytest.raises(KeyError):
            remove_factor(ws, "sf_nonexistent")

    def test_remove_only_removes_target(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        r1 = add_factor(ws, type="keyword", value="keep", query_role="must")
        r2 = add_factor(ws, type="keyword", value="remove", query_role="must")
        remove_factor(ws, r2["id"])
        remaining = list_factors(ws)
        assert len(remaining) == 1
        assert remaining[0]["id"] == r1["id"]


# ---------------------------------------------------------------------------
# compose_query
# ---------------------------------------------------------------------------

class TestComposeQuery:
    def test_compose_empty_workspace(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        result = compose_query(ws)
        assert result["primary_queries"] == []
        assert result["filters"] == {}
        assert result["combined_query"] == ""
        assert result["factor_ids"] == []
        assert result["factor_roles"] == {}

    def test_compose_includes_active_factors_only(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        r1 = add_factor(ws, type="keyword", value="active", query_role="primary")
        r2 = add_factor(ws, type="keyword", value="inactive", query_role="primary")
        toggle_factor(ws, r2["id"], active=False)
        result = compose_query(ws)
        assert r1["id"] in result["factor_ids"]
        assert r2["id"] not in result["factor_ids"]

    def test_compose_primary_queries_from_query_role(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        add_factor(ws, type="keyword", value="deep learning", query_role="primary")
        result = compose_query(ws)
        assert "deep learning" in result["primary_queries"]

    def test_compose_filters_from_filter_role(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        add_factor(ws, type="year_range", value="2020-2024", query_role="filter")
        result = compose_query(ws)
        assert "year_range" in result["filters"]

    def test_compose_combined_query_contains_primary_values(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        add_factor(ws, type="keyword", value="transformer", query_role="primary")
        add_factor(ws, type="keyword", value="attention", query_role="primary")
        result = compose_query(ws)
        assert "transformer" in result["combined_query"]
        assert "attention" in result["combined_query"]

    def test_compose_factor_roles_mapping(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        r = add_factor(ws, type="keyword", value="x", query_role="primary")
        result = compose_query(ws)
        assert r["id"] in result["factor_roles"]
        assert result["factor_roles"][r["id"]] == "primary"

    def test_compose_includes_all_active_factors(self, tmp_path: Path):
        """compose_query returns all active factors; source selection is Skill's job."""
        ws = _workspace(tmp_path)
        add_factor(ws, type="keyword", value="k1", query_role="primary")
        add_factor(ws, type="institution", value="MIT", query_role="filter")
        result = compose_query(ws)
        assert len(result["factor_ids"]) == 2
        assert "institution" in result["filters"]

    def test_compose_must_role_included_in_primary(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        add_factor(ws, type="keyword", value="must_kw", query_role="must")
        result = compose_query(ws)
        assert "must_kw" in result["primary_queries"]

    def test_compose_should_role_included_in_primary(self, tmp_path: Path):
        ws = _workspace(tmp_path)
        add_factor(ws, type="keyword", value="should_kw", query_role="should")
        result = compose_query(ws)
        assert "should_kw" in result["primary_queries"]

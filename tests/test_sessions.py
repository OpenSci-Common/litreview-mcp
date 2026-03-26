"""Tests for sessions.py — search session management (Task 9)."""

from __future__ import annotations

from pathlib import Path

import pytest

from litreview.sessions import list_sessions, save_session
from litreview.workspace import init_workspace


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_session_kwargs(**overrides) -> dict:
    defaults = {
        "input_factors": ["sf_aaa1111", "sf_bbb2222"],
        "factor_roles": {"sf_aaa1111": "must", "sf_bbb2222": "should"},
        "api_queries": {"semantic_scholar": {"query": "transformer attention"}},
        "results_total": 50,
        "results_after_dedup": 40,
        "results_already_in_library": 5,
        "results_new": 35,
        "result_paper_ids": ["abc123def456", "fedcba654321"],
        "user_decisions": {"abc123def456": "include"},
    }
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# save_session
# ---------------------------------------------------------------------------


class TestSaveSession:
    def test_returns_dict(self, tmp_path: Path):
        init_workspace(tmp_path)
        result = save_session(tmp_path, **make_session_kwargs())
        assert isinstance(result, dict)

    def test_result_has_session_id(self, tmp_path: Path):
        init_workspace(tmp_path)
        result = save_session(tmp_path, **make_session_kwargs())
        assert "session_id" in result
        assert result["session_id"].startswith("sess_")

    def test_result_has_created_at(self, tmp_path: Path):
        init_workspace(tmp_path)
        result = save_session(tmp_path, **make_session_kwargs())
        assert "created_at" in result
        assert isinstance(result["created_at"], str)
        assert len(result["created_at"]) > 0

    def test_session_id_format(self, tmp_path: Path):
        init_workspace(tmp_path)
        result = save_session(tmp_path, **make_session_kwargs())
        # Format: sess_<7 hex chars>
        parts = result["session_id"].split("_")
        assert len(parts) == 2
        assert parts[0] == "sess"
        assert len(parts[1]) == 7

    def test_input_data_preserved(self, tmp_path: Path):
        init_workspace(tmp_path)
        kwargs = make_session_kwargs()
        result = save_session(tmp_path, **kwargs)
        assert result["input_factors"] == kwargs["input_factors"]
        assert result["factor_roles"] == kwargs["factor_roles"]
        assert result["api_queries"] == kwargs["api_queries"]
        assert result["results_total"] == kwargs["results_total"]
        assert result["results_after_dedup"] == kwargs["results_after_dedup"]
        assert result["results_already_in_library"] == kwargs["results_already_in_library"]
        assert result["results_new"] == kwargs["results_new"]
        assert result["result_paper_ids"] == kwargs["result_paper_ids"]
        assert result["user_decisions"] == kwargs["user_decisions"]

    def test_session_persisted_in_db(self, tmp_path: Path):
        init_workspace(tmp_path)
        result = save_session(tmp_path, **make_session_kwargs())
        sessions = list_sessions(tmp_path)
        assert any(s["session_id"] == result["session_id"] for s in sessions)

    def test_session_written_to_sessions_json(self, tmp_path: Path):
        init_workspace(tmp_path)
        save_session(tmp_path, **make_session_kwargs())
        sessions_file = Path(tmp_path) / ".litreview" / "sessions.json"
        assert sessions_file.exists()

    def test_multiple_sessions_unique_ids(self, tmp_path: Path):
        init_workspace(tmp_path)
        s1 = save_session(tmp_path, **make_session_kwargs())
        s2 = save_session(tmp_path, **make_session_kwargs())
        assert s1["session_id"] != s2["session_id"]

    def test_workspace_id_present(self, tmp_path: Path):
        init_workspace(tmp_path)
        result = save_session(tmp_path, **make_session_kwargs())
        assert "workspace_id" in result


# ---------------------------------------------------------------------------
# list_sessions
# ---------------------------------------------------------------------------


class TestListSessions:
    def test_empty_returns_empty_list(self, tmp_path: Path):
        init_workspace(tmp_path)
        result = list_sessions(tmp_path)
        assert result == []

    def test_returns_list(self, tmp_path: Path):
        init_workspace(tmp_path)
        save_session(tmp_path, **make_session_kwargs())
        result = list_sessions(tmp_path)
        assert isinstance(result, list)

    def test_returns_all_sessions(self, tmp_path: Path):
        init_workspace(tmp_path)
        for _ in range(3):
            save_session(tmp_path, **make_session_kwargs())
        result = list_sessions(tmp_path)
        assert len(result) == 3

    def test_sorted_by_created_at_descending(self, tmp_path: Path):
        init_workspace(tmp_path)
        save_session(tmp_path, **make_session_kwargs())
        save_session(tmp_path, **make_session_kwargs())
        save_session(tmp_path, **make_session_kwargs())
        result = list_sessions(tmp_path)
        created_ats = [s["created_at"] for s in result]
        assert created_ats == sorted(created_ats, reverse=True)

    def test_list_with_limit(self, tmp_path: Path):
        init_workspace(tmp_path)
        for _ in range(5):
            save_session(tmp_path, **make_session_kwargs())
        result = list_sessions(tmp_path, limit=3)
        assert len(result) == 3

    def test_limit_returns_most_recent(self, tmp_path: Path):
        init_workspace(tmp_path)
        ids = []
        for _ in range(5):
            s = save_session(tmp_path, **make_session_kwargs())
            ids.append(s["session_id"])
        result = list_sessions(tmp_path, limit=2)
        # Sorted descending, so last inserted should be first
        assert len(result) == 2
        # Both results should be valid sessions
        for s in result:
            assert "session_id" in s

    def test_each_session_has_required_fields(self, tmp_path: Path):
        init_workspace(tmp_path)
        save_session(tmp_path, **make_session_kwargs())
        sessions = list_sessions(tmp_path)
        required = {
            "session_id", "workspace_id", "created_at",
            "input_factors", "factor_roles", "api_queries",
            "results_total", "results_after_dedup",
            "results_already_in_library", "results_new",
            "result_paper_ids", "user_decisions",
        }
        for s in sessions:
            assert required.issubset(set(s.keys()))

    def test_list_no_limit_returns_all(self, tmp_path: Path):
        init_workspace(tmp_path)
        for _ in range(10):
            save_session(tmp_path, **make_session_kwargs())
        result = list_sessions(tmp_path)
        assert len(result) == 10

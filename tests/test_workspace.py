"""Tests for workspace management (Task 4)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from litreview.workspace import (
    DB_FILES,
    get_config,
    get_status,
    init_workspace,
    set_config,
)


# ---------------------------------------------------------------------------
# init_workspace
# ---------------------------------------------------------------------------

class TestInitWorkspace:
    def test_creates_litreview_dir(self, tmp_path: Path):
        result = init_workspace(tmp_path)
        assert (tmp_path / ".litreview").is_dir()

    def test_creates_all_db_files(self, tmp_path: Path):
        init_workspace(tmp_path)
        for fname in DB_FILES:
            assert (tmp_path / ".litreview" / fname).exists(), f"Missing {fname}"

    def test_creates_config_json(self, tmp_path: Path):
        init_workspace(tmp_path)
        config_path = tmp_path / ".litreview" / "config.json"
        assert config_path.exists()

    def test_config_has_scoring_weights(self, tmp_path: Path):
        init_workspace(tmp_path)
        config_path = tmp_path / ".litreview" / "config.json"
        config = json.loads(config_path.read_text())
        weights = config["scoring"]["weights"]
        expected_keys = {
            "citation_count",
            "recency",
            "citation_velocity",
            "venue_impact",
            "open_access",
            "author_h_index",
            "keyword_relevance",
        }
        assert set(weights.keys()) == expected_keys

    def test_default_weight_values(self, tmp_path: Path):
        init_workspace(tmp_path)
        config_path = tmp_path / ".litreview" / "config.json"
        config = json.loads(config_path.read_text())
        w = config["scoring"]["weights"]
        assert abs(w["citation_count"] - 0.20) < 1e-9
        assert abs(w["recency"] - 0.20) < 1e-9
        assert abs(w["citation_velocity"] - 0.15) < 1e-9
        assert abs(w["venue_impact"] - 0.15) < 1e-9
        assert abs(w["open_access"] - 0.10) < 1e-9
        assert abs(w["author_h_index"] - 0.10) < 1e-9
        assert abs(w["keyword_relevance"] - 0.10) < 1e-9

    def test_creates_pdfs_dir(self, tmp_path: Path):
        init_workspace(tmp_path)
        assert (tmp_path / ".litreview" / "pdfs").is_dir()

    def test_returns_path(self, tmp_path: Path):
        result = init_workspace(tmp_path)
        assert "path" in result
        assert Path(result["path"]) == tmp_path / ".litreview"

    def test_already_existed_false_on_first_init(self, tmp_path: Path):
        result = init_workspace(tmp_path)
        assert result["already_existed"] is False

    def test_already_existed_true_on_second_init(self, tmp_path: Path):
        init_workspace(tmp_path)
        result = init_workspace(tmp_path)
        assert result["already_existed"] is True

    def test_second_init_does_not_overwrite_config(self, tmp_path: Path):
        init_workspace(tmp_path)
        # Manually change config
        config_path = tmp_path / ".litreview" / "config.json"
        config = json.loads(config_path.read_text())
        config["scoring"]["weights"]["recency"] = 0.99
        config_path.write_text(json.dumps(config))
        # Re-init
        init_workspace(tmp_path)
        config2 = json.loads(config_path.read_text())
        assert abs(config2["scoring"]["weights"]["recency"] - 0.99) < 1e-9


# ---------------------------------------------------------------------------
# get_status
# ---------------------------------------------------------------------------

class TestGetStatus:
    def test_initialized_true_for_valid_workspace(self, tmp_path: Path):
        init_workspace(tmp_path)
        status = get_status(tmp_path)
        assert status["initialized"] is True

    def test_initialized_false_for_empty_dir(self, tmp_path: Path):
        status = get_status(tmp_path)
        assert status["initialized"] is False

    def test_empty_counts(self, tmp_path: Path):
        init_workspace(tmp_path)
        status = get_status(tmp_path)
        assert status["papers_count"] == 0
        assert status["factors_count"] == 0
        assert status["content_factors_count"] == 0
        assert status["sessions_count"] == 0

    def test_counts_reflect_data(self, tmp_path: Path):
        init_workspace(tmp_path)
        # Manually insert records into TinyDB files
        from tinydb import TinyDB
        lit_db = TinyDB(str(tmp_path / ".litreview" / "literature.json"))
        lit_db.insert({"paper_id": "abc"})
        lit_db.insert({"paper_id": "def"})
        lit_db.close()

        sf_db = TinyDB(str(tmp_path / ".litreview" / "search_factors.json"))
        sf_db.insert({"id": "sf_001"})
        sf_db.close()

        status = get_status(tmp_path)
        assert status["papers_count"] == 2
        assert status["factors_count"] == 1


# ---------------------------------------------------------------------------
# get_config
# ---------------------------------------------------------------------------

class TestGetConfig:
    def test_get_all_config(self, tmp_path: Path):
        init_workspace(tmp_path)
        config = get_config(tmp_path)
        assert isinstance(config, dict)
        assert "scoring" in config

    def test_get_top_level_key(self, tmp_path: Path):
        init_workspace(tmp_path)
        scoring = get_config(tmp_path, key="scoring")
        assert "weights" in scoring

    def test_get_nested_key_dot_notation(self, tmp_path: Path):
        init_workspace(tmp_path)
        recency = get_config(tmp_path, key="scoring.weights.recency")
        assert abs(recency - 0.20) < 1e-9

    def test_get_nonexistent_key_returns_none(self, tmp_path: Path):
        init_workspace(tmp_path)
        result = get_config(tmp_path, key="nonexistent.key")
        assert result is None


# ---------------------------------------------------------------------------
# set_config
# ---------------------------------------------------------------------------

class TestSetConfig:
    def test_set_top_level_key(self, tmp_path: Path):
        init_workspace(tmp_path)
        set_config(tmp_path, "my_key", "my_value")
        config = get_config(tmp_path)
        assert config["my_key"] == "my_value"

    def test_set_nested_key_dot_notation(self, tmp_path: Path):
        init_workspace(tmp_path)
        set_config(tmp_path, "scoring.weights.recency", 0.30)
        recency = get_config(tmp_path, key="scoring.weights.recency")
        assert abs(recency - 0.30) < 1e-9

    def test_set_returns_updated_config(self, tmp_path: Path):
        init_workspace(tmp_path)
        result = set_config(tmp_path, "scoring.weights.recency", 0.30)
        assert isinstance(result, dict)
        assert abs(result["scoring"]["weights"]["recency"] - 0.30) < 1e-9

    def test_set_creates_intermediate_keys(self, tmp_path: Path):
        init_workspace(tmp_path)
        set_config(tmp_path, "new_section.sub_key.value", 42)
        val = get_config(tmp_path, key="new_section.sub_key.value")
        assert val == 42

    def test_set_persists_across_reads(self, tmp_path: Path):
        init_workspace(tmp_path)
        set_config(tmp_path, "scoring.weights.citation_count", 0.99)
        # Re-read from disk
        val = get_config(tmp_path, key="scoring.weights.citation_count")
        assert abs(val - 0.99) < 1e-9

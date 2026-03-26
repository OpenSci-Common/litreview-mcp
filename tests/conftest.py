"""Shared pytest fixtures for litreview-mcp tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tinydb import TinyDB
from tinydb.storages import MemoryStorage


@pytest.fixture
def tmp_workspace(tmp_path: Path) -> Path:
    """Create a temporary workspace with .litreview/ directory and empty TinyDB files."""
    litreview_dir = tmp_path / ".litreview"
    litreview_dir.mkdir()

    # Create empty TinyDB JSON files
    for db_name in ("papers.json", "factors.json", "sessions.json", "content_factors.json"):
        db_file = litreview_dir / db_name
        db_file.write_text("{}")

    return tmp_path


@pytest.fixture
def sample_paper_data() -> dict:
    """Return sample paper data dict for testing."""
    return {
        "paper_id": "abc123def456",
        "title": "Attention Is All You Need",
        "year": 2017,
        "external_ids": {
            "doi": "10.48550/arXiv.1706.03762",
            "arxiv": "1706.03762",
            "semantic_scholar": "204e3073870fae3d05bcbc2f6a8e263d9b72e776",
        },
        "authors": [
            {"name": "Ashish Vaswani", "author_id": "s2:1234"},
            {"name": "Noam Shazeer", "author_id": "s2:5678"},
        ],
        "abstract": "The dominant sequence transduction models are based on complex recurrent or convolutional neural networks.",
        "venue": "NeurIPS",
        "citation_count": 50000,
        "fields_of_study": ["Computer Science", "Artificial Intelligence"],
        "open_access_status": "green",
        "pdf_status": "unknown",
        "pdf_path": None,
        "status": "candidate",
        "source_apis": ["semantic_scholar", "arxiv"],
        "first_seen_session_id": "sess_abc1234",
        "added_by": "user",
        "created_at": "2024-01-01T00:00:00+00:00",
    }


@pytest.fixture
def sample_factors() -> list:
    """Return a list of sample SearchFactor dicts for testing."""
    return [
        {
            "id": "sf_a1b2c3d",
            "type": "keyword",
            "value": "transformer",
            "query_role": "must",
            "active": True,
            "sub_type": None,
            "api_ids": {},
            "api_support": ["semantic_scholar", "arxiv"],
            "provenance": "user",
            "promoted_from": None,
            "created_by": "user",
            "created_at": "2024-01-01T00:00:00+00:00",
        },
        {
            "id": "sf_e4f5g6h",
            "type": "keyword",
            "value": "attention mechanism",
            "query_role": "should",
            "active": True,
            "sub_type": None,
            "api_ids": {},
            "api_support": ["semantic_scholar"],
            "provenance": "auto",
            "promoted_from": "cf_xyz789",
            "created_by": None,
            "created_at": "2024-01-02T00:00:00+00:00",
        },
    ]

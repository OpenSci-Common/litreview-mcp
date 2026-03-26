"""Tests for litreview.graphs module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from litreview.workspace import init_workspace
from litreview.library import add_papers_batch
from litreview.factors import add_factor
from litreview.graphs import (
    create_graph,
    list_graphs,
    graph_detail,
    build_graph,
    delete_graph,
)


# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------

SAMPLE_PAPERS = [
    {
        "paper_id": "aaa111bbb222",
        "title": "Tokenization of Real World Assets",
        "authors": [{"name": "Alice Smith"}, {"name": "Bob Jones"}],
        "abstract": "This paper explores RWA tokenization.",
        "year": 2024,
        "venue": "FinTech Journal",
        "url": "https://example.com/paper1",
        "external_ids": {"doi": "10.1234/test1"},
        "citations": 10,
        "fields_of_study": ["Finance", "Blockchain"],
        "status": "in_library",
    },
    {
        "paper_id": "ccc333ddd444",
        "title": "DeFi and Financial Inclusion",
        "authors": "Bob Jones; Charlie Brown",
        "abstract": "Decentralized finance promotes financial inclusion.",
        "year": 2025,
        "venue": "FinTech Journal",
        "url": None,
        "pdf_url": "https://example.com/paper2.pdf",
        "external_ids": {"doi": "10.1234/test2"},
        "citation_count": 5,
        "fields_of_study": ["Finance"],
        "status": "in_library",
    },
    {
        "paper_id": "eee555fff666",
        "title": "Blockchain Scalability",
        "authors": [{"name": "Diana Prince"}],
        "abstract": "Scaling blockchain networks for enterprise.",
        "year": 2023,
        "venue": "IEEE Transactions",
        "url": "https://example.com/paper3",
        "external_ids": {},
        "citations": 30,
        "fields_of_study": ["Blockchain", "Networks"],
        "status": "candidate",
    },
]

PAPER_FACTOR_MAP = {
    "aaa111bbb222": [
        {"factor_value": "asset tokenization", "relevance": "high"},
        {"factor_value": "financial inclusion", "relevance": "low"},
    ],
    "ccc333ddd444": [
        {"factor_value": "decentralized finance", "relevance": "high"},
        {"factor_value": "financial inclusion", "relevance": "high"},
    ],
}


def _workspace(tmp_path: Path) -> Path:
    """Initialise workspace and add sample papers + factors."""
    init_workspace(tmp_path)
    add_papers_batch(base_path=tmp_path, papers=SAMPLE_PAPERS)
    add_factor(tmp_path, type="keyword", value="asset tokenization", query_role="primary")
    add_factor(tmp_path, type="keyword", value="decentralized finance", query_role="primary")
    add_factor(tmp_path, type="keyword", value="financial inclusion", query_role="primary")
    return tmp_path


# ---------------------------------------------------------------------------
# create_graph
# ---------------------------------------------------------------------------

class TestCreateGraph:
    def test_returns_config_with_graph_id(self, tmp_path):
        ws = _workspace(tmp_path)
        config = create_graph(ws, "Test Graph", ["paper", "author"], ["authored"])
        assert "graph_id" in config
        assert config["graph_id"].startswith("g_")

    def test_stores_name(self, tmp_path):
        ws = _workspace(tmp_path)
        config = create_graph(ws, "My Graph", ["paper"], [])
        assert config["name"] == "My Graph"

    def test_stores_node_types(self, tmp_path):
        ws = _workspace(tmp_path)
        config = create_graph(ws, "G", ["paper", "author", "factor"], ["authored"])
        assert config["node_types"] == ["paper", "author", "factor"]

    def test_stores_edge_types(self, tmp_path):
        ws = _workspace(tmp_path)
        config = create_graph(ws, "G", ["paper"], ["authored", "cites"])
        assert config["edge_types"] == ["authored", "cites"]

    def test_stores_paper_filter(self, tmp_path):
        ws = _workspace(tmp_path)
        config = create_graph(ws, "G", ["paper"], [], paper_filter={"status": "in_library"})
        assert config["paper_filter"] == {"status": "in_library"}

    def test_persisted_to_index(self, tmp_path):
        ws = _workspace(tmp_path)
        config = create_graph(ws, "Persist Test", ["paper"], [])
        gid = config["graph_id"]
        # Reload from DB
        fetched = graph_detail(ws, gid)
        assert fetched["graph_id"] == gid
        assert fetched["name"] == "Persist Test"

    def test_has_created_at(self, tmp_path):
        ws = _workspace(tmp_path)
        config = create_graph(ws, "G", ["paper"], [])
        assert "created_at" in config
        assert config["created_at"]

    def test_creates_graphs_dir(self, tmp_path):
        ws = _workspace(tmp_path)
        create_graph(ws, "G", ["paper"], [])
        assert (ws / ".litreview" / "graphs").is_dir()


# ---------------------------------------------------------------------------
# list_graphs
# ---------------------------------------------------------------------------

class TestListGraphs:
    def test_empty_list_initially(self, tmp_path):
        ws = _workspace(tmp_path)
        result = list_graphs(ws)
        assert result == []

    def test_returns_all_configs(self, tmp_path):
        ws = _workspace(tmp_path)
        create_graph(ws, "Graph A", ["paper"], [])
        create_graph(ws, "Graph B", ["paper", "author"], ["authored"])
        result = list_graphs(ws)
        assert len(result) == 2

    def test_sorted_by_created_at_desc(self, tmp_path):
        ws = _workspace(tmp_path)
        create_graph(ws, "First", ["paper"], [])
        create_graph(ws, "Second", ["paper"], [])
        result = list_graphs(ws)
        # Second graph was created later, so should come first
        names = [g["name"] for g in result]
        assert names.index("Second") < names.index("First")


# ---------------------------------------------------------------------------
# graph_detail
# ---------------------------------------------------------------------------

class TestGraphDetail:
    def test_returns_correct_config(self, tmp_path):
        ws = _workspace(tmp_path)
        config = create_graph(ws, "Detail Test", ["paper", "author"], ["authored"])
        gid = config["graph_id"]
        detail = graph_detail(ws, gid)
        assert detail["graph_id"] == gid
        assert detail["name"] == "Detail Test"

    def test_raises_for_unknown_id(self, tmp_path):
        ws = _workspace(tmp_path)
        with pytest.raises(ValueError, match="not found"):
            graph_detail(ws, "g_notexist")


# ---------------------------------------------------------------------------
# build_graph — paper + author nodes + authored edges
# ---------------------------------------------------------------------------

class TestBuildGraphAuthorPaper:
    def test_returns_expected_keys(self, tmp_path):
        ws = _workspace(tmp_path)
        config = create_graph(ws, "G", ["paper", "author"], ["authored"])
        result = build_graph(ws, config["graph_id"])
        assert "graph_id" in result
        assert "html_path" in result
        assert "data_path" in result
        assert "stats" in result

    def test_html_file_exists(self, tmp_path):
        ws = _workspace(tmp_path)
        config = create_graph(ws, "G", ["paper", "author"], ["authored"])
        result = build_graph(ws, config["graph_id"])
        assert Path(result["html_path"]).exists()

    def test_data_file_exists(self, tmp_path):
        ws = _workspace(tmp_path)
        config = create_graph(ws, "G", ["paper", "author"], ["authored"])
        result = build_graph(ws, config["graph_id"])
        assert Path(result["data_path"]).exists()

    def test_html_is_valid_document(self, tmp_path):
        ws = _workspace(tmp_path)
        config = create_graph(ws, "G", ["paper", "author"], ["authored"])
        result = build_graph(ws, config["graph_id"])
        html = Path(result["html_path"]).read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in html
        assert "vis-network" in html

    def test_stats_paper_count(self, tmp_path):
        ws = _workspace(tmp_path)
        config = create_graph(ws, "G", ["paper", "author"], ["authored"])
        result = build_graph(ws, config["graph_id"])
        # All 3 sample papers
        assert result["stats"]["papers"] == 3

    def test_stats_author_count(self, tmp_path):
        ws = _workspace(tmp_path)
        config = create_graph(ws, "G", ["paper", "author"], ["authored"])
        result = build_graph(ws, config["graph_id"])
        # Alice Smith, Bob Jones (deduped), Charlie Brown, Diana Prince = 4
        assert result["stats"]["authors"] == 4

    def test_authored_edges_created(self, tmp_path):
        ws = _workspace(tmp_path)
        config = create_graph(ws, "G", ["paper", "author"], ["authored"])
        result = build_graph(ws, config["graph_id"])
        data = json.loads(Path(result["data_path"]).read_text(encoding="utf-8"))
        authored_edges = [e for e in data["edges"] if e["type"] == "authored"]
        # P1: Alice, Bob = 2; P2: Bob, Charlie = 2; P3: Diana = 1 → 5 total
        assert len(authored_edges) == 5

    def test_paper_filter_status(self, tmp_path):
        ws = _workspace(tmp_path)
        config = create_graph(
            ws, "Filtered", ["paper", "author"], ["authored"],
            paper_filter={"status": "in_library"},
        )
        result = build_graph(ws, config["graph_id"])
        # Only 2 papers are in_library
        assert result["stats"]["papers"] == 2

    def test_updates_index_with_paths(self, tmp_path):
        ws = _workspace(tmp_path)
        config = create_graph(ws, "G", ["paper"], [])
        gid = config["graph_id"]
        build_graph(ws, gid)
        detail = graph_detail(ws, gid)
        assert detail["html_path"] is not None
        assert detail["data_path"] is not None
        assert detail["stats"]


# ---------------------------------------------------------------------------
# build_graph — paper + factor nodes + relates_to edges
# ---------------------------------------------------------------------------

class TestBuildGraphFactorRelates:
    def test_factor_nodes_created(self, tmp_path):
        ws = _workspace(tmp_path)
        config = create_graph(ws, "G", ["paper", "factor"], ["relates_to"])
        result = build_graph(ws, config["graph_id"], paper_factor_map=PAPER_FACTOR_MAP)
        assert result["stats"]["factors"] == 3

    def test_relates_to_edges_with_map(self, tmp_path):
        ws = _workspace(tmp_path)
        config = create_graph(ws, "G", ["paper", "factor"], ["relates_to"])
        result = build_graph(ws, config["graph_id"], paper_factor_map=PAPER_FACTOR_MAP)
        data = json.loads(Path(result["data_path"]).read_text(encoding="utf-8"))
        relates = [e for e in data["edges"] if e["type"] == "relates_to"]
        assert len(relates) == 4  # 2 for paper1 + 2 for paper2

    def test_no_relates_to_edges_without_map(self, tmp_path):
        ws = _workspace(tmp_path)
        config = create_graph(ws, "G", ["paper", "factor"], ["relates_to"])
        result = build_graph(ws, config["graph_id"])
        data = json.loads(Path(result["data_path"]).read_text(encoding="utf-8"))
        relates = [e for e in data["edges"] if e["type"] == "relates_to"]
        assert len(relates) == 0

    def test_relates_to_relevance_preserved(self, tmp_path):
        ws = _workspace(tmp_path)
        config = create_graph(ws, "G", ["paper", "factor"], ["relates_to"])
        result = build_graph(ws, config["graph_id"], paper_factor_map=PAPER_FACTOR_MAP)
        data = json.loads(Path(result["data_path"]).read_text(encoding="utf-8"))
        high_edges = [
            e for e in data["edges"]
            if e["type"] == "relates_to" and e.get("relevance") == "high"
        ]
        # aaa→asset_tokenization:high, ccc→decentralized_finance:high, ccc→financial_inclusion:high
        assert len(high_edges) == 3

    def test_html_embeds_factor_data(self, tmp_path):
        ws = _workspace(tmp_path)
        config = create_graph(ws, "G", ["paper", "factor"], ["relates_to"])
        result = build_graph(ws, config["graph_id"], paper_factor_map=PAPER_FACTOR_MAP)
        html = Path(result["html_path"]).read_text(encoding="utf-8")
        assert "decentralized finance" in html


# ---------------------------------------------------------------------------
# build_graph — venue nodes
# ---------------------------------------------------------------------------

class TestBuildGraphVenue:
    def test_venue_nodes_created(self, tmp_path):
        ws = _workspace(tmp_path)
        config = create_graph(ws, "G", ["paper", "venue"], [])
        result = build_graph(ws, config["graph_id"])
        # "FinTech Journal" (2 papers), "IEEE Transactions" (1 paper) = 2 unique venues
        assert result["stats"]["venues"] == 2

    def test_venue_dedup(self, tmp_path):
        ws = _workspace(tmp_path)
        config = create_graph(ws, "G", ["paper", "venue"], [])
        result = build_graph(ws, config["graph_id"])
        data = json.loads(Path(result["data_path"]).read_text(encoding="utf-8"))
        venue_labels = [n["label"] for n in data["nodes"] if n["type"] == "venue"]
        # Exactly 2 distinct venue labels
        assert len(set(venue_labels)) == 2

    def test_same_venue_edges(self, tmp_path):
        ws = _workspace(tmp_path)
        config = create_graph(ws, "G", ["paper", "venue"], ["same_venue"])
        result = build_graph(ws, config["graph_id"])
        data = json.loads(Path(result["data_path"]).read_text(encoding="utf-8"))
        sv_edges = [e for e in data["edges"] if e["type"] == "same_venue"]
        # FinTech Journal has 2 papers → 1 pair
        assert len(sv_edges) == 1

    def test_no_venue_nodes_without_type(self, tmp_path):
        ws = _workspace(tmp_path)
        config = create_graph(ws, "G", ["paper"], [])
        result = build_graph(ws, config["graph_id"])
        assert result["stats"]["venues"] == 0


# ---------------------------------------------------------------------------
# build_graph — field nodes
# ---------------------------------------------------------------------------

class TestBuildGraphField:
    def test_field_nodes_created(self, tmp_path):
        ws = _workspace(tmp_path)
        config = create_graph(ws, "G", ["paper", "field"], [])
        result = build_graph(ws, config["graph_id"])
        # Finance, Blockchain, Networks = 3 unique fields
        assert result["stats"]["fields"] == 3

    def test_no_field_nodes_without_type(self, tmp_path):
        ws = _workspace(tmp_path)
        config = create_graph(ws, "G", ["paper"], [])
        result = build_graph(ws, config["graph_id"])
        assert result["stats"]["fields"] == 0


# ---------------------------------------------------------------------------
# build_graph — co_authored edges
# ---------------------------------------------------------------------------

class TestBuildGraphCoAuthored:
    def test_co_authored_edges_created(self, tmp_path):
        ws = _workspace(tmp_path)
        config = create_graph(ws, "G", ["paper", "author"], ["authored", "co_authored"])
        result = build_graph(ws, config["graph_id"])
        data = json.loads(Path(result["data_path"]).read_text(encoding="utf-8"))
        co_edges = [e for e in data["edges"] if e["type"] == "co_authored"]
        # P1: Alice-Bob (1 pair); P2: Bob-Charlie (1 pair); P3: Diana alone (0 pairs) = 2
        assert len(co_edges) == 2

    def test_co_authored_no_duplicates(self, tmp_path):
        ws = _workspace(tmp_path)
        config = create_graph(ws, "G", ["paper", "author"], ["authored", "co_authored"])
        result = build_graph(ws, config["graph_id"])
        data = json.loads(Path(result["data_path"]).read_text(encoding="utf-8"))
        co_edges = [e for e in data["edges"] if e["type"] == "co_authored"]
        pairs = [(e["from"], e["to"]) for e in co_edges]
        assert len(pairs) == len(set(pairs))


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

class TestBuildGraphHtml:
    def test_html_contains_graph_data(self, tmp_path):
        ws = _workspace(tmp_path)
        config = create_graph(ws, "My Graph", ["paper", "author"], ["authored"])
        result = build_graph(ws, config["graph_id"])
        html = Path(result["html_path"]).read_text(encoding="utf-8")
        assert "Tokenization of Real World Assets" in html

    def test_html_contains_graph_name(self, tmp_path):
        ws = _workspace(tmp_path)
        config = create_graph(ws, "Special Graph Name", ["paper"], [])
        result = build_graph(ws, config["graph_id"])
        html = Path(result["html_path"]).read_text(encoding="utf-8")
        assert "Special Graph Name" in html

    def test_html_placeholder_replaced(self, tmp_path):
        ws = _workspace(tmp_path)
        config = create_graph(ws, "G", ["paper"], [])
        result = build_graph(ws, config["graph_id"])
        html = Path(result["html_path"]).read_text(encoding="utf-8")
        assert "/*__GRAPH_DATA__*/" not in html
        assert "/*__GRAPH_CONFIG__*/" not in html

    def test_html_edge_click_handler(self, tmp_path):
        ws = _workspace(tmp_path)
        config = create_graph(ws, "G", ["paper", "author"], ["authored"])
        result = build_graph(ws, config["graph_id"])
        html = Path(result["html_path"]).read_text(encoding="utf-8")
        # Edge click support
        assert "showEdgeDetail" in html
        assert "edgesRawMap" in html


# ---------------------------------------------------------------------------
# Each graph gets its own files (no overwriting)
# ---------------------------------------------------------------------------

class TestGraphIsolation:
    def test_separate_html_files(self, tmp_path):
        ws = _workspace(tmp_path)
        c1 = create_graph(ws, "Graph One", ["paper"], [])
        c2 = create_graph(ws, "Graph Two", ["paper", "author"], ["authored"])
        r1 = build_graph(ws, c1["graph_id"])
        r2 = build_graph(ws, c2["graph_id"])
        assert r1["html_path"] != r2["html_path"]

    def test_separate_data_files(self, tmp_path):
        ws = _workspace(tmp_path)
        c1 = create_graph(ws, "Graph One", ["paper"], [])
        c2 = create_graph(ws, "Graph Two", ["paper", "author"], ["authored"])
        r1 = build_graph(ws, c1["graph_id"])
        r2 = build_graph(ws, c2["graph_id"])
        assert r1["data_path"] != r2["data_path"]

    def test_rebuild_updates_same_file(self, tmp_path):
        ws = _workspace(tmp_path)
        config = create_graph(ws, "Rebuild", ["paper"], [])
        r1 = build_graph(ws, config["graph_id"])
        r2 = build_graph(ws, config["graph_id"])
        # Same file paths (not new files each time)
        assert r1["html_path"] == r2["html_path"]

    def test_graphs_in_graphs_subdir(self, tmp_path):
        ws = _workspace(tmp_path)
        config = create_graph(ws, "G", ["paper"], [])
        result = build_graph(ws, config["graph_id"])
        graphs_dir = ws / ".litreview" / "graphs"
        assert Path(result["html_path"]).parent == graphs_dir
        assert Path(result["data_path"]).parent == graphs_dir


# ---------------------------------------------------------------------------
# delete_graph
# ---------------------------------------------------------------------------

class TestDeleteGraph:
    def test_removes_from_index(self, tmp_path):
        ws = _workspace(tmp_path)
        config = create_graph(ws, "To Delete", ["paper"], [])
        gid = config["graph_id"]
        delete_graph(ws, gid)
        with pytest.raises(ValueError):
            graph_detail(ws, gid)

    def test_removes_html_file(self, tmp_path):
        ws = _workspace(tmp_path)
        config = create_graph(ws, "To Delete", ["paper"], [])
        gid = config["graph_id"]
        result = build_graph(ws, gid)
        html_path = Path(result["html_path"])
        assert html_path.exists()
        delete_graph(ws, gid)
        assert not html_path.exists()

    def test_removes_data_file(self, tmp_path):
        ws = _workspace(tmp_path)
        config = create_graph(ws, "To Delete", ["paper"], [])
        gid = config["graph_id"]
        result = build_graph(ws, gid)
        data_path = Path(result["data_path"])
        assert data_path.exists()
        delete_graph(ws, gid)
        assert not data_path.exists()

    def test_returns_deleted_id(self, tmp_path):
        ws = _workspace(tmp_path)
        config = create_graph(ws, "To Delete", ["paper"], [])
        gid = config["graph_id"]
        result = delete_graph(ws, gid)
        assert result["deleted"] == gid

    def test_does_not_affect_other_graphs(self, tmp_path):
        ws = _workspace(tmp_path)
        c1 = create_graph(ws, "Keep", ["paper"], [])
        c2 = create_graph(ws, "Delete", ["paper"], [])
        delete_graph(ws, c2["graph_id"])
        # c1 still accessible
        detail = graph_detail(ws, c1["graph_id"])
        assert detail["name"] == "Keep"

    def test_delete_without_files_ok(self, tmp_path):
        ws = _workspace(tmp_path)
        config = create_graph(ws, "No Files", ["paper"], [])
        # Don't call build_graph — no files
        result = delete_graph(ws, config["graph_id"])
        assert result["files_removed"] == []

"""Tests for litreview.relations module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from litreview.relations import (
    _author_names_match,
    _content_hash,
    _factor_set_hash,
    _find_matching_author,
    _stable_id,
    build_graph_data,
    check_cache,
    deduplicate_factors,
    load_cache,
    render_html,
    save_cache,
    save_graph_html,
    update_cache,
)


# --- Fixtures ---

SAMPLE_PAPERS = [
    {
        "paper_id": "aaa111bbb222",
        "title": "Tokenization of Real World Assets",
        "authors": [{"name": "Alice Smith"}, {"name": "Bob Jones"}],
        "abstract": "This paper explores RWA tokenization and its impact.",
        "year": 2024,
        "venue": "FinTech Journal",
        "url": "https://example.com/paper1",
        "external_ids": {"doi": "10.1234/test1"},
        "citations": 10,
    },
    {
        "paper_id": "ccc333ddd444",
        "title": "DeFi and Financial Inclusion",
        "authors": "Bob Jones; Charlie Brown",  # semicolon string format
        "abstract": "Decentralized finance can promote financial inclusion.",
        "year": 2025,
        "venue": "Blockchain Review",
        "url": None,
        "pdf_url": "https://example.com/paper2.pdf",
        "external_ids": {"doi": "10.1234/test2"},
        "citation_count": 5,
    },
]

FACTOR_VALUES = ["decentralized finance", "asset tokenization", "financial inclusion"]

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


# --- _stable_id ---


# --- Author fuzzy matching ---


class TestAuthorNamesMatch:
    def test_exact_match(self):
        assert _author_names_match("bob jones", "bob jones")

    def test_typo(self):
        assert _author_names_match("bob jonse", "bob jones")

    def test_initial_expansion(self):
        assert _author_names_match("b. jones", "bob jones")

    def test_initial_no_dot(self):
        assert _author_names_match("b jones", "bob jones")

    def test_reverse_initial(self):
        assert _author_names_match("bob jones", "b. jones")

    def test_name_order_swap(self):
        assert _author_names_match("jones, bob", "bob jones")

    def test_different_people(self):
        assert not _author_names_match("alice smith", "bob jones")

    def test_same_surname_different_first(self):
        assert not _author_names_match("alice jones", "bob jones")

    def test_short_names_no_false_positive(self):
        assert not _author_names_match("a. li", "b. li")


class TestFindMatchingAuthor:
    def test_exact_hit(self):
        existing = {"bob jones": "aid_1"}
        assert _find_matching_author("Bob Jones", existing) == "bob jones"

    def test_fuzzy_hit(self):
        existing = {"bob jones": "aid_1"}
        assert _find_matching_author("B. Jones", existing) == "bob jones"

    def test_no_match(self):
        existing = {"bob jones": "aid_1"}
        assert _find_matching_author("Alice Smith", existing) is None

    def test_empty_existing(self):
        assert _find_matching_author("Bob Jones", {}) is None


# --- Factor fuzzy dedup ---


class TestDeduplicateFactors:
    def test_no_duplicates(self):
        canonical, mapping = deduplicate_factors(["DeFi", "blockchain", "RWA"])
        assert len(canonical) == 3

    def test_spelling_variant(self):
        canonical, mapping = deduplicate_factors(
            ["financial inclusion", "financial inclusions"]
        )
        assert len(canonical) == 1
        assert mapping["financial inclusions"] == "financial inclusion"

    def test_preserves_first_as_canonical(self):
        canonical, mapping = deduplicate_factors(
            ["blockchain finance", "blockchain finances"]
        )
        assert canonical[0] == "blockchain finance"

    def test_semantic_synonyms_not_merged(self):
        """DeFi and decentralized finance are semantically similar but
        string-level different — code-level dedup should NOT merge them."""
        canonical, mapping = deduplicate_factors(
            ["DeFi", "decentralized finance"]
        )
        assert len(canonical) == 2

    def test_empty_input(self):
        canonical, mapping = deduplicate_factors([])
        assert canonical == []
        assert mapping == {}

    def test_mapping_complete(self):
        values = ["a", "b", "c"]
        _, mapping = deduplicate_factors(values)
        for v in values:
            assert v.lower() in mapping


class TestStableId:
    def test_deterministic(self):
        assert _stable_id("author", "Alice") == _stable_id("author", "Alice")

    def test_case_insensitive(self):
        assert _stable_id("author", "Alice") == _stable_id("author", "alice")

    def test_strips_whitespace(self):
        assert _stable_id("factor", " DeFi ") == _stable_id("factor", "defi")

    def test_different_prefixes_differ(self):
        assert _stable_id("author", "x") != _stable_id("factor", "x")


# --- build_graph_data ---


class TestBuildGraphData:
    def test_returns_nodes_edges_stats(self):
        result = build_graph_data(SAMPLE_PAPERS, FACTOR_VALUES)
        assert "nodes" in result
        assert "edges" in result
        assert "stats" in result

    def test_paper_nodes_created(self):
        result = build_graph_data(SAMPLE_PAPERS, FACTOR_VALUES)
        paper_nodes = [n for n in result["nodes"] if n["type"] == "paper"]
        assert len(paper_nodes) == 2

    def test_author_nodes_deduplicated(self):
        """Bob Jones appears in both papers; should have one author node."""
        result = build_graph_data(SAMPLE_PAPERS, FACTOR_VALUES)
        author_nodes = [n for n in result["nodes"] if n["type"] == "author"]
        author_names = {n["label"].lower() for n in author_nodes}
        assert "bob jones" in author_names
        # 3 unique authors: Alice Smith, Bob Jones, Charlie Brown
        assert len(author_nodes) == 3

    def test_factor_nodes_created(self):
        result = build_graph_data(SAMPLE_PAPERS, FACTOR_VALUES)
        factor_nodes = [n for n in result["nodes"] if n["type"] == "factor"]
        assert len(factor_nodes) == 3

    def test_authored_edges(self):
        result = build_graph_data(SAMPLE_PAPERS, FACTOR_VALUES)
        authored = [e for e in result["edges"] if e["type"] == "authored"]
        # Paper 1: 2 authors, Paper 2: 2 authors = 4 edges
        assert len(authored) == 4

    def test_no_factor_edges_without_map(self):
        result = build_graph_data(SAMPLE_PAPERS, FACTOR_VALUES, paper_factor_map=None)
        relates = [e for e in result["edges"] if e["type"] == "relates_to"]
        assert len(relates) == 0

    def test_factor_edges_with_map(self):
        result = build_graph_data(SAMPLE_PAPERS, FACTOR_VALUES, PAPER_FACTOR_MAP)
        relates = [e for e in result["edges"] if e["type"] == "relates_to"]
        assert len(relates) == 4  # 2 + 2 from the map

    def test_factor_edge_relevance_preserved(self):
        result = build_graph_data(SAMPLE_PAPERS, FACTOR_VALUES, PAPER_FACTOR_MAP)
        high_edges = [
            e for e in result["edges"]
            if e["type"] == "relates_to" and e.get("relevance") == "high"
        ]
        assert len(high_edges) == 3

    def test_stats_counts(self):
        result = build_graph_data(SAMPLE_PAPERS, FACTOR_VALUES, PAPER_FACTOR_MAP)
        assert result["stats"]["papers"] == 2
        assert result["stats"]["authors"] == 3
        assert result["stats"]["factors"] == 3
        assert result["stats"]["edges"] == 8  # 4 authored + 4 relates_to

    def test_handles_string_authors(self):
        """Paper 2 has semicolon-separated string authors."""
        result = build_graph_data(SAMPLE_PAPERS, FACTOR_VALUES)
        author_nodes = [n for n in result["nodes"] if n["type"] == "author"]
        labels = {n["label"].lower() for n in author_nodes}
        assert "charlie brown" in labels

    def test_author_fuzzy_dedup_initial(self):
        """B. Jones and Bob Jones should merge into one author node."""
        papers = [
            {
                "paper_id": "p1", "title": "Paper 1",
                "authors": [{"name": "Bob Jones"}], "abstract": "x",
            },
            {
                "paper_id": "p2", "title": "Paper 2",
                "authors": [{"name": "B. Jones"}], "abstract": "y",
            },
        ]
        result = build_graph_data(papers, [])
        author_nodes = [n for n in result["nodes"] if n["type"] == "author"]
        assert len(author_nodes) == 1
        # Canonical should be "Bob Jones" (longer)
        assert author_nodes[0]["label"] == "Bob Jones"
        # Both papers should connect to the same author
        authored_edges = [e for e in result["edges"] if e["type"] == "authored"]
        assert len(authored_edges) == 2
        assert authored_edges[0]["from"] == authored_edges[1]["from"]

    def test_factor_fuzzy_dedup_spelling(self):
        """Spelling variants like 'inclusions' vs 'inclusion' should merge."""
        factors = ["financial inclusion", "financial inclusions"]
        result = build_graph_data([], factors)
        factor_nodes = [n for n in result["nodes"] if n["type"] == "factor"]
        assert len(factor_nodes) == 1

    def test_factor_dedup_maps_edges_correctly(self):
        """Edges using a deduplicated factor variant still connect."""
        factors = ["financial inclusion", "financial inclusions"]
        pfm = {"p1": [{"factor_value": "financial inclusions", "relevance": "high"}]}
        papers = [{"paper_id": "p1", "title": "T", "abstract": "a"}]
        result = build_graph_data(papers, factors, pfm)
        relates = [e for e in result["edges"] if e["type"] == "relates_to"]
        assert len(relates) == 1

    def test_empty_papers(self):
        result = build_graph_data([], FACTOR_VALUES)
        assert result["stats"]["papers"] == 0
        assert result["stats"]["authors"] == 0
        assert result["stats"]["factors"] == 3

    def test_empty_factors(self):
        result = build_graph_data(SAMPLE_PAPERS, [])
        assert result["stats"]["factors"] == 0

    def test_paper_node_has_metadata(self):
        result = build_graph_data(SAMPLE_PAPERS, FACTOR_VALUES)
        paper_node = next(n for n in result["nodes"] if n["id"] == "paper_aaa111bbb222")
        assert paper_node["title"] == "Tokenization of Real World Assets"
        assert paper_node["abstract"] == "This paper explores RWA tokenization and its impact."
        assert paper_node["url"] == "https://example.com/paper1"
        assert paper_node["year"] == 2024

    def test_unknown_factor_in_map_ignored(self):
        bad_map = {"aaa111bbb222": [{"factor_value": "nonexistent", "relevance": "high"}]}
        result = build_graph_data(SAMPLE_PAPERS, FACTOR_VALUES, bad_map)
        relates = [e for e in result["edges"] if e["type"] == "relates_to"]
        assert len(relates) == 0


# --- render_html ---


class TestRenderHtml:
    def test_returns_html_string(self):
        graph_data = build_graph_data(SAMPLE_PAPERS, FACTOR_VALUES)
        html = render_html(graph_data)
        assert "<!DOCTYPE html>" in html
        assert "vis-network" in html

    def test_embeds_graph_data(self):
        graph_data = build_graph_data(SAMPLE_PAPERS, FACTOR_VALUES)
        html = render_html(graph_data)
        assert "Tokenization of Real World Assets" in html
        assert "Alice Smith" in html

    def test_placeholder_replaced(self):
        graph_data = build_graph_data(SAMPLE_PAPERS, FACTOR_VALUES)
        html = render_html(graph_data)
        assert "/*__GRAPH_DATA__*/" not in html


# --- save_graph_html ---


class TestSaveGraphHtml:
    def test_saves_file(self, tmp_path):
        (tmp_path / ".litreview").mkdir()
        result = save_graph_html(tmp_path, SAMPLE_PAPERS, FACTOR_VALUES)
        output = Path(result["path"])
        assert output.exists()
        assert output.name == "relation_graph.html"

    def test_returns_stats(self, tmp_path):
        (tmp_path / ".litreview").mkdir()
        result = save_graph_html(tmp_path, SAMPLE_PAPERS, FACTOR_VALUES)
        assert result["stats"]["papers"] == 2
        assert result["stats"]["authors"] == 3

    def test_html_content_valid(self, tmp_path):
        (tmp_path / ".litreview").mkdir()
        result = save_graph_html(tmp_path, SAMPLE_PAPERS, FACTOR_VALUES, PAPER_FACTOR_MAP)
        html = Path(result["path"]).read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in html
        assert "decentralized finance" in html

    def test_creates_parent_dir(self, tmp_path):
        result = save_graph_html(tmp_path, SAMPLE_PAPERS, FACTOR_VALUES)
        assert Path(result["path"]).exists()

    def test_auto_saves_cache(self, tmp_path):
        """save_graph_html with paper_factor_map should persist cache."""
        (tmp_path / ".litreview").mkdir()
        save_graph_html(tmp_path, SAMPLE_PAPERS, FACTOR_VALUES, PAPER_FACTOR_MAP)
        cache = load_cache(tmp_path)
        assert cache["factor_hash"] != ""
        assert "aaa111bbb222" in cache["entries"]


# --- Cache helpers ---


class TestContentHash:
    def test_deterministic(self):
        assert _content_hash("hello") == _content_hash("hello")

    def test_different_inputs_differ(self):
        assert _content_hash("hello") != _content_hash("world")

    def test_returns_12_chars(self):
        assert len(_content_hash("test")) == 12


class TestFactorSetHash:
    def test_deterministic(self):
        assert _factor_set_hash(["a", "b"]) == _factor_set_hash(["a", "b"])

    def test_order_independent(self):
        assert _factor_set_hash(["a", "b"]) == _factor_set_hash(["b", "a"])

    def test_case_insensitive(self):
        assert _factor_set_hash(["DeFi"]) == _factor_set_hash(["defi"])

    def test_different_values_differ(self):
        assert _factor_set_hash(["a"]) != _factor_set_hash(["b"])


# --- load_cache / save_cache ---


class TestCachePersistence:
    def test_load_missing_returns_empty(self, tmp_path):
        cache = load_cache(tmp_path)
        assert cache == {"factor_hash": "", "entries": {}}

    def test_roundtrip(self, tmp_path):
        (tmp_path / ".litreview").mkdir()
        original = {
            "factor_hash": "abc123",
            "entries": {"pid1": {"abstract_hash": "x", "factors": [], "analyzed_at": "t"}},
        }
        save_cache(tmp_path, original)
        loaded = load_cache(tmp_path)
        assert loaded == original

    def test_load_corrupted_returns_empty(self, tmp_path):
        cache_file = tmp_path / ".litreview" / "relation_cache.json"
        cache_file.parent.mkdir(parents=True)
        cache_file.write_text("not json", encoding="utf-8")
        cache = load_cache(tmp_path)
        assert cache == {"factor_hash": "", "entries": {}}


# --- check_cache ---


class TestCheckCache:
    def _make_cache(self, papers, factor_values, paper_factor_map):
        """Helper: build a valid cache from papers + analysis."""
        return update_cache(
            {"factor_hash": "", "entries": {}},
            paper_factor_map, papers, factor_values,
        )

    def test_all_miss_on_empty_cache(self):
        cache = {"factor_hash": "", "entries": {}}
        result = check_cache(SAMPLE_PAPERS, FACTOR_VALUES, cache)
        assert result["cache_hit"] == 0
        assert result["cache_miss"] == 2  # both papers have abstracts

    def test_all_hit_after_cache(self):
        cache = self._make_cache(SAMPLE_PAPERS, FACTOR_VALUES, PAPER_FACTOR_MAP)
        result = check_cache(SAMPLE_PAPERS, FACTOR_VALUES, cache)
        assert result["cache_hit"] == 2
        assert result["cache_miss"] == 0
        assert not result["cache_stale"]

    def test_stale_when_factors_change(self):
        cache = self._make_cache(SAMPLE_PAPERS, FACTOR_VALUES, PAPER_FACTOR_MAP)
        new_factors = ["completely new factor"]
        result = check_cache(SAMPLE_PAPERS, new_factors, cache)
        assert result["cache_stale"]
        assert result["cache_miss"] == 2  # all need re-analysis

    def test_miss_on_abstract_change(self):
        cache = self._make_cache(SAMPLE_PAPERS, FACTOR_VALUES, PAPER_FACTOR_MAP)
        modified_papers = [
            {**SAMPLE_PAPERS[0], "abstract": "Completely rewritten abstract."},
            SAMPLE_PAPERS[1],
        ]
        result = check_cache(modified_papers, FACTOR_VALUES, cache)
        assert result["cache_hit"] == 1  # paper 2 still cached
        assert result["cache_miss"] == 1  # paper 1 changed

    def test_skips_papers_without_abstract(self):
        papers = [{**SAMPLE_PAPERS[0], "abstract": ""}, SAMPLE_PAPERS[1]]
        cache = {"factor_hash": "", "entries": {}}
        result = check_cache(papers, FACTOR_VALUES, cache)
        assert result["cache_miss"] == 1  # only paper 2 has abstract

    def test_cached_map_contains_factors(self):
        cache = self._make_cache(SAMPLE_PAPERS, FACTOR_VALUES, PAPER_FACTOR_MAP)
        result = check_cache(SAMPLE_PAPERS, FACTOR_VALUES, cache)
        assert "aaa111bbb222" in result["cached_map"]
        assert len(result["cached_map"]["aaa111bbb222"]) == 2

    def test_incremental_new_paper(self):
        """Adding a new paper should only miss the new one."""
        cache = self._make_cache(SAMPLE_PAPERS, FACTOR_VALUES, PAPER_FACTOR_MAP)
        new_paper = {
            "paper_id": "eee555fff666",
            "title": "New Paper",
            "abstract": "Brand new research on blockchain.",
        }
        result = check_cache(SAMPLE_PAPERS + [new_paper], FACTOR_VALUES, cache)
        assert result["cache_hit"] == 2
        assert result["cache_miss"] == 1
        assert result["uncached_papers"][0]["paper_id"] == "eee555fff666"


# --- update_cache ---


class TestUpdateCache:
    def test_creates_entries(self):
        cache = {"factor_hash": "", "entries": {}}
        updated = update_cache(cache, PAPER_FACTOR_MAP, SAMPLE_PAPERS, FACTOR_VALUES)
        assert "aaa111bbb222" in updated["entries"]
        assert "ccc333ddd444" in updated["entries"]
        assert updated["factor_hash"] == _factor_set_hash(FACTOR_VALUES)

    def test_preserves_existing_entries(self):
        cache = update_cache(
            {"factor_hash": "", "entries": {}},
            {"aaa111bbb222": [{"factor_value": "x", "relevance": "high"}]},
            SAMPLE_PAPERS, FACTOR_VALUES,
        )
        # Now add only paper 2
        updated = update_cache(
            cache,
            {"ccc333ddd444": [{"factor_value": "y", "relevance": "low"}]},
            SAMPLE_PAPERS, FACTOR_VALUES,
        )
        assert "aaa111bbb222" in updated["entries"]
        assert "ccc333ddd444" in updated["entries"]

    def test_clears_on_factor_change(self):
        cache = update_cache(
            {"factor_hash": "", "entries": {}},
            PAPER_FACTOR_MAP, SAMPLE_PAPERS, FACTOR_VALUES,
        )
        new_factors = ["totally different factor"]
        updated = update_cache(
            cache,
            {"aaa111bbb222": [{"factor_value": "new", "relevance": "high"}]},
            SAMPLE_PAPERS, new_factors,
        )
        # Old entries cleared, only the newly provided one remains
        assert "ccc333ddd444" not in updated["entries"]
        assert "aaa111bbb222" in updated["entries"]

    def test_entry_has_abstract_hash(self):
        cache = {"factor_hash": "", "entries": {}}
        updated = update_cache(cache, PAPER_FACTOR_MAP, SAMPLE_PAPERS, FACTOR_VALUES)
        entry = updated["entries"]["aaa111bbb222"]
        expected_hash = _content_hash(SAMPLE_PAPERS[0]["abstract"])
        assert entry["abstract_hash"] == expected_hash

    def test_entry_has_analyzed_at(self):
        cache = {"factor_hash": "", "entries": {}}
        updated = update_cache(cache, PAPER_FACTOR_MAP, SAMPLE_PAPERS, FACTOR_VALUES)
        assert "analyzed_at" in updated["entries"]["aaa111bbb222"]

    def test_immutable_original_cache(self):
        cache = {"factor_hash": "", "entries": {"old": {"x": 1}}}
        update_cache(cache, PAPER_FACTOR_MAP, SAMPLE_PAPERS, FACTOR_VALUES)
        assert "aaa111bbb222" not in cache["entries"]  # original unchanged

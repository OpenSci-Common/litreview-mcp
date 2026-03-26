"""Tests for litreview.utils module (TDD)."""

from __future__ import annotations

import hashlib
import re

import pytest

from litreview.utils import generate_id, generate_paper_id, normalize_authors, normalize_title


class TestNormalizeTitle:
    def test_lowercase(self):
        assert normalize_title("Attention Is All You Need") == "attention is all you need"

    def test_removes_punctuation(self):
        assert normalize_title("Hello, World!") == "hello world"

    def test_collapses_whitespace(self):
        assert normalize_title("too   many   spaces") == "too many spaces"

    def test_strips_leading_trailing(self):
        assert normalize_title("  padded  ") == "padded"

    def test_combined(self):
        result = normalize_title("  Attention Is All You Need: A Survey (2017)  ")
        assert result == "attention is all you need a survey 2017"

    def test_empty_string(self):
        assert normalize_title("") == ""

    def test_only_punctuation(self):
        assert normalize_title("!!!???") == ""

    def test_unicode_letters_kept(self):
        result = normalize_title("Résumé: über-cool")
        # punctuation removed, lowercase, whitespace collapsed
        assert "résumé" in result
        assert "cool" in result


class TestNormalizeAuthors:
    def test_none_returns_empty(self):
        assert normalize_authors(None) == []

    def test_empty_string_returns_empty(self):
        assert normalize_authors("") == []

    def test_empty_list_returns_empty(self):
        assert normalize_authors([]) == []

    def test_semicolon_separated_string(self):
        result = normalize_authors("Alice; Bob; Charlie")
        assert result == [{"name": "Alice"}, {"name": "Bob"}, {"name": "Charlie"}]

    def test_semicolon_string_strips_whitespace(self):
        result = normalize_authors("  Alice ;  Bob  ")
        assert result == [{"name": "Alice"}, {"name": "Bob"}]

    def test_semicolon_string_skips_empty_segments(self):
        result = normalize_authors("Alice;; ;Bob")
        assert result == [{"name": "Alice"}, {"name": "Bob"}]

    def test_list_of_strings(self):
        result = normalize_authors(["Alice", "Bob"])
        assert result == [{"name": "Alice"}, {"name": "Bob"}]

    def test_list_of_dicts_passthrough(self):
        original = [{"name": "Alice", "hIndex": 42}, {"name": "Bob"}]
        result = normalize_authors(original)
        assert result == original

    def test_mixed_list(self):
        result = normalize_authors(["Alice", {"name": "Bob"}, 123])
        assert result == [{"name": "Alice"}, {"name": "Bob"}, {"name": "123"}]

    def test_single_author_string(self):
        result = normalize_authors("Solo Author")
        assert result == [{"name": "Solo Author"}]

    def test_non_list_non_str_returns_empty(self):
        assert normalize_authors(42) == []


class TestGeneratePaperId:
    def test_doi_priority(self):
        pid = generate_paper_id(doi="10.1000/xyz123")
        expected_input = "doi:10.1000/xyz123"
        expected = hashlib.sha256(expected_input.encode()).hexdigest()[:12]
        assert pid == expected

    def test_arxiv_priority_over_title(self):
        pid = generate_paper_id(arxiv_id="1706.03762", title="Some Title", year=2017, first_author="Smith")
        expected_input = "arxiv:1706.03762"
        expected = hashlib.sha256(expected_input.encode()).hexdigest()[:12]
        assert pid == expected

    def test_doi_priority_over_arxiv(self):
        pid_doi = generate_paper_id(doi="10.1000/xyz", arxiv_id="1234.5678")
        expected_input = "doi:10.1000/xyz"
        expected = hashlib.sha256(expected_input.encode()).hexdigest()[:12]
        assert pid_doi == expected

    def test_title_year_author_fallback(self):
        pid = generate_paper_id(title="Attention Is All You Need", year=2017, first_author="Vaswani")
        norm_title = "attention is all you need"
        expected_input = f"title:{norm_title}|year:2017|author:vaswani"
        expected = hashlib.sha256(expected_input.encode()).hexdigest()[:12]
        assert pid == expected

    def test_title_only_fallback(self):
        pid = generate_paper_id(title="Some Paper")
        norm_title = "some paper"
        expected_input = f"title:{norm_title}|year:None|author:None"
        expected = hashlib.sha256(expected_input.encode()).hexdigest()[:12]
        assert pid == expected

    def test_returns_12_hex_chars(self):
        pid = generate_paper_id(doi="10.1/test")
        assert len(pid) == 12
        assert re.fullmatch(r"[0-9a-f]{12}", pid)

    def test_no_args_raises(self):
        with pytest.raises(ValueError):
            generate_paper_id()

    def test_deterministic(self):
        pid1 = generate_paper_id(doi="10.1000/abc")
        pid2 = generate_paper_id(doi="10.1000/abc")
        assert pid1 == pid2


class TestGenerateId:
    def test_format(self):
        gid = generate_id("sf")
        assert re.fullmatch(r"sf_[0-9a-f]{7}", gid)

    def test_prefix_preserved(self):
        gid = generate_id("session")
        assert gid.startswith("session_")

    def test_hex_suffix_length(self):
        gid = generate_id("cf")
        suffix = gid.split("_", 1)[1]
        assert len(suffix) == 7
        assert re.fullmatch(r"[0-9a-f]{7}", suffix)

    def test_randomness(self):
        ids = {generate_id("x") for _ in range(20)}
        # Very unlikely to get duplicates with random 7-hex-char suffix
        assert len(ids) > 1

    def test_empty_prefix(self):
        gid = generate_id("")
        assert gid.startswith("_")
        assert len(gid) == 8  # "_" + 7 hex chars

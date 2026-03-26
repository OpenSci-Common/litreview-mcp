"""Deduplication engine for litreview-mcp.

Four-level matching (by priority):
1. DOI exact match (case-insensitive)
2. External ID match (s2_paper_id, openalex_id, arxiv_id)
3. Title + year normalized match
4. Fuzzy title match (rapidfuzz ratio >= 90, same first author, year ±1)
"""

from __future__ import annotations

from typing import Any

from rapidfuzz.fuzz import ratio

from litreview.utils import normalize_title

# External ID keys to check for level-2 matching (in priority order)
_EXTERNAL_ID_KEYS = ("s2_paper_id", "openalex_id", "arxiv")


def _get_doi(paper: dict) -> str | None:
    """Return normalised (lowercase) DOI, or None."""
    doi = paper.get("external_ids", {}).get("doi")
    return doi.lower().strip() if doi else None


def _get_first_author_lower(paper: dict) -> str | None:
    authors = paper.get("authors", [])
    if authors:
        name = authors[0].get("name", "")
        return name.lower().strip() if name else None
    return None


def _build_index(papers: list[dict]) -> dict[str, Any]:
    """Build lookup indexes from a list of paper dicts."""
    doi_index: dict[str, dict] = {}         # doi -> paper
    ext_index: dict[tuple, dict] = {}       # (key, value) -> paper
    title_year_index: dict[tuple, dict] = {}  # (norm_title, year) -> paper

    for p in papers:
        doi = _get_doi(p)
        if doi:
            doi_index[doi] = p

        ext_ids = p.get("external_ids", {})
        for key in _EXTERNAL_ID_KEYS:
            val = ext_ids.get(key)
            if val:
                ext_index[(key, val)] = p

        title = p.get("title")
        year = p.get("year")
        if title and year is not None:
            norm = normalize_title(title)
            title_year_index[(norm, year)] = p

    return {
        "doi": doi_index,
        "ext": ext_index,
        "title_year": title_year_index,
        "papers": papers,
    }


def _find_match(candidate: dict, index: dict) -> tuple[dict | None, str | None]:
    """Return (matched_paper, match_type) or (None, None) if no match found."""

    # Level 1: DOI
    doi = _get_doi(candidate)
    if doi and doi in index["doi"]:
        return index["doi"][doi], "doi"

    # Level 2: External IDs
    ext_ids = candidate.get("external_ids", {})
    for key in _EXTERNAL_ID_KEYS:
        val = ext_ids.get(key)
        if val and (key, val) in index["ext"]:
            return index["ext"][(key, val)], "external_id"

    # Level 3: Title + year
    title = candidate.get("title")
    year = candidate.get("year")
    if title and year is not None:
        norm = normalize_title(title)
        if (norm, year) in index["title_year"]:
            return index["title_year"][(norm, year)], "title_year"

    # Level 4: Fuzzy title (ratio >= 90, same first author, year ±1)
    if title and year is not None:
        norm_cand = normalize_title(title)
        first_author_cand = _get_first_author_lower(candidate)
        for existing in index["papers"]:
            existing_title = existing.get("title")
            existing_year = existing.get("year")
            if not existing_title or existing_year is None:
                continue
            if abs(existing_year - year) > 1:
                continue
            first_author_existing = _get_first_author_lower(existing)
            # Both must have a first author and they must match
            if (
                first_author_cand
                and first_author_existing
                and first_author_cand != first_author_existing
            ):
                continue
            # If either has no first author, skip fuzzy (can't confirm)
            if not first_author_cand or not first_author_existing:
                continue
            norm_existing = normalize_title(existing_title)
            score = ratio(norm_cand, norm_existing)
            if score >= 90:
                return existing, "fuzzy_title"

    return None, None


def dedup_papers(candidates: list[dict], existing: list[dict]) -> dict:
    """Deduplicate a list of candidate papers against each other and an existing library.

    Args:
        candidates: List of paper dicts to check for duplicates.
        existing: List of already-known paper dicts (library).

    Returns:
        {
            "unique": [...],        # candidates not found to be duplicates
            "duplicates": [         # candidates that matched something
                {
                    "paper": <candidate>,
                    "matched_with": <matched paper>,
                    "match_type": "doi" | "external_id" | "title_year" | "fuzzy_title"
                },
                ...
            ]
        }
    """
    unique: list[dict] = []
    duplicates: list[dict] = []

    # Start by building index from existing library
    # We'll grow it incrementally as we accept new unique candidates
    index = _build_index(list(existing))

    for candidate in candidates:
        matched, match_type = _find_match(candidate, index)

        if matched is not None:
            duplicates.append(
                {
                    "paper": candidate,
                    "matched_with": matched,
                    "match_type": match_type,
                }
            )
        else:
            unique.append(candidate)
            # Add this newly accepted paper into the index so subsequent
            # candidates can be matched against it too.
            _add_to_index(index, candidate)

    return {"unique": unique, "duplicates": duplicates}


def _add_to_index(index: dict, paper: dict) -> None:
    """Add a single paper to an existing index (in-place)."""
    doi = _get_doi(paper)
    if doi:
        index["doi"][doi] = paper

    ext_ids = paper.get("external_ids", {})
    for key in _EXTERNAL_ID_KEYS:
        val = ext_ids.get(key)
        if val:
            index["ext"][(key, val)] = paper

    title = paper.get("title")
    year = paper.get("year")
    if title and year is not None:
        norm = normalize_title(title)
        index["title_year"][(norm, year)] = paper

    index["papers"].append(paper)

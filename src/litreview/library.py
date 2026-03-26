"""Literature library management for litreview-mcp.

Uses TinyDB stored at <base_path>/.litreview/literature.json.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, List, Optional

from tinydb import Query, TinyDB

from litreview.models import Paper
from litreview.utils import generate_paper_id, normalize_authors, safe_get_author_name


def _get_db(base_path) -> TinyDB:
    """Return a TinyDB instance for the literature store."""
    lit_file = Path(base_path) / ".litreview" / "literature.json"
    lit_file.parent.mkdir(parents=True, exist_ok=True)
    return TinyDB(str(lit_file))


def _make_paper_id(paper_data: dict) -> str:
    """Derive a stable paper_id from the paper data dict."""
    ext = paper_data.get("external_ids", {})
    doi = ext.get("doi")
    arxiv_id = ext.get("arxiv") or ext.get("arxiv_id")
    title = paper_data.get("title")
    year = paper_data.get("year")
    authors = paper_data.get("authors", [])
    first_author = safe_get_author_name(authors[0]) if authors else None
    return generate_paper_id(
        doi=doi,
        arxiv_id=arxiv_id,
        title=title,
        year=year,
        first_author=first_author,
    )


def add_paper(base_path, paper_data: dict) -> dict:
    """Add a single paper to the library.

    If the paper already exists (by paper_id), returns the existing record
    with ``"duplicate": True`` appended.

    Args:
        base_path: Path to the workspace root (parent of .litreview/).
        paper_data: Dict of paper fields. Must include at least a title
            or one of doi/arxiv external_ids.

    Returns:
        The stored paper dict (or existing paper dict with duplicate=True).
    """
    paper_id = paper_data.get("paper_id") or _make_paper_id(paper_data)

    with _get_db(base_path) as db:
        PaperQ = Query()
        existing = db.search(PaperQ.paper_id == paper_id)
        if existing:
            return {**existing[0], "duplicate": True}

        # Build a Paper dataclass to enforce defaults, then merge all extra fields
        known_fields = {k: v for k, v in paper_data.items() if k in Paper.__dataclass_fields__}
        known_fields["paper_id"] = paper_id
        # Normalize authors to List[Dict] before persisting
        known_fields["authors"] = normalize_authors(known_fields.get("authors"))
        # Default to candidate status (user must explicitly promote to in_library)
        if "status" not in known_fields:
            known_fields["status"] = "candidate"
        paper = Paper(**known_fields)
        record = paper.to_dict()
        # Preserve extra fields from search API that aren't in the dataclass
        for k, v in paper_data.items():
            if k not in record and k != "paper_id":
                record[k] = v
        db.insert(record)

    return record


def add_papers_batch(base_path, papers: list[dict]) -> dict:
    """Add multiple papers to the library.

    Args:
        base_path: Path to the workspace root.
        papers: List of paper data dicts.

    Returns:
        {"added": int, "duplicates": int, "papers": [<result dicts>]}
    """
    added = 0
    duplicates = 0
    results = []

    for paper_data in papers:
        result = add_paper(base_path, paper_data)
        results.append(result)
        if result.get("duplicate"):
            duplicates += 1
        else:
            added += 1

    return {"added": added, "duplicates": duplicates, "papers": results}


def accept_paper(base_path, paper_id: str) -> dict:
    """Promote a candidate paper to in_library status.

    Args:
        base_path: Path to the workspace root.
        paper_id: The 12-char paper ID.

    Returns:
        Updated paper dict.

    Raises:
        KeyError: If no paper with that ID exists.
    """
    with _get_db(base_path) as db:
        PaperQ = Query()
        existing = db.search(PaperQ.paper_id == paper_id)
        if not existing:
            raise KeyError(f"Paper not found: {paper_id!r}")
        db.update({"status": "in_library"}, PaperQ.paper_id == paper_id)
        updated = db.search(PaperQ.paper_id == paper_id)
    return updated[0]


def accept_papers_batch(base_path, paper_ids: list[str]) -> dict:
    """Promote multiple candidate papers to in_library."""
    accepted = 0
    for pid in paper_ids:
        try:
            accept_paper(base_path, pid)
            accepted += 1
        except KeyError:
            pass
    return {"accepted": accepted, "total_requested": len(paper_ids)}


def exclude_paper(base_path, paper_id: str) -> dict:
    """Set the status of a paper to 'excluded'.

    Args:
        base_path: Path to the workspace root.
        paper_id: The 12-char paper ID.

    Returns:
        Updated paper dict.

    Raises:
        KeyError: If no paper with that ID exists.
    """
    with _get_db(base_path) as db:
        PaperQ = Query()
        existing = db.search(PaperQ.paper_id == paper_id)
        if not existing:
            raise KeyError(f"Paper not found: {paper_id!r}")
        db.update({"status": "excluded"}, PaperQ.paper_id == paper_id)
        updated = db.search(PaperQ.paper_id == paper_id)

    return updated[0]


def list_papers(
    base_path,
    status: Optional[str] = None,
    sort_by: Optional[str] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
) -> list[dict]:
    """List papers in the library with optional filtering and sorting.

    Args:
        base_path: Path to the workspace root.
        status: Filter by paper status (e.g. "candidate", "excluded").
        sort_by: Field name to sort by. Prefix "-" means ascending order;
            no prefix uses the default (ascending) sort.
        limit: Maximum number of results to return.
        offset: Number of results to skip.

    Returns:
        List of paper dicts.
    """
    with _get_db(base_path) as db:
        if status is not None:
            PaperQ = Query()
            results = db.search(PaperQ.status == status)
        else:
            results = db.all()

    # Sorting
    if sort_by:
        # Strip leading "-" for field name; "-field" means ascending
        if sort_by.startswith("-"):
            field_name = sort_by[1:]
            reverse = False  # ascending
        else:
            field_name = sort_by
            reverse = False  # default ascending

        results = sorted(
            results,
            key=lambda p: (p.get(field_name) is None, p.get(field_name)),
            reverse=reverse,
        )

    # Offset
    if offset:
        results = results[offset:]

    # Limit
    if limit is not None:
        results = results[:limit]

    return results


def paper_detail(base_path, paper_id: str) -> dict:
    """Retrieve a single paper by paper_id.

    Args:
        base_path: Path to the workspace root.
        paper_id: The 12-char paper ID.

    Returns:
        Paper dict.

    Raises:
        KeyError: If no paper with that ID exists.
    """
    with _get_db(base_path) as db:
        PaperQ = Query()
        results = db.search(PaperQ.paper_id == paper_id)

    if not results:
        raise KeyError(f"Paper not found: {paper_id!r}")
    return results[0]


def paper_stats(base_path) -> dict:
    """Return summary statistics for the library.

    Args:
        base_path: Path to the workspace root.

    Returns:
        {
            "total": int,
            "in_library": int,   # status == "included" or "candidate"
            "excluded": int,
            ...one key per distinct status value...
        }
    """
    with _get_db(base_path) as db:
        all_papers = db.all()

    total = len(all_papers)
    excluded = sum(1 for p in all_papers if p.get("status") == "excluded")
    included = sum(1 for p in all_papers if p.get("status") == "included")
    candidate = sum(1 for p in all_papers if p.get("status") == "candidate")
    pending = sum(1 for p in all_papers if p.get("status") == "pending")

    return {
        "total": total,
        "in_library": included + candidate,
        "excluded": excluded,
        "included": included,
        "candidate": candidate,
        "pending": pending,
    }

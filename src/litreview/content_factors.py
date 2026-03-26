"""Content factor library management for litreview-mcp (Task 10)."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from tinydb import Query, TinyDB

from litreview.factors import add_factor
from litreview.models import ContentFactor
from litreview.utils import generate_id


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cf_db(base_path: Path) -> TinyDB:
    return TinyDB(str(base_path / ".litreview" / "content_factors.json"))


# ---------------------------------------------------------------------------
# extract_content_factors
# ---------------------------------------------------------------------------

def extract_content_factors(base_path: Any, paper: dict) -> dict:
    """Extract content factors from paper metadata and persist them.

    Extracts authors (with first_author / co_author roles), venue, and
    fields_of_study.

    Args:
        base_path: Workspace root path.
        paper: Paper metadata dict (at minimum has ``paper_id``).

    Returns:
        Dict with keys:
        - ``paper_id``: str
        - ``extracted_count``: int
        - ``factors``: list of ContentFactor dicts
    """
    base_path = Path(base_path)
    paper_id: str = paper["paper_id"]
    now = _now_iso()
    factors: List[ContentFactor] = []

    # --- Authors ---
    authors: list = paper.get("authors") or []
    for idx, author in enumerate(authors):
        # Support both string and dict author formats
        if isinstance(author, str):
            name = author
            api_ids: Dict[str, str] = {}
        elif isinstance(author, dict):
            name = author.get("name", "") or author.get("authorName", "")
            api_ids = {}
            raw_id = author.get("authorId")
            if raw_id:
                api_ids["s2_author_id"] = str(raw_id)
        else:
            continue
        if not name:
            continue
        role = "first_author" if idx == 0 else "co_author"
        factors.append(
            ContentFactor(
                id=generate_id("cf"),
                paper_id=paper_id,
                type="author",
                value=name,
                api_ids=api_ids,
                role=role,
                promoted=False,
                auto_extracted_at=now,
            )
        )

    # --- Venue ---
    venue = paper.get("venue")
    if venue:
        factors.append(
            ContentFactor(
                id=generate_id("cf"),
                paper_id=paper_id,
                type="venue",
                value=venue,
                api_ids={},
                role="descriptor",
                promoted=False,
                auto_extracted_at=now,
            )
        )

    # --- Fields of study ---
    fields: List[str] = paper.get("fields_of_study") or []
    for field_name in fields:
        if not field_name:
            continue
        factors.append(
            ContentFactor(
                id=generate_id("cf"),
                paper_id=paper_id,
                type="field",
                value=field_name,
                api_ids={},
                role="descriptor",
                promoted=False,
                auto_extracted_at=now,
            )
        )

    # Persist to TinyDB
    db = _cf_db(base_path)
    try:
        records = [cf.to_dict() for cf in factors]
        for record in records:
            db.insert(record)
    finally:
        db.close()

    return {
        "paper_id": paper_id,
        "extracted_count": len(factors),
        "factors": [cf.to_dict() for cf in factors],
    }


# ---------------------------------------------------------------------------
# query_content_factors
# ---------------------------------------------------------------------------

def query_content_factors(
    base_path: Any,
    type: Optional[str] = None,
    paper_id: Optional[str] = None,
    aggregate: Optional[str] = None,
    min_count: Optional[int] = None,
) -> List[dict]:
    """Query content factors from the workspace.

    Args:
        base_path: Workspace root path.
        type: Filter by factor type (e.g. ``"author"``).
        paper_id: Filter by paper_id.
        aggregate: If ``"count"``, group by value and return counts.
        min_count: When aggregating, exclude entries with count < min_count.

    Returns:
        List of dicts. Plain records when not aggregating; aggregated
        ``[{"value": ..., "count": ..., "type": ...}]`` when
        ``aggregate="count"``.
    """
    base_path = Path(base_path)
    db = _cf_db(base_path)
    try:
        F = Query()
        cond = None

        if type is not None:
            type_cond = F.type == type
            cond = type_cond if cond is None else (cond & type_cond)

        if paper_id is not None:
            pid_cond = F.paper_id == paper_id
            cond = pid_cond if cond is None else (cond & pid_cond)

        records = db.search(cond) if cond is not None else db.all()
    finally:
        db.close()

    if aggregate == "count":
        # Group by (type, value)
        counter: Dict[tuple, int] = defaultdict(int)
        type_map: Dict[tuple, str] = {}
        for rec in records:
            key = (rec.get("type", ""), rec.get("value", ""))
            counter[key] += 1
            type_map[key] = rec.get("type", "")

        aggregated = [
            {"value": k[1], "count": v, "type": type_map[k]}
            for k, v in counter.items()
        ]

        # Apply min_count filter
        if min_count is not None:
            aggregated = [item for item in aggregated if item["count"] >= min_count]

        # Sort descending by count
        aggregated.sort(key=lambda x: x["count"], reverse=True)
        return aggregated

    return records


# ---------------------------------------------------------------------------
# promote_content_factor
# ---------------------------------------------------------------------------

def promote_content_factor(base_path: Any, type: str, value: str) -> dict:
    """Promote matching content factors to a search factor.

    1. Finds all ContentFactor records matching ``type`` + ``value``.
    2. Marks them all as ``promoted=True`` in TinyDB.
    3. Collects and merges ``api_ids`` from all matches.
    4. Calls ``factors.add_factor`` with
       ``provenance="promoted_from_content"`` and
       ``promoted_from="<type>:<value>"``.

    Args:
        base_path: Workspace root path.
        type: ContentFactor type (e.g. ``"author"``).
        value: ContentFactor value string.

    Returns:
        Dict with keys:
        - ``factor``: the new (or existing duplicate) SearchFactor dict
        - ``content_factors_marked``: int — number of ContentFactors updated
    """
    base_path = Path(base_path)

    # Find matching content factors
    db = _cf_db(base_path)
    try:
        F = Query()
        matches = db.search((F.type == type) & (F.value == value))

        # Mark all as promoted
        db.update({"promoted": True}, (F.type == type) & (F.value == value))
        marked_count = len(matches)
    finally:
        db.close()

    # Merge api_ids from all matching records
    merged_api_ids: Dict[str, str] = {}
    for rec in matches:
        for k, v in (rec.get("api_ids") or {}).items():
            if k not in merged_api_ids:
                merged_api_ids[k] = v

    # Create search factor
    factor = add_factor(
        base_path,
        type=type,
        value=value,
        query_role="should",
        api_ids=merged_api_ids if merged_api_ids else None,
        provenance="promoted_from_content",
        promoted_from=f"{type}:{value}",
    )

    return {
        "factor": factor,
        "content_factors_marked": marked_count,
    }

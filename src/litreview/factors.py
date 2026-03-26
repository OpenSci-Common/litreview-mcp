"""Search factor library management for litreview-mcp (Task 5)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from tinydb import Query, TinyDB

from litreview.models import SearchFactor
from litreview.utils import generate_id

# ---------------------------------------------------------------------------
# API support map
# Both S2 and OpenAlex
_BOTH_APIS = ["semantic_scholar", "openalex"]
# OpenAlex only
_OA_ONLY = ["openalex"]

_API_SUPPORT_MAP: Dict[str, List[str]] = {
    "query": _BOTH_APIS,
    "author": _BOTH_APIS,
    "venue": _BOTH_APIS,
    "seed_paper": _BOTH_APIS,
    "field": _BOTH_APIS,
    "pub_type": _BOTH_APIS,
    "year_range": _BOTH_APIS,
    "open_access": _BOTH_APIS,
    "citation_min": _BOTH_APIS,
    "keyword": _BOTH_APIS,
    "concept": _BOTH_APIS,
    # OpenAlex only
    "institution": _OA_ONLY,
    "funder": _OA_ONLY,
    "language": _OA_ONLY,
}


def _sf_db(base_path: Path) -> TinyDB:
    return TinyDB(str(base_path / ".litreview" / "search_factors.json"))


def add_factor(
    base_path: Any,
    type: str,
    value: str,
    query_role: str,
    sub_type: Optional[str] = None,
    api_ids: Optional[Dict[str, str]] = None,
    provenance: Optional[str] = None,
    promoted_from: Optional[str] = None,
    created_by: Optional[str] = None,
) -> dict:
    """Add a search factor to the workspace factor library.

    Checks for duplicates (same ``type`` + ``value``). If a duplicate is found
    the existing record is returned with an extra ``"duplicate": True`` flag.

    Returns:
        The stored SearchFactor as a dict (plus ``"duplicate": True`` if
        already present).
    """
    base_path = Path(base_path)
    db = _sf_db(base_path)
    try:
        F = Query()
        existing = db.search((F.type == type) & (F.value == value))
        if existing:
            record = existing[0]
            record["duplicate"] = True
            return record

        factor = SearchFactor(
            id=generate_id("sf"),
            type=type,
            value=value,
            query_role=query_role,
            sub_type=sub_type,
            api_ids=api_ids or {},
            api_support=list(_API_SUPPORT_MAP.get(type, _BOTH_APIS)),
            provenance=provenance,
            promoted_from=promoted_from,
            created_by=created_by,
        )
        record = factor.to_dict()
        db.insert(record)
        return record
    finally:
        db.close()


def list_factors(
    base_path: Any,
    type: Optional[str] = None,
    active_only: Optional[bool] = None,
) -> List[dict]:
    """List search factors, with optional filtering.

    Args:
        base_path: Workspace root path.
        type: Filter by factor type (e.g. ``"keyword"``).
        active_only: If ``True``, only return active factors.
                     If ``False`` or ``None``, return all.

    Returns:
        List of SearchFactor dicts.
    """
    base_path = Path(base_path)
    db = _sf_db(base_path)
    try:
        F = Query()
        cond = None

        if type is not None:
            cond = F.type == type

        if active_only:
            active_cond = F.active == True  # noqa: E712
            cond = active_cond if cond is None else (cond & active_cond)

        if cond is not None:
            return db.search(cond)
        return db.all()
    finally:
        db.close()


def toggle_factor(base_path: Any, factor_id: str, active: bool) -> dict:
    """Set the ``active`` field of a factor.

    Args:
        base_path: Workspace root path.
        factor_id: The factor ``id`` string.
        active: New active state.

    Returns:
        The updated factor dict.

    Raises:
        KeyError: If *factor_id* is not found.
    """
    base_path = Path(base_path)
    db = _sf_db(base_path)
    try:
        F = Query()
        records = db.search(F.id == factor_id)
        if not records:
            raise KeyError(f"Factor not found: {factor_id!r}")
        db.update({"active": active}, F.id == factor_id)
        updated = db.search(F.id == factor_id)[0]
        return updated
    finally:
        db.close()


def remove_factor(base_path: Any, factor_id: str) -> dict:
    """Remove a factor from the library.

    Args:
        base_path: Workspace root path.
        factor_id: The factor ``id`` string.

    Returns:
        The removed factor dict.

    Raises:
        KeyError: If *factor_id* is not found.
    """
    base_path = Path(base_path)
    db = _sf_db(base_path)
    try:
        F = Query()
        records = db.search(F.id == factor_id)
        if not records:
            raise KeyError(f"Factor not found: {factor_id!r}")
        record = records[0]
        db.remove(F.id == factor_id)
        return record
    finally:
        db.close()


def compose_query(
    base_path: Any,
    api_sources: Optional[List[str]] = None,
) -> dict:
    """Compose a search query from active factors.

    Separates factors into *primary* (must/should/primary query_role) and
    *filter* groups. If ``api_sources`` is given, only factors supported by
    at least one of those APIs are included.

    Returns:
        Dict with keys:
        - ``primary_queries``: list of primary query strings
        - ``filters``: dict mapping filter type -> list of values
        - ``combined_query``: space-joined primary query string
        - ``factor_ids``: list of included factor ids
        - ``factor_roles``: dict mapping factor_id -> query_role
    """
    base_path = Path(base_path)
    active_factors = list_factors(base_path, active_only=True)

    # Filter by api_sources if provided
    if api_sources:
        active_factors = [
            f for f in active_factors
            if any(api in f.get("api_support", []) for api in api_sources)
        ]

    primary_queries: List[str] = []
    filters: Dict[str, List[str]] = {}
    factor_ids: List[str] = []
    factor_roles: Dict[str, str] = {}

    _primary_roles = {"must", "should", "primary"}

    for factor in active_factors:
        fid = factor["id"]
        role = factor.get("query_role", "must")
        factor_ids.append(fid)
        factor_roles[fid] = role

        if role in _primary_roles:
            primary_queries.append(factor["value"])
        else:
            # treat as a filter keyed by type
            ftype = factor["type"]
            if ftype not in filters:
                filters[ftype] = []
            filters[ftype].append(factor["value"])

    combined_query = " ".join(primary_queries)

    return {
        "primary_queries": primary_queries,
        "filters": filters,
        "combined_query": combined_query,
        "factor_ids": factor_ids,
        "factor_roles": factor_roles,
    }

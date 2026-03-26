"""Search session management for litreview-mcp (Task 9)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from tinydb import TinyDB

from litreview.models import SearchSession
from litreview.utils import generate_id


def _sessions_db_path(base_path: Any) -> Path:
    return Path(base_path) / ".litreview" / "sessions.json"


def save_session(
    base_path: Any,
    input_factors: List[str],
    factor_roles: Dict[str, str],
    api_queries: Dict[str, Any],
    results_total: int,
    results_after_dedup: int,
    results_already_in_library: int,
    results_new: int,
    result_paper_ids: List[str],
    user_decisions: Dict[str, str],
) -> dict:
    """Create and persist a new SearchSession.

    Args:
        base_path: Workspace root path.
        input_factors: List of SearchFactor ids used.
        factor_roles: Mapping of factor_id -> role.
        api_queries: Mapping of api_name -> query params.
        results_total: Total results before dedup.
        results_after_dedup: Results after deduplication.
        results_already_in_library: Papers already in the library.
        results_new: New papers discovered.
        result_paper_ids: List of paper ids in results.
        user_decisions: Mapping of paper_id -> decision.

    Returns:
        The saved session as a dict.
    """
    workspace_id = str(Path(base_path).resolve())
    session_id = generate_id("sess")

    session = SearchSession(
        session_id=session_id,
        workspace_id=workspace_id,
        input_factors=input_factors,
        factor_roles=factor_roles,
        api_queries=api_queries,
        results_total=results_total,
        results_after_dedup=results_after_dedup,
        results_already_in_library=results_already_in_library,
        results_new=results_new,
        result_paper_ids=result_paper_ids,
        user_decisions=user_decisions,
    )

    db_path = _sessions_db_path(base_path)
    db = TinyDB(str(db_path))
    try:
        session_dict = session.to_dict()
        db.insert(session_dict)
    finally:
        db.close()

    return session_dict


def list_sessions(base_path: Any, limit: Optional[int] = None) -> List[dict]:
    """Return all sessions sorted by created_at descending.

    Args:
        base_path: Workspace root path.
        limit: Optional maximum number of sessions to return.

    Returns:
        List of session dicts sorted by ``created_at`` descending.
    """
    db_path = _sessions_db_path(base_path)
    db = TinyDB(str(db_path))
    try:
        sessions = db.all()
    finally:
        db.close()

    # Strip TinyDB internal doc_id wrapper if present
    sessions = [dict(s) for s in sessions]
    sessions.sort(key=lambda s: s.get("created_at", ""), reverse=True)

    if limit is not None:
        sessions = sessions[:limit]

    return sessions

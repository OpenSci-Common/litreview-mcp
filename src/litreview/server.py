"""FastMCP server for litreview-mcp (Task 11).

Registers 22 MCP tools (lr_ prefix) as thin wrappers around the core modules.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

from litreview import (
    content_factors,
    dedup,
    factors,
    library,
    scoring,
    sessions,
    workspace,
)

mcp = FastMCP("litreview")

# ---------------------------------------------------------------------------
# Workspace (3 tools)
# ---------------------------------------------------------------------------


@mcp.tool()
def lr_init(path: str = ".") -> dict:
    """Initialise a litreview workspace at *path*.

    Creates .litreview/ with all TinyDB JSON databases, config.json with
    default scoring weights, and a pdfs/ directory.
    """
    return workspace.init_workspace(path)


@mcp.tool()
def lr_status(path: str = ".") -> dict:
    """Return workspace status counts (papers, factors, sessions, etc.)."""
    return workspace.get_status(path)


@mcp.tool()
def lr_config(path: str = ".", key: Optional[str] = None, value: Any = None) -> Any:
    """Get or set a workspace config value.

    If *value* is provided, sets the dot-notation *key* to *value* and returns
    the full updated config. If only *key* is given, returns that key's value.
    If neither is given, returns the entire config dict.
    """
    if value is not None and key is not None:
        return workspace.set_config(path, key, value)
    return workspace.get_config(path, key)


# ---------------------------------------------------------------------------
# Search Factors (5 tools)
# ---------------------------------------------------------------------------


@mcp.tool()
def lr_factor_add(
    path: str = ".",
    type: str = "query",
    value: str = "",
    query_role: str = "primary",
    sub_type: Optional[str] = None,
    provenance: str = "user_created",
) -> dict:
    """Add a search factor to the workspace factor library.

    Checks for duplicates (same type + value). Returns existing record with
    duplicate=True if already present.
    """
    return factors.add_factor(
        base_path=path,
        type=type,
        value=value,
        query_role=query_role,
        sub_type=sub_type,
        provenance=provenance,
    )


@mcp.tool()
def lr_factor_list(
    path: str = ".",
    type: Optional[str] = None,
    active_only: bool = False,
) -> List[dict]:
    """List search factors, with optional filtering by type and active status."""
    return factors.list_factors(base_path=path, type=type, active_only=active_only)


@mcp.tool()
def lr_factor_toggle(path: str = ".", factor_id: str = "", active: bool = True) -> dict:
    """Set the active field of a search factor by factor_id."""
    return factors.toggle_factor(base_path=path, factor_id=factor_id, active=active)


@mcp.tool()
def lr_factor_remove(path: str = ".", factor_id: str = "") -> dict:
    """Remove a search factor from the library by factor_id."""
    return factors.remove_factor(base_path=path, factor_id=factor_id)


@mcp.tool()
def lr_factor_compose_query(path: str = ".") -> dict:
    """Compose a search query from active factors.

    Returns primary_queries, filters, combined_query, factor_ids, and
    factor_roles. The Skill layer decides which search sources to call.
    """
    return factors.compose_query(base_path=path)


# ---------------------------------------------------------------------------
# Library (6 tools)
# ---------------------------------------------------------------------------


@mcp.tool()
def lr_paper_add(path: str = ".", paper_data: Optional[dict] = None) -> dict:
    """Add a single paper to the library.

    Returns the stored paper dict. If already present, returns existing record
    with duplicate=True.
    """
    return library.add_paper(base_path=path, paper_data=paper_data or {})


@mcp.tool()
def lr_paper_add_batch(
    path: str = ".",
    papers: Optional[List[dict]] = None,
) -> dict:
    """Add multiple papers to the library in one call.

    Returns {"added": int, "duplicates": int, "papers": [...]}.
    """
    return library.add_papers_batch(base_path=path, papers=papers or [])


@mcp.tool()
def lr_paper_exclude(path: str = ".", paper_id: str = "") -> dict:
    """Set the status of a paper to 'excluded' by paper_id."""
    return library.exclude_paper(base_path=path, paper_id=paper_id)


@mcp.tool()
def lr_paper_list(
    path: str = ".",
    status: Optional[str] = None,
    sort_by: Optional[str] = None,
    limit: Optional[int] = None,
    offset: int = 0,
) -> List[dict]:
    """List papers in the library with optional filtering and sorting.

    Args:
        status: Filter by paper status (e.g. "candidate", "excluded").
        sort_by: Field to sort by.
        limit: Maximum number of results to return.
        offset: Number of results to skip.
    """
    return library.list_papers(
        base_path=path,
        status=status,
        sort_by=sort_by,
        limit=limit,
        offset=offset,
    )


@mcp.tool()
def lr_paper_detail(path: str = ".", paper_id: str = "") -> dict:
    """Retrieve a single paper by paper_id, including extracted content factors."""
    detail = library.paper_detail(base_path=path, paper_id=paper_id)
    cf = content_factors.query_content_factors(base_path=path, paper_id=paper_id)
    detail["content_factors"] = cf
    return detail


@mcp.tool()
def lr_paper_accept(path: str = ".", paper_id: str = "", paper_ids: Optional[List[str]] = None) -> dict:
    """Accept candidate papers into the library (status: candidate -> in_library).

    Pass a single paper_id or a list of paper_ids.
    """
    if paper_ids:
        return library.accept_papers_batch(base_path=path, paper_ids=paper_ids)
    return library.accept_paper(base_path=path, paper_id=paper_id)


@mcp.tool()
def lr_paper_stats(path: str = ".") -> dict:
    """Return summary statistics for the library (total, candidates, in_library, excluded, etc.)."""
    return library.paper_stats(base_path=path)


@mcp.tool()
def lr_export_ris(path: str = ".", status: Optional[str] = "in_library") -> str:
    """Export papers from the library as RIS format string.

    Reads directly from .litreview/ — no need to pass paper data as parameter.
    """
    papers = library.list_papers(base_path=path, status=status)
    lines = []
    for p in papers:
        lines.append("TY  - JOUR")
        lines.append(f"TI  - {p.get('title', '')}")
        for a in (p.get("authors") or []):
            name = a if isinstance(a, str) else (a.get("name", "") if isinstance(a, dict) else str(a))
            if name:
                lines.append(f"AU  - {name}")
        if p.get("year"):
            lines.append(f"PY  - {p['year']}")
        if p.get("venue"):
            lines.append(f"JO  - {p['venue']}")
        if p.get("abstract"):
            lines.append(f"AB  - {p['abstract']}")
        ext = p.get("external_ids", {})
        if ext.get("doi"):
            lines.append(f"DO  - {ext['doi']}")
        lines.append("ER  - ")
        lines.append("")
    return "\n".join(lines)


@mcp.tool()
def lr_export_bibtex(path: str = ".", status: Optional[str] = "in_library") -> str:
    """Export papers from the library as BibTeX format string.

    Reads directly from .litreview/ — no need to pass paper data as parameter.
    """
    papers = library.list_papers(base_path=path, status=status)
    entries = []
    for p in papers:
        key = p.get("paper_id", "unknown")
        authors_list = []
        for a in (p.get("authors") or []):
            name = a if isinstance(a, str) else (a.get("name", "") if isinstance(a, dict) else str(a))
            if name:
                authors_list.append(name)
        author_str = " and ".join(authors_list)
        entry = f"@article{{{key},\n"
        entry += f"  title = {{{p.get('title', '')}}},\n"
        entry += f"  author = {{{author_str}}},\n"
        if p.get("year"):
            entry += f"  year = {{{p['year']}}},\n"
        if p.get("venue"):
            entry += f"  journal = {{{p['venue']}}},\n"
        if p.get("abstract"):
            entry += f"  abstract = {{{p['abstract']}}},\n"
        ext = p.get("external_ids", {})
        if ext.get("doi"):
            entry += f"  doi = {{{ext['doi']}}},\n"
        entry += "}"
        entries.append(entry)
    return "\n\n".join(entries)


# ---------------------------------------------------------------------------
# Dedup (1 tool)
# ---------------------------------------------------------------------------


@mcp.tool()
def lr_dedup(path: str = ".", candidates: Optional[List[dict]] = None) -> dict:
    """Deduplicate candidate papers against each other and the existing library.

    Returns {"unique": [...], "duplicates": [...]}.
    """
    existing = library.list_papers(base_path=path)
    return dedup.dedup_papers(candidates=candidates or [], existing=existing)


# ---------------------------------------------------------------------------
# Scoring (2 tools)
# ---------------------------------------------------------------------------


@mcp.tool()
def lr_score(
    path: str = ".",
    papers: Optional[List[dict]] = None,
    weights: Optional[Dict[str, float]] = None,
) -> List[dict]:
    """Score and rank papers by a weighted multi-metric score.

    Uses active factor values for keyword relevance. Returns papers with
    _score (0-100) and _score_breakdown added, sorted descending by _score.
    """
    active = factors.list_factors(base_path=path, active_only=True)
    active_factor_values = [f["value"] for f in active]
    return scoring.score_papers(
        papers=papers or [],
        weights=weights,
        active_factor_values=active_factor_values,
    )


@mcp.tool()
def lr_score_config(
    path: str = ".",
    weights: Optional[Dict[str, float]] = None,
) -> dict:
    """Get or set the scoring weight configuration.

    If *weights* is provided, updates and returns the new weights.
    Otherwise returns the current weights.
    """
    if weights is not None:
        return scoring.set_score_config(base_path=path, weights=weights)
    return scoring.get_score_config(base_path=path)


# ---------------------------------------------------------------------------
# Sessions (2 tools)
# ---------------------------------------------------------------------------


@mcp.tool()
def lr_session_save(
    path: str = ".",
    input_factors: Optional[List[str]] = None,
    factor_roles: Optional[Dict[str, str]] = None,
    api_queries: Optional[Dict[str, Any]] = None,
    results_total: int = 0,
    results_after_dedup: int = 0,
    results_already_in_library: int = 0,
    results_new: int = 0,
    result_paper_ids: Optional[List[str]] = None,
    user_decisions: Optional[Dict[str, str]] = None,
) -> dict:
    """Save a search session to the sessions database.

    Records all metadata about a search run including factors used, query
    params, result counts, and user decisions.
    """
    return sessions.save_session(
        base_path=path,
        input_factors=input_factors or [],
        factor_roles=factor_roles or {},
        api_queries=api_queries or {},
        results_total=results_total,
        results_after_dedup=results_after_dedup,
        results_already_in_library=results_already_in_library,
        results_new=results_new,
        result_paper_ids=result_paper_ids or [],
        user_decisions=user_decisions or {},
    )


@mcp.tool()
def lr_session_list(path: str = ".", limit: Optional[int] = None) -> List[dict]:
    """List saved search sessions, sorted by created_at descending."""
    return sessions.list_sessions(base_path=path, limit=limit)


# ---------------------------------------------------------------------------
# Content Factors (3 tools)
# ---------------------------------------------------------------------------


@mcp.tool()
def lr_content_extract(
    path: str = ".",
    paper_id: str = "",
    paper_ids: Optional[List[str]] = None,
) -> Any:
    """Extract content factors (authors, venue, fields) from paper(s).

    If paper_ids is given, processes each paper and returns a list of results.
    Otherwise processes a single paper identified by paper_id.
    """
    if paper_ids:
        results = []
        for pid in paper_ids:
            paper = library.paper_detail(base_path=path, paper_id=pid)
            result = content_factors.extract_content_factors(base_path=path, paper=paper)
            results.append(result)
        return results
    else:
        paper = library.paper_detail(base_path=path, paper_id=paper_id)
        return content_factors.extract_content_factors(base_path=path, paper=paper)


@mcp.tool()
def lr_content_query(
    path: str = ".",
    type: Optional[str] = None,
    paper_id: Optional[str] = None,
    aggregate: Optional[str] = None,
    min_count: int = 1,
) -> List[dict]:
    """Query content factors from the workspace with optional filtering and aggregation.

    Set aggregate="count" to group by value and return counts.
    Use min_count to filter aggregated results.
    """
    return content_factors.query_content_factors(
        base_path=path,
        type=type,
        paper_id=paper_id,
        aggregate=aggregate,
        min_count=min_count,
    )


@mcp.tool()
def lr_content_promote(path: str = ".", type: str = "", value: str = "") -> dict:
    """Promote a content factor to a search factor.

    Marks matching content factors as promoted and creates a corresponding
    search factor with provenance="promoted_from_content".
    Returns {"factor": ..., "content_factors_marked": int}.
    """
    return content_factors.promote_content_factor(
        base_path=path, type=type, value=value
    )


if __name__ == "__main__":
    mcp.run()

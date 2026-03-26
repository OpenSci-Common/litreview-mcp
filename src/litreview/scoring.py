"""Scoring system for litreview-mcp (Task 8)."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_DEFAULT_WEIGHTS: Dict[str, float] = {
    "citation_count": 0.20,
    "recency": 0.20,
    "citation_velocity": 0.15,
    "venue_impact": 0.15,
    "open_access": 0.10,
    "author_h_index": 0.10,
    "keyword_relevance": 0.10,
}

_OA_STATUSES = {"gold", "green", "hybrid", "bronze"}


def _current_year() -> int:
    return datetime.now(timezone.utc).year


def _score_citation_count(cc: Optional[int]) -> Optional[float]:
    """log1p(cc)/log1p(10000), capped at 1.0. None if unavailable."""
    if cc is None:
        return None
    return min(1.0, math.log1p(cc) / math.log1p(10000))


def _score_recency(year: Optional[int], current_year: int) -> Optional[float]:
    """max(0, 1 - age/10). None if year unavailable."""
    if year is None:
        return None
    age = current_year - year
    return max(0.0, 1.0 - age / 10.0)


def _score_citation_velocity(
    cc: Optional[int], year: Optional[int], current_year: int
) -> Optional[float]:
    """log1p(cc/(current_year - year + 1))/log1p(500). None if year or cc unavailable."""
    if cc is None or year is None:
        return None
    span = current_year - year + 1
    velocity = cc / span
    return math.log1p(velocity) / math.log1p(500)


def _score_venue_impact(venue: Optional[str]) -> Optional[float]:
    """Placeholder 0.5 if venue exists, None if missing."""
    if not venue:
        return None
    return 0.5


def _score_open_access(oa_status: Optional[str]) -> float:
    """1.0 if oa_status in (gold,green,hybrid,bronze), else 0.0."""
    if oa_status and oa_status.lower() in _OA_STATUSES:
        return 1.0
    return 0.0


def _score_author_h_index(authors: Optional[list]) -> Optional[float]:
    """min(1, hIndex/100) from authors[0].hIndex or .h_index. None if missing."""
    if not authors:
        return None
    first = authors[0]
    if isinstance(first, str):
        return None  # string author has no h-index
    if not isinstance(first, dict):
        return None
    h = first.get("hIndex") or first.get("h_index")
    if h is None:
        return None
    return min(1.0, h / 100.0)


def _score_keyword_relevance(
    title: str,
    abstract: str,
    factor_values: Optional[List[str]],
) -> Optional[float]:
    """Count matches of factor_values in title+abstract / len(factor_values). None if no factors."""
    if not factor_values:
        return None
    text = (title + " " + (abstract or "")).lower()
    matches = sum(1 for fv in factor_values if fv.lower() in text)
    return matches / len(factor_values)


def score_papers(
    papers: List[dict],
    weights: Optional[Dict[str, float]] = None,
    active_factor_values: Optional[List[str]] = None,
) -> List[dict]:
    """Score and sort papers by a weighted multi-metric score.

    Args:
        papers: List of paper dicts.
        weights: Optional custom weight dict. Defaults to _DEFAULT_WEIGHTS.
        active_factor_values: List of factor value strings for keyword relevance.

    Returns:
        List of paper dicts with ``_score`` (0-100) and ``_score_breakdown`` added,
        sorted descending by ``_score``.
    """
    if not papers:
        return []

    w = weights if weights is not None else _DEFAULT_WEIGHTS
    current_year = _current_year()
    result = []

    for paper in papers:
        paper = dict(paper)  # shallow copy to avoid mutating caller's data

        title = paper.get("title") or ""
        abstract = paper.get("abstract") or ""
        year = paper.get("year")
        cc = paper.get("citation_count")
        venue = paper.get("venue")
        oa_status = paper.get("open_access_status")
        authors = paper.get("authors")

        # Compute raw metric values (None = unavailable)
        raw: Dict[str, Optional[float]] = {
            "citation_count": _score_citation_count(cc),
            "recency": _score_recency(year, current_year),
            "citation_velocity": _score_citation_velocity(cc, year, current_year),
            "venue_impact": _score_venue_impact(venue),
            "open_access": _score_open_access(oa_status),
            "author_h_index": _score_author_h_index(authors),
            "keyword_relevance": _score_keyword_relevance(title, abstract, active_factor_values),
        }

        # Build breakdown: only available (non-None) metrics with non-zero weight
        breakdown: Dict[str, float] = {}
        available_weight: float = 0.0

        for metric, value in raw.items():
            metric_weight = w.get(metric, 0.0)
            if value is None or metric_weight == 0.0:
                # Unavailable or zero-weight: record in breakdown but don't add to available weight
                if value is None:
                    # degraded — skip from available weight
                    continue
                # zero weight — include in breakdown as 0 contribution
                breakdown[metric] = 0.0
            else:
                breakdown[metric] = value
                available_weight += metric_weight

        # Fill in zero for zero-weight metrics that have a value
        for metric, value in raw.items():
            if metric not in breakdown and value is not None:
                breakdown[metric] = value  # store the raw value even for zero-weight

        # Actually we need the breakdown to contain all metrics that were computable
        # Re-build clearly:
        breakdown = {}
        available_weight = 0.0
        for metric, value in raw.items():
            metric_weight = w.get(metric, 0.0)
            if value is None:
                # Unavailable - degrade (exclude from available_weight)
                pass
            else:
                breakdown[metric] = value
                available_weight += metric_weight

        # For metrics that are absent from breakdown (degraded), add them with 0 so
        # _score_breakdown has all 7 keys
        for metric in _DEFAULT_WEIGHTS:
            if metric not in breakdown:
                breakdown[metric] = 0.0

        # Compute weighted sum of available metrics
        total_weight = sum(w.get(m, 0.0) for m in _DEFAULT_WEIGHTS)
        weighted_sum = sum(
            breakdown[m] * w.get(m, 0.0)
            for m in _DEFAULT_WEIGHTS
            if raw.get(m) is not None and w.get(m, 0.0) > 0.0
        )

        # Scale: if some metrics degraded, scale up so max possible is still 100
        if available_weight > 0 and available_weight < total_weight:
            score = weighted_sum * (total_weight / available_weight) * 100
        elif available_weight > 0:
            score = weighted_sum * 100
        else:
            score = 0.0

        # Clamp to [0, 100]
        score = max(0.0, min(100.0, score))

        paper["_score"] = round(score, 4)
        paper["_score_breakdown"] = breakdown
        result.append(paper)

    result.sort(key=lambda p: p["_score"], reverse=True)
    return result


def get_score_config(base_path: Any) -> dict:
    """Read scoring.weights from config.json.

    Args:
        base_path: Workspace root path.

    Returns:
        The scoring.weights dict.
    """
    cfg_path = Path(base_path) / ".litreview" / "config.json"
    config: dict = json.loads(cfg_path.read_text())
    return config.get("scoring", {}).get("weights", dict(_DEFAULT_WEIGHTS))


def set_score_config(base_path: Any, weights: dict) -> dict:
    """Write scoring.weights to config.json.

    Args:
        base_path: Workspace root path.
        weights: New weights dict to store.

    Returns:
        The updated weights dict.
    """
    cfg_path = Path(base_path) / ".litreview" / "config.json"
    config: dict = json.loads(cfg_path.read_text())
    if "scoring" not in config:
        config["scoring"] = {}
    config["scoring"]["weights"] = weights
    cfg_path.write_text(json.dumps(config, indent=2))
    return weights

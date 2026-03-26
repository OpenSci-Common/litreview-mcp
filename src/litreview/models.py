"""Data models for litreview-mcp."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class SearchFactor:
    """Represents a search factor used in literature search queries."""

    id: str
    type: str  # e.g. "keyword", "author", "concept"
    value: str
    query_role: str = "must"  # "must" | "should" | "must_not"
    active: bool = True
    sub_type: Optional[str] = None
    api_ids: Dict[str, str] = field(default_factory=dict)
    api_support: List[str] = field(default_factory=list)
    provenance: Optional[str] = None  # "user" | "auto" | "promoted"
    promoted_from: Optional[str] = None  # content_factor id
    created_by: Optional[str] = None
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SearchFactor":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class ContentFactor:
    """Represents a content factor extracted from or associated with a paper."""

    id: str
    paper_id: str
    type: str  # e.g. "keyword", "author", "concept", "citation"
    value: str
    api_ids: Dict[str, str] = field(default_factory=dict)
    role: str = "descriptor"  # "descriptor" | "reference" | "citation"
    promoted: bool = False
    auto_extracted_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ContentFactor":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class Paper:
    """Represents a scientific paper in the library."""

    paper_id: str
    title: str
    year: Optional[int] = None
    external_ids: Dict[str, str] = field(default_factory=dict)  # doi, arxiv, etc.
    authors: List[Dict[str, str]] = field(default_factory=list)
    abstract: Optional[str] = None
    venue: Optional[str] = None
    citation_count: Optional[int] = None
    fields_of_study: List[str] = field(default_factory=list)
    open_access_status: Optional[str] = None  # "gold" | "green" | "closed" | None
    url: Optional[str] = None  # paper landing page (e.g. S2/OA/arxiv URL)
    pdf_url: Optional[str] = None  # direct PDF link if available
    pdf_status: str = "unknown"  # "available" | "downloaded" | "unavailable" | "unknown"
    pdf_path: Optional[str] = None
    status: str = "candidate"  # "candidate" | "included" | "excluded" | "pending"
    source_apis: List[str] = field(default_factory=list)
    first_seen_session_id: Optional[str] = None
    added_by: Optional[str] = None
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Paper":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class SearchSession:
    """Represents a single search session run."""

    session_id: str
    workspace_id: str
    triggered_by: str = "user"  # "user" | "auto"
    input_factors: List[str] = field(default_factory=list)  # SearchFactor ids
    factor_roles: Dict[str, str] = field(default_factory=dict)  # factor_id -> role
    api_queries: Dict[str, Any] = field(default_factory=dict)  # api_name -> query params
    results_total: int = 0
    results_after_dedup: int = 0
    results_already_in_library: int = 0
    results_new: int = 0
    result_paper_ids: List[str] = field(default_factory=list)
    user_decisions: Dict[str, str] = field(default_factory=dict)  # paper_id -> decision
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SearchSession":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

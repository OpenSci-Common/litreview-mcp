"""Utility functions for litreview-mcp."""

from __future__ import annotations

import hashlib
import os
import re
import string
from typing import Optional


def normalize_title(title: str) -> str:
    """Normalize a paper title: lowercase, remove punctuation, collapse whitespace.

    Args:
        title: Raw paper title.

    Returns:
        Normalized title string.
    """
    # Lowercase
    result = title.lower()
    # Remove punctuation (keep letters, digits, whitespace)
    result = re.sub(r"[^\w\s]", " ", result, flags=re.UNICODE)
    # Remove underscores (included in \w)
    result = result.replace("_", " ")
    # Collapse whitespace
    result = re.sub(r"\s+", " ", result).strip()
    return result


def generate_paper_id(
    doi: Optional[str] = None,
    arxiv_id: Optional[str] = None,
    title: Optional[str] = None,
    year: Optional[int] = None,
    first_author: Optional[str] = None,
) -> str:
    """Generate a stable paper ID as SHA256 first 12 hex characters.

    Priority: DOI > arxiv_id > title+year+first_author.

    Args:
        doi: Digital Object Identifier.
        arxiv_id: arXiv paper ID.
        title: Paper title (used as fallback with year and first_author).
        year: Publication year (used in fallback).
        first_author: First author surname (used in fallback).

    Returns:
        12-character lowercase hex string.

    Raises:
        ValueError: If no identifying information is provided.
    """
    if doi:
        key = f"doi:{doi}"
    elif arxiv_id:
        key = f"arxiv:{arxiv_id}"
    elif title:
        norm = normalize_title(title)
        author_str = first_author.lower() if first_author else None
        key = f"title:{norm}|year:{year}|author:{author_str}"
    else:
        raise ValueError(
            "At least one of doi, arxiv_id, or title must be provided to generate a paper ID."
        )

    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return digest[:12]


def safe_get_author_name(author) -> str:
    """Extract author name from either a string or a dict."""
    if isinstance(author, str):
        return author
    if isinstance(author, dict):
        return author.get("name", "") or author.get("authorName", "")
    return str(author)


def safe_get_author_field(author, field: str, default=None):
    """Safely get a field from an author (which may be str or dict)."""
    if isinstance(author, dict):
        return author.get(field, default)
    return default


def generate_id(prefix: str) -> str:
    """Generate a short random ID with a given prefix.

    Format: ``<prefix>_<7 random hex chars>`` e.g. ``sf_a3b2c1d``.

    Args:
        prefix: ID prefix string (e.g. "sf", "cf", "sess").

    Returns:
        ID string like ``sf_a3b2c1d``.
    """
    random_hex = os.urandom(4).hex()[:7]  # 4 bytes -> 8 hex chars, take first 7
    return f"{prefix}_{random_hex}"

"""Workspace management for litreview-mcp (Task 4)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from tinydb import TinyDB

DB_FILES = [
    "search_factors.json",
    "content_factors.json",
    "literature.json",
    "sessions.json",
    "scores.json",
]

_DEFAULT_CONFIG = {
    "scoring": {
        "weights": {
            "citation_count": 0.20,
            "recency": 0.20,
            "citation_velocity": 0.15,
            "venue_impact": 0.15,
            "open_access": 0.10,
            "author_h_index": 0.10,
            "keyword_relevance": 0.10,
        }
    }
}


def _litreview_dir(base_path: Path) -> Path:
    return Path(base_path) / ".litreview"


def _config_path(base_path: Path) -> Path:
    return _litreview_dir(base_path) / "config.json"


def init_workspace(base_path: Any) -> dict:
    """Initialise a litreview workspace under *base_path*.

    Creates ``.litreview/`` with all TinyDB JSON files, ``config.json`` with
    default scoring weights, and ``pdfs/`` directory.

    Returns:
        ``{"path": str, "already_existed": bool}``
    """
    base_path = Path(base_path)
    litdir = _litreview_dir(base_path)

    already_existed = litdir.exists()
    litdir.mkdir(parents=True, exist_ok=True)

    # Create empty TinyDB files if they don't exist yet
    for fname in DB_FILES:
        fpath = litdir / fname
        if not fpath.exists():
            fpath.write_text("{}")

    # Create config only if it doesn't exist (don't overwrite)
    config_file = litdir / "config.json"
    if not config_file.exists():
        config_file.write_text(json.dumps(_DEFAULT_CONFIG, indent=2))

    # Create pdfs/ dir
    (litdir / "pdfs").mkdir(exist_ok=True)

    return {"path": str(litdir), "already_existed": already_existed}


def get_status(base_path: Any) -> dict:
    """Return workspace status counts.

    Returns:
        Dict with keys ``initialized``, ``papers_count``, ``factors_count``,
        ``content_factors_count``, ``sessions_count``.
    """
    base_path = Path(base_path)
    litdir = _litreview_dir(base_path)

    if not litdir.exists():
        return {
            "initialized": False,
            "papers_count": 0,
            "factors_count": 0,
            "content_factors_count": 0,
            "sessions_count": 0,
        }

    def _count(fname: str) -> int:
        fpath = litdir / fname
        if not fpath.exists():
            return 0
        db = TinyDB(str(fpath))
        try:
            return len(db.all())
        finally:
            db.close()

    return {
        "initialized": True,
        "papers_count": _count("literature.json"),
        "factors_count": _count("search_factors.json"),
        "content_factors_count": _count("content_factors.json"),
        "sessions_count": _count("sessions.json"),
    }


def get_config(base_path: Any, key: Optional[str] = None) -> Any:
    """Read workspace configuration.

    Args:
        base_path: Workspace root path.
        key: Optional dot-notation key e.g. ``"scoring.weights.recency"``.
             ``None`` returns the entire config dict.

    Returns:
        The value at *key*, or the entire config if *key* is ``None``.
        Returns ``None`` if the key path does not exist.
    """
    cfg_path = _config_path(Path(base_path))
    config: dict = json.loads(cfg_path.read_text())

    if key is None:
        return config

    parts = key.split(".")
    current: Any = config
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def set_config(base_path: Any, key: str, value: Any) -> dict:
    """Write a config value using dot-notation *key*.

    Intermediate dict keys are created as needed.

    Args:
        base_path: Workspace root path.
        key: Dot-notation key e.g. ``"scoring.weights.recency"``.
        value: New value to store.

    Returns:
        The full updated config dict.
    """
    cfg_path = _config_path(Path(base_path))
    config: dict = json.loads(cfg_path.read_text())

    parts = key.split(".")
    current = config
    for part in parts[:-1]:
        if part not in current or not isinstance(current[part], dict):
            current[part] = {}
        current = current[part]
    current[parts[-1]] = value

    cfg_path.write_text(json.dumps(config, indent=2))
    return config

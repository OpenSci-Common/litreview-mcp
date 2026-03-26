"""Graph configuration and storage for litreview-mcp.

Each graph is a separate persisted task stored in .litreview/graphs/.

Storage structure:
    .litreview/graphs/
    ├── index.json               ← TinyDB: all graph configs
    ├── g_xxx_name.html          ← rendered HTML per graph
    └── g_xxx_name.json          ← full graph data (nodes+edges) per graph
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from tinydb import Query, TinyDB

from litreview import factors as factors_module
from litreview import library
from litreview.relations import (
    _find_matching_author,
    _pick_canonical_name,
    _stable_id,
    _truncate,
    _format_authors_display,
    deduplicate_factors,
)
from litreview.utils import generate_id, normalize_authors, safe_get_author_name


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------


def _graphs_dir(base_path) -> Path:
    d = Path(base_path) / ".litreview" / "graphs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _index_db(base_path) -> TinyDB:
    index_file = _graphs_dir(base_path) / "index.json"
    return TinyDB(str(index_file))


def _safe_slug(name: str) -> str:
    """Convert a graph name to a filesystem-safe slug."""
    slug = re.sub(r"[^\w\s-]", "", name.lower())
    slug = re.sub(r"[\s_]+", "_", slug).strip("_-")
    return slug[:40] or "graph"


# ---------------------------------------------------------------------------
# CRUD: create / list / detail / delete
# ---------------------------------------------------------------------------


def create_graph(
    base_path,
    name: str,
    node_types: list[str],
    edge_types: list[str],
    paper_filter: Optional[dict] = None,
) -> dict:
    """Create a graph configuration record in index.json.

    Args:
        base_path: Workspace root path.
        name: Human-readable graph name.
        node_types: e.g. ["paper", "author", "factor", "venue", "field"]
        edge_types: e.g. ["authored", "relates_to", "cites", "co_authored", "same_venue"]
        paper_filter: Optional filter dict, e.g. {"status": "in_library"}.

    Returns:
        The graph config dict with graph_id.
    """
    graph_id = generate_id("g")
    now = datetime.now(timezone.utc).isoformat()
    slug = _safe_slug(name)
    file_stem = f"{graph_id}_{slug}"

    config = {
        "graph_id": graph_id,
        "name": name,
        "node_types": node_types,
        "edge_types": edge_types,
        "paper_filter": paper_filter or {},
        "file_stem": file_stem,
        "html_path": None,
        "data_path": None,
        "stats": {},
        "created_at": now,
        "updated_at": now,
    }

    db = _index_db(base_path)
    try:
        db.insert(config)
    finally:
        db.close()

    return config


def list_graphs(base_path) -> list[dict]:
    """List all graph configs from index.json, sorted by created_at desc."""
    db = _index_db(base_path)
    try:
        all_configs = db.all()
    finally:
        db.close()
    return sorted(all_configs, key=lambda c: c.get("created_at", ""), reverse=True)


def graph_detail(base_path, graph_id: str) -> dict:
    """Get a single graph config + its stats."""
    db = _index_db(base_path)
    try:
        G = Query()
        results = db.search(G.graph_id == graph_id)
    finally:
        db.close()
    if not results:
        raise ValueError(f"Graph not found: {graph_id}")
    return results[0]


def delete_graph(base_path, graph_id: str) -> dict:
    """Delete a graph config and its associated files.

    Returns:
        {"deleted": graph_id, "files_removed": [...]}.
    """
    config = graph_detail(base_path, graph_id)
    removed = []

    graphs_dir = _graphs_dir(base_path)
    for ext in ("html", "json"):
        fpath = graphs_dir / f"{config['file_stem']}.{ext}"
        if fpath.exists():
            fpath.unlink()
            removed.append(str(fpath))

    db = _index_db(base_path)
    try:
        G = Query()
        db.remove(G.graph_id == graph_id)
    finally:
        db.close()

    return {"deleted": graph_id, "files_removed": removed}


# ---------------------------------------------------------------------------
# Core build logic
# ---------------------------------------------------------------------------


def _build_graph_data(
    config: dict,
    papers: list[dict],
    factor_values: list[str],
    paper_factor_map: Optional[dict[str, list[dict]]] = None,
) -> dict[str, Any]:
    """Build graph data from config's node_types + edge_types.

    Supports:
        Node types: paper, author, factor, venue, field
        Edge types: authored, relates_to, cites, co_authored, same_venue
    """
    node_types = set(config.get("node_types", []))
    edge_types = set(config.get("edge_types", []))

    nodes: list[dict] = []
    edges: list[dict] = []
    paper_node_ids: dict[str, str] = {}  # paper_id -> node_id

    # --- Factor nodes (with fuzzy dedup) ---
    factor_lookup: dict[str, str] = {}  # value_lower -> node_id
    factor_mapping: dict[str, str] = {}  # original_lower -> canonical_lower

    if "factor" in node_types:
        deduped_factors, factor_mapping = deduplicate_factors(factor_values)
        for fv in deduped_factors:
            fid = _stable_id("factor", fv)
            factor_lookup[fv.lower().strip()] = fid
            nodes.append({"id": fid, "label": fv, "type": "factor"})

    # --- Venue nodes ---
    venue_lookup: dict[str, str] = {}  # venue_str_lower -> node_id
    if "venue" in node_types:
        for paper in papers:
            venue = (paper.get("venue") or "").strip()
            if venue and venue.lower() not in venue_lookup:
                vid = _stable_id("venue", venue)
                venue_lookup[venue.lower()] = vid
                nodes.append({"id": vid, "label": venue, "type": "venue"})

    # --- Field nodes ---
    field_lookup: dict[str, str] = {}  # field_lower -> node_id
    if "field" in node_types:
        for paper in papers:
            for field in (paper.get("fields_of_study") or []):
                if not field:
                    continue
                field_str = str(field).strip()
                if field_str.lower() not in field_lookup:
                    fid = _stable_id("field", field_str)
                    field_lookup[field_str.lower()] = fid
                    nodes.append({"id": fid, "label": field_str, "type": "field"})

    # --- Paper + Author nodes ---
    author_seen: dict[str, str] = {}   # name_lower -> node_id
    author_labels: dict[str, str] = {} # name_lower -> display label
    # Track papers per venue and author-paper membership for derived edges
    venue_papers: dict[str, list[str]] = {}  # venue_lower -> [paper_node_id]
    author_papers: dict[str, list[str]] = {} # author_node_id -> [paper_node_id]

    for paper in papers:
        pid = paper.get("paper_id", "")
        paper_node_id = f"paper_{pid}"

        if "paper" in node_types:
            authors_raw = paper.get("authors")
            paper_node_ids[pid] = paper_node_id
            nodes.append({
                "id": paper_node_id,
                "label": _truncate(paper.get("title", "Untitled"), 60),
                "type": "paper",
                "title": paper.get("title", ""),
                "abstract": paper.get("abstract") or "",
                "url": paper.get("url") or "",
                "pdf_url": paper.get("pdf_url") or "",
                "doi": (paper.get("external_ids") or {}).get("doi", ""),
                "authors_display": _format_authors_display(authors_raw),
                "year": paper.get("year"),
                "venue": paper.get("venue") or "",
                "citations": paper.get("citations", 0)
                    or paper.get("citation_count", 0)
                    or 0,
            })

        # --- Author nodes + authored edges ---
        if "author" in node_types:
            authors_raw = paper.get("authors")
            authors_norm = normalize_authors(authors_raw)
            for author_dict in authors_norm:
                name = safe_get_author_name(author_dict)
                if not name:
                    continue
                matched_key = _find_matching_author(name, author_seen)
                if matched_key is None:
                    name_key = name.lower().strip()
                    aid = _stable_id("author", name_key)
                    author_seen[name_key] = aid
                    author_labels[name_key] = name
                    author_papers[aid] = []
                    nodes.append({"id": aid, "label": name, "type": "author"})
                    matched_key = name_key
                else:
                    new_label = _pick_canonical_name(author_labels[matched_key], name)
                    if new_label != author_labels[matched_key]:
                        author_labels[matched_key] = new_label
                        aid = author_seen[matched_key]
                        for n in nodes:
                            if n["id"] == aid:
                                n["label"] = new_label
                                break

                aid = author_seen[matched_key]
                if aid not in author_papers:
                    author_papers[aid] = []
                author_papers[aid].append(paper_node_id)

                if "authored" in edge_types and "paper" in node_types:
                    edges.append({
                        "from": aid,
                        "to": paper_node_id,
                        "type": "authored",
                    })

        # --- Factor → Paper edges ---
        if "relates_to" in edge_types and "factor" in node_types and "paper" in node_types:
            if paper_factor_map and pid in paper_factor_map:
                for mapping_entry in paper_factor_map[pid]:
                    fv_raw = mapping_entry.get("factor_value", "").lower().strip()
                    fv_key = factor_mapping.get(fv_raw, fv_raw)
                    if fv_key in factor_lookup:
                        edges.append({
                            "from": factor_lookup[fv_key],
                            "to": paper_node_id,
                            "type": "relates_to",
                            "relevance": mapping_entry.get("relevance", "medium"),
                        })

        # --- Venue → Paper edge (same_venue derived later; here build lookup) ---
        if "venue" in node_types and "paper" in node_types:
            venue = (paper.get("venue") or "").strip()
            if venue:
                vkey = venue.lower()
                if vkey not in venue_papers:
                    venue_papers[vkey] = []
                venue_papers[vkey].append(paper_node_id)

        # --- Cites edges (paper → paper) ---
        if "cites" in edge_types and "paper" in node_types:
            refs = paper.get("references") or []
            for ref in refs:
                ref_id = ref if isinstance(ref, str) else ref.get("paper_id", "")
                if ref_id and ref_id in paper_node_ids:
                    edges.append({
                        "from": paper_node_id,
                        "to": f"paper_{ref_id}",
                        "type": "cites",
                    })

    # --- Derived: same_venue edges (paper → paper sharing venue) ---
    if "same_venue" in edge_types and "paper" in node_types:
        for vkey, pids in venue_papers.items():
            if len(pids) < 2:
                continue
            for i in range(len(pids)):
                for j in range(i + 1, len(pids)):
                    edges.append({
                        "from": pids[i],
                        "to": pids[j],
                        "type": "same_venue",
                        "venue": vkey,
                    })

    # --- Derived: co_authored edges (author → author sharing a paper) ---
    if "co_authored" in edge_types and "author" in node_types:
        # Build paper → authors lookup
        paper_to_authors: dict[str, list[str]] = {}
        for aid, pids_list in author_papers.items():
            for pnid in pids_list:
                if pnid not in paper_to_authors:
                    paper_to_authors[pnid] = []
                paper_to_authors[pnid].append(aid)
        # For each paper, create co-authored edges between its authors
        seen_pairs: set[tuple[str, str]] = set()
        for pnid, aids in paper_to_authors.items():
            for i in range(len(aids)):
                for j in range(i + 1, len(aids)):
                    pair = tuple(sorted([aids[i], aids[j]]))
                    if pair not in seen_pairs:
                        seen_pairs.add(pair)
                        edges.append({
                            "from": aids[i],
                            "to": aids[j],
                            "type": "co_authored",
                        })

    stats = {
        "papers": sum(1 for n in nodes if n["type"] == "paper"),
        "authors": sum(1 for n in nodes if n["type"] == "author"),
        "factors": sum(1 for n in nodes if n["type"] == "factor"),
        "venues": sum(1 for n in nodes if n["type"] == "venue"),
        "fields": sum(1 for n in nodes if n["type"] == "field"),
        "edges": len(edges),
    }
    return {"nodes": nodes, "edges": edges, "stats": stats}


def build_graph(
    base_path,
    graph_id: str,
    paper_factor_map: Optional[dict[str, list[dict]]] = None,
) -> dict:
    """Build/rebuild a graph: generate data, render HTML, persist everything.

    Args:
        base_path: Workspace root path.
        graph_id: The graph to build.
        paper_factor_map: Optional LLM analysis: {paper_id: [{factor_value, relevance}]}

    Returns:
        {"graph_id": str, "html_path": str, "data_path": str, "stats": dict}
    """
    config = graph_detail(base_path, graph_id)

    # Fetch papers from library with optional filter
    paper_filter = config.get("paper_filter") or {}
    status_filter = paper_filter.get("status") if paper_filter else None
    papers = library.list_papers(base_path=base_path, status=status_filter)

    # Fetch active factors
    active_factors = factors_module.list_factors(base_path=base_path, active_only=True)
    factor_values = [f["value"] for f in active_factors]

    # Build graph data
    graph_data = _build_graph_data(config, papers, factor_values, paper_factor_map)

    # Persist JSON data + HTML
    graphs_dir = _graphs_dir(base_path)
    file_stem = config["file_stem"]

    data_path = graphs_dir / f"{file_stem}.json"
    data_path.write_text(
        json.dumps(graph_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    html = _render_html(graph_data, config)
    html_path = graphs_dir / f"{file_stem}.html"
    html_path.write_text(html, encoding="utf-8")

    # Update index record
    now = datetime.now(timezone.utc).isoformat()
    db = _index_db(base_path)
    try:
        G = Query()
        db.update(
            {
                "html_path": str(html_path),
                "data_path": str(data_path),
                "stats": graph_data["stats"],
                "updated_at": now,
            },
            G.graph_id == graph_id,
        )
    finally:
        db.close()

    return {
        "graph_id": graph_id,
        "html_path": str(html_path),
        "data_path": str(data_path),
        "stats": graph_data["stats"],
    }


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------


def _render_html(graph_data: dict[str, Any], config: dict) -> str:
    """Render graph data as a self-contained interactive HTML page."""
    data_json = json.dumps(graph_data, ensure_ascii=False, indent=None)
    config_json = json.dumps(
        {
            "name": config.get("name", "Graph"),
            "node_types": config.get("node_types", []),
            "edge_types": config.get("edge_types", []),
        },
        ensure_ascii=False,
    )
    html = _GRAPH_HTML_TEMPLATE.replace("/*__GRAPH_DATA__*/", data_json)
    html = html.replace("/*__GRAPH_CONFIG__*/", config_json)
    return html


_GRAPH_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Literature Graph</title>
<script src="https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js"></script>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  height: 100vh; display: flex; flex-direction: column;
  background: #f5f5f5; color: #333;
}

/* --- Header --- */
.header {
  background: #1a1a2e; color: #fff; padding: 12px 24px;
  display: flex; align-items: center; justify-content: space-between;
  flex-shrink: 0;
}
.header h1 { font-size: 18px; font-weight: 600; }
.legend { display: flex; gap: 16px; font-size: 13px; flex-wrap: wrap; }
.legend-item { display: flex; align-items: center; gap: 6px; }
.legend-dot {
  width: 12px; height: 12px; border-radius: 50%; display: inline-block;
}
.dot-author { background: #4FC3F7; }
.dot-paper  { background: #81C784; }
.dot-factor { background: #FFB74D; }
.dot-venue  { background: #CE93D8; }
.dot-field  { background: #F48FB1; }

/* --- Main layout --- */
.main { display: flex; flex: 1; overflow: hidden; }

#graph-container {
  flex: 1; background: #fafafa; position: relative;
}

/* --- Detail panel --- */
#detail-panel {
  width: 380px; border-left: 1px solid #e0e0e0; background: #fff;
  overflow-y: auto; padding: 24px; flex-shrink: 0;
  transition: width 0.2s;
}
#detail-panel.collapsed { width: 0; padding: 0; overflow: hidden; }

.detail-placeholder {
  color: #999; text-align: center; margin-top: 40%;
  font-size: 14px; line-height: 1.8;
}

.detail-header { margin-bottom: 16px; }
.detail-type {
  display: inline-block; font-size: 11px; font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.5px; padding: 2px 8px;
  border-radius: 4px; margin-bottom: 8px;
}
.type-author { background: #E1F5FE; color: #0277BD; }
.type-paper  { background: #E8F5E9; color: #2E7D32; }
.type-factor { background: #FFF3E0; color: #E65100; }
.type-venue  { background: #F3E5F5; color: #6A1B9A; }
.type-field  { background: #FCE4EC; color: #AD1457; }
.type-edge   { background: #E3F2FD; color: #1565C0; }

.detail-title { font-size: 16px; font-weight: 600; line-height: 1.4; margin-bottom: 4px; }
.detail-meta  { font-size: 13px; color: #666; margin-bottom: 12px; }

.detail-section { margin-bottom: 16px; }
.detail-section h3 {
  font-size: 12px; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.5px; color: #999; margin-bottom: 8px;
}
.detail-abstract {
  font-size: 13px; line-height: 1.7; color: #444;
  max-height: 300px; overflow-y: auto;
}

.detail-link {
  display: inline-flex; align-items: center; gap: 4px;
  color: #1976D2; text-decoration: none; font-size: 13px;
  padding: 6px 12px; border: 1px solid #1976D2; border-radius: 6px;
  transition: all 0.15s;
}
.detail-link:hover { background: #1976D2; color: #fff; }

/* --- Paper list in author/factor detail --- */
.paper-list { list-style: none; }
.paper-list li {
  padding: 10px 0; border-bottom: 1px solid #f0f0f0;
  font-size: 13px; cursor: pointer; transition: background 0.1s;
}
.paper-list li:hover { background: #f9f9f9; margin: 0 -24px; padding: 10px 24px; }
.paper-list .paper-item-title { font-weight: 500; color: #333; line-height: 1.4; }
.paper-list .paper-item-meta  { color: #999; font-size: 12px; margin-top: 2px; }

/* --- Stats bar --- */
.stats-bar {
  position: absolute; bottom: 12px; left: 12px; z-index: 10;
  background: rgba(255,255,255,0.92); backdrop-filter: blur(8px);
  padding: 8px 14px; border-radius: 8px; font-size: 12px; color: #666;
  box-shadow: 0 1px 4px rgba(0,0,0,0.1);
  pointer-events: none;
}

/* Relevance badge */
.relevance-badge {
  display: inline-block; font-size: 10px; font-weight: 600;
  padding: 1px 6px; border-radius: 4px; margin-left: 6px;
}
.rel-high   { background: #E8F5E9; color: #2E7D32; }
.rel-medium { background: #FFF3E0; color: #E65100; }
.rel-low    { background: #F5F5F5; color: #757575; }
</style>
</head>
<body>

<div class="header">
  <h1 id="graph-title">Literature Graph</h1>
  <div class="legend" id="legend"></div>
</div>

<div class="main">
  <div id="graph-container"></div>
  <div class="stats-bar" id="stats-bar"></div>
  <div id="detail-panel">
    <div class="detail-placeholder">
      Click a node or edge to view details<br>
      <span style="font-size:12px; margin-top:8px; display:block;">
        Drag to pan &middot; Scroll to zoom
      </span>
    </div>
  </div>
</div>

<script>
// --- Data ---
const RAW    = /*__GRAPH_DATA__*/;
const CONFIG = /*__GRAPH_CONFIG__*/;

document.getElementById("graph-title").textContent = CONFIG.name || "Literature Graph";

const nodesMap = {};
RAW.nodes.forEach(n => { nodesMap[n.id] = n; });

// Edge index for edge click: store raw edge objects with vis-assigned id
const edgesRawMap = {}; // vis edge id -> raw edge

// --- Legend ---
const LEGEND_ITEMS = {
  author: { label: "Author",  cls: "dot-author" },
  paper:  { label: "Paper",   cls: "dot-paper"  },
  factor: { label: "Concept", cls: "dot-factor" },
  venue:  { label: "Venue",   cls: "dot-venue"  },
  field:  { label: "Field",   cls: "dot-field"  },
};
const legendEl = document.getElementById("legend");
(CONFIG.node_types || []).forEach(t => {
  const item = LEGEND_ITEMS[t];
  if (item) {
    legendEl.innerHTML += `<span class="legend-item"><span class="legend-dot ${item.cls}"></span> ${item.label}</span>`;
  }
});

// --- Build vis.js data ---
const NODE_COLORS = {
  author: "#4FC3F7",
  paper:  "#81C784",
  factor: "#FFB74D",
  venue:  "#CE93D8",
  field:  "#F48FB1",
};
const NODE_SHAPES = {
  author: "dot",
  paper:  "diamond",
  factor: "triangle",
  venue:  "ellipse",
  field:  "box",
};
const NODE_SIZES = { author: 14, paper: 18, factor: 16, venue: 14, field: 12 };

const visNodes = RAW.nodes.map(n => ({
  id: n.id,
  label: n.label,
  color: {
    background: NODE_COLORS[n.type] || "#B0BEC5",
    border: NODE_COLORS[n.type] || "#B0BEC5",
    highlight: { background: NODE_COLORS[n.type] || "#B0BEC5", border: "#333" }
  },
  shape: NODE_SHAPES[n.type] || "dot",
  size: NODE_SIZES[n.type] || 14,
  font: {
    size: n.type === "paper" ? 11 : 12, color: "#333",
    strokeWidth: 2, strokeColor: "#fff"
  },
}));

const EDGE_STYLES = {
  authored:    { color: "#B0BEC5", dashes: false,      width: 1,   arrows: "" },
  relates_to:  { color: "#FFB74D", dashes: [5, 5],     width: 1.5, arrows: "to" },
  cites:       { color: "#90A4AE", dashes: false,      width: 1,   arrows: "to" },
  co_authored: { color: "#4FC3F7", dashes: [2, 2],     width: 1,   arrows: "" },
  same_venue:  { color: "#CE93D8", dashes: [8, 4],     width: 1,   arrows: "" },
};
const RELEVANCE_WIDTH = { high: 2.5, medium: 1.5, low: 0.8 };

const visEdgesArr = RAW.edges.map((e, idx) => {
  const style = EDGE_STYLES[e.type] || EDGE_STYLES.authored;
  const w = e.relevance ? (RELEVANCE_WIDTH[e.relevance] || 1.5) : style.width;
  const visId = `edge_${idx}`;
  edgesRawMap[visId] = e;
  return {
    id: visId,
    from: e.from, to: e.to,
    color: { color: style.color, opacity: 0.6 },
    dashes: style.dashes,
    width: w,
    arrows: style.arrows || undefined,
    smooth: { type: "continuous" },
  };
});

// --- Create network ---
const container = document.getElementById("graph-container");
const network = new vis.Network(container, {
  nodes: new vis.DataSet(visNodes),
  edges: new vis.DataSet(visEdgesArr),
}, {
  physics: {
    solver: "forceAtlas2Based",
    forceAtlas2Based: {
      gravitationalConstant: -40, centralGravity: 0.005,
      springLength: 120, springConstant: 0.02
    },
    stabilization: { iterations: 200 },
  },
  interaction: { hover: true, tooltipDelay: 200, zoomView: true },
  layout: { improvedLayout: true },
});

// --- Stats bar ---
const sb = document.getElementById("stats-bar");
const parts = [];
if (RAW.stats.papers)  parts.push(`${RAW.stats.papers} papers`);
if (RAW.stats.authors) parts.push(`${RAW.stats.authors} authors`);
if (RAW.stats.factors) parts.push(`${RAW.stats.factors} concepts`);
if (RAW.stats.venues)  parts.push(`${RAW.stats.venues} venues`);
if (RAW.stats.fields)  parts.push(`${RAW.stats.fields} fields`);
parts.push(`${RAW.stats.edges} connections`);
sb.textContent = parts.join(" \u00b7 ");

// --- Detail panel ---
const panel = document.getElementById("detail-panel");

function getNeighborPapers(nodeId) {
  return RAW.edges
    .filter(e => e.from === nodeId || e.to === nodeId)
    .map(e => e.from === nodeId ? e.to : e.from)
    .filter(id => nodesMap[id] && nodesMap[id].type === "paper")
    .map(id => nodesMap[id]);
}

function getNeighborFactors(nodeId) {
  return RAW.edges
    .filter(e => (e.from === nodeId || e.to === nodeId) && e.type === "relates_to")
    .map(e => e.from === nodeId ? e.to : e.from)
    .filter(id => nodesMap[id] && nodesMap[id].type === "factor")
    .map(id => nodesMap[id]);
}

function paperLink(node) {
  const url = node.url || (node.doi ? `https://doi.org/${node.doi}` : "") || node.pdf_url;
  return url
    ? `<a class="detail-link" href="${url}" target="_blank" rel="noopener">Open paper \u2192</a>`
    : "";
}

function renderPaperList(papers, clickable) {
  if (!papers.length)
    return "<p style='color:#999;font-size:13px;'>No connected papers</p>";
  return `<ul class="paper-list">${papers.map(p => {
    const meta = [p.year, p.venue].filter(Boolean).join(" \u00b7 ");
    return `<li data-node-id="${p.id}" ${clickable ? 'class="clickable"' : ""}>
      <div class="paper-item-title">${p.title || p.label}</div>
      ${meta ? `<div class="paper-item-meta">${meta}</div>` : ""}
    </li>`;
  }).join("")}</ul>`;
}

function showPaperDetail(n) {
  const meta = [n.year, n.venue, n.citations ? `${n.citations} citations` : ""]
    .filter(Boolean).join(" \u00b7 ");
  const factors = getNeighborFactors(n.id);
  const factorHtml = factors.length
    ? `<div class="detail-section"><h3>Related Concepts</h3>
        <div style="display:flex;flex-wrap:wrap;gap:6px;">
          ${factors.map(f =>
            `<span style="background:#FFF3E0;color:#E65100;padding:2px 8px;border-radius:4px;font-size:12px;">
              ${f.label}
            </span>`).join("")}
        </div></div>`
    : "";
  panel.innerHTML = `
    <div class="detail-header">
      <span class="detail-type type-paper">Paper</span>
      <div class="detail-title">${n.title || n.label}</div>
      <div class="detail-meta">${n.authors_display || ""}</div>
      ${meta ? `<div class="detail-meta">${meta}</div>` : ""}
    </div>
    ${n.abstract
      ? `<div class="detail-section"><h3>Abstract</h3>
          <div class="detail-abstract">${n.abstract}</div></div>`
      : ""}
    ${factorHtml}
    <div style="margin-top:16px;">${paperLink(n)}</div>
  `;
}

function showAuthorDetail(n) {
  const papers = getNeighborPapers(n.id);
  panel.innerHTML = `
    <div class="detail-header">
      <span class="detail-type type-author">Author</span>
      <div class="detail-title">${n.label}</div>
      <div class="detail-meta">${papers.length} paper${papers.length !== 1 ? "s" : ""}</div>
    </div>
    <div class="detail-section">
      <h3>Papers</h3>${renderPaperList(papers, true)}
    </div>
  `;
  bindPaperListClicks();
}

function showFactorDetail(n) {
  const papers = getNeighborPapers(n.id);
  panel.innerHTML = `
    <div class="detail-header">
      <span class="detail-type type-factor">Concept</span>
      <div class="detail-title">${n.label}</div>
      <div class="detail-meta">${papers.length} related paper${papers.length !== 1 ? "s" : ""}</div>
    </div>
    <div class="detail-section">
      <h3>Related Papers</h3>${renderPaperList(papers, true)}
    </div>
  `;
  bindPaperListClicks();
}

function showVenueDetail(n) {
  const papers = getNeighborPapers(n.id);
  // For venue: papers sharing this venue string (same_venue edges) + direct connections
  const venuePapers = RAW.nodes.filter(nd => nd.type === "paper" && nd.venue &&
    nd.venue.toLowerCase() === n.label.toLowerCase());
  const allPapers = [...new Map([...papers, ...venuePapers].map(p => [p.id, p])).values()];
  panel.innerHTML = `
    <div class="detail-header">
      <span class="detail-type type-venue">Venue</span>
      <div class="detail-title">${n.label}</div>
      <div class="detail-meta">${allPapers.length} paper${allPapers.length !== 1 ? "s" : ""}</div>
    </div>
    <div class="detail-section">
      <h3>Papers</h3>${renderPaperList(allPapers, true)}
    </div>
  `;
  bindPaperListClicks();
}

function showFieldDetail(n) {
  const papers = RAW.nodes.filter(nd =>
    nd.type === "paper" && (nd.fields_of_study || [])
      .some(f => String(f).toLowerCase() === n.label.toLowerCase())
  );
  panel.innerHTML = `
    <div class="detail-header">
      <span class="detail-type type-field">Field</span>
      <div class="detail-title">${n.label}</div>
      <div class="detail-meta">${papers.length} paper${papers.length !== 1 ? "s" : ""}</div>
    </div>
    <div class="detail-section">
      <h3>Papers</h3>${renderPaperList(papers, true)}
    </div>
  `;
  bindPaperListClicks();
}

function showEdgeDetail(rawEdge) {
  const srcNode = nodesMap[rawEdge.from];
  const tgtNode = nodesMap[rawEdge.to];
  const EDGE_TYPE_LABELS = {
    authored:    "Authored",
    relates_to:  "Relates To",
    cites:       "Cites",
    co_authored: "Co-authored",
    same_venue:  "Same Venue",
  };
  const relBadge = rawEdge.relevance
    ? `<span class="relevance-badge rel-${rawEdge.relevance}">${rawEdge.relevance}</span>`
    : "";
  panel.innerHTML = `
    <div class="detail-header">
      <span class="detail-type type-edge">Relationship</span>
      <div class="detail-title">
        ${EDGE_TYPE_LABELS[rawEdge.type] || rawEdge.type}${relBadge}
      </div>
    </div>
    <div class="detail-section">
      <h3>Source</h3>
      <div style="cursor:pointer;padding:8px;background:#f9f9f9;border-radius:6px;font-size:13px;"
           data-node-id="${srcNode ? srcNode.id : ""}">
        ${srcNode ? `<strong>${srcNode.label}</strong><br><span style="color:#999;">${srcNode.type}</span>` : rawEdge.from}
      </div>
    </div>
    <div class="detail-section">
      <h3>Target</h3>
      <div style="cursor:pointer;padding:8px;background:#f9f9f9;border-radius:6px;font-size:13px;"
           data-node-id="${tgtNode ? tgtNode.id : ""}">
        ${tgtNode ? `<strong>${tgtNode.label}</strong><br><span style="color:#999;">${tgtNode.type}</span>` : rawEdge.to}
      </div>
    </div>
    ${rawEdge.relevance
      ? `<div class="detail-section"><h3>Relevance</h3>
          <span class="relevance-badge rel-${rawEdge.relevance}" style="font-size:13px;padding:4px 10px;">
            ${rawEdge.relevance}
          </span></div>`
      : ""}
    ${rawEdge.venue
      ? `<div class="detail-section"><h3>Venue</h3><p style="font-size:13px;">${rawEdge.venue}</p></div>`
      : ""}
  `;
  // Allow clicking source/target node cards to navigate
  panel.querySelectorAll("[data-node-id]").forEach(el => {
    const nid = el.getAttribute("data-node-id");
    if (nid && nodesMap[nid]) {
      el.addEventListener("click", () => {
        const nd = nodesMap[nid];
        showNodeDetail(nd);
        network.selectNodes([nid]);
        network.focus(nid, { scale: 1.2, animation: { duration: 400 } });
      });
    }
  });
}

function showNodeDetail(node) {
  if (node.type === "paper")  showPaperDetail(node);
  else if (node.type === "author")  showAuthorDetail(node);
  else if (node.type === "factor")  showFactorDetail(node);
  else if (node.type === "venue")   showVenueDetail(node);
  else if (node.type === "field")   showFieldDetail(node);
}

function bindPaperListClicks() {
  panel.querySelectorAll(".paper-list li[data-node-id]").forEach(li => {
    li.style.cursor = "pointer";
    li.addEventListener("click", () => {
      const nid = li.getAttribute("data-node-id");
      const node = nodesMap[nid];
      if (node) {
        showPaperDetail(node);
        network.selectNodes([nid]);
        network.focus(nid, { scale: 1.2, animation: { duration: 400 } });
      }
    });
  });
}

// --- Event handlers ---
network.on("click", params => {
  // Edge click (takes priority if an edge was clicked without a node)
  if (!params.nodes.length && params.edges.length) {
    const edgeVisId = params.edges[0];
    const rawEdge = edgesRawMap[edgeVisId];
    if (rawEdge) {
      showEdgeDetail(rawEdge);
      return;
    }
  }
  if (!params.nodes.length) return;
  const nodeId = params.nodes[0];
  const node = nodesMap[nodeId];
  if (!node) return;
  showNodeDetail(node);
});

network.on("deselectNode", params => {
  // Only reset if nothing is selected
  if (!params.nodes || !params.nodes.length) {
    panel.innerHTML = `<div class="detail-placeholder">
      Click a node or edge to view details<br>
      <span style="font-size:12px; margin-top:8px; display:block;">
        Drag to pan &middot; Scroll to zoom
      </span>
    </div>`;
  }
});
</script>
</body>
</html>
"""

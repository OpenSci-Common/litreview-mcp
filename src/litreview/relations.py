"""Relation graph builder and HTML renderer for litreview-mcp.

Builds interactive HTML graphs showing:
- Author ↔ Paper relationships (bipartite)
- SearchFactor ↔ Paper relationships (knowledge graph from LLM analysis)
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from rapidfuzz.fuzz import ratio, token_sort_ratio

from litreview.utils import normalize_authors, safe_get_author_name


def _stable_id(prefix: str, value: str) -> str:
    """Generate a deterministic node ID from prefix + value."""
    digest = hashlib.md5(value.lower().strip().encode("utf-8")).hexdigest()[:8]
    return f"{prefix}_{digest}"


def _format_authors_display(authors) -> str:
    """Format authors for display in the detail panel."""
    if isinstance(authors, str):
        return authors
    if isinstance(authors, list):
        names = [
            safe_get_author_name(a) if isinstance(a, dict) else str(a)
            for a in authors
        ]
        return "; ".join(n for n in names if n)
    return ""


_AUTHOR_THRESHOLD = 85
_FACTOR_THRESHOLD = 80


def _author_names_match(a: str, b: str) -> bool:
    """Check if two author names likely refer to the same person.

    Handles:
    - Fuzzy match (ratio >= 85): "Bob Jonse" ↔ "Bob Jones"
    - Initial expansion: "B. Jones" ↔ "Bob Jones"
    - Order swap: "Jones, Bob" ↔ "Bob Jones" (via token_sort_ratio)
    """
    if ratio(a, b) >= _AUTHOR_THRESHOLD:
        return True
    if token_sort_ratio(a, b) >= _AUTHOR_THRESHOLD:
        return True
    # Initial expansion: "b. jones" ↔ "bob jones"
    parts_a = a.replace(".", " ").split()
    parts_b = b.replace(".", " ").split()
    if len(parts_a) < 2 or len(parts_b) < 2:
        return False
    # Surnames (last token) must be very close
    if ratio(parts_a[-1], parts_b[-1]) < 90:
        return False
    # First token: one is an initial of the other
    fa, fb = parts_a[0], parts_b[0]
    if (len(fa) == 1 and fb.startswith(fa)) or (len(fb) == 1 and fa.startswith(fb)):
        return True
    return False


def _find_matching_author(
    name: str, existing: dict[str, str],
) -> Optional[str]:
    """Find an existing author key that fuzzy-matches the given name."""
    name_lower = name.lower().strip()
    if name_lower in existing:
        return name_lower
    for existing_name in existing:
        if _author_names_match(name_lower, existing_name):
            return existing_name
    return None


def _pick_canonical_name(current: str, new: str) -> str:
    """Pick the more complete name as canonical (longer wins)."""
    return new if len(new) > len(current) else current


def deduplicate_factors(
    factor_values: list[str], threshold: int = _FACTOR_THRESHOLD,
) -> tuple[list[str], dict[str, str]]:
    """Group similar factor values by fuzzy match, return canonical list + mapping.

    Handles spelling variants like "financial inclusions" ↔ "financial inclusion".
    Does NOT handle semantic synonyms ("DeFi" ↔ "decentralized finance") —
    that requires LLM-level normalization.

    Returns:
        (canonical_list, mapping) where mapping is {original_lower: canonical_lower}.
    """
    canonical: list[str] = []
    mapping: dict[str, str] = {}

    for fv in factor_values:
        fv_lower = fv.lower().strip()
        matched = False
        for canon in canonical:
            canon_lower = canon.lower().strip()
            if token_sort_ratio(fv_lower, canon_lower) >= threshold:
                mapping[fv_lower] = canon_lower
                matched = True
                break
        if not matched:
            canonical.append(fv)
            mapping[fv_lower] = fv_lower

    return canonical, mapping


def build_graph_data(
    papers: list[dict],
    factor_values: list[str],
    paper_factor_map: Optional[dict[str, list[dict]]] = None,
) -> dict[str, Any]:
    """Build unified graph data from papers, factors, and LLM analysis.

    Args:
        papers: Paper dicts from the library.
        factor_values: Search factor value strings.
        paper_factor_map: paper_id -> [{"factor_value": str, "relevance": str}]
            from LLM analysis. If None, factor nodes are still shown but
            have no edges to papers.

    Returns:
        {"nodes": [...], "edges": [...], "stats": {...}}
    """
    nodes: list[dict] = []
    edges: list[dict] = []
    author_seen: dict[str, str] = {}  # name_lower -> node_id
    author_labels: dict[str, str] = {}  # name_lower -> display label
    factor_lookup: dict[str, str] = {}  # value_lower -> node_id

    # --- Factor nodes (with fuzzy dedup) ---
    deduped_factors, factor_mapping = deduplicate_factors(factor_values)
    for fv in deduped_factors:
        fid = _stable_id("factor", fv)
        factor_lookup[fv.lower().strip()] = fid
        nodes.append({"id": fid, "label": fv, "type": "factor"})

    # --- Paper + Author nodes ---
    for paper in papers:
        pid = paper.get("paper_id", "")
        paper_node_id = f"paper_{pid}"
        authors_raw = paper.get("authors")
        authors_norm = normalize_authors(authors_raw)

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

        # Author → Paper edges (with fuzzy dedup)
        for author_dict in authors_norm:
            name = safe_get_author_name(author_dict)
            if not name:
                continue
            matched_key = _find_matching_author(name, author_seen)
            if matched_key is None:
                # New author
                name_key = name.lower().strip()
                aid = _stable_id("author", name_key)
                author_seen[name_key] = aid
                author_labels[name_key] = name
                nodes.append({"id": aid, "label": name, "type": "author"})
                matched_key = name_key
            else:
                # Existing author — update label if new name is more complete
                new_label = _pick_canonical_name(author_labels[matched_key], name)
                if new_label != author_labels[matched_key]:
                    author_labels[matched_key] = new_label
                    # Update the node label in-place
                    aid = author_seen[matched_key]
                    for n in nodes:
                        if n["id"] == aid:
                            n["label"] = new_label
                            break
            edges.append({
                "from": author_seen[matched_key],
                "to": paper_node_id,
                "type": "authored",
            })

        # Factor → Paper edges (from LLM analysis, with fuzzy factor mapping)
        if paper_factor_map and pid in paper_factor_map:
            for mapping_entry in paper_factor_map[pid]:
                fv_raw = mapping_entry.get("factor_value", "").lower().strip()
                # Resolve through factor dedup mapping
                fv_key = factor_mapping.get(fv_raw, fv_raw)
                if fv_key in factor_lookup:
                    edges.append({
                        "from": factor_lookup[fv_key],
                        "to": paper_node_id,
                        "type": "relates_to",
                        "relevance": mapping_entry.get("relevance", "medium"),
                    })

    stats = {
        "papers": sum(1 for n in nodes if n["type"] == "paper"),
        "authors": sum(1 for n in nodes if n["type"] == "author"),
        "factors": sum(1 for n in nodes if n["type"] == "factor"),
        "edges": len(edges),
    }
    return {"nodes": nodes, "edges": edges, "stats": stats}


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "\u2026"


def render_html(graph_data: dict[str, Any]) -> str:
    """Render graph data as a self-contained interactive HTML page."""
    data_json = json.dumps(graph_data, ensure_ascii=False, indent=None)
    return _HTML_TEMPLATE.replace("/*__GRAPH_DATA__*/", data_json)


def save_graph_html(
    base_path,
    papers: list[dict],
    factor_values: list[str],
    paper_factor_map: Optional[dict[str, list[dict]]] = None,
) -> dict[str, Any]:
    """Build graph and save as HTML file.

    Returns:
        {"path": str, "stats": dict}
    """
    graph_data = build_graph_data(papers, factor_values, paper_factor_map)
    html = render_html(graph_data)
    output_path = Path(base_path) / ".litreview" / "relation_graph.html"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    # Auto-save cache if paper_factor_map provided
    if paper_factor_map:
        cache = load_cache(base_path)
        updated = update_cache(cache, paper_factor_map, papers, factor_values)
        save_cache(base_path, updated)

    return {"path": str(output_path), "stats": graph_data["stats"]}


# ---------------------------------------------------------------------------
# Cache — persist LLM analysis to avoid redundant calls
# ---------------------------------------------------------------------------

_CACHE_FILE = "relation_cache.json"


def _content_hash(text: str) -> str:
    """SHA-256 first 12 hex chars of text content."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _factor_set_hash(factor_values: list[str]) -> str:
    """Hash of sorted, lowered factor values — detects factor set changes."""
    normalized = sorted(v.lower().strip() for v in factor_values)
    return _content_hash("|".join(normalized))


def load_cache(base_path) -> dict[str, Any]:
    """Load relation cache from disk. Returns empty structure if not found."""
    cache_path = Path(base_path) / ".litreview" / _CACHE_FILE
    if cache_path.exists():
        try:
            return json.loads(cache_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"factor_hash": "", "entries": {}}


def save_cache(base_path, cache: dict[str, Any]) -> None:
    """Persist relation cache to disk."""
    cache_path = Path(base_path) / ".litreview" / _CACHE_FILE
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def check_cache(
    papers: list[dict],
    factor_values: list[str],
    cache: dict[str, Any],
) -> dict[str, Any]:
    """Determine which papers need LLM analysis and which are cached.

    Returns:
        {
            "cached_map": {paper_id: [factor mappings...]},  -- reusable results
            "uncached_papers": [{paper_id, title, abstract}, ...],  -- need analysis
            "cache_hit": int,
            "cache_miss": int,
            "cache_stale": bool,  -- True if factor set changed
        }
    """
    current_fh = _factor_set_hash(factor_values)
    stored_fh = cache.get("factor_hash", "")
    entries = cache.get("entries", {})

    # If factor set changed, entire cache is stale
    factors_changed = current_fh != stored_fh

    cached_map: dict[str, list[dict]] = {}
    uncached_papers: list[dict] = []

    for paper in papers:
        pid = paper.get("paper_id", "")
        abstract = paper.get("abstract") or ""

        # Skip papers without abstract — nothing to analyze
        if not abstract.strip():
            continue

        entry = entries.get(pid)
        hit = (
            not factors_changed
            and entry is not None
            and entry.get("abstract_hash") == _content_hash(abstract)
        )

        if hit:
            cached_map[pid] = entry["factors"]
        else:
            uncached_papers.append({
                "paper_id": pid,
                "title": paper.get("title", ""),
                "abstract": abstract,
            })

    return {
        "cached_map": cached_map,
        "uncached_papers": uncached_papers,
        "cache_hit": len(cached_map),
        "cache_miss": len(uncached_papers),
        "cache_stale": factors_changed,
    }


def update_cache(
    cache: dict[str, Any],
    paper_factor_map: dict[str, list[dict]],
    papers: list[dict],
    factor_values: list[str],
) -> dict[str, Any]:
    """Merge new LLM analysis into cache. Returns a new cache dict (immutable)."""
    now = datetime.now(timezone.utc).isoformat()
    current_fh = _factor_set_hash(factor_values)
    stored_fh = cache.get("factor_hash", "")

    # If factors changed, start fresh
    entries = {} if current_fh != stored_fh else dict(cache.get("entries", {}))

    # Build paper_id → abstract lookup
    abstract_lookup = {
        p["paper_id"]: (p.get("abstract") or "")
        for p in papers
        if p.get("paper_id")
    }

    # Merge new analysis
    for pid, factor_list in paper_factor_map.items():
        abstract = abstract_lookup.get(pid, "")
        entries[pid] = {
            "abstract_hash": _content_hash(abstract),
            "factors": factor_list,
            "analyzed_at": now,
        }

    return {"factor_hash": current_fh, "entries": entries}


# ---------------------------------------------------------------------------
# HTML Template
# ---------------------------------------------------------------------------

_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Literature Relation Graph</title>
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
.legend { display: flex; gap: 16px; font-size: 13px; }
.legend-item { display: flex; align-items: center; gap: 6px; }
.legend-dot {
  width: 12px; height: 12px; border-radius: 50%; display: inline-block;
}
.dot-author { background: #4FC3F7; }
.dot-paper { background: #81C784; }
.dot-factor { background: #FFB74D; }

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
.type-paper { background: #E8F5E9; color: #2E7D32; }
.type-factor { background: #FFF3E0; color: #E65100; }

.detail-title { font-size: 16px; font-weight: 600; line-height: 1.4; margin-bottom: 4px; }
.detail-meta { font-size: 13px; color: #666; margin-bottom: 12px; }

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
.paper-list .paper-item-meta { color: #999; font-size: 12px; margin-top: 2px; }

/* --- Stats bar --- */
.stats-bar {
  position: absolute; bottom: 12px; left: 12px; z-index: 10;
  background: rgba(255,255,255,0.92); backdrop-filter: blur(8px);
  padding: 8px 14px; border-radius: 8px; font-size: 12px; color: #666;
  box-shadow: 0 1px 4px rgba(0,0,0,0.1);
  pointer-events: none;
}
</style>
</head>
<body>

<div class="header">
  <h1>Literature Relation Graph</h1>
  <div class="legend">
    <span class="legend-item"><span class="legend-dot dot-author"></span> Author</span>
    <span class="legend-item"><span class="legend-dot dot-paper"></span> Paper</span>
    <span class="legend-item"><span class="legend-dot dot-factor"></span> Concept</span>
  </div>
</div>

<div class="main">
  <div id="graph-container"></div>
  <div class="stats-bar" id="stats-bar"></div>
  <div id="detail-panel">
    <div class="detail-placeholder">
      Click a node to view details<br>
      <span style="font-size:12px; margin-top:8px; display:block;">
        Drag to pan &middot; Scroll to zoom
      </span>
    </div>
  </div>
</div>

<script>
// --- Data ---
const RAW = /*__GRAPH_DATA__*/;
const nodesMap = {};
RAW.nodes.forEach(n => { nodesMap[n.id] = n; });

// --- Build vis.js data ---
const NODE_COLORS = { author: "#4FC3F7", paper: "#81C784", factor: "#FFB74D" };
const NODE_SHAPES = { author: "dot", paper: "diamond", factor: "triangle" };
const NODE_SIZES  = { author: 14, paper: 18, factor: 16 };

const visNodes = RAW.nodes.map(n => ({
  id: n.id,
  label: n.label,
  color: { background: NODE_COLORS[n.type], border: NODE_COLORS[n.type],
           highlight: { background: NODE_COLORS[n.type], border: "#333" } },
  shape: NODE_SHAPES[n.type] || "dot",
  size: NODE_SIZES[n.type] || 14,
  font: { size: n.type === "paper" ? 11 : 12, color: "#333",
          strokeWidth: 2, strokeColor: "#fff" },
}));

const EDGE_STYLES = {
  authored: { color: "#B0BEC5", dashes: false, width: 1 },
  relates_to: { color: "#FFB74D", dashes: [5, 5], width: 1.5 },
};
const RELEVANCE_WIDTH = { high: 2.5, medium: 1.5, low: 0.8 };

const visEdges = RAW.edges.map(e => {
  const style = EDGE_STYLES[e.type] || EDGE_STYLES.authored;
  const w = e.relevance ? (RELEVANCE_WIDTH[e.relevance] || 1.5) : style.width;
  return {
    from: e.from, to: e.to,
    color: { color: style.color, opacity: 0.6 },
    dashes: style.dashes,
    width: w,
    smooth: { type: "continuous" },
  };
});

// --- Create network ---
const container = document.getElementById("graph-container");
const network = new vis.Network(container, {
  nodes: new vis.DataSet(visNodes),
  edges: new vis.DataSet(visEdges),
}, {
  physics: {
    solver: "forceAtlas2Based",
    forceAtlas2Based: { gravitationalConstant: -40, centralGravity: 0.005,
                        springLength: 120, springConstant: 0.02 },
    stabilization: { iterations: 200 },
  },
  interaction: { hover: true, tooltipDelay: 200, zoomView: true },
  layout: { improvedLayout: true },
});

// --- Stats ---
const sb = document.getElementById("stats-bar");
sb.textContent = `${RAW.stats.papers} papers \u00b7 ${RAW.stats.authors} authors \u00b7 ${RAW.stats.factors} concepts \u00b7 ${RAW.stats.edges} connections`;

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

function getNeighborAuthors(nodeId) {
  return RAW.edges
    .filter(e => (e.from === nodeId || e.to === nodeId) && e.type === "authored")
    .map(e => e.from === nodeId ? e.to : e.from)
    .filter(id => nodesMap[id] && nodesMap[id].type === "author")
    .map(id => nodesMap[id]);
}

function paperLink(node) {
  const url = node.url || (node.doi ? `https://doi.org/${node.doi}` : "") || node.pdf_url;
  return url ? `<a class="detail-link" href="${url}" target="_blank" rel="noopener">Open paper \u2192</a>` : "";
}

function renderPaperList(papers, clickable) {
  if (!papers.length) return "<p style='color:#999;font-size:13px;'>No connected papers</p>";
  return `<ul class="paper-list">${papers.map(p => {
    const meta = [p.year, p.venue].filter(Boolean).join(" \u00b7 ");
    return `<li data-node-id="${p.id}" ${clickable ? 'class="clickable"' : ""}>
      <div class="paper-item-title">${p.title || p.label}</div>
      ${meta ? `<div class="paper-item-meta">${meta}</div>` : ""}
    </li>`;
  }).join("")}</ul>`;
}

function showPaperDetail(n) {
  const meta = [n.year, n.venue, n.citations ? `${n.citations} citations` : ""].filter(Boolean).join(" \u00b7 ");
  const factors = getNeighborFactors(n.id);
  const factorHtml = factors.length
    ? `<div class="detail-section"><h3>Related Concepts</h3><div style="display:flex;flex-wrap:wrap;gap:6px;">${
        factors.map(f => `<span style="background:#FFF3E0;color:#E65100;padding:2px 8px;border-radius:4px;font-size:12px;">${f.label}</span>`).join("")
      }</div></div>` : "";
  panel.innerHTML = `
    <div class="detail-header">
      <span class="detail-type type-paper">Paper</span>
      <div class="detail-title">${n.title || n.label}</div>
      <div class="detail-meta">${n.authors_display || ""}</div>
      ${meta ? `<div class="detail-meta">${meta}</div>` : ""}
    </div>
    ${n.abstract ? `<div class="detail-section"><h3>Abstract</h3><div class="detail-abstract">${n.abstract}</div></div>` : ""}
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
    <div class="detail-section"><h3>Papers</h3>${renderPaperList(papers, true)}</div>
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
    <div class="detail-section"><h3>Related Papers</h3>${renderPaperList(papers, true)}</div>
  `;
  bindPaperListClicks();
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
  if (!params.nodes.length) return;
  const nodeId = params.nodes[0];
  const node = nodesMap[nodeId];
  if (!node) return;

  if (node.type === "paper") showPaperDetail(node);
  else if (node.type === "author") showAuthorDetail(node);
  else if (node.type === "factor") showFactorDetail(node);
});

network.on("deselectNode", () => {
  panel.innerHTML = `<div class="detail-placeholder">
    Click a node to view details<br>
    <span style="font-size:12px; margin-top:8px; display:block;">
      Drag to pan &middot; Scroll to zoom
    </span>
  </div>`;
});
</script>
</body>
</html>
"""

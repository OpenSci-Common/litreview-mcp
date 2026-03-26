---
name: litreview-relation
description: >
  Build interactive relation graphs from the literature library.
  Use when user says "生成关系图", "关联图谱", "知识图谱", "作者关系",
  "relation graph", "knowledge graph", "show connections", "文献关系".
---

# litreview-relation: Interactive Literature Relation Graph

Generates an interactive HTML graph showing author-paper and concept-paper relationships. The graph supports click-to-inspect: clicking any node reveals related papers, abstracts, and links in a detail panel.

Uses an incremental cache so that only new or changed papers require LLM analysis.

---

## IMPORTANT: Path Rule

All litreview MCP tool calls MUST pass the `path` parameter as the **absolute path** of the user's current working directory. NEVER omit `path` or use the default `"."` — the default resolves to the MCP server's process directory, not the user's project.

Determine the user's project directory at the start (e.g. via `pwd`) and use it consistently for every `lr_*` call.

---

## Step 1: Load Data and Check Cache

Call this tool to retrieve cached results and identify papers needing analysis:

```
lr_relation_cache_load(path="<project_path>")
```

If no papers exist in the library, tell the user:
> "文献库为空。请先运行「搜索论文」添加文献。"

The tool returns:
```json
{
  "cached_map": {"paper_id": [{"factor_value": "...", "relevance": "high"}]},
  "uncached_papers": [{"paper_id": "...", "title": "...", "abstract": "..."}],
  "cache_hit": 7,
  "cache_miss": 3,
  "cache_stale": false
}
```

- If `cache_stale` is true, factor set has changed — all papers need re-analysis.
- If `cache_miss` is 0, skip Step 2 entirely — use `cached_map` directly in Step 3.

Also call in parallel to get factor values for the analysis prompt:

```
lr_factor_list(path="<project_path>", active_only=true)
```

Collect: **factor_values** = the `value` field from each active factor.

---

## Step 2: LLM Analysis — Only Uncached Papers

Analyze ONLY the papers in `uncached_papers`. For each paper's abstract, determine which factor values are semantically related.

Produce a `new_analysis` map with this exact format:

```json
{
  "<paper_id>": [
    {"factor_value": "<exact factor value string>", "relevance": "high"},
    {"factor_value": "<exact factor value string>", "relevance": "medium"}
  ]
}
```

**Rules:**
- Only include factors that are genuinely relevant to the paper's abstract content.
- `factor_value` MUST exactly match one of the factor_values (case-insensitive matching is handled internally).
- `relevance` levels:
  - **high** — the factor is a core topic of the paper
  - **medium** — the factor is discussed or related
  - **low** — the factor is only tangentially mentioned
- Skip factors that have no relevance to the abstract.

**Efficiency:** Process all uncached papers in a single analysis pass.

Then **merge** the cached and new results:

```
merged_map = {**cached_map, **new_analysis}
```

---

## Step 3: Build and Save Graph

Call the relation build tool with the merged analysis:

```
lr_relation_build(
  path="<project_path>",
  paper_factor_map=<merged_map>
)
```

The tool automatically saves the analysis to cache for next time.

Optional: pass `status="in_library"` to include only accepted papers.

Returns:
```json
{
  "path": "/absolute/path/to/.litreview/relation_graph.html",
  "stats": {"papers": 10, "authors": 25, "factors": 8, "edges": 67}
}
```

---

## Step 4: Present Results

Show the user:

1. **Cache efficiency**: how many papers were cached vs newly analyzed
2. **Stats summary**: number of papers, authors, concepts, and connections
3. **File path**: where the HTML was saved
4. **How to open**: suggest `open <path>` (macOS) or provide the path for the user to open in a browser

Example output:
> 关系图谱已生成（缓存命中 7 篇，新分析 3 篇）：
> - 10 篇论文 · 25 位作者 · 8 个概念 · 67 条连接
> - 文件: `.litreview/relation_graph.html`
> - 打开方式: `open .litreview/relation_graph.html`
>
> 点击图中节点可查看文献详情和摘要，点击文献链接可跳转到原文。

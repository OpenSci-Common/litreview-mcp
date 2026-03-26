---
name: litreview-relation
description: >
  Build interactive relation graphs from the literature library.
  Use when user says "生成关系图", "关联图谱", "知识图谱", "作者关系",
  "relation graph", "knowledge graph", "show connections", "文献关系",
  "查看图谱列表", "重建图谱", "删除图谱", "图谱探索", "graph exploration".
---

# litreview-relation: Graph-Based Literature Exploration

Builds, persists, and manages interactive HTML knowledge graphs from your literature library. Each graph is an independent task with its own node types, edge types, and ID. Graphs can be rebuilt with updated data or deleted.

---

## IMPORTANT: Path Rule

All litreview MCP tool calls MUST pass the `path` parameter as the **absolute path** of the user's current working directory. NEVER omit `path` or use the default `"."` — the default resolves to the MCP server's process directory, not the user's project.

Determine the user's project directory at the start (e.g. via `pwd`) and use it consistently for every `lr_*` call.

---

## Entry Points

Check the user's intent first and route to the matching workflow:

| User says | Workflow |
|---|---|
| "查看图谱列表" / "我的图谱" / "list graphs" | → [List Graphs](#list-graphs) |
| "重建图谱 X" / "rebuild graph X" | → [Rebuild Graph](#rebuild-graph) |
| "删除图谱 X" / "delete graph X" | → [Delete Graph](#delete-graph) |
| "生成关系图" / "新建图谱" / anything else | → [Create New Graph](#create-new-graph) |

---

## List Graphs

```
lr_graph_list(path="<project_path>")
```

Display the returned list, showing for each graph: ID, name, node types, edge types, creation date, and node/edge counts if available.

Then offer:
> "输入「重建图谱 <ID>」可以用最新数据重建，输入「删除图谱 <ID>」可以删除。"

---

## Rebuild Graph

```
lr_graph_detail(path="<project_path>", graph_id="<X>")
```

Retrieve the stored config (node_types, edge_types, paper_filter). Then proceed from [Step 7](#step-7-llm-analysis-relates_to-only) using those same parameters, skipping Steps 1–6.

---

## Delete Graph

```
lr_graph_delete(path="<project_path>", graph_id="<X>")
```

Confirm with the user before deleting if they did not explicitly include the graph ID in their message.

---

## Create New Graph

### Step 1: Check Library Status

Call in parallel:

```
lr_paper_stats(path="<project_path>")
lr_factor_list(path="<project_path>", active_only=true)
```

If the library has no papers, stop and tell the user:
> "文献库为空。请先运行「搜索论文」添加文献，再生成关系图谱。"

Store `factor_list` and total paper count for validation in later steps.

---

### Step 2: Present Node Type Options

Present all available node types and explain what each one means:

```
可用节点类型（选择要纳入图谱的实体）：

  [A] paper   — 文献库中的论文
  [B] author  — 论文作者（自动去重）
  [C] factor  — 检索因子 / 研究概念
  [D] venue   — 期刊或会议（来自论文元数据）
  [E] field   — 研究领域（来自论文元数据）

请选择要包含的节点类型（可多选，如 A B C）：
```

Wait for user selection.

---

### Step 3: Present Edge Type Options

Based on the selected node types, show only the compatible edge types. Always show all but mark incompatible ones:

```
可用关系类型（选择要建立的连接）：

  [1] authored      — 作者 → 论文（需要 author + paper 节点）
  [2] relates_to    — 因子 → 论文（需要 factor + paper 节点；需 LLM 分析）
  [3] cites         — 论文 → 论文（需要引文数据）
  [4] co_authored   — 作者 ↔ 作者（派生自共同作者关系）
  [5] same_venue    — 论文 ↔ 论文（派生自相同发表场所）

请选择要建立的关系类型（可多选，如 1 2）：
```

Wait for user selection.

---

### Step 4: Validation and Rejection Policy

Run ALL checks below in order. Stop at the first hard rejection; for warnings ask the user to confirm before continuing.

**Check 1 — No edge types selected (hard reject)**

If user selected no edge types:
> "没有关系类型就无法形成图谱，请至少选一种关系。"

Return to Step 3.

**Check 2 — Only paper nodes, no other node type (hard reject)**

If `node_types == ["paper"]`:
> "只有论文节点没有其他节点类型，图谱会缺乏关系结构。建议至少加上 author 或 factor。"

Return to Step 2.

**Check 3 — Edge type requires a node type not selected (auto-fix)**

For each selected edge type, verify the required nodes are included:

| Edge type | Required nodes |
|---|---|
| authored | author, paper |
| relates_to | factor, paper |
| cites | paper |
| co_authored | author |
| same_venue | paper, venue |

If a required node type is missing, **auto-add it** and inform the user:
> "「authored」关系需要 author 节点，已自动加入。"

**Check 4 — relates_to selected but no active factors (hard reject)**

If `relates_to` is in edge_types AND `factor_list` is empty:
> "当前没有活跃的检索因子，relates_to 关系需要因子。请先添加因子或选择其他关系类型。"

Return to Step 3.

**Check 5 — cites selected but no citation data (warn + confirm)**

If `cites` is in edge_types, check paper stats for citation data. If none found:
> "当前文献库没有引文数据，建议先运行「引文追踪」或去掉 cites 关系。确认继续？"

If user declines, return to Step 3.

**Check 6 — Estimated node count too large (warn + confirm)**

Estimate total nodes from: paper count + (author estimate: papers × 3) + factor count + venue count, depending on selected node types. If estimated total > 500:
> "预计 X 个节点，图谱可能难以阅读。建议缩小范围（如只看 in_library 的论文）或减少节点类型。确认继续？"

If user wants to narrow the scope, ask whether to filter by `status="in_library"` and return to Step 2 or 3 as needed.

---

### Step 5: Name the Graph

Suggest a name based on the selected types, e.g.:

- paper + author + authored → "论文-作者关系图"
- paper + factor + relates_to → "论文-概念关联图"
- paper + author + factor + authored + relates_to → "综合知识图谱"

Ask the user:
> "图谱名称建议：「<suggested_name>」，直接回车确认或输入自定义名称："

---

### Step 6: Create Graph Config

```
lr_graph_create(
  path="<project_path>",
  name="<graph_name>",
  node_types=["paper", "author", ...],
  edge_types=["authored", ...],
  paper_filter=<"in_library" or null>
)
```

Store the returned `graph_id` for subsequent steps.

---

### Step 7: LLM Analysis (relates_to only)

**Skip this step entirely if `relates_to` is NOT in the selected edge types.**

#### 7a: Load cache

```
lr_relation_cache_load(path="<project_path>")
```

Returns:
```json
{
  "cached_map": {"paper_id": [{"factor_value": "...", "relevance": "high"}]},
  "uncached_papers": [{"paper_id": "...", "title": "...", "abstract": "..."}],
  "cache_hit": 7,
  "cache_miss": 3,
  "cache_stale": false
}
```

- If `cache_stale` is true, the factor set has changed — all papers need re-analysis.
- If `cache_miss` is 0, skip 7b and use `cached_map` directly in 7c.

Collect `factor_values` = the `value` field from each active factor in `factor_list`.

#### 7b: Analyze uncached papers

Analyze ONLY the papers in `uncached_papers`. For each paper's abstract, determine which factor values are semantically related.

Produce a `new_analysis` map:

```json
{
  "<paper_id>": [
    {"factor_value": "<exact factor value string>", "relevance": "high"},
    {"factor_value": "<exact factor value string>", "relevance": "medium"}
  ]
}
```

Rules:
- Only include factors that are genuinely relevant to the paper's abstract.
- `factor_value` MUST exactly match one of the `factor_values` strings.
- Relevance levels: **high** = core topic, **medium** = discussed/related, **low** = tangentially mentioned.
- Skip factors with no relevance to the abstract.
- **Synonym awareness:** Treat semantic synonyms as matches (e.g. "DeFi" matches "decentralized finance", "RWA" matches "real world asset"). Use the exact `factor_value` string in output, not the synonym found in the abstract.
- Process all uncached papers in a single analysis pass.

#### 7c: Merge results

```python
merged_map = {**cached_map, **new_analysis}
```

Pass `merged_map` as `paper_factor_map` to the build step.

---

### Step 8: Build Graph

```
lr_graph_build(
  path="<project_path>",
  graph_id="<graph_id>",
  paper_factor_map=<merged_map or null>
)
```

Returns:
```json
{
  "path": "/absolute/path/to/.litreview/graphs/<graph_id>.html",
  "stats": {"papers": 10, "authors": 25, "factors": 8, "edges": 67}
}
```

---

### Step 9: Present Results

Show the user a summary:

```
图谱已生成：「<graph_name>」（ID: <graph_id>）

节点: X 篇论文 · Y 位作者 · Z 个概念 · ...
连接: N 条边

文件: .litreview/graphs/<graph_id>.html
打开: open .litreview/graphs/<graph_id>.html
```

If `relates_to` was included, also show cache efficiency:
> 缓存命中 X 篇，新分析 Y 篇

Remind the user:
> "点击图中节点可查看文献详情和摘要，点击论文链接可跳转原文。"

---

### Step 10: Follow-up Options

After presenting results, offer:

```
接下来你可以：
  · 「查看图谱列表」— 查看所有已保存的图谱
  · 「重建图谱 <graph_id>」— 用最新数据重建此图谱
  · 「创建新图谱」— 用不同的节点/关系类型新建一个图谱
```

---
name: litreview-search
description: >
  Search and rank academic papers. Use when user says "搜索论文", "检索文献", "查找论文",
  "search papers", "find papers", "用这些关键词搜索", "开始搜索", "run search".
  Also trigger when search factors exist and user expresses search intent.
---

# litreview-search: Search and Rank Academic Papers

This skill executes a structured literature search, persists all results as candidates, and lets the user browse/sort/accept into the library.

See `references/query-mapping.md` for factor-to-API parameter mapping details.

---

## IMPORTANT: Path Rule

All litreview MCP tool calls MUST pass the `path` parameter as the **absolute path** of the user's current working directory. NEVER omit `path` or use the default `"."` — the default resolves to the MCP server's process directory, not the user's project.

Determine the user's project directory at the start (e.g. via `pwd`) and use it consistently for every `lr_*` call.

---

## Step 1: Load Active Factors

Call `lr_factor_list` to retrieve all active search factors:

```
lr_factor_list(path="<project_path>", active_only=true)
```

If no active factors are found, tell the user:
> "尚未配置检索因子。请先运行「初始化litreview」或手动添加因子。"

---

## Step 2: Compose Query Parameters

Call `lr_factor_compose_query` to generate query parameters from active factors:

```
lr_factor_compose_query(path="<project_path>")
```

Returns: primary_queries, filters, combined_query, factor_ids, factor_roles.

---

## Step 3: Show Query Plan for Confirmation

**Before executing any searches**, present the query plan transparently:

```
即将执行以下检索计划：

主查询词: "large language model reasoning"
过滤条件:
  - 年份: 2022-2024
  - 领域: artificial intelligence
数据源: Semantic Scholar, OpenAlex
每个来源返回数量: 50 篇

是否确认执行？（可调整参数、数据源或返回数量）
```

Wait for user confirmation. Allow adjustments.

---

## Step 4: Execute Searches

Based on confirmed plan, call paper-search MCP tools:

```
search_semantic(query="<combined_query>", max_results=50)
search_openalex(query="<combined_query>", max_results=50)
```

**If seed_paper factors exist:**
```
snowball_search(paper_id=<seed_id>, direction="both", max_results_per_direction=30)
```

The Skill decides which sources to use based on user's research domain and preferences. Refer to `references/query-mapping.md` for factor-to-API mapping.

---

## Step 5: Ingest Results (Dedup + Score + Persist)

**This is the critical step.** Call `lr_search_ingest` to persist ALL search results:

```
lr_search_ingest(
  path="<project_path>",
  raw_results=<combined_results_from_all_sources>,
  input_factors=<factor_ids>,
  api_queries=[{"api": "semantic_scholar", "results_count": 50}, ...],
)
```

This single call does:
1. Deduplicates against existing library
2. Scores all unique papers
3. **Persists every result as `status="candidate"` in literature.json**
4. Saves the search session with all metadata

Returns top 20 scored papers for immediate display, plus statistics.

**All results are now persisted** — even if the conversation ends, the user can come back and browse them.

---

## Step 6: Show Ranked Results

Present results from the `lr_search_ingest` response:

```
检索结果已保存（共 143 篇 → 去重后 98 篇 → 新增 93 篇候选）

Top 20 候选论文（按评分排序）：

#1  [82.3分] Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks
    Lewis et al. | NeurIPS 2020 | 引用: 3500 | 开放获取
    摘要: We explore a general-purpose fine-tuning recipe...

#2  [76.1分] Chain-of-Thought Prompting Elicits Reasoning in LLMs
    Wei et al. | NeurIPS 2022 | 引用: 3241
    ...
```

---

## Step 7: User Decisions

User can now browse and decide:

- **查看更多**: `lr_paper_list(path="<project_path>", status="candidate", sort_by="citation_count", limit=20, offset=20)`
- **按不同方式排序**: `lr_paper_list(path="<project_path>", status="candidate", sort_by="year")` 或 sort_by="_score", "citation_count" 等
- **接受入库**: `lr_paper_accept(path="<project_path>", paper_ids=[...])` — 状态变为 in_library
- **排除**: `lr_paper_exclude(path="<project_path>", paper_id="...")` — 状态变为 excluded
- **调整权重重新评分**: `lr_score_config(path="<project_path>", weights={...})` 然后重新 `lr_score`
- **查看详情**: `lr_paper_detail(path="<project_path>", paper_id="...")`

Continue until user signals done.

> 提醒用户：所有搜索结果已持久化保存，可随时通过 `lr_paper_list(status="candidate")` 回来浏览。

---

## Step 8: Summary

Summarize the session:

```
本次搜索完成：
  检索: 143 篇（Semantic Scholar 50 + OpenAlex 50 + Snowball 43）
  去重后: 98 篇
  新增候选: 93 篇
  已接受入库: 12 篇
  已排除: 3 篇
  待审核: 78 篇候选

搜索会话已保存，可随时继续审核候选论文。
```

---

## Error Handling

- If a search source returns an error, report it and continue with other sources.
- If `lr_search_ingest` fails, fall back to calling `lr_dedup`, `lr_score`, `lr_paper_add_batch`, `lr_session_save` separately.
- If no results from any source, suggest: broaden query, remove year filters, or use `litreview-expand`.

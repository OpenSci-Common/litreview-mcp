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
See also `docs/search-factor-agent-guide.md` for the full factor type registry, query composition rules, and error handling.

---

## IMPORTANT: Path Rule

All litreview MCP tool calls MUST pass the `path` parameter as the **absolute path** of the user's current working directory. NEVER omit `path` or use the default `"."` — the default resolves to the MCP server's process directory, not the user's project.

Determine the user's project directory at the start (e.g. via `pwd`) and use it consistently for every `lr_*` call.

---

## IMPORTANT: Fewer Query Keywords = Better Results

**Do NOT combine too many query-type factors into a single search.** The more keywords in a query, the stricter the intersection against title + abstract, and the fewer results returned.

- **1–2 query factors per search** is ideal.
- If 3+ query factors are active, warn the user and suggest deactivating some or running separate searches.
- Use filter factors (year_range, field, venue, etc.) to narrow results — these don't reduce keyword matching.
- If a search returns 0 results, first try reducing active query factors.

---

## Step 1: Load and Present All Factors for Selection

Call `lr_factor_list` to retrieve all active search factors:

```
lr_factor_list(path="<project_path>", active_only=True)
```

If no active factors are found, tell the user:
> "尚未配置检索因子。请先运行「初始化litreview」或手动添加因子。"

**Present all active factors as a selectable list**, grouped by primary vs filter.

Primary factor types are: `query`, `keyword`, `method`, `author`, `venue`, `seed_paper`.
Filter factor types are: `field`, `year_range`, `pub_type`, `open_access`, `citation_min`, `institution`, `language`, `funder`.

Display format:

```
当前活跃的检索因子：
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
主检索因子:
  关键词类（每个单独搜索一轮）:
    [1] [query/topic]  "quantum error correction"
    [2] [method]       "surface codes"
    [3] [keyword]      "topological qubits"
  轴类（附加到每轮关键词搜索中）:
    [4] [author]       "John Preskill"
  种子论文类（独立轮次，使用引文/推荐 API）:
    [5] [seed_paper]   "Attention Is All You Need"

过滤因子（应用于所有搜索轮次）:
  [6] [field]        Physics
  [7] [year_range]   2022-2026
  [8] [pub_type]     Review

请选择本次搜索要使用的因子：
  • 输入编号，如 1,2,5,6
  • 输入「全部」使用所有因子（主因子将逐个搜索）
  • 输入「只用 1」只搜索第一个主因子
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Wait for user selection before proceeding.

---

## Step 2: Compose Query and Build Search Plan

First, call `lr_factor_compose_query` to get the deterministic factor-to-query mapping:

```
lr_factor_compose_query(path="<project_path>")
```

This returns `primary_queries`, `filters`, `factor_ids`, and `factor_roles`. Use this output to validate the factor types and filter parameters. Refer to `references/query-mapping.md` for the exact API parameter mapping of each filter type.

Then, based on the user's selection from Step 1, build the search plan.

**CRITICAL RULE: NEVER combine multiple keyword-type factors (query/keyword/method) into one search query.** Each keyword-type factor gets its own search round. However, `author` and `venue` factors CAN be added to a keyword round as narrowing parameters (they act as intersection filters within the same API call).

### Round construction logic

1. Group selected factors: keyword-type (`query`, `keyword`, `method`), axis-type (`author`, `venue`), filters (all others), and `seed_paper`.
2. Each keyword-type factor becomes one round. If `author`/`venue` factors are also selected, attach them to each keyword round as API parameters.
3. If only `author`/`venue` are selected (no keyword-type), each gets its own round.
4. Each `seed_paper` gets its own round (uses citation API, not keyword search).
5. All filter factors apply to every round.

### Search Round Plan

Example with query + query + author + filters:

```
检索计划（共 2 轮）：
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
第 1 轮: [query/topic] "quantum error correction"
  + author: "John Preskill"
  过滤: field=Physics, year=2022-2026
  数据源: Semantic Scholar + OpenAlex
  每源: 50 篇

第 2 轮: [method] "surface codes"
  + author: "John Preskill"
  过滤: field=Physics, year=2022-2026
  数据源: Semantic Scholar + OpenAlex
  每源: 50 篇
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
预计总检索: 最多 200 篇（去重后通常更少）
结果将自动去重合并。

确认执行？（可调整轮次、数据源或返回数量）
```

Wait for user confirmation. Allow adjustments (remove rounds, change limits, etc.).

---

## Step 3: Execute Searches Round by Round

Execute each search round sequentially. **Each round uses exactly ONE keyword-type factor, plus any selected author/venue as co-parameters, plus all selected filters.**

For each round:

### Keyword-type round (query/keyword/method), optionally with author/venue:
```
search_semantic(query="<keyword_value>", author="<author>", venue="<venue>", <filter_params>, max_results=50)
search_openalex(query="<keyword_value>", authorships_author_display_name="<author>", primary_location_source_display_name="<venue>", <filter_params>, max_results=50)
```
Omit `author`/`venue` params if those factors are not selected.

### Author-only round (when no keyword-type factor in this round):
```
search_semantic(author="<author_name>", <filter_params>, max_results=50)
search_openalex(authorships_author_display_name="<author_name>", <filter_params>, max_results=50)
```

### Venue-only round (when no keyword-type factor in this round):
```
search_semantic(venue="<venue_name>", <filter_params>, max_results=50)
search_openalex(primary_location_source_display_name="<venue_name>", <filter_params>, max_results=50)
```

### Seed-paper primary factor:

Ask user which direction to trace (if not already specified):
- `forward` — who cites this paper?
- `backward` — what does this paper cite?
- `both` — both directions (default if user has no preference)

```
snowball_search(paper_id=<seed_id>, direction="<forward|backward|both>", max_results_per_direction=30)
```

**After each round**, briefly report progress:
```
第 1/2 轮完成: [query/topic] "quantum error correction" + author: "John Preskill" → 获取 87 篇
第 2/2 轮完成: [method] "surface codes" + author: "John Preskill" → 获取 43 篇
全部轮次完成，共获取 130 篇原始结果，正在去重合并...
```

Collect all raw results from all rounds, then proceed to ingestion.

Refer to `references/query-mapping.md` for factor-to-API parameter mapping.

---

## Step 4: Ingest Results (Dedup + Score + Persist)

**This is the critical step.** After all rounds complete, call `lr_search_ingest` with the **combined raw results from ALL rounds**:

```
lr_search_ingest(
  path="<project_path>",
  raw_results=<combined_results_from_all_rounds>,
  input_factors=<all_selected_factor_ids>,
  api_queries=[
    {"api": "semantic_scholar", "query": "quantum error correction", "results_count": 50},
    {"api": "openalex", "query": "quantum error correction", "results_count": 50},
    {"api": "semantic_scholar", "query": "surface codes", "results_count": 43},
    ...
  ],
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

## Step 5: Show Ranked Results

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

## Step 6: User Decisions

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

## Step 7: Summary

Summarize the session:

```
本次搜索完成（共 2 轮）：
  第 1 轮 [query/topic] "quantum error correction" + author: "John Preskill" → 87 篇
  第 2 轮 [method] "surface codes" + author: "John Preskill"                 → 43 篇
  ────────────────────────────────
  原始总计: 130 篇
  去重后:   98 篇
  新增候选: 93 篇
  已接受入库: 15 篇
  已排除: 2 篇
  待审核: 76 篇候选

搜索会话已保存，可随时继续审核候选论文。
```

---

## Error Handling

- If a search source returns an error, report it and continue with other sources.
- If `lr_search_ingest` fails, fall back to calling `lr_dedup`, `lr_score`, `lr_paper_add_batch`, `lr_session_save` separately.
- If no results from any source, suggest: broaden query, remove year filters, or use `litreview-expand`.

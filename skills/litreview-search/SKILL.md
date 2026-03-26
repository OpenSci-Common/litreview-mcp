---
name: litreview-search
description: >
  Search and rank academic papers. Use when user says "搜索论文", "检索文献", "查找论文",
  "search papers", "find papers", "用这些关键词搜索", "开始搜索", "run search".
  Also trigger when search factors exist and user expresses search intent.
---

# litreview-search: Search and Rank Academic Papers

This skill executes a structured literature search using registered factors, deduplicates and scores results, and presents ranked papers for user decisions.

See `references/query-mapping.md` for factor-to-API parameter mapping details.

---

## IMPORTANT: Path Rule

All litreview MCP tool calls MUST pass the `path` parameter as the **absolute path** of the user's current working directory. NEVER omit `path` or use the default `"."` — the default resolves to the MCP server's process directory, not the user's project.

Determine the user's project directory at the start (e.g. via `pwd`) and use it consistently for every `lr_*` call.

---

## Step 1: Load Active Factors

Call `lr_factor_list` to retrieve all active search factors:

```
lr_factor_list(active_only=true)
```

If no active factors are found, tell the user:
> "尚未配置检索因子。请先运行「初始化litreview」或手动添加因子（例如：「添加检索因子 query: transformer」）。"

Group factors by type for use in the next step.

---

## Step 2: Compose Query Parameters

Call `lr_factor_compose_query` to generate optimized API query parameters from the active factors:

```
lr_factor_compose_query()
```

This returns a structured query plan with:
- Primary query string
- Author filters
- Venue/source filters
- Year range
- Seed papers for snowball search
- Recommended API endpoints

---

## Step 3: Show Query Plan for Confirmation

Before executing any searches, present the query plan to the user transparently:

```
即将执行以下检索计划：

主查询词: "large language model reasoning"
API 端点: Semantic Scholar, OpenAlex
过滤条件:
  - 年份: 2022-2024
  - 领域: artificial intelligence
  - 会议: NeurIPS
每个来源返回数量: 50 篇

是否确认执行？（可调整参数或添加/移除来源）
```

Wait for user confirmation. Allow user to:
- Confirm and proceed
- Adjust result count per source
- Add or remove API endpoints
- Modify query string

---

## Step 4: Execute Searches

Based on the confirmed plan, call the paper-search MCP tools. Run searches in parallel where possible.

**Semantic Scholar search:**
```
search_semantic(
  query="<primary_query>",
  limit=50,
  year=<year_range>,
  fields_of_study=<field_list>
)
```

**OpenAlex search:**
```
search_openalex(
  query="<primary_query>",
  limit=50,
  publication_year=<year_range>,
  primary_topic=<field>
)
```

**Snowball search** (only if `seed_paper` factors exist):
```
snowball_search(
  paper_id=<seed_doi_or_id>,
  direction="both",
  limit=30
)
```

Refer to `references/query-mapping.md` for the full mapping of factor types to API parameters.

Inform the user of progress: "正在检索 Semantic Scholar... 正在检索 OpenAlex..."

---

## Step 5: Deduplicate Results

Combine all results from all sources and call `lr_dedup` to remove duplicate papers:

```
lr_dedup(papers=<combined_results>)
```

Report deduplication statistics:
> "共检索到 143 篇论文（Semantic Scholar: 50, OpenAlex: 50, Snowball: 43），去重后保留 98 篇。"

---

## Step 6: Score and Rank

Call `lr_score` to score and rank all deduplicated papers against the active factors and scoring weights:

```
lr_score(papers=<deduped_results>)
```

This returns papers sorted by composite score with individual dimension scores.

---

## Step 7: Show Ranked Results

Present the top results in a readable format. Show at minimum the top 20 papers:

```
检索结果（共 98 篇，按相关性排序）：

#1  [总分 0.92] Reasoning with Language Model Prompting: A Survey
    作者: Shuofei Qiao et al. | 来源: arXiv 2023 | 引用: 412
    相关性: 0.95 | 时效性: 0.88 | 引用量: 0.90
    摘要: This paper surveys...

#2  [总分 0.87] Chain-of-Thought Prompting Elicits Reasoning in LLMs
    作者: Jason Wei et al. | 来源: NeurIPS 2022 | 引用: 3241
    ...
```

After displaying results, offer options:
- "加入文献库" — add selected papers
- "排除某篇" — exclude a paper
- "调整权重后重新评分" — adjust weights and re-score
- "查看完整摘要" — read full abstract of a paper

---

## Step 8: Wait for User Decisions

Process user decisions interactively:

- **Add paper(s)**: Call `lr_paper_add` or hand off to `litreview-library` skill
- **Exclude paper**: Call `lr_factor_add(type="exclude", value=<paper_id>)` to blacklist
- **Adjust weights**: Call `lr_config(scoring_weights={...})` then re-run `lr_score`
- **View details**: Call `read_semantic_paper` or `read_openalex_paper` for full metadata

Continue until user signals they are done (e.g., "保存会话", "结束搜索", "好了").

---

## Step 9: Save Session

Call `lr_session_save` to record the search session for future reference:

```
lr_session_save(
  query_plan=<composed_params>,
  result_count=<total>,
  added_count=<added>,
  excluded_count=<excluded>
)
```

Confirm to user:
> "会话已保存。共添加 12 篇论文到文献库，排除 3 篇。可随时继续检索或扩展关键词。"

---

## Error Handling

- If `search_semantic` or `search_openalex` returns an error, report it and continue with available results from other sources.
- If `lr_dedup` fails, proceed with combined results and warn about potential duplicates.
- If `lr_score` fails, display unranked results with a warning.
- If no results are returned from any source, suggest: broadening the query, removing year filters, or running `litreview-expand` to discover alternative keywords.

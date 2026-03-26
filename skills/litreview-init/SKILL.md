---
name: litreview-init
description: >
  Initialize a literature review workspace and manage search factors. Use when user says "新建文献调研", "开始文献检索",
  "初始化litreview", "创建调研项目", "lit review setup", "start literature review",
  "new research project". Also use when user wants to manage search factors: "添加因子", "删除因子",
  "查看因子", "修改因子", "add factor", "list factors", "remove factor", "edit factors",
  "管理检索因子", "因子管理". Proactively suggest when user describes a research topic
  but no .litreview/ directory exists.
---

# litreview-init: Initialize Workspace & Manage Search Factors

See `docs/search-factor-agent-guide.md` for the full factor type registry, query composition rules, and error handling.

This skill covers two workflows:
1. **Initialize** — create a new workspace and extract initial search factors from the user's research topic
2. **Factor Management** — CRUD operations on search factors (add, list, edit, activate/deactivate, delete)

---

## IMPORTANT: Path Rule

All litreview MCP tool calls MUST pass the `path` parameter as the **absolute path** of the user's current working directory. NEVER omit `path` or use the default `"."` — the default resolves to the MCP server's process directory, not the user's project.

Determine the user's project directory at the start (e.g. via `pwd`) and use it consistently:

```
lr_init(path="/absolute/path/to/user/project")
lr_factor_add(path="/absolute/path/to/user/project", ...)
lr_status(path="/absolute/path/to/user/project")
```

---

## IMPORTANT: Search Principle — Fewer Query Keywords = Better Results

**Do NOT combine too many query-type factors into a single search.** Academic search APIs match ALL keywords against title + abstract simultaneously. The more keywords you add, the stricter the intersection, and the fewer results you get.

Guidelines:
- **1–2 query factors per search** is ideal. Each query should be a concise phrase (1–5 words).
- If the user has many topics, **keep them as separate factors and run separate searches** for each, then merge results. Do NOT concatenate them into one giant query.
- Use **filter factors** (year_range, field, venue, etc.) to narrow results — filters restrict the result set without reducing keyword matches.
- If a search returns 0 results, the first thing to try is reducing the number of active query factors.

> 原则：关键词越多，结果越少。每次搜索建议只激活 1–2 个查询因子，用过滤因子来缩小范围。多个主题应分批搜索后合并。

---

# Part A: Initialize Workspace

## Step 1: Create Workspace

Call `lr_init` to initialize the `.litreview/` directory structure in the current working directory.

```
lr_init()
```

Expected output: workspace path and confirmation message. If the workspace already exists, notify the user and ask whether to proceed (it may reset config).

---

## Step 2: Gather Research Topic

Ask the user to describe their research topic in natural language. Prompt example:

> "请描述你的研究主题：你想调研什么领域？关注哪些方法、问题或作者？有没有特定时间段或发表场所（期刊/会议）？"

Wait for the user's response before proceeding.

---

## Step 3: Analyze Topic and Extract Search Factors

Analyze the user's description and extract structured search factors. Refer to the **Factor Type Reference** section below for full details on each type.

### Factor Categories at a Glance

Factors are divided into two categories:

**Primary factors** (can independently trigger a search — at least one required):

| Type         | Description                          | Example                          |
|--------------|--------------------------------------|----------------------------------|
| `query`      | Core keyword or concept (sub_type: topic/method/concept) | "transformer attention mechanism"|
| `keyword`    | Supplementary keyword (appended to query) | "few-shot learning"          |
| `method`     | Specific technique (appended to query) | "retrieval-augmented generation"|
| `author`     | Target researcher                    | "Yoshua Bengio"                  |
| `venue`      | Journal or conference                | "NeurIPS", "Nature"              |
| `seed_paper` | Known paper for citation tracing     | DOI or title of a paper          |

> Note: `query`, `keyword`, and `method` are all keyword-search types — they map to the `query` parameter in search APIs. The distinction is semantic (helps organize your factors). Each still gets its own search round.

**Filter factors** (must combine with at least one primary — narrows results):

| Type         | Description                          | Example                          |
|--------------|--------------------------------------|----------------------------------|
| `field`      | Academic discipline                  | "Computer Science"               |
| `year_range` | Publication year window              | "2022-2026"                      |
| `pub_type`   | Publication format                   | "Review", "Conference"           |
| `open_access`| Only open-access papers              | true                             |
| `citation_min`| Minimum citation count              | 50                               |
| `institution`| Author affiliation (OpenAlex only)   | "MIT"                            |
| `language`   | Paper language (OpenAlex only)       | "en"                             |
| `funder`     | Funding agency (OpenAlex only)       | "NSF"                            |

Extract as many relevant factors as possible. Be generous — it is better to propose more and let the user trim.

When presenting extracted factors, **group by category** and briefly explain what each does if the user is unfamiliar:

```
从你的描述中，我提取到以下检索因子：

━━━ 主检索因子（Search Subjects）━━━
  1. [query/topic]  "large language model reasoning"
     → 搜索标题和摘要中包含此关键词的论文
  2. [method] "chain-of-thought prompting"
     → 搜索标题和摘要中包含此方法的论文

━━━ 过滤因子（Filters）━━━
  3. [field]        "artificial intelligence"
     → 限定在此学科领域内
  4. [year_range]   "2022-2026"
     → 限定发表时间范围

请确认这些因子是否正确，或告诉我需要添加、修改、删除哪些。
💡 提示：主检索因子建议不超过 2 个，多个主题可以分批搜索。
```

---

## Step 4: Explain Factor Types on Demand

If the user asks "这些类型是什么意思？", "explain factors", "有哪些因子类型？", or "给我看个例子", provide explanations using the templates below. You do NOT need to explain all types unprompted — only explain when the user asks, or briefly annotate unfamiliar types in the extraction output.

### User-Facing Explanation Templates

Use these templates when the user asks about a specific factor type:

- **query**: "这个关键词会在论文标题和摘要中搜索匹配。建议每个 query 控制在 1–5 个词，过长的查询会导致结果过少。"
- **author**: "会先在学术数据库中识别该研究者，然后检索其发表的所有论文。如果同名作者较多，系统会列出候选供你选择。"
- **venue**: "限定在特定期刊或会议中搜索。可以单独使用来浏览某个期刊的论文，也可以和关键词组合使用。"
- **seed_paper**: "不使用关键词搜索，而是以你选定的论文为起点，追踪其引用网络或发现相似论文。这是发现关键词搜索无法找到的论文的最佳方式。支持三种模式：向前引用（谁引用了它）、向后引用（它引用了谁）、推荐（相似论文）。"
- **field**: "将结果限定在特定学科下。当某个关键词在不同领域有不同含义时特别有用。"
- **year_range**: "限定发表时间范围。格式：'2020-2024'、'2023-'（2023至今）、'2024'（仅2024年）。"
- **pub_type**: "按出版类型过滤。提示：先搜索 Review 类型是快速了解新领域的好方法。"
- **open_access**: "启用后，只返回有免费全文 PDF 的论文。"
- **citation_min**: "设置最低引用次数。注意：这会排除尚未积累引用的新论文，建议同时运行一次不带此过滤器的搜索。"
- **institution**: "按作者所属机构过滤。⚠️ 仅 OpenAlex 支持，Semantic Scholar 结果不受此过滤。"
- **language**: "按论文语言过滤（如 'en', 'zh'）。⚠️ 仅 OpenAlex 支持。"
- **funder**: "按资助机构过滤（如 'NSF', 'ERC'）。⚠️ 仅 OpenAlex 支持。"

### Example Scenarios (show when user asks for examples)

**Example 1: Exploring a new research topic**
```
主检索因子:
  [query/topic] "retrieval augmented generation"
过滤因子:
  [field] "Computer Science"
  [year_range] "2023-2026"
→ 搜索计算机科学领域 2023 年以来关于 RAG 的论文
```

**Example 2: Following a specific researcher**
```
主检索因子:
  [author] "Patrick Lewis"
过滤因子:
  [year_range] "2020-2026"
→ 检索 Patrick Lewis 在 2020 年后发表的所有论文
```

**Example 3: Survey-style broad review**
```
主检索因子:
  [query/topic] "large language model"
过滤因子:
  [pub_type] "Review"
  [year_range] "2023-2026"
  [citation_min] 20
→ 搜索 2023 年以来关于 LLM 的综述文章（至少 20 次引用）
```

**Example 4: Citation tracing from a key paper**
```
主检索因子:
  [seed_paper] "Attention Is All You Need" (mode: forward)
过滤因子:
  [field] "Computer Science"
  [year_range] "2023-2026"
→ 追踪引用了 "Attention Is All You Need" 的近期论文
```

---

## Step 5: User Confirmation and Modification

Present the extracted factors list and wait for the user to:
- Confirm all factors as-is
- Request additions, removals, or edits
- Ask for explanations of factor types (use templates above)

Incorporate any feedback and re-present if significant changes were made.

---

## Step 6: Register Confirmed Factors

For each confirmed factor, call `lr_factor_add`. Use appropriate `query_role`:
- Primary factors: `query_role="primary"` (or `"must"` / `"should"` for query weight distinction)
- Filter factors: `query_role="filter"`

```
lr_factor_add(type="query", value="large language model reasoning", query_role="primary", sub_type="topic")
lr_factor_add(type="query", value="chain-of-thought prompting", query_role="primary", sub_type="method")
lr_factor_add(type="field", value="artificial intelligence", query_role="filter")
lr_factor_add(type="year_range", value="2022-2026", query_role="filter")
```

Notes:
- For `query` type, set `sub_type` to `"topic"`, `"method"`, or `"concept"` to help organize factors.
- Seed papers should be registered with type `seed_paper` and the paper's DOI or title as value.
- Call factors one by one; handle any errors before proceeding.

---

## Step 7: Set Default Scoring Weights

Call `lr_config` to establish default scoring weights for the project:

```
lr_config(path="<project_path>", key="scoring_weights", value={
  "relevance": 0.4,
  "recency": 0.2,
  "citation_count": 0.2,
  "venue_prestige": 0.1,
  "author_match": 0.1
})
```

Inform the user these weights can be adjusted at any time during the search workflow.

---

## Step 8: Show Initialization Summary

Call `lr_status` to display the current workspace state:

```
lr_status()
```

Present the summary including:
- Factor count grouped by category (primary vs filter)
- Scoring configuration
- Reminder about the "fewer keywords" principle
- Suggested next step: run `litreview-search` to begin searching

Example closing message:
```
初始化完成！

已注册检索因子：
  主检索因子: 2 个 (query × 2)
  过滤因子:   2 个 (field × 1, year_range × 1)

💡 搜索时建议每次只激活 1–2 个主检索因子。多个主题分批搜索效果更好。

接下来可以开始检索论文，请说「开始搜索」或「搜索论文」。
也可以随时说「查看因子」或「管理因子」来调整检索因子。
```

---

# Part B: Search Factor Management (CRUD)

Use these operations when the user wants to manage factors outside of initialization. The workspace must already exist (`.litreview/` directory present).

---

## Operation: List Factors

Triggered by: "查看因子", "列出因子", "list factors", "show factors", "因子列表"

Call `lr_factor_list` and present grouped by category:

```
lr_factor_list(path="<project_path>")
```

Display format:

```
当前检索因子：
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
主检索因子（Search Subjects）:
  1. ✅ [query/topic]  "RAG optimization"           (sf_a1b2c3d)
  2. ✅ [method] "dense passage retrieval"     (sf_e4f5g6h)
  3. ❌ [author]       "Patrick Lewis"               (sf_i7j8k9l)  ← 已停用

过滤因子（Filters）:
  4. ✅ [field]        Computer Science              (sf_m1n2o3p)
  5. ✅ [year_range]   2022-2026                     (sf_q4r5s6t)
  6. ❌ [citation_min] 50                            (sf_u7v8w9x)  ← 已停用
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ = 活跃（下次搜索会使用）  ❌ = 停用（保留但不参与搜索）
```

To list only a specific type:
```
lr_factor_list(path="<project_path>", type="query")
lr_factor_list(path="<project_path>", type="author")
```

To list only active factors:
```
lr_factor_list(path="<project_path>", active_only=true)
```

---

## Operation: Add Factor

Triggered by: "添加因子", "add factor", "新增关键词", "加个过滤条件"

1. Determine the factor type and value from the user's request (or ask if unclear)
2. Validate: non-empty value, correct type, check for duplicates
3. For types requiring ID resolution (author, venue, institution, funder): inform user that IDs will be resolved when search executes
4. If the user is unfamiliar with factor types, use the explanation templates from Step 4
5. Register via `lr_factor_add`

```
lr_factor_add(path="<project_path>", type="query", value="prompt engineering", query_role="primary", sub_type="method")
```

After adding, confirm:
> "已添加 [method] 'prompt engineering'。当前共有 N 个活跃主检索因子、M 个过滤因子。"

**Warning if too many primary query factors are active:**
If the user has 3+ active query-type factors after adding, warn:
> "⚠️ 当前有 N 个活跃的查询因子。关键词越多，搜索结果越少。建议搜索时只激活其中 1–2 个，或分批搜索。"

---

## Operation: Activate / Deactivate Factor

Triggered by: "停用因子", "激活因子", "deactivate", "activate", "暂时不用这个"

```
lr_factor_toggle(path="<project_path>", factor_id="sf_xxx", active=false)
lr_factor_toggle(path="<project_path>", factor_id="sf_xxx", active=true)
```

Confirm:
> "因子 [type] 'value' 已停用，下次搜索将不包含此因子。"
> "因子 [type] 'value' 已激活，下次搜索将包含此因子。"

---

## Operation: Delete Factor

Triggered by: "删除因子", "remove factor", "去掉这个因子"

```
lr_factor_remove(path="<project_path>", factor_id="sf_xxx")
```

**Before deleting, confirm with user** — deletion is permanent (deactivation is reversible):
> "确认删除 [type] 'value'？如果只是暂时不用，可以选择停用而非删除。"

After deletion:
1. If the factor had `provenance="promoted_from_content"`, reset the corresponding content factors' `promoted` field back to `false` so they can be re-promoted later.
2. Historical search sessions referencing this factor are NOT modified (they store factor snapshots).
> "已删除因子 [type] 'value'。"

---

## Operation: Edit Factor

There is no direct edit API. To modify a factor's value:
1. Delete the old factor: `lr_factor_remove`
2. Add the new factor: `lr_factor_add`

Inform the user:
> "因子不支持直接修改。我会先删除旧因子，再添加修改后的版本。"

---

## Operation: Promote Content Factor to Search Factor

Triggered by: "提升内容因子", "promote content factor", "把这个作者加为检索因子"

Content factors are automatically extracted from papers in the library (authors, venues, fields). High-frequency content factors can be promoted to search factors.

1. Query high-frequency content factors:
```
lr_content_query(path="<project_path>", aggregate="count", min_count=3)
```

2. Present top candidates by frequency:
```
高频内容因子（出现在 3+ 篇论文中）：
  1. [author] "Yoshua Bengio"    — 出现在 5 篇论文中
  2. [venue]  "NeurIPS"          — 出现在 4 篇论文中
  3. [field]  "Machine Learning"  — 出现在 3 篇论文中

是否要将其中某个提升为检索因子？
```

3. Promote selected factor:
```
lr_content_promote(path="<project_path>", type="author", value="Yoshua Bengio")
```

This creates a new search factor with `provenance="promoted_from_content"` and marks the original content factors as `promoted=true`.

After promotion:
> "已将 [author] 'Yoshua Bengio' 提升为检索因子。该作者出现在你文献库的 5 篇论文中。"

---

## Operation: Explain Factor Types

Triggered by: "因子类型有哪些", "explain factor types", "有什么过滤条件", "能过滤什么"

Present the full factor category table from Step 3 (Factor Categories at a Glance), then offer to show examples:
> "需要看具体的使用示例吗？"

If yes, show the example scenarios from Step 4 (Explain Factor Types on Demand).

---

## Error Handling

- If `lr_init` fails because the directory already exists, ask: "工作区已存在，是否重新配置因子？（现有数据将保留）"
- If `lr_factor_add` fails for any factor, report the error, skip that factor, and continue with the rest.
- If `lr_factor_add` returns `duplicate: true`, inform user: "此因子已存在，无需重复添加。"
- If `lr_config` fails, warn the user that default weights could not be set; they can be configured manually later.
- If user tries to search with only filter factors and no primary factor, block and explain: "过滤因子不能独立搜索，需要至少一个主检索因子（query、author、venue 或 seed_paper）。"

---
name: litreview-init
description: >
  Initialize a literature review workspace. Use when user says "新建文献调研", "开始文献检索",
  "初始化litreview", "创建调研项目", "lit review setup", "start literature review",
  "new research project". Also proactively suggest when user describes a research topic
  but no .litreview/ directory exists.
---

# litreview-init: Initialize a Literature Review Workspace

This skill sets up a new literature review project by creating a workspace, extracting search factors from the user's research topic, and configuring initial scoring weights.

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

Analyze the user's description and extract structured search factors. Factor types supported by litreview:

| Factor Type  | Description                              | Example                          |
|--------------|------------------------------------------|----------------------------------|
| `query`      | Core keyword or concept query            | "transformer attention mechanism" |
| `field`      | Academic field or sub-domain             | "natural language processing"    |
| `method`     | Specific technique or methodology        | "retrieval-augmented generation" |
| `author`     | Target author(s) to include              | "Yann LeCun"                     |
| `venue`      | Target journal or conference             | "NeurIPS", "ACL", "Nature"       |
| `year_range` | Publication year filter                  | "2020-2024"                      |
| `seed_paper` | Known paper to use as citation seed      | DOI or title                     |
| `keyword`    | Supplementary keyword                    | "few-shot learning"              |

Extract as many relevant factors as possible. Be generous — it is better to propose more factors and let the user trim them than to miss important ones.

Present the extracted factors clearly, for example:

```
从你的描述中，我提取到以下检索因子：

1. [query] "large language model reasoning"
2. [field] "artificial intelligence"
3. [method] "chain-of-thought prompting"
4. [method] "in-context learning"
5. [year_range] "2022-2024"
6. [venue] "NeurIPS"

请确认这些因子是否正确，或告诉我需要添加、修改、删除哪些。
```

---

## Step 4: User Confirmation and Modification

Present the extracted factors list and wait for the user to:
- Confirm all factors as-is
- Request additions, removals, or edits
- Provide additional context

Incorporate any feedback and re-present if significant changes were made.

---

## Step 5: Register Confirmed Factors

For each confirmed factor, call `lr_factor_add`:

```
lr_factor_add(type="query", value="large language model reasoning", weight=1.0)
lr_factor_add(type="field", value="artificial intelligence", weight=0.8)
lr_factor_add(type="method", value="chain-of-thought prompting", weight=0.9)
lr_factor_add(type="method", value="in-context learning", weight=0.9)
lr_factor_add(type="year_range", value="2022-2024", weight=0.7)
lr_factor_add(type="venue", value="NeurIPS", weight=0.6)
```

Notes:
- `weight` reflects the factor's importance to scoring (0.0–1.0). Use judgment based on user emphasis.
- Seed papers should be registered with type `seed_paper` and the paper's DOI or title as value.
- Call factors one by one; handle any errors before proceeding.

---

## Step 6: Set Default Scoring Weights

Call `lr_config` to establish default scoring weights for the project:

```
lr_config(
  scoring_weights={
    "relevance": 0.4,
    "recency": 0.2,
    "citation_count": 0.2,
    "venue_prestige": 0.1,
    "author_match": 0.1
  }
)
```

Inform the user these weights can be adjusted at any time during the search workflow.

---

## Step 7: Show Initialization Summary

Call `lr_status` to display the current workspace state:

```
lr_status()
```

Present the summary to the user, including:
- Number of registered factors
- Scoring configuration
- Suggested next step: run `litreview-search` to begin searching

Example closing message:
> "初始化完成！已注册 6 个检索因子。接下来可以开始检索论文，请说「开始搜索」或「搜索论文」。"

---

## Error Handling

- If `lr_init` fails because the directory already exists, ask: "工作区已存在，是否重新配置因子？（现有数据将保留）"
- If `lr_factor_add` fails for any factor, report the error, skip that factor, and continue with the rest.
- If `lr_config` fails, warn the user that default weights could not be set; they can be configured manually later.

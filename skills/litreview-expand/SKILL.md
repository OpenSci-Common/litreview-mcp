---
name: litreview-expand
description: >
  Expand search and discover related papers. Use when user says "扩展关键词", "引文追踪",
  "谁引用了这篇", "这篇引用了谁", "找相似论文", "推荐论文", "expand keywords",
  "trace citations", "find similar", "who cited this". Also proactively suggest after
  new papers are added to library.
---

# litreview-expand: Expand Search and Discover Related Papers

This skill offers three complementary expansion methods: semantic keyword expansion (analyzing abstracts to propose new factors), citation tracking (snowball search from seed papers), and content factor promotion (surfacing high-frequency concepts from library abstracts).

See `references/expansion-prompts.md` for the abstract analysis prompt template.

---

## IMPORTANT: Path Rule

All litreview MCP tool calls MUST pass the `path` parameter as the **absolute path** of the user's current working directory. NEVER omit `path` or use the default `"."` — the default resolves to the MCP server's process directory, not the user's project.

Determine the user's project directory at the start (e.g. via `pwd`) and use it consistently for every `lr_*` call.

---

## Determine Expansion Mode

At skill entry, determine which sub-workflow to use based on the user's intent:

| User Says | Mode |
|-----------|------|
| "扩展关键词", "推荐新关键词", "expand keywords" | Semantic Expansion |
| "引文追踪", "谁引用了这篇", "这篇引用了谁", "trace citations", "who cited this" | Citation Tracking |
| "找高频概念", "提升内容因子", "content factors", "high-frequency terms" | Content Factor Promotion |
| "找相似论文", "find similar" | Either Citation Tracking or Semantic Expansion |

If unclear, present the three options and ask the user which approach they prefer.

---

## Sub-Workflow A: Semantic Expansion

Analyze library papers' abstracts to extract new concepts and propose additional search factors. **The user chooses which papers to use as "seeds" — never auto-select without confirmation.**

### A1: Retrieve Library Papers

```
lr_paper_list(path="<project_path>", status="in_library", sort_by="citation_count")
```

If fewer than 3 papers in library, suggest adding more first.

### A2: Present Seed Candidates with Expansion Potential

Evaluate each paper's "seed value" based on:
- **Abstract richness**: length and information density (longer, method-heavy abstracts yield more concepts)
- **Citation impact**: highly cited papers tend to define key terminology
- **Novelty**: papers with concepts NOT already in the factor list are more valuable

Present candidates with your recommendation and reasoning:

```
文献库共 15 篇论文。以下是语义扩展种子候选：

推荐种子（摘要信息量大，包含尚未覆盖的概念）：
  #1  RAG for Knowledge Tasks (Lewis 2020)
      摘要 312 词 | 引用 3500 | 含方法论述语: dense retrieval, knowledge grounding
  #4  Chain-of-Thought Prompting (Wei 2022)
      摘要 280 词 | 引用 3241 | 含新概念: few-shot reasoning, step-by-step
  #7  Constitutional AI (Bai 2022)
      摘要 256 词 | 引用 890 | 含新方向: AI alignment, RLHF critique

扩展价值较低（摘要过短或概念已被现有因子覆盖）：
  #2  Attention Is All You Need — 摘要仅 80 词
  #5  BERT — 概念已在因子库中（transformer, pre-training）
  ...

请选择用作种子的论文（输入编号，如 "1,4,7" 或 "全部推荐"）：
```

### A3: User Confirms Seeds

Wait for the user to confirm or adjust the seed selection. Proceed ONLY after confirmation.

### A4: Analyze Seed Abstracts for New Concepts

Retrieve full abstracts for selected seeds:
```
lr_paper_detail(path="<project_path>", paper_id=<id>)
```

Use the prompt template from `references/expansion-prompts.md` to analyze.

Also retrieve current factors to avoid duplicates:
```
lr_factor_list(path="<project_path>", active_only=true)
```

Key analysis goals:
- Identify recurring technical terms and methodologies NOT yet in factor list
- Find related sub-fields or adjacent research areas
- Note frequently co-cited techniques or datasets
- Detect emerging terminology representing the field's frontier

### A5: Propose New Factors with Rationale

Present proposed factors, linking each back to the seed paper(s) that inspired it:

```
基于 3 篇种子论文的摘要分析，建议添加以下新检索因子：

1. [method] "dense passage retrieval" — 来自 #1 RAG 论文，核心检索技术
2. [method] "knowledge grounding" — 来自 #1，将检索结果融入生成的方法
3. [concept] "few-shot reasoning" — 来自 #4 CoT 论文，新兴推理范式
4. [concept] "AI alignment" — 来自 #7 Constitutional AI，安全研究方向
5. [keyword] "RLHF critique" — 来自 #7，具体对齐技术

请选择要添加的因子（输入编号，或「全部添加」，或「跳过」）：
```

### A6: Register Selected Factors

For each selected factor:
```
lr_factor_add(path="<project_path>", type="method", value="dense passage retrieval", query_role="primary", provenance="ai_suggested")
```

After registration:
> "已添加 4 个新检索因子。是否立即用新因子重新检索？（说「开始搜索」）"

---

## Sub-Workflow B: Citation Tracking

Perform forward and backward citation search from a seed paper.

### B1: Identify Seed Paper

Ask the user to specify a paper, or offer to use a recently added paper:

> "请指定要追踪引用的论文（可提供标题、DOI 或文献库编号）。"

Retrieve its details:
```
lr_paper_detail(paper_id=<lr_id>)
```

Extract the DOI or Semantic Scholar ID for the snowball search.

### B2: Choose Citation Direction

Ask or infer the direction:
- "谁引用了这篇" → `direction="forward"` (papers that cite this)
- "这篇引用了谁" → `direction="backward"` (papers this cites)
- "找相似" / general → `direction="both"`

### B3: Execute Snowball Search

```
snowball_search(
  paper_id="<doi_or_semantic_id>",
  direction="<forward|backward|both>",
  limit=50
)
```

Report progress: "正在追踪「<title>」的引用关系..."

### B4: Deduplicate Against Library

Remove papers already in the library:
```
lr_dedup(papers=<snowball_results>)
```

Report:
> "发现 47 篇相关论文，其中 12 篇已在文献库中，新增 35 篇候选。"

### B5: Score and Rank New Candidates

```
lr_score(papers=<new_candidates>)
```

### B6: Present Results

Display ranked new candidates and wait for user decisions (add/exclude). Use the same display format as `litreview-search` Step 7.

---

## Sub-Workflow C: Content Factor Promotion

Surface high-frequency concepts extracted from library abstracts and promote them to search factors.

### C1: Query Content Factors with Frequency Aggregation

```
lr_content_query(aggregate="count", min_frequency=3)
```

This returns terms extracted from library paper abstracts, sorted by frequency of occurrence across papers.

### C2: Filter Against Existing Factors

Retrieve active factors and remove any already registered:
```
lr_factor_list(active_only=true)
```

Exclude content factors that are already registered as search factors.

### C3: Present High-Frequency Terms

Show the top content factors by frequency:

```
文献库高频内容因子（出现在多篇论文摘要中）:

频次  概念/术语
---  --------
 12  "instruction tuning"         [尚未注册为检索因子]
  9  "RLHF"                       [已注册]
  8  "alignment"                  [尚未注册为检索因子]
  7  "constitutional AI"          [尚未注册为检索因子]
  6  "red teaming"                [尚未注册为检索因子]
  5  "scaling laws"               [已注册]

选择要提升为检索因子的术语（输入编号列表，或「全部未注册的」）：
```

### C4: Promote Selected Terms to Factors

For each user-selected term, call `lr_content_promote`:

```
lr_content_promote(
  content_factor="instruction tuning",
  factor_type="method",
  weight=0.75
)
```

Confirm each promotion:
> "已将「instruction tuning」提升为 method 类检索因子（权重 0.75）。"

### C5: Suggest Next Search

After promoting factors, ask:
> "已添加 3 个新检索因子。是否立即以新因子重新检索？"

---

## Proactive Suggestion (Post-Add Trigger)

After the `litreview-library` skill adds new papers, proactively suggest expansion:

> "已添加 5 篇新论文到文献库。建议运行以下扩展操作：
> - 「扩展关键词」— 分析摘要发现新研究方向
> - 「引文追踪」— 追踪某篇论文的引用关系
>
> 是否现在运行？"

Only suggest this once per batch addition, not repeatedly.

---

## Error Handling

- If `lr_paper_list` returns fewer than 3 papers, warn that semantic expansion may be low quality and suggest adding more papers first.
- If `snowball_search` fails or returns empty, check if the DOI/ID is valid; suggest trying `read_semantic_paper` first to confirm paper identity.
- If `lr_content_query` returns no results, inform that content extraction has not run yet; suggest running `lr_content_extract` on existing papers.
- If `lr_factor_add` fails (duplicate), skip silently and continue with remaining factors.

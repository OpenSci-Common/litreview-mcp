---
name: litreview-library
description: >
  Manage your literature library. Use when user says "加入文献库", "添加论文", "排除这篇",
  "查看文献库", "文献库状态", "下载PDF", "管理文献", "add to library", "show my papers",
  "library status", "download pdf", "read this paper",
  "导入文献", "导入DOI", "导入BibTeX", "import papers", "import doi", "import bibtex",
  "从Zotero导入", "批量导入", "我有一批DOI".
---

# litreview-library: Manage Your Literature Library

This skill handles three workflows: **adding** papers from search results, **importing** papers from external sources (DOI, BibTeX, RIS), and **browsing** the existing library.

---

## IMPORTANT: Path Rule

All litreview MCP tool calls MUST pass the `path` parameter as the **absolute path** of the user's current working directory. NEVER omit `path` or use the default `"."` — the default resolves to the MCP server's process directory, not the user's project.

Determine the user's project directory at the start (e.g. via `pwd`) and use it consistently for every `lr_*` call.

---

## Determine Intent

At skill entry, determine which sub-workflow applies:

- **Add workflow**: "加入文献库", "添加论文", "add to library", "收录这篇", "接受候选论文"
- **Import workflow**: "导入文献", "导入DOI", "导入BibTeX", "import papers", "我有一批DOI", "从Zotero导入", "导入RIS", "批量导入"
- **Browse workflow**: "查看文献库", "文献库状态", "show my papers", "library status", "有哪些论文", "查看详情"

If ambiguous, ask:
> "你想做什么？\n1. 从搜索结果中添加论文\n2. 从外部导入（DOI/BibTeX/RIS）\n3. 浏览现有文献库"

---

## Sub-Workflow A: Add Papers (from search results)

### A1: Identify Papers to Add

Determine the paper(s) to add from context:
- From search candidates: `lr_paper_list(path="<project_path>", status="candidate")`
- User references a number, title, or paper_id

### A2: Accept into Library

```
lr_paper_accept(path="<project_path>", paper_ids=["<id1>", "<id2>", ...])
```

This changes status from "candidate" to "in_library".

### A3: Extract Content Factors

```
lr_content_extract(path="<project_path>", paper_ids=["<id1>", "<id2>"])
```

### A4: Optional PDF Download

```
download_with_fallback(source="semantic", paper_id="<id>", doi="<doi>", save_path="<project_path>/.litreview/pdfs/")
```

### A5: Show Result

```
已入库 5 篇论文:
  #1 Attention Is All You Need (Vaswani et al., 2017)
  #2 BERT: Pre-training of Deep Bidirectional Transformers (Devlin et al., 2019)
  ...
提取了 23 个内容因子（8 位作者、3 个期刊、12 个领域标签）
```

---

## Sub-Workflow B: Import from External Sources

### B1: Determine Import Source

Ask or detect from context:
- **Single DOI**: user gives one DOI like "10.1038/s41586-021-03819-2"
- **DOI list**: user gives multiple DOIs (pasted, or in a file)
- **BibTeX file**: user provides a .bib file path or pastes BibTeX content
- **RIS file**: user provides a .ris file path
- **Paper URL**: user gives an arxiv/semantic scholar/doi.org URL
- **Paper title**: user gives a title to search

### B2: Import by DOI(s)

**Single DOI:**
1. Call paper-search to fetch full metadata:
```
get_crossref_paper_by_doi(doi="<doi>")
```
2. Store with full metadata:
```
lr_paper_add(path="<project_path>", paper_data=<crossref_result>)
```
3. Extract content factors:
```
lr_content_extract(path="<project_path>", paper_id="<paper_id>")
```

**Multiple DOIs:**
1. For each DOI, call `get_crossref_paper_by_doi` to fetch metadata
2. Batch store:
```
lr_paper_add_batch(path="<project_path>", papers=<enriched_papers>)
```
3. Batch extract:
```
lr_content_extract(path="<project_path>", paper_ids=[...])
```

Report:
> "已导入 15 篇论文（3 篇重复已跳过）。提取了 67 个内容因子。"

### B3: Import from BibTeX

1. Read the .bib file content (use Read tool if user gives a file path)
2. Call:
```
lr_import_bibtex(path="<project_path>", bibtex_content="<file_content>")
```
3. For each imported paper that has a DOI, enrich with full metadata:
```
get_crossref_paper_by_doi(doi="<doi>")
```
Then update the record (call `lr_paper_add` which will detect duplicate and skip, or the Skill can update fields).
4. Extract content factors for all imported papers.

Report:
> "从 BibTeX 文件导入了 42 篇论文。其中 38 篇已通过 DOI 补全了完整元数据。"

### B4: Import from URL

Parse the URL to determine the source:
- `arxiv.org/abs/XXXX.XXXXX` → extract arxiv_id, call `search_arxiv(query=arxiv_id)`
- `doi.org/10.XXXX/...` → extract DOI, follow DOI import flow
- `semanticscholar.org/paper/...` → extract S2 ID, call `search_semantic`
- Other → try `search_papers(query="<url_or_title>")`

Then follow DOI import flow with the fetched metadata.

### B5: Import from Title

1. Search for the paper:
```
search_semantic(query="<title>", max_results=5)
```
2. Show matches and let user confirm which one:
> "找到以下匹配论文，请确认：\n1. [exact title match] (2020, NeurIPS)\n2. [similar title] (2021, ICML)"
3. Import the confirmed paper.

---

## Sub-Workflow C: Browse Library

### C1: List Papers

```
lr_paper_list(
  path="<project_path>",
  status="in_library",
  sort_by="citation_count",
  limit=20
)
```

User can request different sorts: "按年份排序", "按评分排序", "按引用排序"

Show as numbered list with key metadata.

### C2: View Paper Details

```
lr_paper_detail(path="<project_path>", paper_id="<id>")
```

Display: full metadata, score breakdown, content factors, PDF status, URL/DOI links.

### C3: Library Statistics

```
lr_paper_stats(path="<project_path>")
```

### C4: Exclude a Paper

```
lr_paper_exclude(path="<project_path>", paper_id="<id>")
```

---

## Error Handling

- If `lr_paper_add` returns `duplicate: true`, inform: "该论文已在文献库中（ID: <id>）。"
- If `get_crossref_paper_by_doi` fails, fall back to `search_semantic(query="<doi>")`.
- If BibTeX parsing fails, report which entries failed and continue with successful ones.
- If `lr_content_extract` fails, warn and continue.
- If `download_with_fallback` fails, log but don't block.
- If `lr_paper_list` returns empty, suggest "运行搜索" or "导入文献".

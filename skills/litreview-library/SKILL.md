---
name: litreview-library
description: >
  Manage your literature library. Use when user says "加入文献库", "添加论文", "排除这篇",
  "查看文献库", "文献库状态", "下载PDF", "管理文献", "add to library", "show my papers",
  "library status", "download pdf", "read this paper".
---

# litreview-library: Manage Your Literature Library

This skill handles two primary workflows: adding papers to the library (with optional PDF download and content extraction), and browsing/inspecting the existing library.

---

## Determine Intent

At skill entry, determine which sub-workflow applies based on the user's request:

- **Add workflow**: "加入文献库", "添加论文", "add to library", "收录这篇", "下载PDF", "read this paper"
- **Browse workflow**: "查看文献库", "文献库状态", "show my papers", "library status", "有哪些论文", "查看详情"

If the intent is ambiguous, ask:
> "你想添加论文到文献库，还是查看现有文献库的内容？"

---

## Sub-Workflow A: Add Papers to Library

### A1: Identify Papers to Add

Determine the paper(s) to add from context:
- From a previous search result (user references a number or title)
- From a DOI, URL, or title the user provides directly
- From a list the user provides for batch addition

If unclear which papers to add, ask the user to specify.

### A2: Add Paper(s) to Library

**Single paper:**
```
lr_paper_add(
  title="<title>",
  authors=["<author1>", "<author2>"],
  year=<year>,
  doi="<doi>",
  venue="<venue>",
  abstract="<abstract>",
  source="semantic" | "openalex" | "manual",
  source_id="<api_id>"
)
```

**Multiple papers (batch):**
```
lr_paper_add_batch(papers=[
  { title: "...", authors: [...], year: ..., doi: "...", ... },
  { title: "...", authors: [...], year: ..., doi: "...", ... }
])
```

On success, report:
> "已添加「<title>」到文献库（ID: <lr_id>）。"

### A3: Extract Content Factors

After adding, call `lr_content_extract` to parse the abstract and extract conceptual factors:

```
lr_content_extract(paper_id=<lr_id>)
```

This enriches the paper's metadata with extracted concepts, methods, and keywords for future expansion. Report the number of factors extracted.

### A4: Optional PDF Download

If the user wants the full PDF (e.g., "下载PDF", "下载全文", "read this paper"):

```
download_with_fallback(
  doi="<doi>",
  title="<title>",
  output_dir=".litreview/pdfs/"
)
```

`download_with_fallback` tries multiple sources in order (Unpaywall, Semantic Scholar, arXiv, Sci-Hub fallback, etc.) and returns the local file path on success.

If download succeeds, confirm:
> "PDF 已下载到 `.litreview/pdfs/<filename>.pdf`。"

If download fails, inform:
> "无法下载该论文的 PDF（可能需要订阅权限）。已保存元数据，可稍后手动获取。"

### A5: Show Addition Result

Present a summary of what was added:

```
已添加到文献库:
  标题: Attention Is All You Need
  作者: Vaswani et al. (2017)
  来源: NeurIPS 2017 | 引用量: 92,431
  提取概念: transformer, self-attention, encoder-decoder, multi-head attention
  PDF: .litreview/pdfs/attention-is-all-you-need.pdf
```

Suggest next actions:
- "继续添加更多论文"
- "查看文献库统计"
- "扩展检索（基于这篇论文的引用）"

---

## Sub-Workflow B: Browse Library

### B1: List Papers

Call `lr_paper_list` to retrieve papers from the library:

```
lr_paper_list(
  status=<"all" | "included" | "excluded">,
  sort_by=<"score" | "year" | "citation_count" | "added_date">,
  limit=20,
  offset=0
)
```

Default: show included papers sorted by score, 20 per page.

Display as a numbered list:

```
文献库（共 34 篇已收录论文）:

#1  [评分 0.92] Attention Is All You Need
    Vaswani et al. | NeurIPS 2017 | 引用: 92,431
    状态: 已收录 | 添加时间: 2024-03-10

#2  [评分 0.88] BERT: Pre-training of Deep Bidirectional Transformers
    Devlin et al. | NAACL 2019 | 引用: 47,821
    状态: 已收录 | 添加时间: 2024-03-10
...
```

Offer pagination: "显示更多（第 2 页）" if results exceed limit.

### B2: View Paper Details

If the user asks for details on a specific paper:

```
lr_paper_detail(paper_id=<lr_id>)
```

Display:
- Full metadata (title, authors, year, venue, DOI, abstract)
- Score breakdown by dimension
- Extracted content factors
- PDF availability status
- Related papers in library (if any)

### B3: Library Statistics

If the user asks for an overview or status:

```
lr_paper_stats()
```

Display a summary dashboard:

```
文献库统计:
  总计: 47 篇论文
  已收录: 34 篇 | 已排除: 8 篇 | 待决定: 5 篇
  平均评分: 0.74
  年份分布: 2019(3), 2020(5), 2021(8), 2022(9), 2023(7), 2024(2)
  顶级期刊/会议: NeurIPS(8), ICML(6), ACL(5), arXiv(10)
  已下载 PDF: 12 篇
  提取概念总数: 218 个
```

### B4: Exclude a Paper

If the user wants to exclude a paper from the library:

```
lr_paper_update(paper_id=<lr_id>, status="excluded", reason="<optional_reason>")
```

Confirm:
> "已将「<title>」标记为排除。该论文不会影响后续检索和导出，但仍保留在记录中。"

---

## Error Handling

- If `lr_paper_add` fails due to a duplicate DOI, inform the user: "该论文已在文献库中（ID: <existing_id>）。是否更新其元数据？"
- If `lr_content_extract` fails, warn and continue: "内容因子提取失败，可稍后重试。"
- If `lr_paper_list` returns empty, suggest running `litreview-search` first.
- If `download_with_fallback` fails, log the failure but do not block the add workflow.

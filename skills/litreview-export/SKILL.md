---
name: litreview-export
description: >
  Export literature data. Use when user says "导出文献", "导出BibTeX", "导出RIS",
  "生成参考文献列表", "export papers", "export bibtex", "generate bibliography".
---

# litreview-export: Export Literature Data

This skill exports papers from the library in various formats: BibTeX, RIS, CSV, or a Markdown summary report.

---

## IMPORTANT: Path Rule

All litreview MCP tool calls MUST pass the `path` parameter as the **absolute path** of the user's current working directory. NEVER omit `path` or use the default `"."` — the default resolves to the MCP server's process directory, not the user's project.

Determine the user's project directory at the start (e.g. via `pwd`) and use it consistently for every `lr_*` call.

---

## Step 1: Retrieve Papers for Export

Call `lr_paper_list` to get the papers to export:

```
lr_paper_list(
  status="included",
  sort_by="score",
  limit=500
)
```

Report the count to the user:
> "文献库中共有 34 篇已收录论文可供导出。"

Allow the user to filter before exporting:
- Export all included papers (default)
- Export top N by score: "导出评分前 20 的论文"
- Export by year range: "导出 2022 年后的论文"
- Export a specific selection by ID

Apply filters via `lr_paper_list` parameters before proceeding.

---

## Step 2: Choose Export Format

If the user has not specified a format, present the options:

```
请选择导出格式：

1. BibTeX (.bib)     — 用于 LaTeX 参考文献管理（Overleaf, Zotero 等）
2. RIS (.ris)        — 通用格式，兼容 EndNote, Mendeley, Zotero
3. CSV (.csv)        — 电子表格格式，适合数据分析
4. Markdown 报告     — 人类可读的文献综述摘要（含摘要和评分）
5. JSON              — 机器可读的完整数据导出

请输入格式编号：
```

---

## Step 3: Execute Export

### Format: BibTeX or RIS

Use the `export_papers` tool from the paper-search MCP:

```
export_papers(
  papers=<paper_list>,
  format="bibtex" | "ris",
  output_path=".litreview/exports/<filename>.<ext>"
)
```

`export_papers` accepts a list of paper metadata objects and generates a formatted citation file.

Default output path:
- BibTeX: `.litreview/exports/library.bib`
- RIS: `.litreview/exports/library.ris`

Allow user to specify a custom filename if desired.

On success, confirm:
> "已导出 34 篇论文到 `.litreview/exports/library.bib`。"

---

### Format: CSV

Use `export_papers` with CSV format:

```
export_papers(
  papers=<paper_list>,
  format="csv",
  output_path=".litreview/exports/library.csv",
  fields=["title", "authors", "year", "venue", "doi", "citation_count", "score", "abstract"]
)
```

On success:
> "已导出 34 篇论文到 `.litreview/exports/library.csv`（包含字段：标题、作者、年份、期刊、DOI、引用量、评分、摘要）。"

---

### Format: Markdown Report

Generate a structured Markdown report directly (agent-generated, not via external tool):

**Report structure:**

```markdown
# 文献调研报告
生成时间: <timestamp>
检索主题: <from lr_status>
论文总数: <N> 篇

---

## 概述

[2-3 sentences summarizing the research area and key findings from the library]

## 检索因子

| 类型   | 值                            | 权重 |
|--------|-------------------------------|------|
| query  | large language model reasoning | 1.0  |
| method | chain-of-thought prompting    | 0.9  |
...

## 核心文献（评分 Top 10）

### 1. <title> (<year>)
**作者**: <authors>
**来源**: <venue> | **引用量**: <citation_count> | **评分**: <score>
**DOI**: <doi>

**摘要**: <abstract>

---

### 2. ...

## 完整文献列表

| # | 标题 | 作者 | 年份 | 来源 | 引用量 | 评分 |
|---|------|------|------|------|--------|------|
| 1 | ... | ... | ... | ... | ... | ... |
...

## BibTeX 引用

\`\`\`bibtex
@article{...}
\`\`\`
```

Write the report to `.litreview/exports/report.md`.

For the summary section, analyze the paper titles, abstracts, and extracted content factors to write a brief human-readable synthesis of what the library covers. Keep it to 3-5 sentences.

---

### Format: JSON

```
export_papers(
  papers=<paper_list>,
  format="json",
  output_path=".litreview/exports/library.json"
)
```

Includes all metadata, scores, extracted factors, and library-specific fields.

---

## Step 4: Confirm Export and Offer Next Steps

After successful export:

```
导出完成！

文件: .litreview/exports/library.bib
格式: BibTeX
论文数: 34 篇
文件大小: ~42 KB

后续操作:
- 「生成 Markdown 报告」— 同时生成可读摘要
- 「导出 CSV」— 导出电子表格格式
- 再次运行可覆盖更新导出文件
```

---

## Error Handling

- If `export_papers` is unavailable or fails, fall back to agent-generated output:
  - BibTeX: generate `@article{...}` entries manually from paper metadata
  - RIS: generate `TY - JOUR / TI - ...` format manually
  - Inform user: "export_papers 工具不可用，已由 AI 直接生成格式化内容。"
- If output directory `.litreview/exports/` does not exist, create it before writing.
- If no papers are included in the library, prompt: "文献库为空，请先添加论文后再导出。"
- For very large libraries (>200 papers), warn that Markdown report generation may take a moment.

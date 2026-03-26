# LitReview MCP — 完整体验清单

## 前置准备

### 1. 安装 litreview MCP

```bash
cd litreview-mcp
pip install -e ".[dev]"
```

### 2. 配置 MCP Server

在 Claude Code 的 MCP 配置中添加：

```json
{
  "mcpServers": {
    "litreview": {
      "command": "python",
      "args": ["-m", "litreview.server"],
      "cwd": "/path/to/litreview-mcp"
    }
  }
}
```

确保 **paper-search** MCP 也已配置并可用。

### 3. 安装 Skills

将 `skills/` 下的 5 个目录复制到 Claude Code 的 skills 目录：

```bash
cp -r skills/litreview-* ~/.claude/skills/
```

---

## 体验流程

### 场景 1：初始化工作空间

**触发方式：** 说 "新建文献调研" 或 "开始文献检索"

**体验步骤：**

1. 告诉 agent 你的研究课题：
   > "我要调研 RAG（检索增强生成）在医疗领域的应用"

2. Agent 会：
   - 调用 `lr_init` 创建 `.litreview/` 工作空间
   - 分析你的课题，提取初始检索因子
   - 展示提取结果请你确认

3. 你可以：
   - 确认全部因子
   - 修改某个因子的值
   - 添加 agent 遗漏的因子
   - 删除不需要的因子

4. 确认后 agent 写入因子库，展示工作空间初始化状态

**验证点：**
- [ ] `.litreview/` 目录已创建
- [ ] `lr_status` 显示因子数量正确
- [ ] `lr_factor_list` 能看到所有确认的因子

---

### 场景 2：首次文献检索

**触发方式：** 说 "搜索论文" 或 "开始搜索"

**体验步骤：**

1. Agent 读取活跃因子，组合查询参数
2. **展示查询计划**（透明度要求）：
   > "将使用以下条件搜索：
   > - 主查询: 'retrieval augmented generation medical'
   > - 过滤: field=healthcare, year=2022-
   > - 数据源: Semantic Scholar + OpenAlex
   > 确认执行？"

3. 你确认后，agent 调用 paper-search MCP 执行搜索
4. 调用 `lr_dedup` 去重，展示统计：
   > "Semantic Scholar 返回 47 篇，OpenAlex 返回 62 篇
   > 跨源去重后 83 篇，其中已在库中 0 篇，新论文 83 篇"

5. 调用 `lr_score` 评分排序，展示 Top 20：
   > | # | 标题 | 年份 | 引用 | 评分 | 评分详情 |
   > |---|------|------|------|------|----------|
   > | 1 | RAG for Knowledge... | 2020 | 3500 | 82.3 | 引用:0.9 新近:0.6 ... |

6. 你做出决策：
   - "前 10 篇加入文献库"
   - "第 15 篇排除"
   - "调高新近度权重到 0.3 重新排序"

**验证点：**
- [ ] 搜索前展示了完整查询计划
- [ ] 去重统计数字合理
- [ ] 评分有分项明细
- [ ] 可以调整权重后重排
- [ ] `lr_session_list` 能看到本次搜索记录

---

### 场景 3：论文入库与内容因子提取

**触发方式：** 在搜索结果中说 "把前 5 篇加入文献库"

**体验步骤：**

1. Agent 调用 `lr_paper_add_batch` 批量入库
2. 自动调用 `lr_content_extract` 提取内容因子
3. 可选：调用 `download_with_fallback` 下载 PDF
4. 展示入库结果：
   > "已添加 5 篇论文，提取了 32 个内容因子（12 位作者、5 个期刊、15 个领域标签）"

**验证点：**
- [ ] `lr_paper_list` 显示 5 篇论文
- [ ] `lr_paper_detail` 显示单篇详情含内容因子
- [ ] `lr_paper_stats` 统计正确
- [ ] `lr_content_query(type="author", aggregate="count")` 能看到作者频次

---

### 场景 4：浏览文献库

**触发方式：** 说 "查看文献库" 或 "文献库状态"

**体验步骤：**

1. 查看统计概览：
   > "文献库状态：5 篇在库，0 篇已排除
   > 检索因子：3 个（2 个活跃）
   > 内容因子：32 个
   > 搜索会话：1 次"

2. 按不同方式浏览：
   - "按引用量排序" → `lr_paper_list(sort_by="citation_count")`
   - "按评分排序" → `lr_paper_list(sort_by="_score")`
   - "看第 3 篇的详情" → `lr_paper_detail`

3. 查看单篇论文详情：
   > **标题:** RAG for Knowledge-Intensive NLP Tasks
   > **作者:** Lewis, Perez, ...
   > **评分:** 82.3 (引用:18.0 新近:12.0 速度:14.2 ...)
   > **内容因子:** 作者×5, 期刊: NeurIPS, 领域: CS, NLP
   > **发现路径:** 通过搜索会话 #1 发现（RAG + healthcare + 2022-）

**验证点：**
- [ ] 统计数字与实际一致
- [ ] 排序功能正常
- [ ] 详情页含评分分项和内容因子

---

### 场景 5：引文追踪（滚雪球）

**触发方式：** 说 "看看这篇论文被谁引用了" 或 "trace citations"

**体验步骤：**

1. 指定一篇论文（通过编号或标题）
2. Agent 获取论文外部 ID，调用 `snowball_search`
3. 展示前向引用结果（经过去重和评分）：
   > "找到 156 篇引用该论文的文献
   > 去重后 142 篇，其中 3 篇已在库中
   > Top 10 新论文如下..."

4. 也可以做反向追踪：
   > "这篇论文引用了 38 篇文献，其中 2 篇已在库中"

5. 选择入库：
   > "把评分前 5 的加入文献库"

**验证点：**
- [ ] 引文追踪返回结果
- [ ] 与现有库去重正确
- [ ] 新入库论文自动提取内容因子
- [ ] 搜索会话记录了本次追踪

---

### 场景 6：内容因子分析与晋升

**触发方式：** 说 "哪些作者出现最多" 或 "分析内容因子"

**体验步骤：**

1. 查看高频作者：
   > | 作者 | 出现次数 |
   > |------|----------|
   > | Yoshua Bengio | 8 篇 |
   > | Patrick Lewis | 5 篇 |
   > | Ashish Vaswani | 4 篇 |

2. 查看高频期刊：
   > "NeurIPS (6篇), ACL (4篇), EMNLP (3篇)"

3. 晋升操作：
   > "把 Bengio 加入检索因子，找他更多论文"

4. Agent 调用 `lr_content_promote`：
   > "已将 Yoshua Bengio 晋升为检索因子
   > 标记了 8 条内容因子记录为 promoted
   > 新因子已激活，可用于下次搜索"

5. 直接进入新一轮搜索：
   > "用新因子搜索论文"

**验证点：**
- [ ] 聚合统计正确
- [ ] 晋升后 `lr_factor_list` 包含新因子
- [ ] 新因子的 provenance 为 "promoted_from_content"
- [ ] 原内容因子标记为 promoted=true
- [ ] 可以用新因子发起搜索

---

### 场景 7：语义扩展

**触发方式：** 说 "扩展关键词" 或 "expand keywords"

**体验步骤：**

1. Agent 读取最近入库论文的摘要
2. 分析摘要，提取候选新因子：
   > "基于最近 5 篇论文的摘要，建议添加以下检索因子：
   > - 'dense passage retrieval' (method)
   > - 'knowledge grounding' (concept)
   > - 'biomedical NER' (topic)
   > 确认添加哪些？"

3. 你选择确认/修改/拒绝
4. 确认的因子写入因子库

**验证点：**
- [ ] 提议的因子与已有因子不重复
- [ ] 确认后因子库更新
- [ ] 新因子可用于后续搜索

---

### 场景 8：导出文献

**触发方式：** 说 "导出文献" 或 "export bibtex"

**体验步骤：**

1. 选择导出格式：
   - BibTeX (.bib)
   - RIS (.ris)
   - CSV (.csv)
   - Markdown 报告

2. 可选过滤：
   - "只导出评分 > 70 的"
   - "只导出 2022 年以后的"

3. Agent 生成导出文件

**验证点：**
- [ ] 导出文件内容完整
- [ ] BibTeX/RIS 格式正确可导入 Zotero

---

### 场景 9：多轮迭代搜索

**完整闭环体验：**

```
第 1 轮: 初始化 → 搜索 → 入库 10 篇
    ↓
第 2 轮: 语义扩展 → 新因子 → 搜索 → 入库 8 篇
    ↓
第 3 轮: 引文追踪（种子论文）→ 入库 5 篇
    ↓
第 4 轮: 内容因子分析 → 晋升高频作者 → 搜索 → 入库 6 篇
    ↓
分析: 查看文献库统计、高频作者、高频期刊
    ↓
导出: BibTeX + Markdown 报告
```

**验证点：**
- [ ] 每轮搜索都有独立的会话记录
- [ ] 去重正确（不会重复入库）
- [ ] 因子库逐轮扩展
- [ ] 内容因子库随入库论文增长
- [ ] 最终导出包含所有入库论文

---

## MCP 工具速查表

| 工具 | 功能 |
|------|------|
| `lr_init` | 初始化工作空间 |
| `lr_status` | 工作空间状态概览 |
| `lr_config` | 读取/设置配置 |
| `lr_factor_add` | 添加检索因子 |
| `lr_factor_list` | 列出检索因子 |
| `lr_factor_toggle` | 激活/停用因子 |
| `lr_factor_remove` | 删除因子 |
| `lr_factor_compose_query` | 从活跃因子组合查询 |
| `lr_paper_add` | 添加论文 |
| `lr_paper_add_batch` | 批量添加 |
| `lr_paper_exclude` | 排除论文 |
| `lr_paper_list` | 列出文献库 |
| `lr_paper_detail` | 论文详情 |
| `lr_paper_stats` | 文献库统计 |
| `lr_dedup` | 去重 |
| `lr_score` | 评分排序 |
| `lr_score_config` | 评分权重配置 |
| `lr_session_save` | 保存搜索会话 |
| `lr_session_list` | 搜索历史 |
| `lr_content_extract` | 提取内容因子 |
| `lr_content_query` | 查询/聚合内容因子 |
| `lr_content_promote` | 晋升为检索因子 |

## paper-search MCP 常用工具

| 工具 | 用途 |
|------|------|
| `search_semantic` | Semantic Scholar 搜索 |
| `search_openalex` | OpenAlex 搜索 |
| `search_papers` | 统一多源搜索 |
| `snowball_search` | 引文追踪（前向/后向/双向） |
| `download_with_fallback` | 智能 PDF 下载 |
| `read_arxiv_paper` | 下载并提取 arXiv 论文全文 |
| `export_papers` | 导出 CSV/RIS/BibTeX |
| `get_crossref_paper_by_doi` | DOI 精确查询 |

# LitReview 文献调研系统 — 安装指南

本系统由两个 MCP Server + 5 个 Skill 组成，需要在 Claude Code 中配置后使用。

## 前置要求

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) 已安装
- Python 3.10+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) 包管理器（推荐）或 pip

## 一、克隆仓库

```bash
# 选择一个目录存放
mkdir -p ~/mcp-servers && cd ~/mcp-servers

# 克隆两个仓库
git clone https://github.com/OpenSci-Common/paper-search.git
git clone https://github.com/OpenSci-Common/litreview-mcp.git
```

## 二、安装依赖

```bash
# paper-search
cd ~/mcp-servers/paper-search
uv sync        # 或 pip install -e .

# litreview-mcp
cd ~/mcp-servers/litreview-mcp
uv sync        # 或 pip install -e ".[dev]"
```

## 三、注册 MCP Server

```bash
# 注册 paper-search MCP（文献检索、下载、引文追踪）
claude mcp add --scope user paper-search -- \
  uv run --directory ~/mcp-servers/paper-search \
  -m paper_search.transports.mcp_server

# 注册 litreview MCP（因子管理、文献库、去重、评分、会话）
claude mcp add --scope user litreview -- \
  uv run --directory ~/mcp-servers/litreview-mcp \
  -m litreview
```

> `--scope user` 表示全局可用。如果只想在某个项目中使用，去掉此参数，在项目目录下执行。

## 四、安装 Skills

```bash
# 将 5 个 Skill 复制到 Claude Code 的 skills 目录
cp -r ~/mcp-servers/litreview-mcp/skills/litreview-init    ~/.claude/skills/
cp -r ~/mcp-servers/litreview-mcp/skills/litreview-search  ~/.claude/skills/
cp -r ~/mcp-servers/litreview-mcp/skills/litreview-library ~/.claude/skills/
cp -r ~/mcp-servers/litreview-mcp/skills/litreview-expand  ~/.claude/skills/
cp -r ~/mcp-servers/litreview-mcp/skills/litreview-export  ~/.claude/skills/
```

## 五、验证安装

启动 Claude Code，输入 `/mcp` 查看 MCP 状态，应该看到：

```
✓ paper-search  (50+ tools)
✓ litreview     (25 tools)
```

然后试试说：

> "新建文献调研"

Agent 应该触发 `litreview-init` Skill，开始引导你初始化工作空间。

## 快速体验

```
1. "我要调研 RAG 在医疗领域的应用"       → 初始化 + 提取因子
2. "搜索论文"                             → 检索 + 去重 + 评分
3. "把前 5 篇加入文献库"                  → 入库 + 提取内容因子
4. "看看第一篇被谁引用了"                 → 引文追踪
5. "哪些作者出现最多"                     → 内容因子分析
6. "导出 BibTeX"                          → 导出文献
```

完整体验清单见 [GETTING_STARTED.md](./GETTING_STARTED.md)。

## 系统架构

```
          你的自然语言
               │
     ┌─────────▼──────────┐
     │    5 个 Skills      │  ← 编排工作流
     └──┬──────────────┬───┘
        │              │
  ┌─────▼─────┐  ┌─────▼──────┐
  │ litreview  │  │paper-search│
  │   MCP      │  │   MCP      │
  │ (25 tools) │  │ (50+ tools)│
  │            │  │            │
  │ 因子管理    │  │ 搜索 22 源  │
  │ 文献库     │  │ 引文追踪    │
  │ 去重/评分   │  │ PDF 下载   │
  │ 会话记录    │  │ 全文阅读    │
  │ 内容因子    │  │ 基础导出    │
  │ 导出       │  │            │
  └─────┬──────┘  └────────────┘
        │
  ┌─────▼──────┐
  │ .litreview/ │  ← 项目目录下
  │ JSON 数据   │
  └────────────┘
```

## 卸载

```bash
# 移除 MCP
claude mcp remove paper-search
claude mcp remove litreview

# 移除 Skills
rm -rf ~/.claude/skills/litreview-*

# 删除仓库
rm -rf ~/mcp-servers/paper-search ~/mcp-servers/litreview-mcp
```

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

**ljg-xray-paper**（论文X光机）是一个 Claude Code Skill 插件，用于解构学术论文，穿透学术黑话，还原作者最底层的逻辑模型。

项目包含两个部分：
1. **Skill 插件**（纯配置型）：通过 `/ljg-xray-paper` 在 Claude Code 中直接调用
2. **Web 前端**（`web/`）：通过浏览器上传 PDF，支持三语言分析、PDF 在线阅读、AI 对话

## 项目结构

```
ljg-xray-paper/
├── .claude-plugin/
│   ├── plugin.json          # 插件元数据（名称、描述、作者）
│   └── marketplace.json     # Marketplace 发布配置（版本号）
├── skills/
│   └── ljg-xray-paper/
│       └── SKILL.md         # 核心文件：Skill 定义、执行流程和输出模板
├── web/                     # Web 前端（FastAPI + vanilla JS）
│   ├── app.py               # FastAPI 主应用，路由定义
│   ├── models.py            # SQLite 数据模型（aiosqlite）
│   ├── analyzer.py          # Claude CLI 调用封装（分析 + 对话）
│   ├── pdf_utils.py         # PDF 文本提取 + 页面渲染（PyMuPDF）
│   ├── requirements.txt     # Python 依赖
│   ├── .gitignore           # 忽略 data/, .venv/, __pycache__/
│   ├── data/                # 运行时数据（gitignore）
│   │   ├── pdfs/            # 上传的 PDF 文件
│   │   └── papers.db        # SQLite 数据库
│   ├── .venv/               # Python 虚拟环境（gitignore）
│   └── static/
│       ├── index.html       # 三 Tab SPA（UPLOAD / PAPER / RESULTS）
│       ├── style.css        # 暗色主题，响应式
│       └── app.js           # 前端交互逻辑
├── README.md
├── CLAUDE.md
└── LICENSE                  # MIT
```

**关键文件**：
- `skills/ljg-xray-paper/SKILL.md` — Skill 核心，包含角色定义、7 步执行流程、org-mode/markdown 双模板和质量标准
- `web/analyzer.py` — Web 版分析 prompt（从 SKILL.md 适配而来）和 Claude CLI 调用逻辑

## 架构

### Skill 插件（三层配置驱动）

1. **插件注册层**（`.claude-plugin/`）：向 Claude Code 注册插件身份和 Marketplace 信息
2. **Skill 定义层**（`SKILL.md`）：YAML frontmatter 声明 Skill 元数据（`user_invocable: true`），正文定义分析角色、执行流程和输出模板
3. **文档层**（`README.md`, `CLAUDE.md`）：用户和开发者文档

用户通过 `/ljg-xray-paper <论文>` 调用时，Claude Code 将 SKILL.md 注入上下文作为 prompt 执行。

### Web 前端架构

```
Browser (3 tabs: UPLOAD / PAPER / RESULTS)
  ├── POST /api/upload          → 上传 PDF，自动触发三语言分析
  ├── GET  /api/papers          → 论文列表
  ├── GET  /api/papers/{id}/page/{n} → PDF 单页 PNG
  ├── GET  /api/papers/{id}/result?lang=zh → 分析结果（JSON 或 SSE）
  └── POST /api/papers/{id}/chat → AI 对话（SSE 流式）
FastAPI (async, port 8899)
  ├── SQLite (papers / results / chat_messages)
  ├── PyMuPDF (PDF 文本提取 + 页面渲染)
  └── claude CLI subprocess (分析 + 对话)
```

**Web 版对 SKILL.md 的适配**：
- 去掉步骤 1（等待输入）→ 直接分析 `<paper>` 内的文本
- 去掉步骤 5（emacs 检查）→ 固定 markdown 输出
- 去掉步骤 7（保存文件）→ 直接输出 markdown，不写文件
- 添加语言指令：支持 EN/JA/ZH 三语言输出

## Skill 执行流程

接收论文输入 → 认知提取（去噪/提取/批判） → 五维分析框架 → ASCII 逻辑图 → 检测 emacs 决定输出格式（org-mode 或 markdown） → 生成报告 → 保存到 `~/Documents/notes/` 并打开

输出文件遵循 Denote 命名规范：`{YYYYMMDDTHHMMSS}--xray-{短标题}__read.{org|md}`

## 开发说明

### Skill 插件
- 不需要编译、构建、lint 或测试命令
- 修改 Skill 行为：编辑 `skills/ljg-xray-paper/SKILL.md`
- 修改插件元数据/版本：编辑 `.claude-plugin/` 下的 JSON 文件
- ASCII 图表限制：仅使用基础 ASCII 符号（`+`, `-`, `|`, `>`, `<`, `/`, `\`, `*`, `=`, `.`），禁止 Unicode

### Web 前端
- **启动**：`cd web && .venv/bin/python app.py`（端口 8899）
- **依赖安装**：`cd web && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`
- **数据库重置**：删除 `web/data/papers.db`，重启服务即自动重建
- 前端无构建步骤，纯 vanilla JS + marked.js (CDN)

### Claude CLI 调用注意事项（重要）

在 `analyzer.py` 中调用 claude CLI 时，以下经验至关重要：

1. **`--tools ""`**：必须禁用所有工具。否则 Claude 会读取项目中的 CLAUDE.md/SKILL.md，触发工具调用（如 Write）而非直接输出文本，导致 `result` 字段为空
2. **`--system-prompt`**（不是 `--system`）：参数名必须完整
3. **`--verbose`**：`--output-format stream-json` 必须搭配 `--verbose`，否则报错
4. **prompt 通过 stdin 传入**：论文文本通常 30000+ 字符，超出 OS 命令行参数长度限制，必须用 stdin 而非 `-p <prompt>` 传入。用法：`claude -p` （不带参数）+ stdin 写入
5. **stream-json 输出格式**：三种事件类型——`system`（init）、`assistant`（含 message.content）、`result`（含最终 result 文本）。当前实现只从 `result` 事件提取文本
6. **`reload_excludes=["data/*"]`**：uvicorn reload 必须排除 data 目录，否则 SQLite 写入会触发服务重启，中断 SSE 连接

### aiosqlite 用法注意

- `aiosqlite.connect(DB_PATH)` 本身就是 async context manager，直接 `async with aiosqlite.connect(...) as db:` 即可
- **不要** `await` 后再 `async with`（如 `async with await get_db() as db:`），会导致线程复用崩溃

### FastAPI 注意

- 使用 `lifespan` 而非已废弃的 `@app.on_event("startup")`
- 已完成的分析结果用 JSON 直接返回，正在运行的用 SSE 流式返回（避免 EventSource 自动重连问题）

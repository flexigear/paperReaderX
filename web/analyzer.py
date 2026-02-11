"""Claude CLI integration for paper analysis and chat."""

import asyncio
import json
import logging
from collections.abc import AsyncGenerator

import models

log = logging.getLogger(__name__)

# --- X-ray analysis prompt (adapted from SKILL.md for web) ---

XRAY_SYSTEM = """你是 **深层学术解析员**，一名拥有极高结构化思维的"审稿人"。
你的任务不是"总结"论文，而是"解构"论文。穿透学术黑话的迷雾，还原作者最底层的逻辑模型。"""

XRAY_PROMPT_TEMPLATE = """请分析以下学术论文。

## 执行认知提取算法

### 去噪
- 忽略背景介绍、客套话和通用的已知知识
- 跳过冗长的 Related Work（除非有关键对比）
- 过滤掉"为了发表而写"的填充内容

### 提取
- 锁定论文的核心贡献（Delta）
- 识别作者的"灵光一闪"时刻
- 找出决定成败的 1-2 个关键操作

### 批判
- 寻找逻辑漏洞或边界条件
- 识别隐形假设
- 标记未解决的问题

## 输出格式

请严格按照以下 markdown 模板输出分析报告：

# xray-{{简短标题}}

**Authors**: {{作者}}

## NAPKIN FORMULA

```
+----------------------------------------------------------+
|                                                          |
|   {{餐巾纸公式}}                                          |
|                                                          |
+----------------------------------------------------------+
```

{{一句话解释公式含义}}

## PROBLEM

**痛点定义**: {{一句话定义问题}}

**前人困境**: {{为什么之前解决不了}}

## INSIGHT

**核心直觉**: {{作者的灵光一闪，用最直白的语言}}

**关键步骤**:
1. {{神来之笔1}}
2. {{神来之笔2}}

## DELTA

**vs SOTA**: {{相比当前最佳的具体提升}}

**新拼图**: {{为人类知识库增加了什么}}

## CRITIQUE

**隐形假设**:
- {{假设1}}
- {{假设2}}

**未解之谜**:
- {{遗留问题1}}
- {{遗留问题2}}

## LOGIC FLOW

```
{{纯 ASCII 逻辑结构图: 问题 --> 洞见 --> 方法 --> 结果}}
```

## NAPKIN SKETCH

```
{{餐巾纸图: 用 ASCII 绘制核心概念}}
```

## 输出质量标准

- **高密度**: 使用列表和关键词，不写长段落
- **直白**: 用最简单的语言解释复杂概念
- **批判**: 必须指出至少一个隐形假设或未解问题
- **ASCII Art**: 仅用纯 ASCII 基础符号（+, -, |, >, <, /, \\, *, =, .），不用 Unicode
- **餐巾纸图/公式**: 必须一眼能懂

## 语言要求

请使用{lang_name}输出所有分析内容。

## 论文内容

<paper>
{paper_text}
</paper>"""

LANG_NAMES = {
    "en": "English",
    "ja": "日本語",
    "zh": "中文",
}


def build_analysis_prompt(paper_text: str, lang: str) -> str:
    lang_name = LANG_NAMES.get(lang, "English")
    return XRAY_PROMPT_TEMPLATE.format(paper_text=paper_text, lang_name=lang_name)


def build_chat_prompt(paper_text: str, result_content: str,
                      chat_history: list[dict], user_message: str) -> str:
    history_str = ""
    for msg in chat_history:
        role = "User" if msg["role"] == "user" else "Assistant"
        history_str += f"{role}: {msg['content']}\n\n"

    return f"""基于以下论文内容和 X-ray 分析报告回答用户问题。请直接、准确地回答。

<paper>
{paper_text}
</paper>

<xray-report>
{result_content}
</xray-report>

<chat-history>
{history_str}
</chat-history>

用户问题: {user_message}"""


async def stream_claude_cli(prompt: str, system: str | None = None) -> AsyncGenerator[str, None]:
    """Run claude CLI and yield text chunks from stream-json output.

    Passes prompt via stdin to avoid OS argument length limits.
    """
    cmd = [
        "claude", "-p",
        "--output-format", "stream-json",
        "--verbose",
        "--model", "sonnet",
        "--tools", "",
    ]
    if system:
        cmd.extend(["--system-prompt", system])

    log.info("Starting claude CLI (prompt via stdin, %d chars)", len(prompt))
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    # Send prompt via stdin
    proc.stdin.write(prompt.encode("utf-8"))
    await proc.stdin.drain()
    proc.stdin.close()

    try:
        async for line in proc.stdout:
            line = line.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            etype = event.get("type")

            # "result" event contains the final text
            if etype == "result":
                result_text = event.get("result", "")
                if result_text:
                    yield result_text
    finally:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        await proc.wait()


async def run_analysis(paper_id: str, lang: str) -> None:
    """Run X-ray analysis for a paper in a specific language. Updates DB as it streams."""
    paper = await models.get_paper(paper_id)
    if not paper:
        log.error("Paper %s not found", paper_id)
        return

    result = await models.get_result(paper_id, lang)
    if not result:
        log.error("Result record not found for paper=%s lang=%s", paper_id, lang)
        return

    result_id = result["id"]
    await models.update_result_status(result_id, "running")

    try:
        prompt = build_analysis_prompt(paper["text"], lang)
        async for chunk in stream_claude_cli(prompt, system=XRAY_SYSTEM):
            await models.append_result_content(result_id, chunk)

        await models.update_result_status(result_id, "done")
        log.info("Analysis done: paper=%s lang=%s", paper_id, lang)
    except Exception:
        log.exception("Analysis failed: paper=%s lang=%s", paper_id, lang)
        await models.update_result_status(result_id, "error")


async def start_all_analyses(paper_id: str) -> None:
    """Create result records and launch analysis for all three languages."""
    for lang in ["en", "ja", "zh"]:
        existing = await models.get_result(paper_id, lang)
        if not existing:
            await models.create_result(paper_id, lang)
        asyncio.create_task(run_analysis(paper_id, lang))


async def stream_chat(paper_id: str, user_message: str) -> AsyncGenerator[str, None]:
    """Stream a chat response about a paper."""
    paper = await models.get_paper(paper_id)
    if not paper:
        yield "Error: paper not found"
        return

    # Get the best available analysis result (prefer zh, then en, then ja)
    result_content = ""
    for lang in ["zh", "en", "ja"]:
        result = await models.get_result(paper_id, lang)
        if result and result["status"] == "done" and result["content"]:
            result_content = result["content"]
            break

    history = await models.get_chat_history(paper_id)

    # Save user message
    await models.add_chat_message(paper_id, "user", user_message)

    prompt = build_chat_prompt(paper["text"], result_content, history, user_message)

    full_response = []
    async for chunk in stream_claude_cli(prompt):
        full_response.append(chunk)
        yield chunk

    # Save assistant response
    await models.add_chat_message(paper_id, "assistant", "".join(full_response))

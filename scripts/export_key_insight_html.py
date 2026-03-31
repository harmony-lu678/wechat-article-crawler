#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
按「公众号正文关键内容提炼」六段式规则，调用配置中的 OpenAI 兼容接口，生成 output/articles_key_insight.html。
依赖 config.yaml 中 ai_summary 的 api_key / base_url / model（可与公众号总结共用）。
"""

import argparse
import hashlib
import html
import json
import os
import re
import sys
import time
from typing import Optional

import requests
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC = os.path.join(ROOT, "data", "processed", "articles_by_account.json")
RAW = os.path.join(ROOT, "data", "raw", "articles.json")
OUT = os.path.join(ROOT, "output", "articles_key_insight.html")
CONFIG = os.path.join(ROOT, "config.yaml")

KEY_INSIGHT_SYSTEM = """你是一名资深数据产品负责人 + 技术架构专家。你必须严格按照用户给出的【输出要求】与【结构要求】生成内容，不要偏离。"""

KEY_INSIGHT_USER_TEMPLATE = """请将以下内容总结为一篇「微信公众号文章正文的关键内容提炼版本」。

【目标】
输出一篇适合公众号正文的“高密度干货总结”，用于读者快速理解核心方法论与落地方案。

【输入】
一段原始正文（可能涉及数据产品 / NL2SQL / Agent / 数据治理 / RAG / 语义层设计等，也可能为其它技术资讯——请据实提炼，勿强行套用不存在的概念）。

【输出要求】

1️⃣ 结构要求（必须遵守）
输出内容严格分为以下结构：

一、背景与核心问题（3-5点）
- 提炼本质矛盾（不要复述表面问题）
- 用“❌ vs ✅”对比表达

二、核心方法论（最多3个）
- 每个方法论一句话总结
- 必须具备“抽象能力”（可迁移）

三、关键系统设计（重点）
- 用结构化方式描述（列表 or 小模块）
- 包含：
  - 核心数据结构（如 semantic_json）
  - 系统链路（NL → SQL）
  - 关键决策点（为什么这样设计）

四、落地路径（必须可执行）
- 分阶段（Step1 / Step2 / Step3）
- 每一步明确：
  - 做什么
  - 依赖什么
  - 产出什么

五、关键优化点 / 避坑（3-5条）
- 必须是“非显而易见”的坑
- 用“如果…会导致…”表达

六、一句话总结（必须有）
- 高抽象 + 可传播

---

2️⃣ 内容要求

- 不要流水账，不要复述原文
- 强调：
  - 为什么这样设计（而不是做了什么）
  - 如何规模化（而不是一次性方案）
- 所有概念必须“产品化表达”，避免纯技术堆砌
- 优先使用：
  - 对比（A vs B）
  - 收敛（从复杂到简单）
  - 抽象（从case到方法论）

---

3️⃣ 风格要求

- 信息密度高（类似技术博客Top 5%水平）
- 句子短，结论前置
- 少废话，无情绪，无故事
- 每一段都必须有“可复用价值”

---

4️⃣ 特别约束（非常重要）

- 不要写成“教程”
- 不要写成“PRD”
- 不要写成“流水总结”
- 必须让读者在 1 分钟内抓住：
  👉 核心设计
  👉 可复用方法
  👉 落地路径

---

【可选加分项】

如果内容中涉及以下概念，请自动强化表达：
- semantic_json → 作为“语义中间层”
- RAG → 作为“知识检索引擎”
- Agent → 作为“决策系统”
- NL2SQL → 作为“执行层”

---

【输出格式】

直接输出正文，不要解释，不要加前后缀，不要说明你做了什么。

---

【文章标题】
{title}

【原文正文】
{body}
"""


def load_config():
    with open(CONFIG, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def flatten_articles(grouped: dict) -> list:
    out = []
    for acc, arts in grouped.items():
        for a in arts:
            out.append((acc, a))
    return out


def call_llm(cfg: dict, user_content: str) -> Optional[str]:
    ai = cfg.get("ai_summary") or {}
    base = (ai.get("base_url") or "").rstrip("/")
    key = ai.get("api_key")
    model = ai.get("model")
    max_tokens = int(ai.get("max_tokens", 4096))
    temp = float(ai.get("temperature", 0.25))
    if not base or not key:
        return None
    url = f"{base}/chat/completions"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": KEY_INSIGHT_SYSTEM},
            {"role": "user", "content": user_content},
        ],
        "max_tokens": max_tokens,
        "temperature": temp,
    }
    r = requests.post(url, headers=headers, json=payload, timeout=300)
    r.raise_for_status()
    data = r.json()
    ch = data.get("choices") or []
    if not ch:
        return None
    return (ch[0].get("message") or {}).get("content", "").strip()


def slug(s: str) -> str:
    return "a-" + hashlib.md5(s.encode("utf-8")).hexdigest()[:12]


# --- 提炼正文：轻量排版（**加粗、列表、中文章节标题、文件名） ---
_SECTION_ZH = re.compile(r"^[一二三四五六七八九十百千]+、\s*\S")
_NUM_LINE = re.compile(r"^(\d+)\.\s+(.+)$")


def _bullet_line_content(s: str) -> Optional[str]:
    """无序列表行内容；** 开头的行不是列表（避免与 Markdown 粗体冲突）。"""
    if s.startswith("**"):
        return None
    if s.startswith("- "):
        return s[2:].strip()
    if s.startswith("* "):
        return s[2:].strip()
    if len(s) > 1 and s.startswith("•"):
        return s[1:].strip()
    if len(s) > 1 and s.startswith("·"):
        return s[1:].strip()
    return None
_FILE_REF = re.compile(
    r"([\w\u4e00-\u9fff\-]+\.(?:png|jpg|jpeg|gif|webp)\d*)",
    re.IGNORECASE,
)


def _inline_format(line: str) -> str:
    """**粗体** + 文件名 → code 标签；分段转义。"""
    out: list[str] = []
    pos = 0
    for m in _FILE_REF.finditer(line):
        if m.start() > pos:
            out.append(_bold_segments(line[pos : m.start()]))
        fn = html.escape(m.group(1), quote=False)
        out.append(f'<code class="file-ref" title="文中提及的文件名">{fn}</code>')
        pos = m.end()
    if pos < len(line):
        out.append(_bold_segments(line[pos:]))
    if not out:
        return _bold_segments(line)
    return "".join(out)


def _bold_segments(s: str) -> str:
    parts = s.split("**")
    chunks: list[str] = []
    for i, part in enumerate(parts):
        esc = html.escape(part, quote=False)
        if i % 2 == 1:
            chunks.append(f'<strong class="insight-em">{esc}</strong>')
        else:
            chunks.append(esc)
    return "".join(chunks)


def insight_text_to_html(text: str) -> str:
    """
    将模型返回的纯文本转为带结构的 HTML（非完整 Markdown，覆盖常见形态）。
    """
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return '<p class="insight-p empty">（无内容）</p>'

    lines = text.split("\n")
    blocks: list[str] = []
    i = 0
    n = len(lines)

    while i < n:
        raw = lines[i]
        s = raw.strip()
        if not s:
            i += 1
            continue

        md_h = re.match(r"^(#{1,6})\s+(.+)$", s)
        if md_h:
            level = len(md_h.group(1))
            title = md_h.group(2).strip()
            tag = "h3" if level <= 2 else "h4"
            cls = "insight-section" if level <= 2 else "insight-sub"
            blocks.append(f'<{tag} class="{cls} md">{_inline_format(title)}</{tag}>')
            i += 1
            continue

        # 中文大节：一、二、…
        if _SECTION_ZH.match(s):
            blocks.append(f'<h3 class="insight-section">{_inline_format(s)}</h3>')
            i += 1
            continue

        # 连续列表行：- / * / • / ·（* 须为「* 」单星+空格，避免误判 **粗体**）
        bc = _bullet_line_content(s)
        if bc is not None:
            items: list[str] = []
            while i < n:
                t = lines[i].strip()
                if not t:
                    break
                c = _bullet_line_content(t)
                if c is not None:
                    items.append(c)
                    i += 1
                    continue
                break
            if items:
                lis = "".join(f'<li>{_inline_format(x)}</li>' for x in items)
                blocks.append(f'<ul class="insight-ul">{lis}</ul>')
            continue

        # 有序列表 1. 2.
        if _NUM_LINE.match(s):
            items: list[str] = []
            while i < n:
                t = lines[i].strip()
                if not t:
                    break
                nm = _NUM_LINE.match(t)
                if nm:
                    items.append(nm.group(2).strip())
                    i += 1
                    continue
                break
            if items:
                lis = "".join(f'<li>{_inline_format(x)}</li>' for x in items)
                blocks.append(f'<ol class="insight-ol">{lis}</ol>')
            continue

        # 段落：合并到空行或遇到上述结构
        para: list[str] = []
        while i < n:
            t = lines[i].strip()
            if not t:
                break
            if re.match(r"^(#{1,6})\s+", t) or _SECTION_ZH.match(t):
                break
            if _bullet_line_content(t) is not None:
                break
            if _NUM_LINE.match(t):
                break
            para.append(t)
            i += 1
        inner = "<br/>".join(_inline_format(x) for x in para)
        blocks.append(f'<p class="insight-p">{inner}</p>')

    return "\n".join(blocks) if blocks else f'<p class="insight-p">{_inline_format(text)}</p>'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-articles", type=int, default=0, help="0 表示全部；用于控制 API 次数")
    ap.add_argument("--max-chars", type=int, default=0, help="单篇正文最大字符；0 表示读配置")
    ap.add_argument("--interval", type=float, default=0, help="请求间隔秒；0 表示读配置")
    args = ap.parse_args()

    cfg = load_config()
    kcfg = cfg.get("key_insight_html") or {}
    if args.max_chars <= 0:
        args.max_chars = int(kcfg.get("max_article_chars", 18000))
    if args.interval <= 0:
        args.interval = float(kcfg.get("request_interval_sec", 2.0))
    if not kcfg.get("enabled", True):
        print("config.yaml 中 key_insight_html.enabled 为 false，跳过生成")
        return

    ai = cfg.get("ai_summary") or {}
    if not ai.get("api_key") or not ai.get("base_url") or not ai.get("model"):
        print("请在 ai_summary 中配置 api_key、base_url、model 后重试")
        return

    if os.path.isfile(PROC):
        with open(PROC, "r", encoding="utf-8") as f:
            grouped = json.load(f)
    else:
        from collections import defaultdict

        with open(RAW, "r", encoding="utf-8") as f:
            articles = json.load(f)

        def account_key(a):
            n = a.get("account_name") or "未知公众号"
            b = a.get("biz_id") or "unknown"
            return f"{n}_{b}" if b != "unknown" else n

        grouped = defaultdict(list)
        for a in articles:
            grouped[account_key(a)].append(a)
        grouped = dict(grouped)

    flat = flatten_articles(grouped)
    if args.max_articles > 0:
        flat = flat[: args.max_articles]

    parts = [
        "<!DOCTYPE html>",
        '<html lang="zh-CN"><head><meta charset="utf-8"/>',
        '<meta name="viewport" content="width=device-width, initial-scale=1"/>',
        "<title>公众号正文 · 高密度提炼</title>",
        "<style>",
        ":root {",
        "  --bg:#0d1117; --surface:#161b22; --border:#30363d; --muted:#8b949e;",
        "  --text:#e6edf3; --body:#d1d5da; --accent:#58a6ff; --strong:#79c0ff;",
        "}",
        "body{font-family:'PingFang SC',system-ui,-apple-system,sans-serif;background:var(--bg);color:var(--text);",
        "  padding:20px 20px 56px;line-height:1.65;max-width:46rem;margin:0 auto;}",
        "h1{font-size:1.25rem;font-weight:600;margin:0 0 10px;letter-spacing:.02em;}",
        ".meta{color:var(--muted);font-size:0.82rem;margin-bottom:22px;line-height:1.5;}",
        "article{border:1px solid var(--border);border-radius:12px;padding:20px 22px 24px;margin-bottom:20px;",
        "  background:var(--surface);}",
        "article h2{font-size:1.05rem;font-weight:600;margin:0 0 10px;line-height:1.45;color:var(--accent);}",
        ".sub{font-size:0.78rem;color:var(--muted);margin-bottom:16px;padding-bottom:14px;border-bottom:1px solid var(--border);}",
        ".insight-root{font-size:0.92rem;color:var(--body);word-break:break-word;}",
        ".insight-section{font-size:0.98rem;font-weight:600;color:var(--text);margin:22px 0 12px;padding:8px 0 8px 12px;",
        "  border-left:3px solid var(--accent);background:rgba(88,166,255,.06);border-radius:0 8px 8px 0;}",
        ".insight-section:first-child{margin-top:0;}",
        ".insight-section.md{border-left-color:#a371f7;background:rgba(163,113,247,.08);}",
        ".insight-sub{font-size:0.88rem;font-weight:600;color:#c9d1d9;margin:16px 0 8px;}",
        ".insight-p{margin:0 0 14px;line-height:1.78;letter-spacing:.015em;}",
        ".insight-p:last-child{margin-bottom:0;}",
        ".insight-p.empty{color:var(--muted);font-style:italic;}",
        ".insight-em{color:var(--strong);font-weight:600;}",
        ".insight-ul,.insight-ol{margin:8px 0 16px;padding-left:1.35rem;}",
        ".insight-ul li,.insight-ol li{margin:8px 0;line-height:1.65;padding-left:4px;}",
        ".insight-ul{list-style:disc;}",
        ".insight-ol{list-style:decimal;}",
        "ul.insight-ul li::marker{color:var(--accent);}",
        "ol.insight-ol li::marker{color:var(--muted);font-weight:600;}",
        ".file-ref{font-family:ui-monospace,SFMono-Regular,monospace;font-size:0.82em;padding:2px 6px;",
        "  border-radius:4px;background:#21262d;border:1px solid var(--border);color:#b1bac4;}",
        "</style></head><body>",
        "<h1>微信公众号 · 关键内容提炼（六段式）</h1>",
        f'<p class="meta">共处理 {len(flat)} 篇 · 规则：高密度干货 / 非流水账 · 生成于 {time.strftime("%Y-%m-%d %H:%M")}</p>',
    ]

    for acc, a in flat:
        title = a.get("title") or "（无标题）"
        body = (a.get("content") or "").strip()
        if len(body) > args.max_chars:
            body = body[: args.max_chars] + "\n\n…（正文已截断以适配模型上下文）"

        user_prompt = KEY_INSIGHT_USER_TEMPLATE.replace("{title}", title).replace(
        "{body}", body or "（无正文）"
    )
        try:
            text = call_llm(cfg, user_prompt)
        except Exception as e:
            text = f"（生成失败：{e}）"

        if not text:
            text = "（无返回内容）"

        parts.append(f'<article id="{slug(title + acc)}">')
        parts.append(f"<h2>{html.escape(title)}</h2>")
        parts.append(
            f'<div class="sub">{html.escape(a.get("account_name") or "")} · {html.escape(a.get("publish_time") or "")}</div>'
        )
        parts.append(f'<div class="insight-root">{insight_text_to_html(text)}</div>')
        parts.append("</article>")
        time.sleep(max(0.0, args.interval))

    parts.append("</body></html>")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    sys.path.insert(0, ROOT)
    main()

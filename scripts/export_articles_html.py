#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 processed JSON / raw articles 生成阅读向 HTML。
UI 风格：仿「竞品监控」浅色主题 —— 顶栏 + 公众号 pill 选择 + 文章日期卡片。
"""

import html
import json
import os
import sys
from collections import defaultdict
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from utils import article_body_plain_to_html, sanitize_summary_for_public, body_to_excerpt_html

RAW   = os.path.join(ROOT, "data", "raw",       "articles.json")
PROC  = os.path.join(ROOT, "data", "processed", "articles_by_account.json")
SUMS  = os.path.join(ROOT, "output", "summaries.json")
OUT   = os.path.join(ROOT, "output", "articles_view.html")

CONTENT_MAX = 80_000


# ── helpers ────────────────────────────────────────────────────────────────

def account_key(art: dict) -> str:
    name = art.get("account_name") or "未知公众号"
    biz  = art.get("biz_id") or ""
    return f"{name}::{biz}" if biz else name


def disp_name(arts: list, acc_key: str) -> str:
    for a in arts:
        n = a.get("account_name", "").strip()
        if n:
            return n
    return acc_key.split("::")[0]


def clip(text: str) -> str:
    if not text:
        return ""
    if len(text) <= CONTENT_MAX:
        return text
    return text[:CONTENT_MAX] + f"\n\n…（已截断，全文约 {len(text)} 字）"


def weekday(ds: str) -> str:
    WD = ["周一","周二","周三","周四","周五","周六","周日"]
    try:
        d = datetime.strptime(ds[:10], "%Y-%m-%d")
        return f"{ds[:10]}  {WD[d.weekday()]}"
    except Exception:
        return ds[:10] if ds else ""


def e(s: str) -> str:
    return html.escape(str(s), quote=False)


# ── CSS ────────────────────────────────────────────────────────────────────

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --bg:       #f0f2f5;
  --surface:  #ffffff;
  --border:   #e4e7ed;
  --text:     #1d2129;
  --muted:    #86909c;
  --accent:   #1677ff;
  --acbg:     #e8f3ff;
  --acbd:     #bedaff;
  --shadow:   0 2px 8px rgba(0,0,0,.06);
  --r:        8px;
}
body {
  font-family: 'PingFang SC', 'Helvetica Neue', system-ui, sans-serif;
  background: var(--bg);
  color: var(--text);
  min-height: 100vh;
  font-size: 14px;
  line-height: 1.6;
}

/* ── header ──────────────────────────── */
.hdr {
  position: sticky; top: 0; z-index: 100;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  height: 54px;
  display: flex; align-items: center;
  padding: 0 28px;
  gap: 12px;
}
.hdr-logo {
  font-size: 16px; font-weight: 700;
  color: var(--text);
  display: flex; align-items: center; gap: 6px;
  flex-shrink: 0;
}
.hdr-logo svg { color: var(--accent); }
.hdr-title {
  flex: 1; text-align: center;
  font-size: 16px; font-weight: 600;
  color: var(--text);
}
.hdr-meta {
  flex-shrink: 0;
  display: flex; align-items: center; gap: 6px;
  font-size: 13px; color: var(--muted);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 4px 12px;
}

/* ── pill section ─────────────────────── */
.pill-section {
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  position: sticky; top: 54px; z-index: 90;
  overflow: hidden;
}
.pill-bar {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 28px;
  cursor: pointer;
  user-select: none;
}
.pill-bar:hover { background: #fafbfc; }
.pill-label {
  font-size: 12px; color: var(--muted);
  font-weight: 500; letter-spacing: .3px;
  flex: 1;
}
.pill-current {
  font-size: 12px; color: var(--accent);
  background: var(--acbg);
  border: 1px solid var(--acbd);
  border-radius: 12px;
  padding: 2px 10px;
  max-width: 160px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  display: none;
}
.pill-section.collapsed .pill-current { display: inline-block; }
.pill-toggle-icon {
  font-size: 11px; color: var(--muted);
  transition: transform .2s;
  flex-shrink: 0;
}
.pill-section.collapsed .pill-toggle-icon { transform: rotate(180deg); }
.pill-body {
  padding: 0 28px 14px;
  max-height: 600px;
  overflow: hidden;
  transition: max-height .3s ease, padding .3s ease, opacity .25s;
  opacity: 1;
}
.pill-section.collapsed .pill-body {
  max-height: 0;
  padding-top: 0;
  padding-bottom: 0;
  opacity: 0;
}
.pill-row {
  display: flex; flex-wrap: wrap; gap: 8px;
}
.pill {
  display: inline-flex; align-items: center; gap: 5px;
  border: 1px solid var(--acbd);
  background: var(--surface);
  color: var(--accent);
  font-size: 13px; font-weight: 500;
  padding: 5px 14px;
  border-radius: 20px;
  cursor: pointer;
  transition: all .18s;
  line-height: 1.4;
}
.pill:hover {
  background: var(--acbg);
  border-color: var(--accent);
}
.pill.active {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}
.pill .cnt {
  font-size: 11px;
  background: rgba(22,119,255,.12);
  border-radius: 10px;
  padding: 1px 5px;
  min-width: 18px;
  text-align: center;
}
.pill.active .cnt {
  background: rgba(255,255,255,.25);
}

/* ── content area ─────────────────────── */
.content {
  max-width: 820px;
  margin: 0 auto;
  padding: 24px 16px 60px;
}
.empty-hint {
  text-align: center;
  padding: 80px 0;
  color: var(--muted);
  font-size: 15px;
}
.empty-hint .icon { font-size: 40px; display: block; margin-bottom: 10px; }

/* ── account panel ─────────────────────── */
.panel { display: none; }
.panel.active { display: block; }

.panel-head {
  display: flex; align-items: center; gap: 10px;
  margin-bottom: 20px;
  padding-bottom: 14px;
  border-bottom: 2px solid var(--acbd);
}
.panel-head-name {
  font-size: 18px; font-weight: 700; color: var(--text);
}
.panel-head-tag {
  font-size: 12px; color: var(--accent);
  border: 1px solid var(--acbd);
  background: var(--acbg);
  border-radius: 12px;
  padding: 2px 10px;
}

/* AI summary block */
.ai-sum {
  background: var(--surface);
  border: 1px solid var(--acbd);
  border-radius: var(--r);
  padding: 16px 20px;
  margin-bottom: 22px;
  position: relative;
}
.ai-sum-title {
  font-size: 12px; font-weight: 600;
  color: var(--accent);
  letter-spacing: .5px;
  margin-bottom: 10px;
  display: flex; align-items: center; gap: 6px;
}
.ai-sum-body {
  font-size: 13px; color: #374151; line-height: 1.75;
}
.ai-sum-body h3 {
  font-size: 13px; font-weight: 700;
  color: var(--text);
  margin: 10px 0 4px;
}
.ai-sum-body p { margin: 4px 0; }
.ai-sum-body ul, .ai-sum-body ol {
  padding-left: 20px; margin: 4px 0;
}
.ai-sum-body li { margin: 2px 0; }
.ai-sum-body strong { color: var(--text); font-weight: 600; }

/* ── date group ───────────────────────── */
.date-group { margin-bottom: 18px; }
.date-header {
  display: flex; align-items: center; gap: 8px;
  font-size: 13px; font-weight: 600;
  color: var(--muted);
  margin-bottom: 10px;
  padding: 0 4px;
}
.date-header::before {
  content: '';
  display: inline-block;
  width: 4px; height: 4px;
  border-radius: 50%;
  background: var(--accent);
}

/* ── article card ─────────────────────── */
.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--r);
  padding: 18px 20px;
  margin-bottom: 10px;
  box-shadow: var(--shadow);
  transition: box-shadow .2s;
}
.card:hover {
  box-shadow: 0 4px 16px rgba(0,0,0,.1);
}
.card-title {
  font-size: 15px; font-weight: 600;
  color: var(--text);
  line-height: 1.5;
  margin-bottom: 6px;
}
.card-title a {
  color: var(--text);
  text-decoration: none;
}
.card-title a:hover { color: var(--accent); }

.card-meta {
  display: flex; gap: 10px;
  font-size: 12px; color: var(--muted);
  margin-bottom: 12px;
  flex-wrap: wrap;
  align-items: center;
}
.score-chip {
  background: var(--acbg);
  color: var(--accent);
  border-radius: 10px;
  padding: 1px 8px;
  font-weight: 600;
  font-size: 11px;
}

.digest-wrap {
  border-left: 3px solid var(--acbd);
  padding-left: 12px;
  margin-bottom: 12px;
  color: #374151;
  font-size: 13.5px;
  line-height: 1.7;
}

/* collapsible full body */
.body-toggle {
  font-size: 12px; color: var(--accent);
  cursor: pointer;
  user-select: none;
  list-style: none;
  display: inline-flex; align-items: center; gap: 4px;
  padding: 3px 0;
}
.body-toggle::-webkit-details-marker { display: none; }
.body-detail { }
.body-detail[open] > .body-toggle::before { content: '▾ '; }
.body-detail:not([open]) > .body-toggle::before { content: '▸ '; }

.body-content {
  margin-top: 10px;
  padding: 12px 14px;
  background: #fafbfc;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 13px; color: #374151;
  line-height: 1.75;
  max-height: 480px;
  overflow-y: auto;
}
.body-content h3 {
  font-size: 13px; font-weight: 700;
  color: var(--text);
  margin: 10px 0 4px;
}
.body-content p { margin: 5px 0; }
.body-content p.excerpt-p { margin: 0 0 8px; line-height: 1.8; }
.body-content p.excerpt-p:last-child { margin-bottom: 0; }
.body-content strong { font-weight: 600; color: var(--text); }
.body-content br { line-height: 2; }

.card-footer {
  margin-top: 12px; padding-top: 10px;
  border-top: 1px solid var(--border);
  display: flex; justify-content: flex-end;
}
.card-link {
  font-size: 12px; color: var(--accent);
  text-decoration: none;
  display: inline-flex; align-items: center; gap: 4px;
}
.card-link:hover { text-decoration: underline; }

/* search bar */
.search-wrap {
  position: relative;
  display: flex; align-items: center;
  margin-left: auto;
  max-width: 200px;
}
.search-input {
  width: 100%;
  padding: 6px 10px 6px 30px;
  border: 1px solid var(--border);
  border-radius: 20px;
  font-size: 13px;
  outline: none;
  color: var(--text);
  background: var(--bg);
  transition: border-color .15s;
}
.search-input:focus { border-color: var(--accent); }
.search-icon {
  position: absolute; left: 10px;
  color: var(--muted); font-size: 13px;
  pointer-events: none;
}

/* ── highlight marks ──────────────────── */
mark { border-radius: 3px; padding: 0 2px; font-style: normal; }
mark.hl-key    { background: #fff3b0; color: #78350f; font-weight: 600; }
mark.hl-num    { background: #dbeafe; color: #1d4ed8; font-weight: 500; }
mark.hl-quote  { background: #dcfce7; color: #15803d; }
mark.hl-action { background: #fce7f3; color: #be185d; font-weight: 500; }
"""


# ── JS ─────────────────────────────────────────────────────────────────────

JS = """
(function(){
  const pills     = document.querySelectorAll('.pill[data-acc]');
  const panels    = document.querySelectorAll('.panel');
  const hint      = document.getElementById('empty-hint');
  const search    = document.getElementById('search-input');
  const pillSec   = document.querySelector('.pill-section');
  const pillBar   = document.querySelector('.pill-bar');
  const pillCur   = document.querySelector('.pill-current');

  function collapse() {
    if (pillSec) pillSec.classList.add('collapsed');
  }
  function expand() {
    if (pillSec) pillSec.classList.remove('collapsed');
  }

  function showPanel(accId, autoCollapse) {
    panels.forEach(p => p.classList.remove('active'));
    pills.forEach(p  => p.classList.remove('active'));
    if (hint) hint.style.display = 'none';
    const panel = document.getElementById('panel-' + accId);
    const pill  = document.querySelector('.pill[data-acc="' + accId + '"]');
    if (panel) panel.classList.add('active');
    if (pill)  {
      pill.classList.add('active');
      if (pillCur) pillCur.textContent = pill.dataset.name || '';
    }
    if (autoCollapse) {
      collapse();
      setTimeout(() => {
        const top = (pillSec ? pillSec.getBoundingClientRect().bottom + window.scrollY : 0);
        window.scrollTo({ top: top - 54, behavior: 'smooth' });
      }, 120);
    }
  }

  // pill click: select & collapse
  pills.forEach(pill => {
    pill.addEventListener('click', () => showPanel(pill.dataset.acc, true));
  });

  // pill-bar click: toggle collapse
  if (pillBar) {
    pillBar.addEventListener('click', () => {
      if (pillSec.classList.contains('collapsed')) expand();
      else collapse();
    });
  }

  // auto-select first (expanded, no scroll)
  if (pills.length) showPanel(pills[0].dataset.acc, false);

  // search / filter pills
  if (search) {
    search.addEventListener('click', e => e.stopPropagation()); // don't toggle when clicking search
    search.addEventListener('input', function(){
      const q = this.value.trim().toLowerCase();
      pills.forEach(pill => {
        const name = pill.dataset.name || '';
        pill.style.display = (!q || name.includes(q)) ? '' : 'none';
      });
      if (pillSec && pillSec.classList.contains('collapsed')) expand();
    });
  }
})();
"""


# ── builder ────────────────────────────────────────────────────────────────

def build_html(accounts_sorted, summaries, total, date_min, date_max):
    date_range = f"{date_min}  ~  {date_max}" if date_min else ""

    # Header
    out = []
    out.append(f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>公众号资讯 · 日报</title>
<style>{CSS}</style>
</head>
<body>
<header class="hdr">
  <div class="hdr-logo">
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
      <path d="M4 4h16v3H4z" rx="1"/><rect x="4" y="9" width="16" height="11" rx="1"/>
      <line x1="8" y1="13" x2="16" y2="13"/><line x1="8" y1="17" x2="12" y2="17"/>
    </svg>
    公众号资讯
  </div>
  <div class="hdr-title">资讯日报</div>
  <div class="search-wrap">
    <span class="search-icon">🔍</span>
    <input class="search-input" id="search-input" placeholder="搜索公众号…"/>
  </div>
  <div class="hdr-meta">
    📅 {e(date_range) if date_range else '—'}
  </div>
</header>
""")

    # Pill section
    out.append('<div class="pill-section">')
    # Clickable bar (always visible, toggles collapse)
    out.append(
        f'<div class="pill-bar">'
        f'<span class="pill-label">共 {len(accounts_sorted)} 个公众号 · {total} 篇文章</span>'
        f'<span class="pill-current"></span>'
        f'<span class="pill-toggle-icon">▲</span>'
        f'</div>'
    )
    # Collapsible body
    out.append('<div class="pill-body"><div class="pill-row">')
    for idx, (acc_key_val, arts) in enumerate(accounts_sorted):
        name = disp_name(arts, acc_key_val)
        out.append(
            f'<button class="pill" data-acc="{idx}" data-name="{e(name.lower())}">'
            f'{e(name)} <span class="cnt">{len(arts)}</span>'
            f'</button>'
        )
    out.append('</div></div>')  # pill-row / pill-body
    out.append('</div>')  # pill-section

    # Content area
    out.append('<div class="content">')
    out.append('<div class="empty-hint" id="empty-hint"><span class="icon">📰</span>选择左上方公众号查看文章</div>')

    for idx, (acc_key_val, arts) in enumerate(accounts_sorted):
        name     = disp_name(arts, acc_key_val)
        sum_text = sanitize_summary_for_public(summaries.get(acc_key_val, ""))

        out.append(f'<div class="panel" id="panel-{idx}">')

        # Panel header
        out.append(f'''<div class="panel-head">
  <div class="panel-head-name">{e(name)}</div>
  <div class="panel-head-tag">{len(arts)} 篇</div>
</div>''')

        # AI summary block
        if sum_text.strip():
            sum_html = article_body_plain_to_html(sum_text)
            out.append(f'''<div class="ai-sum">
  <div class="ai-sum-title">🤖 AI 摘要</div>
  <div class="ai-sum-body">{sum_html}</div>
</div>''')

        # Group articles by date
        by_date = defaultdict(list)
        for art in arts:
            d = (art.get("publish_time") or "")[:10]
            by_date[d].append(art)

        for date_str in sorted(by_date.keys(), reverse=True):
            day_arts = by_date[date_str]
            out.append(f'<div class="date-group">')
            out.append(f'<div class="date-header">{e(weekday(date_str))}</div>')

            for art in day_arts:
                title   = (art.get("title") or "（无标题）").strip()
                url     = art.get("url") or art.get("link") or ""
                digest  = (art.get("digest") or "").strip()
                body    = clip((art.get("content") or art.get("body") or "").strip())
                score   = art.get("signal_score")
                ts      = (art.get("publish_time") or "")

                excerpt_html = body_to_excerpt_html(body, max_chars=500) if body else ""

                out.append('<div class="card">')

                # Title
                if url:
                    out.append(f'<div class="card-title"><a href="{e(url)}" target="_blank" rel="noopener">{e(title)}</a></div>')
                else:
                    out.append(f'<div class="card-title">{e(title)}</div>')

                # Meta row
                meta_parts = []
                if ts:
                    meta_parts.append(e(ts[:16]))
                if score is not None:
                    meta_parts.append(f'<span class="score-chip">★ {score}</span>')
                if meta_parts:
                    out.append(f'<div class="card-meta">{"  ·  ".join(meta_parts)}</div>')

                # Digest
                if digest:
                    out.append(f'<div class="digest-wrap">{e(digest)}</div>')

                # Body excerpt (collapsible, ~500 chars with highlights)
                if excerpt_html:
                    out.append('<details class="body-detail" open>')
                    out.append('<summary class="body-toggle">正文摘要（约 500 字）</summary>')
                    out.append(f'<div class="body-content">{excerpt_html}</div>')
                    out.append('</details>')

                # Footer link
                if url:
                    out.append(f'<div class="card-footer"><a class="card-link" href="{e(url)}" target="_blank" rel="noopener">🔗 原文</a></div>')

                out.append('</div>')  # .card

            out.append('</div>')  # .date-group

        out.append('</div>')  # .panel

    out.append('</div>')  # .content

    out.append(f'<script>{JS}</script>')
    out.append('</body></html>')
    return "\n".join(out)


# ── main ───────────────────────────────────────────────────────────────────

def main():
    summaries = {}
    if os.path.isfile(SUMS):
        with open(SUMS, "r", encoding="utf-8") as f:
            summaries = json.load(f)

    if os.path.isfile(PROC):
        with open(PROC, "r", encoding="utf-8") as f:
            grouped: dict = json.load(f)
        total = sum(len(v) for v in grouped.values())
    else:
        with open(RAW, "r", encoding="utf-8") as f:
            articles = json.load(f)
        grouped = defaultdict(list)
        for a in articles:
            grouped[account_key(a)].append(a)
        from last30days_signals import apply_last30days_pipeline
        for k in list(grouped.keys()):
            grouped[k] = apply_last30days_pipeline(grouped[k])
        total = len(articles)

    accounts_sorted = sorted(grouped.items(), key=lambda x: -len(x[1]))

    all_dates = [
        a.get("publish_time", "")[:10]
        for arts in grouped.values()
        for a in arts
        if a.get("publish_time")
    ]
    date_min = min(all_dates) if all_dates else ""
    date_max = max(all_dates) if all_dates else ""

    html_content = build_html(accounts_sorted, summaries, total, date_min, date_max)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"✓ 已写出 {OUT}  ({len(html_content):,} chars)")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成每日资讯简报 HTML：output/YYYY-MM-DD-wechat-crawler.html
布局：左侧侧边栏（公众号列表）+ 右侧内容区（首页词云/Top10 + 各公众号文章卡片）
特性：
  - 文章卡片显示 AI 摘要（Markdown → HTML，通过 marked.js 渲染）
  - 正文节选（~500字，高亮关键词）
  - 顶部日期筛选器（默认今日）
"""

import html as html_mod
import json
import os
import re
import sys
from collections import Counter
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from utils import body_to_excerpt_html

PROC  = os.path.join(ROOT, "data", "processed", "articles_by_account.json")
SUMS  = os.path.join(ROOT, "output", "summaries.json")
OUT_DIR = os.path.join(ROOT, "output")

STOPWORDS = {
    '的','了','在','是','和','有','我','这','那','也','都','就','还','不','到',
    '他','她','它','AI','ai','上','中','下','与','及','对','为','被','让','将',
    '从','如','但','且','你','我','他','她','它','们','啊','呢','吧','哦','哈',
    '嗯','嘛','a','an','the','in','of','to','and','is','for','with','on','by',
    'at','this','that','from',
}


def safe_id(name: str) -> str:
    return re.sub(r'[^a-zA-Z0-9\u4e00-\u9fff]', '_', name)


def get_summary_text(summaries: dict, url: str) -> str:
    obj = summaries.get(url, {})
    if isinstance(obj, dict):
        return obj.get('summary', '') or obj.get('text', '')
    if isinstance(obj, str):
        return obj
    return ''


def build_wordcloud_data(articles: list) -> str:
    freq: Counter = Counter()
    for a in articles:
        title = a.get('title', '')
        for m in re.finditer(r'[\u4e00-\u9fff]{2,8}', title):
            w = m.group()
            if w not in STOPWORDS:
                freq[w] += 1
        for m in re.finditer(r'[A-Za-z]{3,}', title):
            w = m.group()
            if w.lower() not in STOPWORDS:
                freq[w] += 1
    top = freq.most_common(80)
    return json.dumps([[w, max(cnt * 10, 14)] for w, cnt in top], ensure_ascii=False)


def generate(target_date: str | None = None) -> str:
    if target_date is None:
        target_date = date.today().isoformat()

    with open(PROC, encoding='utf-8') as f:
        raw = json.load(f)
    with open(SUMS, encoding='utf-8') as f:
        summaries = json.load(f)

    # 只取目标日期的文章
    all_articles: list[dict] = []
    for acc_key, arts in raw.items():
        for a in arts:
            if a.get('publish_time', '') == target_date:
                a = dict(a)
                a['_acc_name'] = acc_key.rsplit('_', 1)[0]
                all_articles.append(a)

    print(f"[export_daily_report] {target_date} 共 {len(all_articles)} 篇文章")

    wc_data = build_wordcloud_data(all_articles)

    # 按账号分组，按文章数降序
    acc_map: dict[str, list] = {}
    for a in all_articles:
        acc_map.setdefault(a['_acc_name'], []).append(a)
    sorted_accs = sorted(acc_map.items(), key=lambda x: -len(x[1]))

    # Top 10（按 score 降序）
    top10 = sorted(all_articles, key=lambda a: a.get('score', 0), reverse=True)[:10]
    top_articles_json = json.dumps(
        [{'title': a.get('title', ''), 'url': a.get('url', ''),
          'score': a.get('score', 0), 'account': a['_acc_name']}
         for a in top10],
        ensure_ascii=False
    )

    # 侧边栏
    sidebar_items = ''
    for acc_name, arts in sorted_accs:
        sid = safe_id(acc_name)
        cnt = len(arts)
        sidebar_items += (
            f'<div class="nav-item" data-acc="{sid}" onclick="showPanel(\'{sid}\')">'
            f'{html_mod.escape(acc_name)}'
            f'<span class="nav-badge">{cnt}</span></div>\n'
        )

    # 文章面板
    panels_html = ''
    for acc_name, arts in sorted_accs:
        sid = safe_id(acc_name)
        cards = ''
        for a in arts:
            title     = a.get('title', '无标题')
            url       = a.get('url', '#')
            score     = a.get('score', 0)
            pub       = a.get('publish_time', '')
            body_text = (a.get('content') or a.get('body') or '').strip()
            summary   = get_summary_text(summaries, url)
            excerpt   = body_to_excerpt_html(body_text, max_chars=500) if body_text else ''

            score_color = (
                '#e74c3c' if score >= 8
                else '#e67e22' if score >= 6
                else '#7f8c8d'
            )

            # Markdown 摘要存入 data-md 属性，由 marked.js 前端渲染
            if summary:
                md_attr = html_mod.escape(summary)
                summary_block = (
                    f'<div class="card-summary" data-md="{md_attr}">'
                    f'<div class="summary-label">AI 摘要</div></div>'
                )
            else:
                summary_block = '<div class="card-no-summary">暂无 AI 摘要</div>'

            excerpt_block = (
                f'<details open><summary>正文节选</summary>'
                f'<div class="card-excerpt">{excerpt}</div></details>'
            ) if excerpt else ''

            cards += f'''
<div class="article-card" data-date="{pub}">
  <div class="card-header">
    <a class="card-title" href="{html_mod.escape(url)}" target="_blank">{html_mod.escape(title)}</a>
    <span class="card-score" style="background:{score_color}">{score}分</span>
  </div>
  <div class="card-meta">{pub} · {html_mod.escape(acc_name)}</div>
  {summary_block}
  {excerpt_block}
</div>'''
        panels_html += f'<div class="panel" id="panel-{sid}" style="display:none">{cards}</div>\n'

    # ── 输出 HTML ───────────────────────────────────────────────────────────────
    html_out = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>AI资讯日报 · {target_date}</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<script src="https://cdn.jsdelivr.net/npm/wordcloud2.js@1.2.2/src/wordcloud2.js"></script>
<script src="https://cdn.jsdelivr.net/npm/marked@9/marked.min.js"></script>
<style>
:root {{
  --bg:#f5f6fa; --surface:#fff; --primary:#2c3e7a; --accent:#3498db;
  --border:#e8ecf0; --text:#2c3e50; --muted:#7f8c8d; --radius:10px;
}}
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Segoe UI',sans-serif;
      background:var(--bg);color:var(--text);min-height:100vh;display:flex;flex-direction:column;}}
/* ─── 顶栏 ─────────────────────────────── */
.topbar{{background:var(--primary);color:#fff;padding:12px 24px;display:flex;
         align-items:center;justify-content:space-between;position:sticky;
         top:0;z-index:100;box-shadow:0 2px 8px rgba(0,0,0,.2);}}
.topbar-title{{font-size:18px;font-weight:700;}}
.date-filter{{display:flex;align-items:center;gap:8px;font-size:13px;}}
.date-input{{padding:4px 8px;border:1px solid rgba(255,255,255,.4);border-radius:6px;
             background:rgba(255,255,255,.15);color:#fff;font-size:12px;}}
.date-input::-webkit-calendar-picker-indicator{{filter:invert(1);}}
.date-today-btn{{padding:4px 10px;background:rgba(255,255,255,.25);border:none;
                 border-radius:6px;color:#fff;cursor:pointer;font-size:12px;}}
.date-today-btn:hover{{background:rgba(255,255,255,.4);}}
.date-filter-count{{font-size:12px;opacity:.85;}}
/* ─── 布局 ─────────────────────────────── */
.layout{{display:flex;flex:1;height:calc(100vh - 52px);overflow:hidden;}}
.sidebar{{width:220px;background:var(--surface);border-right:1px solid var(--border);
          overflow-y:auto;flex-shrink:0;padding:12px 0;}}
.sidebar-section{{padding:6px 16px;font-size:11px;color:var(--muted);font-weight:600;
                  letter-spacing:.5px;text-transform:uppercase;margin-top:8px;}}
.nav-item{{padding:9px 16px;cursor:pointer;font-size:14px;display:flex;align-items:center;
           justify-content:space-between;transition:background .15s;border-left:3px solid transparent;}}
.nav-item:hover{{background:#f0f4ff;}}
.nav-item.active{{background:#eef2ff;border-left-color:var(--accent);color:var(--accent);font-weight:600;}}
.nav-item.empty-filtered{{opacity:.4;pointer-events:none;}}
.nav-badge{{background:var(--accent);color:#fff;border-radius:10px;font-size:11px;
            padding:1px 7px;min-width:20px;text-align:center;}}
.home-nav{{padding:10px 16px;cursor:pointer;font-size:14px;font-weight:600;
           color:var(--primary);border-left:3px solid var(--primary);
           background:#eef2ff;display:flex;align-items:center;gap:6px;}}
/* ─── 内容区 ─────────────────────────────── */
.content{{flex:1;overflow-y:auto;padding:20px 24px;}}
.wc-wrap{{background:var(--surface);border-radius:var(--radius);padding:20px;
          border:1px solid var(--border);margin-bottom:20px;}}
.wc-title{{font-size:16px;font-weight:700;color:var(--primary);margin-bottom:12px;}}
#wc-canvas{{width:100%;height:260px;}}
.wc-fallback{{display:flex;flex-wrap:wrap;gap:8px;}}
.wc-fallback span{{background:#eef2ff;color:var(--primary);border-radius:20px;
                   padding:4px 12px;font-size:13px;}}
.top-articles{{background:var(--surface);border-radius:var(--radius);padding:20px;
               border:1px solid var(--border);}}
.top-articles h3{{font-size:15px;font-weight:700;color:var(--primary);margin-bottom:12px;}}
.top-item{{padding:10px 0;border-bottom:1px solid var(--border);display:flex;
           align-items:flex-start;gap:10px;}}
.top-item:last-child{{border-bottom:none;}}
.top-rank{{width:24px;height:24px;border-radius:50%;background:var(--accent);color:#fff;
           font-size:12px;font-weight:700;display:flex;align-items:center;
           justify-content:center;flex-shrink:0;margin-top:1px;}}
.top-rank.gold{{background:#f39c12;}}.top-rank.silver{{background:#95a5a6;}}.top-rank.bronze{{background:#cd7f32;}}
.top-item a{{font-size:14px;color:var(--text);text-decoration:none;line-height:1.5;}}
.top-item a:hover{{color:var(--accent);}}
.top-item-meta{{font-size:12px;color:var(--muted);margin-top:2px;}}
/* ─── 文章卡片 ─────────────────────────────── */
.article-card{{background:var(--surface);border-radius:var(--radius);padding:16px 20px;
               border:1px solid var(--border);margin-bottom:14px;transition:box-shadow .15s;}}
.article-card:hover{{box-shadow:0 2px 12px rgba(44,62,122,.1);}}
.card-header{{display:flex;align-items:flex-start;justify-content:space-between;
              gap:12px;margin-bottom:4px;}}
.card-title{{font-size:15px;font-weight:600;color:var(--text);text-decoration:none;
             line-height:1.5;flex:1;}}
.card-title:hover{{color:var(--accent);}}
.card-score{{border-radius:20px;padding:2px 10px;color:#fff;font-size:12px;
             font-weight:700;white-space:nowrap;flex-shrink:0;}}
.card-meta{{font-size:12px;color:var(--muted);margin-bottom:10px;}}
.summary-label{{font-size:11px;color:var(--accent);font-weight:700;
                letter-spacing:.5px;text-transform:uppercase;margin-bottom:8px;}}
.card-summary{{font-size:13px;color:#444;line-height:1.8;margin-bottom:10px;
               background:#f8faff;padding:12px 16px;border-radius:8px;
               border-left:3px solid var(--accent);}}
/* Markdown 渲染样式 */
.card-summary h1,.card-summary h2,.card-summary h3,.card-summary h4{{
  color:var(--primary);margin:10px 0 5px;font-weight:700;}}
.card-summary h1{{font-size:15px;}}
.card-summary h2{{font-size:14px;border-bottom:1px solid var(--border);padding-bottom:3px;}}
.card-summary h3{{font-size:13px;}}
.card-summary p{{margin:4px 0;line-height:1.75;}}
.card-summary ul,.card-summary ol{{padding-left:18px;margin:4px 0;}}
.card-summary li{{margin:3px 0;line-height:1.7;}}
.card-summary strong{{color:#2c3e50;font-weight:700;}}
.card-summary em{{color:#16a085;}}
.card-summary code{{background:#eef2ff;padding:1px 5px;border-radius:4px;
                    font-size:12px;color:#c0392b;font-family:monospace;}}
.card-summary pre{{background:#f4f6fb;padding:10px;border-radius:6px;
                   overflow-x:auto;font-size:12px;margin:6px 0;}}
.card-summary blockquote{{border-left:3px solid var(--accent);color:#555;margin:6px 0;
                          background:#f0f7ff;border-radius:0 4px 4px 0;padding:6px 10px;}}
.card-summary hr{{border:none;border-top:1px solid var(--border);margin:8px 0;}}
.card-summary table{{border-collapse:collapse;width:100%;font-size:12px;margin:6px 0;}}
.card-summary th{{background:#eef2ff;padding:5px 8px;border:1px solid var(--border);
                  color:var(--primary);font-weight:700;text-align:left;}}
.card-summary td{{padding:4px 8px;border:1px solid var(--border);}}
.card-summary tr:nth-child(even) td{{background:#f8faff;}}
.card-no-summary{{font-size:12px;color:var(--muted);margin-bottom:8px;font-style:italic;}}
details summary{{font-size:13px;color:var(--muted);cursor:pointer;user-select:none;padding:4px 0;}}
details[open] summary{{color:var(--accent);}}
.card-excerpt{{font-size:13px;line-height:1.8;color:#444;margin-top:8px;}}
.excerpt-p{{margin-bottom:8px;}}
.hl-num{{color:#e74c3c;font-weight:600;}}
.hl-quote{{color:#16a085;font-style:italic;}}
.hl-verb{{font-weight:600;color:var(--primary);}}
</style>
</head>
<body>
<div class="topbar">
  <div class="topbar-title">🗞️ AI资讯日报 · {target_date}</div>
  <div class="date-filter">
    <span>📅</span>
    <input class="date-input" type="date" id="dateFrom" value="{target_date}">
    <span>—</span>
    <input class="date-input" type="date" id="dateTo" value="{target_date}">
    <button class="date-today-btn" onclick="setToday()">今天</button>
    <span class="date-filter-count" id="filterCount"></span>
  </div>
</div>
<div class="layout">
  <div class="sidebar">
    <div class="home-nav" onclick="showPanel(\'home\')">🏠 今日热点</div>
    <div class="sidebar-section">公众号 ({len(sorted_accs)})</div>
    {sidebar_items}
  </div>
  <div class="content">
    <div class="panel" id="panel-home">
      <div class="wc-wrap">
        <div class="wc-title">今日热点话题词云</div>
        <canvas id="wc-canvas"></canvas>
      </div>
      <div class="top-articles">
        <h3>📈 今日 Top 10 文章</h3>
        <div id="topList"></div>
      </div>
    </div>
    {panels_html}
  </div>
</div>
<script>
const WC_DATA = {wc_data};
const TOP_ARTS = {top_articles_json};

// 词云
(function(){{
  try {{
    WordCloud(document.getElementById('wc-canvas'), {{
      list: WC_DATA, gridSize: 8, weightFactor: 2.2,
      fontFamily: 'PingFang SC,sans-serif',
      color: function() {{
        return ['#2c3e7a','#3498db','#e74c3c','#16a085','#e67e22','#8e44ad'][Math.floor(Math.random()*6)];
      }},
      rotateRatio: 0.3, rotationSteps: 2, backgroundColor: 'transparent', drawOutOfBound: false
    }});
  }} catch(e) {{
    const cvs = document.getElementById('wc-canvas');
    const fb = document.createElement('div'); fb.className = 'wc-fallback';
    WC_DATA.slice(0,40).forEach(function(d) {{
      const sp = document.createElement('span');
      sp.textContent = d[0]; sp.style.fontSize = Math.min(d[1]/3+10,28)+'px';
      fb.appendChild(sp);
    }});
    cvs.parentNode.replaceChild(fb, cvs);
  }}
}})();

// Top 10
(function(){{
  const el = document.getElementById('topList');
  TOP_ARTS.forEach(function(a, i) {{
    const rc = i===0?'gold':i===1?'silver':i===2?'bronze':'';
    el.innerHTML += '<div class="top-item"><div class="top-rank '+rc+'">'+(i+1)+'</div>'
      +'<div><a href="'+a.url+'" target="_blank">'+a.title+'</a>'
      +'<div class="top-item-meta">'+a.account+' · '+a.score+'分</div></div></div>';
  }});
}})();

// Markdown 渲染 AI 摘要
(function(){{
  if (typeof marked === 'undefined') return;
  marked.setOptions({{breaks: true, gfm: true}});
  document.querySelectorAll('.card-summary[data-md]').forEach(function(el) {{
    const label = el.querySelector('.summary-label');
    const raw = el.getAttribute('data-md');
    if (!raw) return;
    el.innerHTML = '';
    if (label) el.appendChild(label);
    const div = document.createElement('div');
    div.innerHTML = marked.parse(raw);
    el.appendChild(div);
  }});
}})();

function showPanel(id) {{
  document.querySelectorAll('.panel').forEach(function(p) {{ p.style.display = 'none'; }});
  const el = document.getElementById('panel-' + id);
  if (el) el.style.display = '';
  document.querySelectorAll('.nav-item').forEach(function(n) {{ n.classList.remove('active'); }});
  const ni = document.querySelector('[data-acc="' + id + '"]');
  if (ni) ni.classList.add('active');
}}

function applyDateFilter() {{
  const from = document.getElementById('dateFrom').value;
  const to   = document.getElementById('dateTo').value;
  let total = 0;
  document.querySelectorAll('.nav-item').forEach(function(nav) {{
    const accId = nav.dataset.acc;
    const panel = document.getElementById('panel-' + accId);
    if (!panel) return;
    let visible = 0;
    panel.querySelectorAll('.article-card').forEach(function(card) {{
      const d = card.dataset.date || '';
      const show = (!from || d >= from) && (!to || d <= to);
      card.style.display = show ? '' : 'none';
      if (show) visible++;
    }});
    total += visible;
    nav.classList.toggle('empty-filtered', visible === 0);
    const badge = nav.querySelector('.nav-badge');
    if (badge) badge.textContent = visible;
  }});
  document.getElementById('filterCount').textContent = '共 ' + total + ' 篇';
}}

function setToday() {{
  const t = new Date().toISOString().slice(0,10);
  document.getElementById('dateFrom').value = t;
  document.getElementById('dateTo').value   = t;
  applyDateFilter();
}}

document.getElementById('dateFrom').addEventListener('change', applyDateFilter);
document.getElementById('dateTo').addEventListener('change', applyDateFilter);
applyDateFilter();
showPanel('home');
</script>
</body>
</html>'''

    out_path = os.path.join(OUT_DIR, f"{target_date}-wechat-crawler.html")
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html_out)
    print(f"[export_daily_report] ✓ 已写出 {out_path}  ({len(html_out):,} chars)")
    return out_path


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='生成每日资讯简报 HTML')
    parser.add_argument('--date', default=None, help='目标日期 YYYY-MM-DD（默认今天）')
    args = parser.parse_args()
    generate(args.date)

#!/usr/bin/env bash
# 每日定时任务入口：完整爬取 + 导出浏览用 HTML
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p "$ROOT/logs"

LOG="$ROOT/logs/daily_$(date +%Y%m%d).log"

if [[ -f "$ROOT/.venv/bin/python" ]]; then
  PY="$ROOT/.venv/bin/python"
else
  PY="python3"
fi

{
  echo "=== $(date -Iseconds) 开始 daily crawl ==="

  # Step 1: 轮询各公众号最新文章链接（前 24 小时），追加到 extra_urls.txt
  # 微信直连限速时自动降级为 Sogou 模式
  echo "--- Step 1: 轮询新文章链接（微信直连） ---"
  "$PY" "$ROOT/scripts/poll_new_articles.py" --hours 24 || {
    echo "--- Step 1 降级: Sogou 模式 ---"
    "$PY" "$ROOT/scripts/poll_new_articles.py" --hours 24 --sogou || true
  }

  # Step 2: 爬取 + AI 摘要 + 导出
  echo "--- Step 2: 爬取 & 摘要 ---"
  "$PY" "$ROOT/main.py" --mode full

  # Step 3: 为新文章生成 AI 摘要（未在 summaries.json 缓存的文章）
  echo "--- Step 3: AI 摘要补全 ---"
  "$PY" "$ROOT/scripts/summarize_new_articles.py"

  # Step 4: 生成阅读页 HTML
  echo "--- Step 4: 导出阅读页 ---"
  "$PY" "$ROOT/scripts/export_articles_html.py"

  # Step 5: 生成每日简报 HTML（带 AI 摘要 Markdown 渲染）
  echo "--- Step 5: 导出每日简报 ---"
  "$PY" "$ROOT/scripts/export_daily_report.py"

  # Step 6: 六段式高密度提炼（耗 API，仅当 RUN_KEY_INSIGHT=1 时跑）
  if [[ "${RUN_KEY_INSIGHT:-0}" == "1" ]]; then
    echo "--- Step 6: key insight HTML ---"
    "$PY" "$ROOT/scripts/export_key_insight_html.py"
  fi

  echo "=== $(date -Iseconds) 结束 ==="
} >>"$LOG" 2>&1

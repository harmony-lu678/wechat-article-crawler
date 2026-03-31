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
  "$PY" "$ROOT/main.py" --mode full
  "$PY" "$ROOT/scripts/export_articles_html.py"
  # 六段式高密度提炼（耗 API，仅当 RUN_KEY_INSIGHT=1 时跑全文）
  if [[ "${RUN_KEY_INSIGHT:-0}" == "1" ]]; then
    "$PY" "$ROOT/scripts/export_key_insight_html.py"
  fi
  echo "=== $(date -Iseconds) 结束 ==="
} >>"$LOG" 2>&1

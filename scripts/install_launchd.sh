#!/usr/bin/env bash
# 安装 macOS launchd：每天 9:30 执行 run_daily_crawl.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/scripts/com.user.wechat-article-crawler.daily.plist"
DEST="$HOME/Library/LaunchAgents/com.user.wechat-article-crawler.daily.plist"

mkdir -p "$ROOT/logs"
cp "$SRC" "$DEST"
launchctl unload "$DEST" 2>/dev/null || true
launchctl load "$DEST"
echo "已安装并加载: $DEST"
echo "卸载: launchctl unload \"$DEST\" && rm \"$DEST\""
echo "下次运行: 每天 9:30 本机时间；或手动: $ROOT/scripts/run_daily_crawl.sh"

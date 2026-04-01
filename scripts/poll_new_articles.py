#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
轮询各公众号最新文章（前 N 小时内发布），将新 URL 追加到 config/extra_urls.txt。

两种模式（自动按优先级切换）：
  1. WeChat 直连模式（推荐）：需要在 config.yaml 配置 poll.wechat_cookie
     请求 mp.weixin.qq.com/mp/profile_ext?action=getmsg，返回 JSON 文章列表
  2. Sogou 搜索模式（无需登录，速率较低）：
     搜索 weixin.sogou.com 获取近期文章链接

运行方式：
  python scripts/poll_new_articles.py                # 默认前 24 小时
  python scripts/poll_new_articles.py --hours 48     # 前 48 小时
  python scripts/poll_new_articles.py --dry-run      # 只打印不写入
"""

import argparse
import json
import os
import re
import sys
import time
import yaml
import logging
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlencode, urlparse, parse_qs

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [poll] %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(ROOT, "logs", "poll.log"), encoding="utf-8"),
    ],
)
logger = logging.getLogger("poll")

EXTRA_URLS = os.path.join(ROOT, "config", "extra_urls.txt")
ACCOUNTS_FILE = os.path.join(ROOT, "config", "monitor_accounts.yaml")
PROC = os.path.join(ROOT, "data", "processed", "articles_by_account.json")

SOGOU_SEARCH  = "https://weixin.sogou.com/weixin"
WX_SEARCHBIZ  = "https://mp.weixin.qq.com/cgi-bin/searchbiz"
WX_APPMSG     = "https://mp.weixin.qq.com/cgi-bin/appmsg"

HEADERS_BROWSER = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9",
}


# ── 工具函数 ──────────────────────────────────────────────────────────────────

def _load_dotenv() -> dict[str, str]:
    """读取项目根目录的 .env 文件，返回 key→value 字典（不覆盖已有环境变量）。"""
    env_path = os.path.join(ROOT, ".env")
    env: dict[str, str] = {}
    if not os.path.isfile(env_path):
        return env
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip()
    return env


def load_config() -> dict:
    with open(os.path.join(ROOT, "config.yaml"), encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    # 用 .env / 环境变量补充 cookie / token（.env 优先于 config.yaml 空值）
    dotenv = _load_dotenv()
    poll = cfg.setdefault("poll", {})
    if not poll.get("wechat_cookie"):
        poll["wechat_cookie"] = os.environ.get("WX_COOKIE") or dotenv.get("WX_COOKIE", "")
    if not poll.get("wechat_token"):
        poll["wechat_token"] = os.environ.get("WX_TOKEN") or dotenv.get("WX_TOKEN", "")
    return cfg


def load_accounts() -> list[dict]:
    """
    加载要监控的账号列表。
    优先读 config/monitor_accounts.yaml；若不存在则从 processed JSON 自动生成。
    """
    if os.path.isfile(ACCOUNTS_FILE):
        with open(ACCOUNTS_FILE, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data.get("accounts", [])

    # 自动从 processed data 提取
    if not os.path.isfile(PROC):
        logger.error("找不到账号数据，请先运行 main.py 或创建 config/monitor_accounts.yaml")
        return []

    with open(PROC, encoding="utf-8") as f:
        grouped = json.load(f)

    accounts = []
    for arts in grouped.values():
        if not arts:
            continue
        a = arts[0]
        name = a.get("account_name", "").strip()
        biz = a.get("biz_id", "").strip()
        if name and biz:
            accounts.append({"name": name, "biz_id": biz})
    logger.info("从 processed JSON 自动加载 %d 个账号", len(accounts))
    return accounts


def load_existing_urls() -> set[str]:
    """读取 extra_urls.txt 中已有的 URL（避免重复写入）。"""
    urls: set[str] = set()
    if os.path.isfile(EXTRA_URLS):
        with open(EXTRA_URLS, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "mp.weixin.qq.com" in line:
                    urls.add(line)
    return urls


def is_wx_article_url(url: str) -> bool:
    return bool(url and "mp.weixin.qq.com" in url and "/s" in url)


def parse_sogou_date(date_str: str, now: datetime) -> Optional[datetime]:
    """
    将搜狗显示的时间字符串转换为 datetime 对象。
    常见格式：'1小时前'  '3天前'  '昨天'  '2026-03-30'  '03月31日'
    """
    date_str = date_str.strip()
    try:
        # 绝对日期 yyyy-mm-dd
        if re.match(r"\d{4}-\d{2}-\d{2}", date_str):
            return datetime.strptime(date_str[:10], "%Y-%m-%d")
        # mm月dd日
        m = re.match(r"(\d+)月(\d+)日", date_str)
        if m:
            month, day = int(m.group(1)), int(m.group(2))
            return datetime(now.year, month, day)
        # X小时前
        m = re.match(r"(\d+)小时前", date_str)
        if m:
            return now - timedelta(hours=int(m.group(1)))
        # X分钟前
        m = re.match(r"(\d+)分钟前", date_str)
        if m:
            return now - timedelta(minutes=int(m.group(1)))
        # 昨天
        if "昨天" in date_str:
            return now - timedelta(days=1)
        # X天前
        m = re.match(r"(\d+)天前", date_str)
        if m:
            return now - timedelta(days=int(m.group(1)))
    except Exception:
        pass
    return None


# ── 模式 1：WeChat MP 后台直连（需 cookie + token）──────────────────────────────

def _get_fakeid(account_name: str, token: str,
                session: requests.Session) -> Optional[str]:
    """通过 searchbiz 接口用账号名查 fakeid。"""
    try:
        resp = session.get(WX_SEARCHBIZ, params={
            "action": "search_biz",
            "begin": 0,
            "count": 5,
            "query": account_name,
            "token": token,
            "lang": "zh_CN",
            "f": "json",
            "ajax": "1",
        }, timeout=15)
        data = resp.json()
        biz_list = data.get("list", [])
        if not biz_list:
            return None
        # 优先完全匹配 nickname
        for b in biz_list:
            if b.get("nickname", "").strip() == account_name.strip():
                return b.get("fakeid")
        return biz_list[0].get("fakeid")
    except Exception as e:
        logger.warning("searchbiz %s 失败: %s", account_name, e)
        return None


def fetch_wx_direct(account_name: str, cookie: str, token: str,
                    hours: int, session: requests.Session) -> list[str]:
    """
    通过 MP 后台 appmsg list_ex 接口拉取账号最新文章列表，返回符合时间窗口的 URL。
    Step1: searchbiz 获取 fakeid
    Step2: appmsg list_ex 分页拉文章，直到超出时间窗口
    """
    fakeid = _get_fakeid(account_name, token, session)
    if not fakeid:
        logger.debug("未找到 fakeid: %s，跳过直连", account_name)
        return []

    cutoff = datetime.now() - timedelta(hours=hours)
    urls: list[str] = []
    begin = 0
    count = 20

    while True:
        try:
            resp = session.get(WX_APPMSG, params={
                "action": "list_ex",
                "begin": begin,
                "count": count,
                "fakeid": fakeid,
                "type": "9",
                "query": "",
                "token": token,
                "lang": "zh_CN",
                "f": "json",
                "ajax": "1",
            }, timeout=15)
            data = resp.json()
        except Exception as e:
            logger.warning("appmsg %s 失败: %s", account_name, e)
            break

        base = data.get("base_resp", {})
        if base.get("ret") != 0:
            logger.warning("appmsg %s ret=%s", account_name, base.get("ret"))
            break

        art_list = data.get("app_msg_list", [])
        if not art_list:
            break

        has_older = False
        for art in art_list:
            ts = art.get("update_time", 0)
            pub_dt = datetime.fromtimestamp(ts) if ts else None
            url = art.get("link", "")

            if pub_dt and pub_dt < cutoff:
                has_older = True
                continue  # 不 break，同一批次可能混排
            if is_wx_article_url(url):
                urls.append(url)

        # 若本批全部或部分超出时间窗口，不再翻页
        if has_older or len(art_list) < count:
            break

        begin += count
        time.sleep(1.5)

    return urls


# ── 模式 2：Sogou 搜索（无需登录）─────────────────────────────────────────────

def fetch_sogou(account_name: str, hours: int,
                session: requests.Session) -> list[str]:
    """
    通过搜狗微信搜索账号名，返回近 N 小时内发布的文章 URL 列表。
    """
    params = {
        "type": "2",          # 2=文章搜索
        "query": account_name,
        "ie": "utf8",
        "s_from": "input",
    }
    try:
        resp = session.get(SOGOU_SEARCH, params=params,
                           headers=HEADERS_BROWSER, timeout=20)
        html = resp.text
    except Exception as e:
        logger.warning("Sogou 搜索 %s 失败: %s", account_name, e)
        return []

    now = datetime.now()
    cutoff = now - timedelta(hours=hours)
    urls: list[str] = []

    # 搜狗结果里的文章链接（跳转链接，需解析或直接提取 wx 链接）
    # 1. 尝试直接找嵌入的 mp.weixin.qq.com 链接
    wx_links = re.findall(
        r'href="(https://mp\.weixin\.qq\.com/s[^"]+)"', html
    )
    # 2. 搜狗跳转链接：/link?url=... 含日期戳的条目
    sogou_items = re.findall(
        r'<div class="txt-box">(.*?)</div>\s*</div>',
        html, re.DOTALL
    )

    # 从搜狗 article 结构提取（简化版）
    # 每条结果格式：<span class="s2">账号名</span>...<span class="s3">日期</span>
    # 以及 <a href="..."> 链接
    article_blocks = re.findall(
        r'uigs="article_title_\d+"[^>]*href="([^"]+)"[^>]*>.*?'
        r'<span class=["\']s3["\']>([^<]+)<',
        html, re.DOTALL
    )

    for raw_url, date_str in article_blocks:
        raw_url = raw_url.replace("&amp;", "&")
        pub_dt = parse_sogou_date(date_str, now)
        if pub_dt and pub_dt < cutoff:
            continue
        # 如果是搜狗跳转链接需要解析，先尝试提取直接链接
        if "mp.weixin.qq.com" in raw_url:
            if is_wx_article_url(raw_url):
                urls.append(raw_url)

    # 补充直接找到的 wx 链接（可能有重复，外层去重）
    urls.extend(wx_links)

    # 过滤纯链接中含 __biz 且与 account_name 不一定对应的情况
    # 这里用 set 去重即可，精确度依赖搜索结果相关性
    return list(dict.fromkeys(urls))  # 保序去重


# ── 主流程 ───────────────────────────────────────────────────────────────────

def poll(hours: int = 24, dry_run: bool = False) -> int:
    config = load_config()
    accounts = load_accounts()
    if not accounts:
        logger.error("没有账号可监控，退出")
        return 0

    poll_cfg = config.get("poll", {})
    wx_cookie = poll_cfg.get("wechat_cookie", "").strip()
    wx_token  = poll_cfg.get("wechat_token",  "").strip()
    request_interval = poll_cfg.get("request_interval", 3)

    existing_urls = load_existing_urls()
    new_urls: list[str] = []

    session = requests.Session()
    session.headers.update({
        **HEADERS_BROWSER,
        "Cookie": wx_cookie,
        "Referer": "https://mp.weixin.qq.com/",
    })

    use_direct = bool(wx_cookie and wx_token)
    mode = "WeChat MP后台直连" if use_direct else "Sogou搜索"
    logger.info("轮询模式: %s | 窗口: 前 %d 小时 | 账号数: %d",
                mode, hours, len(accounts))

    for i, acc in enumerate(accounts):
        name = acc.get("name", "")
        biz = acc.get("biz_id", "")
        logger.info("[%d/%d] %s", i + 1, len(accounts), name)

        try:
            if use_direct:
                found = fetch_wx_direct(name, wx_cookie, wx_token, hours, session)
            else:
                found = fetch_sogou(name, hours, session)
        except Exception as e:
            logger.warning("账号 %s 轮询异常: %s", name, e)
            found = []

        added = 0
        for url in found:
            url = url.strip()
            if is_wx_article_url(url) and url not in existing_urls:
                new_urls.append(url)
                existing_urls.add(url)
                added += 1

        logger.info("  → 新增 %d 篇", added)
        time.sleep(request_interval)

    logger.info("本次共发现新文章 %d 篇", len(new_urls))

    if not new_urls:
        return 0

    if dry_run:
        logger.info("[dry-run] 不写入文件，仅打印:")
        for u in new_urls:
            print(u)
        return len(new_urls)

    # 追加写入 extra_urls.txt
    os.makedirs(os.path.dirname(EXTRA_URLS), exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    with open(EXTRA_URLS, "a", encoding="utf-8") as f:
        f.write(f"\n# ── 轮询新增 {today} ──────────────────────\n")
        for url in new_urls:
            f.write(url + "\n")

    logger.info("已追加到 %s", EXTRA_URLS)
    return len(new_urls)


def main():
    parser = argparse.ArgumentParser(description="轮询公众号最新文章")
    parser.add_argument("--hours", type=int, default=24,
                        help="抓取最近 N 小时内的文章（默认 24）")
    parser.add_argument("--dry-run", action="store_true",
                        help="仅打印，不写入 extra_urls.txt")
    args = parser.parse_args()

    os.makedirs(os.path.join(ROOT, "logs"), exist_ok=True)
    count = poll(hours=args.hours, dry_run=args.dry_run)
    print(f"轮询完成，新增 {count} 篇文章链接")


if __name__ == "__main__":
    main()

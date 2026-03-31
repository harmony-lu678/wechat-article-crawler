#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工具函数模块
"""

import html
import os
import re
import time
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse, parse_qs
import hashlib
from fake_useragent import UserAgent

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/crawler.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def get_random_user_agent() -> str:
    """获取随机User-Agent"""
    try:
        ua = UserAgent()
        return ua.random
    except:
        # 备用User-Agent列表
        user_agents = [
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
        ]
        import random
        return random.choice(user_agents)


def load_extra_urls_from_file(path: str) -> list:
    """
    从文本文件加载额外微信文章链接（每行一个 URL，# 开头为注释）。
    若整行不是 URL，会尝试提取行内首个 mp.weixin.qq.com 链接。

    Args:
        path: 文件路径（相对 cwd 或绝对路径）

    Returns:
        去重后的 URL 列表（保持顺序）
    """
    if not path or not os.path.isfile(path):
        return []

    urls = []
    url_in_line = re.compile(r"https?://mp\.weixin\.qq\.com/s[^\s\)\]\"\'<>]*")

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if is_wechat_article_url(line):
                urls.append(line)
                continue
            m = url_in_line.search(line)
            if m:
                u = m.group(0).rstrip(".,;，。；")
                if is_wechat_article_url(u):
                    urls.append(u)

    seen = set()
    out = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def merge_url_lists(*lists: list) -> list:
    """多个 URL 列表按顺序合并并去重。"""
    seen = set()
    out = []
    for lst in lists:
        for u in lst:
            if u not in seen:
                seen.add(u)
                out.append(u)
    return out


def is_wechat_article_url(url: str) -> bool:
    """
    判断是否为微信公众号文章链接

    Args:
        url: 待检查的URL

    Returns:
        bool: 是否为微信文章链接
    """
    if not url or not isinstance(url, str):
        return False

    return 'mp.weixin.qq.com' in url and '/s' in url


def extract_article_id(url: str) -> Optional[str]:
    """
    从微信文章URL中提取唯一ID

    Args:
        url: 微信文章URL

    Returns:
        文章唯一ID（使用__biz和mid组合）
    """
    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        biz = params.get('__biz', [''])[0]
        mid = params.get('mid', [''])[0]
        idx = params.get('idx', ['1'])[0]

        if biz and mid:
            return f"{biz}_{mid}_{idx}"

        # 如果无法解析，使用URL的MD5作为ID
        return hashlib.md5(url.encode()).hexdigest()
    except Exception as e:
        logger.warning(f"提取文章ID失败: {url}, 错误: {e}")
        return None


def extract_biz_id(url: str) -> Optional[str]:
    """
    从微信文章URL中提取公众号BIZ ID

    Args:
        url: 微信文章URL

    Returns:
        公众号BIZ ID
    """
    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        biz = params.get('__biz', [''])[0]
        return biz if biz else None
    except Exception as e:
        logger.warning(f"提取BIZ ID失败: {url}, 错误: {e}")
        return None


def clean_text(text: str) -> str:
    """
    清理文本内容

    Args:
        text: 原始文本

    Returns:
        清理后的文本
    """
    if not text:
        return ""

    # 移除多余的空白字符
    text = re.sub(r'\s+', ' ', text)
    # 移除首尾空白
    text = text.strip()

    return text


def is_within_date_range(date_str: str, days: int = 30) -> bool:
    """
    判断日期是否在指定天数范围内

    Args:
        date_str: 日期字符串
        days: 天数范围

    Returns:
        是否在范围内
    """
    try:
        # 尝试多种日期格式
        date_formats = [
            '%Y-%m-%d',
            '%Y/%m/%d',
            '%Y年%m月%d日',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d %H:%M'
        ]

        article_date = None
        for fmt in date_formats:
            try:
                article_date = datetime.strptime(date_str, fmt)
                break
            except:
                continue

        if not article_date:
            logger.warning(f"无法解析日期: {date_str}")
            return True  # 无法解析时默认包含

        cutoff_date = datetime.now() - timedelta(days=days)
        return article_date >= cutoff_date

    except Exception as e:
        logger.warning(f"日期判断失败: {date_str}, 错误: {e}")
        return True  # 出错时默认包含


def format_file_size(size_bytes: int) -> str:
    """
    格式化文件大小

    Args:
        size_bytes: 字节数

    Returns:
        格式化的文件大小字符串
    """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"


def sanitize_filename(filename: str, max_length: int = 200) -> str:
    """
    清理文件名，移除非法字符

    Args:
        filename: 原始文件名
        max_length: 最大长度

    Returns:
        清理后的文件名
    """
    # 移除非法字符
    filename = re.sub(r'[\\/*?:"<>|]', '_', filename)
    # 移除多余空格
    filename = re.sub(r'\s+', '_', filename)
    # 限制长度
    if len(filename) > max_length:
        filename = filename[:max_length]

    return filename


def retry_on_failure(func, max_retries: int = 3, delay: int = 5):
    """
    失败重试装饰器

    Args:
        func: 要执行的函数
        max_retries: 最大重试次数
        delay: 重试延迟(秒)

    Returns:
        函数执行结果
    """
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"执行失败，{delay}秒后重试 ({attempt + 1}/{max_retries}): {e}")
                time.sleep(delay)
            else:
                logger.error(f"执行失败，已达最大重试次数: {e}")
                raise


def estimate_tokens(text: str) -> int:
    """
    估算文本的token数量（粗略估算）
    中文：1字符 ≈ 1.5 tokens
    英文：1单词 ≈ 1.3 tokens

    Args:
        text: 文本内容

    Returns:
        估算的token数量
    """
    if not text:
        return 0

    # 统计中文字符
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    # 统计英文单词
    english_words = len(re.findall(r'[a-zA-Z]+', text))
    # 其他字符
    other_chars = len(text) - chinese_chars - english_words

    # 估算token数
    tokens = int(chinese_chars * 1.5 + english_words * 1.3 + other_chars * 0.5)

    return tokens


def split_text_by_tokens(text: str, max_tokens: int = 6000) -> list:
    """
    按token数量分割文本

    Args:
        text: 原始文本
        max_tokens: 每段最大token数

    Returns:
        分割后的文本列表
    """
    if estimate_tokens(text) <= max_tokens:
        return [text]

    chunks = []
    current_chunk = ""

    # 按段落分割
    paragraphs = text.split('\n\n')

    for para in paragraphs:
        para_tokens = estimate_tokens(current_chunk + para)

        if para_tokens <= max_tokens:
            current_chunk += para + '\n\n'
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = para + '\n\n'

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks


class RateLimiter:
    """请求频率限制器"""

    def __init__(self, interval: float = 3.0):
        """
        初始化频率限制器

        Args:
            interval: 请求间隔(秒)
        """
        self.interval = interval
        self.last_request_time = 0

    def wait(self):
        """等待到下次请求时间"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.interval:
            sleep_time = self.interval - time_since_last
            logger.debug(f"等待 {sleep_time:.2f} 秒...")
            time.sleep(sleep_time)

        self.last_request_time = time.time()


def dedupe_articles_by_url(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    按 url 去重，保留首次出现；无 url 时按 title+publish_time 去重。
    避免同一链接多次进入 CSV/合并列表导致正文与总结重复。
    """
    seen_url: Set[str] = set()
    seen_fp: Set[str] = set()
    out: List[Dict[str, Any]] = []
    for a in articles:
        u = (a.get("url") or "").strip()
        if u:
            if u in seen_url:
                continue
            seen_url.add(u)
        else:
            fp = f"{a.get('title') or ''}|{a.get('publish_time') or ''}"
            if fp in seen_fp:
                continue
            seen_fp.add(fp)
        out.append(a)
    if len(out) < len(articles):
        logger.info("按 URL/标题去重: %s → %s 篇", len(articles), len(out))
    return out


def dedupe_consecutive_body_text(text: str) -> str:
    """
    去掉连续重复的段落与段内连续重复行（微信正文已落库时，导出 HTML 仍可再清一遍）。
    """
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n{2,}", text)
    merged: list[str] = []
    for b in blocks:
        b = b.strip()
        if not b:
            continue
        if merged and merged[-1] == b:
            continue
        lines = [ln.rstrip() for ln in b.split("\n")]
        dedup_lines: list[str] = []
        for ln in lines:
            s = ln.strip()
            if not s:
                continue
            if dedup_lines and dedup_lines[-1].strip() == s:
                continue
            dedup_lines.append(ln)
        merged.append("\n".join(dedup_lines))
    final: list[str] = []
    for b in merged:
        if final and final[-1] == b:
            continue
        final.append(b)
    return "\n\n".join(final)


def _inline_md_bold_line(line: str) -> str:
    parts = line.split("**")
    chunks: list[str] = []
    for i, p in enumerate(parts):
        esc = html.escape(p, quote=False)
        if i % 2 == 1:
            chunks.append(f'<strong class="article-body-strong">{esc}</strong>')
        else:
            chunks.append(esc)
    return "".join(chunks)


def sanitize_summary_for_public(text: str) -> str:
    """
    总结写入对外 Markdown / JSON / HTML 前的查重兜底：
    - 连续重复段落与段内连续重复行（dedupe_consecutive_body_text）
    - 全局完全相同的段落仅保留首次（非连续重复，常见于分节套话）
    """
    if not text:
        return text
    t = dedupe_consecutive_body_text(text.strip())
    return _dedupe_global_duplicate_paragraphs(t)


def _dedupe_global_duplicate_paragraphs(text: str) -> str:
    blocks = re.split(r"\n{2,}", text)
    seen: Set[str] = set()
    out: list[str] = []
    for b in blocks:
        b = b.strip()
        if not b:
            continue
        if b in seen:
            continue
        seen.add(b)
        out.append(b)
    return "\n\n".join(out)


def article_body_plain_to_html(text: str) -> str:
    """
    阅读页正文：去重 + 将 ## 标题与 **粗体** 转为 HTML（内容已转义）。
    """
    text = dedupe_consecutive_body_text(text)
    if not text:
        return ""
    parts = re.split(r"\n{2,}", text)
    out: list[str] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if part.startswith("## "):
            out.append(
                f'<h3 class="article-body-h3">{html.escape(part[3:].strip())}</h3>'
            )
        else:
            lines = part.split("\n")
            inner = "<br/>".join(_inline_md_bold_line(ln) for ln in lines)
            out.append(f'<p class="article-body-p">{inner}</p>')
    return "\n".join(out)


# ── 正文 500 字摘要 + 关键词高亮 ─────────────────────────────────────────────

# 信息密度评分：用于优先选句
_INFO_SCORE = re.compile(
    r'\d[\d.,]*\s*(?:%|亿|万|千|百|倍|个|项|家|款|种|篇|次|人|年|月)'
    r'|[「『][^」』]{4,40}[」』]'
    r'|\*\*.+?\*\*'
    r'|首次|重磅|突破|发布|推出|上线|宣布|增长|下降|超过|达到',
    re.UNICODE,
)

# 单遍高亮：combined regex，各组互斥，不会二次替换
# group1=bold内容  group2=数字+单位  group3=中文引号  group4=动作词
_HL_COMBINED = re.compile(
    r'\*\*(.+?)\*\*'                                                    # g1 bold
    r'|(\d[\d.,]*\s*(?:%|亿|万|千|百|倍|个|项|家|款|种|篇|次|人|年|月))'  # g2 num
    r'|([「『][^」』]{4,40}[」』])'                                       # g3 Chinese quote only
    r'|(首次|重磅|突破|发布|推出|上线|宣布|增长|下降|超过|达到)',           # g4 action
    re.UNICODE,
)


def _score_sentence(s: str) -> int:
    return len(_INFO_SCORE.findall(s))


def _smart_excerpt(text: str, max_chars: int = 500) -> str:
    """
    从正文提取约 max_chars 字的高信息密度摘要。
    按句子断开后，优先选信息密度高的句子（保持原顺序），再补前段普通句。
    返回保留段落分隔符（\\n\\n）的纯文本。
    """
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE).strip()
    if not text:
        return ""

    # 按段落分割，段内再按句子分割，构建 (para_idx, sent_idx, text) 列表
    paragraphs = re.split(r'\n{2,}', text)
    all_sents: list[tuple[int, int, str]] = []
    for pi, para in enumerate(paragraphs):
        raw = re.split(r'(?<=[。！？])', para.strip())
        for si, s in enumerate(raw):
            s = s.strip()
            if s and len(s) > 3:
                all_sents.append((pi, si, s))

    if not all_sents:
        return text[:max_chars] + ("…" if len(text) > max_chars else "")

    scored = [(pi, si, s, _score_sentence(s)) for pi, si, s in all_sents]
    high = [(pi, si, s) for pi, si, s, sc in scored if sc >= 1]
    low  = [(pi, si, s) for pi, si, s, sc in scored if sc == 0]

    selected: set[tuple[int, int]] = set()
    seen_text: set[str] = set()
    total = 0
    result: list[tuple[int, int, str]] = []

    for pool in (high, low):
        for pi, si, s in pool:
            if total >= max_chars:
                break
            if (pi, si) not in selected and s not in seen_text:
                selected.add((pi, si))
                seen_text.add(s)
                result.append((pi, si, s))
                total += len(s)

    result.sort()  # 恢复原顺序

    # 按段重组，段间用 \n\n 分隔
    by_para: dict[int, list[str]] = {}
    for pi, _si, s in result:
        by_para.setdefault(pi, []).append(s)

    excerpt = "\n\n".join("".join(sents) for _pi, sents in sorted(by_para.items()))

    if len(excerpt) > max_chars + 30:
        excerpt = excerpt[:max_chars] + "…"
    return excerpt or text[:max_chars] + "…"


def _apply_highlights(line: str) -> str:
    """
    单遍扫描：对原始纯文本行应用高亮，返回 HTML 片段。
    绝不对已生成的 HTML 做二次匹配，彻底避免标签嵌套。
    """
    out: list[str] = []
    pos = 0
    for m in _HL_COMBINED.finditer(line):
        out.append(html.escape(line[pos:m.start()]))
        pos = m.end()
        if m.group(1) is not None:
            out.append(f'<mark class="hl-key">{html.escape(m.group(1))}</mark>')
        elif m.group(2) is not None:
            out.append(f'<mark class="hl-num">{html.escape(m.group(2))}</mark>')
        elif m.group(3) is not None:
            out.append(f'<mark class="hl-quote">{html.escape(m.group(3))}</mark>')
        elif m.group(4) is not None:
            out.append(f'<mark class="hl-action">{html.escape(m.group(4))}</mark>')
    out.append(html.escape(line[pos:]))
    return "".join(out)


def body_to_excerpt_html(text: str, max_chars: int = 500) -> str:
    """
    从正文提取约 max_chars 字的摘要，高亮关键数字、粗体词、引号金句、动作词。
    段落间用 <p> 包裹，行内换行用 <br/>，返回可直接嵌入 HTML 的片段。
    """
    # 连续重复 + 全局重复段落都去掉，再提取摘要
    text = dedupe_consecutive_body_text(text)
    text = _dedupe_global_duplicate_paragraphs(text)
    if not text:
        return ""
    excerpt = _smart_excerpt(text, max_chars)
    # 按段落分割，每段独立 <p>
    paras = re.split(r'\n{2,}', excerpt)
    html_paras: list[str] = []
    for para in paras:
        lines = para.split("\n")
        hl_lines = [_apply_highlights(ln) for ln in lines if ln.strip()]
        if hl_lines:
            inner = "<br/>".join(hl_lines)
            html_paras.append(f'<p class="excerpt-p">{inner}</p>')
    return "\n".join(html_paras)


if __name__ == "__main__":
    # 测试代码
    test_url = "https://mp.weixin.qq.com/s?__biz=MjM5NDQ3ODI3NQ==&mid=2651430654&idx=1&sn=e28a4214561b065ebb40fcb732630a77"

    print(f"是否为微信文章: {is_wechat_article_url(test_url)}")
    print(f"文章ID: {extract_article_id(test_url)}")
    print(f"BIZ ID: {extract_biz_id(test_url)}")

    test_text = "这是一段测试文本，包含中文和English words。"
    print(f"估算token数: {estimate_tokens(test_text)}")

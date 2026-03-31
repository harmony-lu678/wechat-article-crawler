#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
摘要与排序信号：借鉴 last30days-skill 的检索策略。
参考: https://github.com/mvanhorn/last30days-skill
     - scripts/lib/dedupe.py  (n-gram Jaccard、混合相似度、去重保留高分)
     - scripts/lib/score.py   (相关性 + 时效 + 互动/信号加权)
     - SPEC.md (normalize → score → dedupe 流水线)

微信公众号无 Reddit 点赞数据，用「正文长度」作为 richness 代理，参与分与 last30days 中
engagement 地位类似；无检索 query 时 relevance 用标题长度与是否有 digest 估计。
"""

from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

# 与 last30days score.py 比例同构（无互动数据时用 richness 替代 engagement）
WEIGHT_RELEVANCE = 0.45
WEIGHT_RECENCY = 0.25
WEIGHT_RICHNESS = 0.30

# 去重：与 dedupe.py 默认 0.7 接近；正文极长时略放宽避免误杀
DEFAULT_DEDUPE_THRESHOLD = 0.72

# 英文 stopwords（与 dedupe._tokenize 思路一致，便于中英混排）
_STOPWORDS = frozenset({
    "the", "a", "an", "to", "for", "how", "is", "in", "of", "on",
    "and", "with", "from", "by", "at", "this", "that", "it", "my",
    "your", "i", "me", "we", "you", "what", "are", "do", "can",
    "its", "be", "or", "not", "no", "so", "if", "but", "about",
    "all", "just", "get", "has", "have", "was", "will", "show",
})


def normalize_text(text: str) -> str:
    """与 last30days dedupe.normalize_text 一致：小写、去标点、压空白。"""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def get_ngrams(text: str, n: int = 3) -> Set[str]:
    """字符 n-gram（对中文同样有效，无需分词）。"""
    text = normalize_text(text)
    if len(text) < n:
        return {text} if text else set()
    return {text[i : i + n] for i in range(len(text) - n + 1)}


def jaccard_similarity(set_a: Set[str], set_b: Set[str]) -> float:
    if not set_a or not set_b:
        return 0.0
    inter = len(set_a & set_b)
    union = len(set_a | set_b)
    return inter / union if union > 0 else 0.0


def _tokenize_mixed(text: str) -> Set[str]:
    """中英混合：英文去 stopword；中文取连续 2+ 字块，减少与 last30days token Jaccard 差异。"""
    text = text.lower()
    tokens: Set[str] = set()
    for m in re.finditer(r"[a-z]{3,}", text):
        w = m.group(0)
        if w not in _STOPWORDS:
            tokens.add(w)
    for m in re.finditer(r"[\u4e00-\u9fff]{2,}", text):
        tokens.add(m.group(0))
    return tokens


def _token_jaccard(text_a: str, text_b: str) -> float:
    ta, tb = _tokenize_mixed(text_a), _tokenize_mixed(text_b)
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return inter / union if union else 0.0


def hybrid_similarity(text_a: str, text_b: str) -> float:
    """last30days dedupe._hybrid_similarity：max(字符 trigram Jaccard, token Jaccard)。"""
    tri = jaccard_similarity(get_ngrams(text_a, 3), get_ngrams(text_b, 3))
    tok = _token_jaccard(text_a, text_b)
    return max(tri, tok)


def _compare_fingerprint(article: Dict[str, Any]) -> str:
    """用于相似度：标题 + 正文前段（控制长度）。"""
    title = article.get("title") or ""
    body = article.get("content") or ""
    return f"{title}\n{body[:4000]}"


def log1p_safe(x: Optional[int]) -> float:
    if x is None or x < 0:
        return 0.0
    return math.log1p(x)


def normalize_to_100(values: List[float], default: float = 50.0) -> List[float]:
    """与 last30days score.normalize_to_100 一致。"""
    valid = [v for v in values if v is not None]
    if not valid:
        return [default for _ in values]

    min_val, max_val = min(valid), max(valid)
    rng = max_val - min_val
    if rng == 0:
        return [50.0 for _ in values]

    out = []
    for v in values:
        if v is None:
            out.append(default)
        else:
            out.append(((v - min_val) / rng) * 100.0)
    return out


def _parse_date_days_ago(publish_time: str) -> Optional[int]:
    if not publish_time:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S"):
        try:
            d = datetime.strptime(publish_time[:19], fmt)
            return (datetime.now() - d).days
        except ValueError:
            continue
    return None


def recency_subscore(publish_time: str) -> int:
    """0–100：越新越高。"""
    days = _parse_date_days_ago(publish_time)
    if days is None:
        return 50
    # 当天 ~100，约 60 天衰减到 ~40
    s = 100.0 - min(days, 120) * 0.85
    return max(0, min(100, int(s)))


def relevance_subscore(article: Dict[str, Any]) -> int:
    """无 query 时的启发式：标题信息量 + digest。"""
    title = article.get("title") or ""
    base = min(100, 40 + len(title.strip()) // 2)
    if (article.get("digest") or "").strip():
        base = min(100, base + 12)
    return max(0, min(100, base))


def score_articles_batch(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    为同一批文章打 last30days 风格综合分，写入 article['_signal']。
    """
    if not articles:
        return articles

    lens = [len((a.get("content") or "").strip()) for a in articles]
    raw_rich = [log1p_safe(L) for L in lens]
    rich_norm = normalize_to_100(raw_rich)

    out: List[Dict[str, Any]] = []
    for i, a in enumerate(articles):
        rel = relevance_subscore(a)
        rec = recency_subscore(a.get("publish_time") or "")
        rich = int(rich_norm[i]) if i < len(rich_norm) else 50

        overall = (
            WEIGHT_RELEVANCE * rel
            + WEIGHT_RECENCY * rec
            + WEIGHT_RICHNESS * rich
        )
        score = max(0, min(100, int(overall)))

        a["_signal"] = {
            "score": score,
            "relevance": rel,
            "recency": rec,
            "richness": rich,
        }
        out.append(a)

    out.sort(key=lambda x: x.get("_signal", {}).get("score", 0), reverse=True)
    return out


def dedupe_articles_by_similarity(
    articles: List[Dict[str, Any]],
    threshold: float = DEFAULT_DEDUPE_THRESHOLD,
) -> Tuple[List[Dict[str, Any]], int]:
    """
    近重复检测：已按分从高到低排序时，保留高分、丢弃与已保留条相似度 >= threshold 的条。
    返回 (列表, 剔除条数)。
    """
    if len(articles) <= 1:
        return articles, 0

    kept: List[Dict[str, Any]] = []
    removed = 0
    fps = [_compare_fingerprint(a) for a in articles]

    for idx, a in enumerate(articles):
        fp = fps[idx]
        is_dup = False
        for k in kept:
            kfp = _compare_fingerprint(k)
            if hybrid_similarity(fp, kfp) >= threshold:
                is_dup = True
                break
        if is_dup:
            removed += 1
        else:
            kept.append(a)

    return kept, removed


def apply_last30days_pipeline(
    articles: List[Dict[str, Any]],
    dedupe: bool = True,
    threshold: float = DEFAULT_DEDUPE_THRESHOLD,
) -> List[Dict[str, Any]]:
    """打分 →（可选）去重，返回新列表。"""
    scored = score_articles_batch(list(articles))
    if not dedupe:
        return scored
    kept, n = dedupe_articles_by_similarity(scored, threshold)
    if n and kept:
        kept[0]["_dedupe_removed"] = n
    return kept

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI内容总结模块 - 支持OpenAI和Anthropic API
"""

import logging
import requests
from typing import Dict, List, Optional
from utils import (
    dedupe_articles_by_url,
    estimate_tokens,
    sanitize_summary_for_public,
    split_text_by_tokens,
)

logger = logging.getLogger(__name__)


class ArticleSummarizer:
    """文章内容总结器"""

    def __init__(self, config: Dict):
        """
        初始化总结器

        Args:
            config: 配置字典
        """
        self.config = config
        self.enabled = config['ai_summary']['enabled']
        # 仅使用缓存/简单总结：不发起任何 AI 请求（用于“对外展示”阶段的离线生成）
        self.cache_only = bool(config.get("ai_summary", {}).get("cache_only", False))

        if self.enabled and not self.cache_only:
            self.api_key = config['ai_summary']['api_key']
            self.base_url = config['ai_summary']['base_url'].rstrip('/')
            self.model = config['ai_summary']['model']
            self.max_tokens = config['ai_summary']['max_tokens']
            self.temperature = config['ai_summary']['temperature']
            self.system_prompt = config['ai_summary']['system_prompt']
            self.user_prompt_template = config['ai_summary']['user_prompt_template']

            # 自动检测API类型
            self.api_type = config['ai_summary'].get('api_type', 'auto')
            if self.api_type == 'auto':
                # 根据base_url或model名称自动判断
                if 'anthropic' in self.base_url.lower() or 'claude' in self.model.lower() or 'sonnet' in self.model.lower():
                    self.api_type = 'anthropic'
                else:
                    self.api_type = 'openai'

            self.summary_max_chars = int(
                config["ai_summary"].get("summary_max_chars_per_article", 12000)
            )
            logger.info(f"AI总结已启用，API类型: {self.api_type}, 模型: {self.model}")
        else:
            if self.cache_only and self.enabled:
                logger.info("AI总结处于 cache_only 模式：将跳过 API 请求")
            else:
                logger.info("AI总结未启用")

    def summarize_account_articles(
        self,
        account_name: str,
        articles: List[Dict]
    ) -> Optional[str]:
        """
        总结某个公众号的所有文章

        Args:
            account_name: 公众号名称
            articles: 文章列表

        Returns:
            总结内容，失败返回None
        """
        if not self.enabled:
            logger.warning("AI总结未启用，跳过")
            return None

        if not articles:
            logger.warning(f"公众号 {account_name} 没有文章，跳过总结")
            return None

        articles = dedupe_articles_by_url(articles)

        try:
            logger.info(f"开始总结公众号: {account_name}, 文章数: {len(articles)}")

            # 准备文章内容
            articles_content = self._format_articles_for_summary(articles)

            # 检查token数量
            total_tokens = estimate_tokens(articles_content)
            logger.info(f"文章内容估算token数: {total_tokens}")

            # 如果内容过长，分批处理
            if total_tokens > 80000:  # 超过80k tokens
                logger.warning(f"内容过长 ({total_tokens} tokens)，采用分批总结")
                return self._summarize_in_batches(account_name, articles)

            # 生成提示词
            user_prompt = self.user_prompt_template.format(
                account_name=account_name,
                article_count=len(articles),
                articles_content=articles_content
            )

            # 调用AI接口
            summary = self._call_ai_api(user_prompt)

            if summary:
                logger.info(f"成功生成总结: {account_name}")
                return sanitize_summary_for_public(summary)
            else:
                logger.error(f"总结生成失败: {account_name}")
                return None

        except Exception as e:
            logger.error(f"总结公众号文章时出错: {account_name}, 错误: {e}")
            return None

    def _format_articles_for_summary(self, articles: List[Dict]) -> str:
        """
        格式化文章内容用于总结

        Args:
            articles: 文章列表

        Returns:
            格式化后的内容
        """
        formatted_articles = []
        max_c = getattr(self, "summary_max_chars", 12000)

        for idx, article in enumerate(articles, 1):
            body = article.get("content", "") or ""
            if len(body) > max_c:
                body = (
                    body[:max_c]
                    + f"\n\n…（正文已截断至前 {max_c} 字；微信文末导流/声明等重复块已弱化，完整内容见原文链接）"
                )
            # 提取完整信息，确保不遗漏关键内容
            article_text = f"""
---
【文章 {idx}】
标题: {article.get('title', '未知')}
发布时间: {article.get('publish_time', '未知')}
作者: {article.get('author', '未知')}

正文内容:
{body}

---
"""
            formatted_articles.append(article_text.strip())

        return '\n\n'.join(formatted_articles)

    def _summarize_in_batches(
        self,
        account_name: str,
        articles: List[Dict]
    ) -> Optional[str]:
        """
        分批总结文章（当内容过长时）

        Args:
            account_name: 公众号名称
            articles: 文章列表

        Returns:
            总结内容
        """
        logger.info(f"开始分批总结: {account_name}")

        # 将文章分成多批
        batch_size = 5  # 每批处理5篇
        batches = [articles[i:i + batch_size] for i in range(0, len(articles), batch_size)]

        batch_summaries = []

        for idx, batch in enumerate(batches, 1):
            logger.info(f"处理第 {idx}/{len(batches)} 批")

            # 格式化这一批文章
            articles_content = self._format_articles_for_summary(batch)

            # 生成提示词
            user_prompt = f"""
请总结以下文章（第 {idx} 批，共 {len(batch)} 篇）：

{articles_content}

请提取关键信息、重要数据、核心观点和技术细节；表述紧凑，避免与可能存在的其他批次在套话上重复（最终报告会合并去重）。
"""

            # 调用AI
            batch_summary = self._call_ai_api(user_prompt)
            if batch_summary:
                batch_summaries.append(f"### 第 {idx} 批总结\n{batch_summary}")

        # 合并所有批次的总结
        if batch_summaries:
            combined_summary = '\n\n'.join(batch_summaries)

            # 再次总结（提炼最终结论）
            final_prompt = f"""
以下是公众号【{account_name}】的分批总结（各批之间可能有信息重叠，你必须合并为一份无重复的最终报告）：

{combined_summary}

请生成最终的整体总结报告，硬性要求：
1. 同一观点、同一数据只写一次；禁止把各批总结分段照抄拼接。
2. 若多批提到同一主题，合并为一条叙述，不要分节重复。
3. 报告结构清晰，包含：整体方向、合并后的核心要点、趋势洞察、3–5 篇重点文章（每篇仅标题 + 一句推荐语，勿复述前文大段分析）。
"""

            final_summary = self._call_ai_api(final_prompt)
            raw = final_summary if final_summary else combined_summary
            return sanitize_summary_for_public(raw) if raw else None

        return None

    def _call_ai_api(self, user_prompt: str) -> Optional[str]:
        """
        调用AI API生成总结 - 支持OpenAI和Anthropic格式

        Args:
            user_prompt: 用户提示词

        Returns:
            生成的总结内容
        """
        try:
            if self.api_type == 'anthropic':
                return self._call_anthropic_api(user_prompt)
            else:
                return self._call_openai_api(user_prompt)
        except Exception as e:
            logger.error(f"调用AI API失败: {e}")
            return None

    def _call_openai_api(self, user_prompt: str) -> Optional[str]:
        """调用OpenAI格式的API"""
        try:
            url = f"{self.base_url}/chat/completions"

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "max_tokens": self.max_tokens,
                "temperature": self.temperature
            }

            logger.info(f"正在调用OpenAI API: {url}")

            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=300  # 增加到5分钟
            )

            response.raise_for_status()
            result = response.json()

            if 'choices' in result and len(result['choices']) > 0:
                summary = result['choices'][0]['message']['content'].strip()
                logger.info(f"AI总结生成成功，长度: {len(summary)} 字符")
                return summary
            else:
                logger.error(f"API响应格式异常: {result}")
                return None

        except requests.exceptions.Timeout:
            logger.error("API请求超时（5分钟）")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"调用OpenAI API失败: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"响应内容: {e.response.text[:500]}")
            return None

    def _call_anthropic_api(self, user_prompt: str) -> Optional[str]:
        """调用Anthropic格式的API"""
        try:
            url = f"{self.base_url}/v1/messages"

            headers = {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json"
            }

            payload = {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "system": self.system_prompt,
                "messages": [
                    {"role": "user", "content": user_prompt}
                ]
            }

            logger.info(f"正在调用Anthropic API: {url}")

            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=300  # 5分钟
            )

            response.raise_for_status()
            result = response.json()

            if 'content' in result and len(result['content']) > 0:
                summary = result['content'][0]['text'].strip()
                logger.info(f"AI总结生成成功，长度: {len(summary)} 字符")
                return summary
            else:
                logger.error(f"API响应格式异常: {result}")
                return None

        except requests.exceptions.Timeout:
            logger.error("API请求超时（5分钟）")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"调用Anthropic API失败: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"响应内容: {e.response.text[:500]}")
            return None

    def generate_simple_summary(self, articles: List[Dict]) -> str:
        """
        生成简单总结（不使用AI）

        Args:
            articles: 文章列表

        Returns:
            简单总结内容
        """
        if not articles:
            return "暂无文章"

        summary_parts = []

        # last30days-skill 风格信号说明（若已打分）
        if articles and isinstance(articles[0], dict) and articles[0].get("_signal"):
            summary_parts.append("## 🔎 检索信号（last30days 策略）")
            summary_parts.append(
                "- 综合分 = 相关性×0.45 + 时效×0.25 + 正文丰富度×0.30；"
                "近重复条用字符 n-gram 与 token Jaccard 混合相似度剔除，保留高分条。"
            )
            rm = articles[0].get("_dedupe_removed")
            if rm:
                summary_parts.append(f"- 本组剔除近重复: {rm} 篇")
            summary_parts.append("")

        # 基本统计
        summary_parts.append(f"## 📊 基本统计")
        summary_parts.append(f"- 文章总数: {len(articles)}")

        # 按发布时间统计
        if articles[0].get('publish_time'):
            dates = [a['publish_time'] for a in articles if a.get('publish_time')]
            if dates:
                summary_parts.append(f"- 时间范围: {min(dates)} ~ {max(dates)}")

        # 文章列表（已按 last30days 综合分排序）
        summary_parts.append(f"\n## 📝 文章列表\n")
        for idx, article in enumerate(articles, 1):
            title = article.get('title', '未知标题')
            publish_time = article.get('publish_time', '未知时间')
            sig = article.get("_signal")
            if sig:
                summary_parts.append(
                    f"{idx}. 【{publish_time}】{title} "
                    f"（信号分 {sig.get('score', 0)}｜相关 {sig.get('relevance')}｜"
                    f"时效 {sig.get('recency')}｜丰富 {sig.get('richness')}）"
                )
            else:
                summary_parts.append(f"{idx}. 【{publish_time}】{title}")

        return sanitize_summary_for_public("\n".join(summary_parts))


if __name__ == "__main__":
    # 测试代码
    test_config = {
        'ai_summary': {
            'enabled': False,
            'api_key': 'test',
            'base_url': 'https://api.openai.com/v1',
            'model': 'gpt-4o',
            'max_tokens': 4000,
            'temperature': 0.3,
            'system_prompt': '你是一位内容分析师',
            'user_prompt_template': '请总结: {articles_content}',
            'api_type': 'auto'
        }
    }

    summarizer = ArticleSummarizer(test_config)
    print("ArticleSummarizer initialized")

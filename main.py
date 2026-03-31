#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信公众号文章爬虫与总结系统 - 主程序
"""

import os
import sys
import json
import yaml
import logging
import argparse
import pandas as pd
from typing import Dict, List
from datetime import datetime
from tqdm import tqdm
from collections import defaultdict

from utils import (
    is_wechat_article_url,
    extract_biz_id,
    is_within_date_range,
    load_extra_urls_from_file,
    merge_url_lists,
    dedupe_articles_by_url,
    sanitize_summary_for_public,
)
from crawler import WechatArticleCrawler
from summarizer import ArticleSummarizer

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/main.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class WechatArticleCrawlerSystem:
    """微信公众号文章爬虫与总结系统"""

    def __init__(self, config_path: str = 'config.yaml'):
        """
        初始化系统

        Args:
            config_path: 配置文件路径
        """
        logger.info("初始化爬虫系统...")

        # 加载配置
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)

        # 初始化组件
        self.crawler = WechatArticleCrawler(self.config)
        self.summarizer = ArticleSummarizer(self.config)

        # 数据存储
        self.all_articles = []
        self.articles_by_account = defaultdict(list)

        logger.info("系统初始化完成")

    def load_urls_from_csv(self) -> List[str]:
        """
        从CSV文件加载微信文章链接

        Returns:
            文章URL列表
        """
        csv_file = self.config['csv_file']
        logger.info(f"读取CSV文件: {csv_file}")

        try:
            # 读取CSV文件
            df = pd.read_csv(csv_file)

            # 查找包含URL的列
            url_column = None
            for col in df.columns:
                if 'source' in col.lower() or 'url' in col.lower() or '链接' in col:
                    url_column = col
                    break

            if url_column is None:
                # 尝试从所有列中查找微信链接
                logger.warning("未找到明确的URL列，将从所有列中搜索")
                urls = []
                for col in df.columns:
                    for value in df[col].dropna():
                        if isinstance(value, str) and is_wechat_article_url(value):
                            urls.append(value)
            else:
                # 从指定列提取URL
                urls = df[url_column].dropna().tolist()

            # 过滤出微信文章链接
            wechat_urls = [url for url in urls if is_wechat_article_url(str(url))]

            logger.info(f"从CSV文件中找到 {len(wechat_urls)} 个微信文章链接")

            extra_path = self.config.get("extra_urls_file") or ""
            if extra_path:
                if not os.path.isabs(extra_path):
                    extra_path = os.path.join(os.getcwd(), extra_path)
                extra = load_extra_urls_from_file(extra_path)
                logger.info(
                    f"从额外链接文件加载 {len(extra)} 个: {extra_path}"
                )
                wechat_urls = merge_url_lists(wechat_urls, extra)
                logger.info(f"CSV 与额外文件合并去重后共 {len(wechat_urls)} 个链接")

            return wechat_urls

        except Exception as e:
            logger.error(f"读取CSV文件失败: {e}")
            return []

    def crawl_articles(self, urls: List[str]) -> List[Dict]:
        """
        爬取文章

        Args:
            urls: 文章URL列表

        Returns:
            文章列表
        """
        logger.info(f"开始爬取 {len(urls)} 篇文章...")

        # 使用tqdm显示进度
        articles = []
        for url in tqdm(urls, desc="爬取进度", unit="篇"):
            article = self.crawler.fetch_article(url)
            if article:
                articles.append(article)

        logger.info(f"爬取完成，成功: {len(articles)}/{len(urls)}")

        # 保存原始数据
        self._save_raw_articles(articles)

        return articles

    def filter_articles_by_date(
        self,
        articles: List[Dict],
        days: int = 30
    ) -> List[Dict]:
        """
        按日期过滤文章

        Args:
            articles: 文章列表
            days: 天数范围

        Returns:
            过滤后的文章列表
        """
        logger.info(f"过滤近 {days} 天的文章...")

        filtered = []
        for article in articles:
            publish_time = article.get('publish_time', '')
            if is_within_date_range(publish_time, days):
                filtered.append(article)

        logger.info(f"过滤完成: {len(filtered)}/{len(articles)} 篇在时间范围内")
        return filtered

    def group_articles_by_account(self, articles: List[Dict]) -> Dict[str, List[Dict]]:
        """
        按公众号分组文章

        Args:
            articles: 文章列表

        Returns:
            按公众号分组的文章字典
        """
        logger.info("按公众号分组文章...")

        grouped = defaultdict(list)

        for article in articles:
            account_name = article.get('account_name', '未知公众号')
            biz_id = article.get('biz_id', 'unknown')

            # 使用公众号名称作为key，如果有biz_id则组合使用
            key = f"{account_name}_{biz_id}" if biz_id != 'unknown' else account_name
            grouped[key].append(article)

        logger.info(f"共 {len(grouped)} 个公众号")

        # 打印每个公众号的文章数
        for account, arts in sorted(grouped.items(), key=lambda x: len(x[1]), reverse=True):
            logger.info(f"  - {account}: {len(arts)} 篇")

        return dict(grouped)

    def generate_summaries(self, articles_by_account: Dict[str, List[Dict]]) -> Dict[str, str]:
        """
        生成总结

        Args:
            articles_by_account: 按公众号分组的文章

        Returns:
            公众号总结字典
        """
        logger.info("开始生成总结...")

        summaries = {}

        for account_name, articles in tqdm(
            articles_by_account.items(),
            desc="总结进度",
            unit="个公众号"
        ):
            logger.info(f"正在总结: {account_name} ({len(articles)} 篇)")

            if self.summarizer.enabled and not getattr(self.summarizer, "cache_only", False):
                # 使用AI生成总结
                summary = self.summarizer.summarize_account_articles(account_name, articles)
            else:
                # 生成简单总结
                summary = self.summarizer.generate_simple_summary(articles)

            if summary:
                summaries[account_name] = summary
                logger.info(f"总结完成: {account_name}")
            else:
                logger.warning(f"总结失败: {account_name}")

        logger.info(f"总结生成完成，共 {len(summaries)} 个公众号")
        return summaries

    def save_results(
        self,
        articles_by_account: Dict[str, List[Dict]],
        summaries: Dict[str, str]
    ):
        """
        保存结果

        Args:
            articles_by_account: 按公众号分组的文章
            summaries: 公众号总结
        """
        logger.info("保存结果...")
        summaries = {
            k: sanitize_summary_for_public(v.strip())
            if isinstance(v, str) and v.strip()
            else v
            for k, v in summaries.items()
        }

        # 1. 保存分组后的文章数据
        if self.config['output']['save_json']:
            processed_file = 'data/processed/articles_by_account.json'
            with open(processed_file, 'w', encoding='utf-8') as f:
                json.dump(articles_by_account, f, ensure_ascii=False, indent=2)
            logger.info(f"已保存分组文章数据: {processed_file}")

        # 2. 保存总结报告（Markdown）
        if self.config['output']['save_markdown']:
            self._save_markdown_report(articles_by_account, summaries)

        # 3. 保存总结报告（JSON）
        if self.config['output']['save_json']:
            summary_json = 'output/summaries.json'
            if summaries:
                with open(summary_json, 'w', encoding='utf-8') as f:
                    json.dump(summaries, f, ensure_ascii=False, indent=2)
                logger.info(f"已保存总结JSON: {summary_json}")
            else:
                logger.warning("summaries 为空，跳过写入 summaries.json（避免覆盖已有缓存）")

        # 4. 生成索引文件
        if self.config['output']['generate_index']:
            self._generate_index_file(articles_by_account, summaries)

        logger.info("结果保存完成")

    def _save_raw_articles(self, articles: List[Dict]):
        """保存原始文章数据"""
        raw_file = 'data/raw/articles.json'
        with open(raw_file, 'w', encoding='utf-8') as f:
            json.dump(articles, f, ensure_ascii=False, indent=2)
        logger.info(f"已保存原始文章数据: {raw_file} ({len(articles)} 篇)")

    def _save_markdown_report(
        self,
        articles_by_account: Dict[str, List[Dict]],
        summaries: Dict[str, str]
    ):
        """保存Markdown格式的总结报告"""
        report_file = 'output/summary_report.md'

        with open(report_file, 'w', encoding='utf-8') as f:
            # 标题
            f.write("# 微信公众号文章内容总结报告\n\n")
            f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            # 概览统计
            total_accounts = len(articles_by_account)
            total_articles = sum(len(arts) for arts in articles_by_account.values())

            f.write("## 📊 整体概览\n\n")
            f.write(f"- 公众号数量: {total_accounts} 个\n")
            f.write(f"- 文章总数: {total_articles} 篇\n")
            f.write(f"- 时间范围: 近 {self.config['days_range']} 天\n\n")

            # 按公众号统计
            f.write("## 📈 公众号文章数量排行\n\n")
            sorted_accounts = sorted(
                articles_by_account.items(),
                key=lambda x: len(x[1]),
                reverse=True
            )
            for idx, (account, arts) in enumerate(sorted_accounts, 1):
                f.write(f"{idx}. **{account}**: {len(arts)} 篇\n")

            f.write("\n---\n\n")

            # 详细总结
            f.write("## 📝 各公众号详细总结\n\n")

            for account_name, articles in sorted_accounts:
                f.write(f"### {account_name}\n\n")

                # 文章数量
                f.write(f"**文章数量**: {len(articles)} 篇\n\n")

                # AI总结
                if account_name in summaries:
                    f.write(f"{summaries[account_name]}\n\n")

                # 文章列表
                f.write("#### 文章列表\n\n")
                for idx, article in enumerate(articles, 1):
                    title = article.get('title', '未知标题')
                    publish_time = article.get('publish_time', '未知时间')
                    url = article.get('url', '')
                    f.write(f"{idx}. [{title}]({url}) - {publish_time}\n")

                f.write("\n---\n\n")

        logger.info(f"已保存Markdown报告: {report_file}")

    def _generate_index_file(
        self,
        articles_by_account: Dict[str, List[Dict]],
        summaries: Dict[str, str]
    ):
        """生成索引文件"""
        index_file = 'output/index.md'

        with open(index_file, 'w', encoding='utf-8') as f:
            f.write("# 文章爬取索引\n\n")
            f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            f.write("## 文件列表\n\n")
            f.write("- [完整总结报告](summary_report.md)\n")
            f.write("- [总结数据JSON](summaries.json)\n")
            f.write("- [分组文章数据](../data/processed/articles_by_account.json)\n")
            f.write("- [原始文章数据](../data/raw/articles.json)\n\n")

            f.write("## 公众号列表\n\n")
            for account, arts in sorted(articles_by_account.items()):
                f.write(f"- [{account}](summary_report.md#{account.replace(' ', '-')}) - {len(arts)} 篇\n")

        logger.info(f"已生成索引文件: {index_file}")

    def run_full_pipeline(self):
        """运行完整流程"""
        logger.info("=" * 60)
        logger.info("开始执行完整流程")
        logger.info("=" * 60)

        try:
            # 1. 加载URL
            urls = self.load_urls_from_csv()
            if not urls:
                logger.error("未找到有效的文章链接")
                return

            # 2. 爬取文章
            articles = self.crawl_articles(urls)
            if not articles:
                logger.error("未能成功爬取文章")
                return

            # 3. 过滤文章（按日期）
            filtered_articles = self.filter_articles_by_date(
                articles,
                days=self.config['days_range']
            )
            filtered_articles = dedupe_articles_by_url(filtered_articles)

            # 4. 按公众号分组
            articles_by_account = self.group_articles_by_account(filtered_articles)

            # 4.5 last30days-skill 风格：相关性+时效+正文丰富度打分，近重复合并（见 last30days_signals.py）
            sig_cfg = self.config.get("last30days_signals") or {}
            if sig_cfg.get("enabled", True):
                from last30days_signals import apply_last30days_pipeline

                dedupe_on = sig_cfg.get("dedupe", True)
                th = float(sig_cfg.get("dedupe_threshold", 0.72))
                for acc_key in list(articles_by_account.keys()):
                    articles_by_account[acc_key] = apply_last30days_pipeline(
                        articles_by_account[acc_key],
                        dedupe=dedupe_on,
                        threshold=th,
                    )

            # 5. 生成总结
            summaries = self.generate_summaries(articles_by_account)

            # 6. 保存结果
            self.save_results(articles_by_account, summaries)

            logger.info("=" * 60)
            logger.info("完整流程执行完成！")
            logger.info(f"总结报告已保存到: output/summary_report.md")
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"执行流程时出错: {e}", exc_info=True)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='微信公众号文章爬虫与总结系统')
    parser.add_argument(
        '--mode',
        type=str,
        default='full',
        choices=['full', 'crawl', 'summarize'],
        help='运行模式: full=完整流程, crawl=仅爬取, summarize=仅总结'
    )
    parser.add_argument(
        '--config',
        type=str,
        default='config.yaml',
        help='配置文件路径'
    )

    args = parser.parse_args()

    # 创建系统实例
    system = WechatArticleCrawlerSystem(args.config)

    # 执行对应模式
    if args.mode == 'full':
        system.run_full_pipeline()
    elif args.mode == 'crawl':
        urls = system.load_urls_from_csv()
        articles = system.crawl_articles(urls)
        logger.info(f"爬取完成，共 {len(articles)} 篇")
    elif args.mode == 'summarize':
        # 从已保存的数据生成总结（不重新爬取）
        # - 优先使用 output/summaries.json 作为“缓存总结”，避免逐个公众号请求 API
        # - 仅当缓存不存在或缺失条目时，才尝试实时生成
        logger.info("从已有数据生成总结（不重新爬取，优先使用缓存总结）...")
        try:
            proc_path = os.path.join("data", "processed", "articles_by_account.json")
            raw_path = os.path.join("data", "raw", "articles.json")
            cache_summary_path = os.path.join("output", "summaries.json")

            articles_by_account: Dict[str, List[Dict]] = {}
            if os.path.isfile(proc_path):
                with open(proc_path, "r", encoding="utf-8") as f:
                    articles_by_account = json.load(f)
                logger.info(
                    "已加载分组文章数据: %s（%s 个公众号）",
                    proc_path,
                    len(articles_by_account),
                )
            elif os.path.isfile(raw_path):
                with open(raw_path, "r", encoding="utf-8") as f:
                    articles = json.load(f)
                logger.info("已加载原始文章数据: %s（%s 篇）", raw_path, len(articles))

                # 与 full pipeline 一致：日期过滤 → 去重 → 分组
                filtered = system.filter_articles_by_date(
                    articles,
                    days=system.config["days_range"],
                )
                filtered = dedupe_articles_by_url(filtered)
                articles_by_account = system.group_articles_by_account(filtered)
            else:
                logger.error("未找到已保存数据：%s 或 %s", proc_path, raw_path)
                return

            cached_summaries: Dict[str, str] = {}
            if os.path.isfile(cache_summary_path):
                try:
                    with open(cache_summary_path, "r", encoding="utf-8") as f:
                        cached_summaries = json.load(f) or {}
                    logger.info(
                        "已加载缓存总结: %s（%s 条）",
                        cache_summary_path,
                        len(cached_summaries),
                    )
                except Exception as e:
                    logger.warning("读取缓存总结失败，将回退到实时生成：%s", e)
                    cached_summaries = {}

            # last30days-skill 信号（便于输出排序与摘要）
            sig_cfg = system.config.get("last30days_signals") or {}
            if sig_cfg.get("enabled", True):
                from last30days_signals import apply_last30days_pipeline

                dedupe_on = sig_cfg.get("dedupe", True)
                th = float(sig_cfg.get("dedupe_threshold", 0.72))
                for acc_key in list(articles_by_account.keys()):
                    articles_by_account[acc_key] = apply_last30days_pipeline(
                        articles_by_account[acc_key],
                        dedupe=dedupe_on,
                        threshold=th,
                    )

            # 生成/补齐 summaries
            summaries: Dict[str, str] = dict(cached_summaries) if cached_summaries else {}
            missing = [k for k in articles_by_account.keys() if k not in summaries or not summaries.get(k)]
            if missing:
                logger.info("缓存缺失 %s 个公众号总结，将尝试补齐（可能触发 AI 请求）", len(missing))
                # 仅对缺失项生成，避免重复请求
                for k in missing:
                    one = system.generate_summaries({k: articles_by_account[k]})
                    if one and one.get(k):
                        summaries[k] = one[k]
            else:
                logger.info("缓存已覆盖全部公众号，总结生成将跳过 AI 请求")

            system.save_results(articles_by_account, summaries)
            logger.info("总结生成完成，已写入 output/summary_report.md 与 output/summaries.json")
        except Exception as e:
            logger.error(f"summarize 模式执行失败: {e}", exc_info=True)


if __name__ == "__main__":
    main()

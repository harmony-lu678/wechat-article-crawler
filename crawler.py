#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信公众号文章爬虫模块
"""

import requests
import time
import logging
from typing import Dict, Optional, List
from utils import (
    get_random_user_agent,
    is_wechat_article_url,
    extract_article_id,
    extract_biz_id,
    RateLimiter,
    retry_on_failure
)
from parser import WechatArticleParser

logger = logging.getLogger(__name__)


class WechatArticleCrawler:
    """微信公众号文章爬虫"""

    def __init__(self, config: Dict):
        """
        初始化爬虫

        Args:
            config: 配置字典
        """
        self.config = config
        self.parser = WechatArticleParser()
        self.rate_limiter = RateLimiter(
            interval=config['crawler']['request_interval']
        )
        self.session = self._create_session()
        self.crawled_articles = set()  # 记录已爬取的文章ID

    def _create_session(self) -> requests.Session:
        """创建HTTP会话"""
        session = requests.Session()
        session.headers.update({
            'User-Agent': get_random_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Cache-Control': 'max-age=0',
        })
        return session

    def fetch_article(self, url: str) -> Optional[Dict]:
        """
        抓取单篇文章

        Args:
            url: 文章URL

        Returns:
            文章信息字典，失败返回None
        """
        if not is_wechat_article_url(url):
            logger.warning(f"非微信文章链接: {url}")
            return None

        article_id = extract_article_id(url)
        if article_id in self.crawled_articles:
            logger.info(f"文章已爬取，跳过: {url}")
            return None

        # 频率限制
        self.rate_limiter.wait()

        try:
            # 定义请求函数用于重试
            def make_request():
                logger.info(f"正在抓取: {url}")
                response = self.session.get(
                    url,
                    timeout=self.config['crawler']['timeout'],
                    allow_redirects=True
                )
                response.raise_for_status()
                return response

            # 执行请求（带重试）
            response = retry_on_failure(
                make_request,
                max_retries=self.config['crawler']['max_retries'],
                delay=self.config['crawler']['retry_delay']
            )

            # 检查响应
            if response.status_code != 200:
                logger.warning(f"请求失败，状态码: {response.status_code}, URL: {url}")
                return None

            # 检查是否被重定向到错误页面
            if '该内容已被发布者删除' in response.text or '此内容因违规无法查看' in response.text:
                logger.warning(f"文章已删除或违规: {url}")
                return None

            # 解析文章
            article = self.parser.parse_article(response.text, url)

            if article:
                # 添加额外信息
                article['article_id'] = article_id
                article['biz_id'] = extract_biz_id(url)

                # 记录已爬取
                self.crawled_articles.add(article_id)

                logger.info(f"成功抓取文章: {article['title']}")
                return article
            else:
                logger.warning(f"文章解析失败: {url}")
                return None

        except requests.exceptions.Timeout:
            logger.error(f"请求超时: {url}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"请求异常: {url}, 错误: {e}")
            return None
        except Exception as e:
            logger.error(f"未知错误: {url}, 错误: {e}")
            return None

    def fetch_articles_batch(self, urls: List[str]) -> List[Dict]:
        """
        批量抓取文章

        Args:
            urls: 文章URL列表

        Returns:
            文章信息列表
        """
        articles = []
        total = len(urls)

        logger.info(f"开始批量抓取，共 {total} 篇文章")

        for idx, url in enumerate(urls, 1):
            logger.info(f"进度: {idx}/{total}")

            article = self.fetch_article(url)
            if article:
                articles.append(article)

            # 每10篇文章记录一次进度
            if idx % 10 == 0:
                logger.info(f"已抓取 {len(articles)}/{idx} 篇文章")

        logger.info(f"批量抓取完成，成功: {len(articles)}/{total}")
        return articles

    def get_crawled_count(self) -> int:
        """获取已爬取文章数量"""
        return len(self.crawled_articles)


if __name__ == "__main__":
    # 测试代码
    test_config = {
        'crawler': {
            'request_interval': 3,
            'timeout': 30,
            'max_retries': 3,
            'retry_delay': 5
        }
    }

    crawler = WechatArticleCrawler(test_config)
    test_url = "https://mp.weixin.qq.com/s?__biz=MjM5NDQ3ODI3NQ==&mid=2651430654&idx=1"

    article = crawler.fetch_article(test_url)
    if article:
        print(f"标题: {article['title']}")
        print(f"作者: {article['author']}")
        print(f"内容长度: {len(article['content'])} 字符")

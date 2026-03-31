#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试脚本 - 爬取单篇文章验证系统
"""

import yaml
from crawler import WechatArticleCrawler
from parser import WechatArticleParser

# 测试URL
TEST_URL = "https://mp.weixin.qq.com/s?__biz=MjM5NDQ3ODI3NQ==&mid=2651430654&idx=1&sn=e28a4214561b065ebb40fcb732630a77"

def test_single_article():
    """测试爬取单篇文章"""
    print("=" * 60)
    print("测试单篇文章爬取")
    print("=" * 60)

    # 加载配置
    with open('config.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    # 创建爬虫
    crawler = WechatArticleCrawler(config)

    # 爬取文章
    print(f"\n正在爬取测试文章...")
    print(f"URL: {TEST_URL[:80]}...\n")

    article = crawler.fetch_article(TEST_URL)

    if article:
        print("✓ 爬取成功！\n")
        print("文章信息:")
        print(f"  标题: {article['title']}")
        print(f"  公众号: {article['account_name']}")
        print(f"  作者: {article['author']}")
        print(f"  发布时间: {article['publish_time']}")
        print(f"  正文长度: {len(article['content'])} 字符")
        print(f"\n正文预览 (前500字):")
        print("-" * 60)
        print(article['content'][:500])
        print("-" * 60)
        print("\n✓ 测试通过！系统运行正常。")

        # 提取关键要点
        parser = WechatArticleParser()
        key_points = parser.extract_key_points(article['content'])
        if key_points:
            print(f"\n关键要点:")
            for point in key_points[:5]:
                print(f"  - {point}")

        return True
    else:
        print("✗ 爬取失败")
        print("可能原因:")
        print("  1. 网络连接问题")
        print("  2. 文章已删除")
        print("  3. 请求被限制")
        print("\n请检查日志文件: logs/crawler.log")
        return False

if __name__ == "__main__":
    test_single_article()

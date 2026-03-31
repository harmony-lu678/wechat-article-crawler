#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小规模测试 - 爬取前5篇文章
"""

import yaml
import pandas as pd
from crawler import WechatArticleCrawler
from summarizer import ArticleSummarizer
from utils import is_wechat_article_url
import json

def test_small_batch():
    """测试爬取5篇文章"""
    print("=" * 60)
    print("小规模测试：爬取前5篇文章")
    print("=" * 60)

    # 加载配置
    with open('config.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    # 读取CSV
    csv_file = config['csv_file']
    df = pd.read_csv(csv_file)

    # 提取微信链接
    urls = []
    for col in df.columns:
        for value in df[col].dropna():
            if isinstance(value, str) and is_wechat_article_url(value):
                urls.append(value)

    print(f"\n✓ 从CSV中找到 {len(urls)} 个微信文章链接")
    print(f"  测试爬取前 5 篇...\n")

    # 创建爬虫
    crawler = WechatArticleCrawler(config)

    # 爬取前5篇
    articles = []
    for i, url in enumerate(urls[:5], 1):
        print(f"\n[{i}/5] 正在爬取...")
        print(f"URL: {url[:80]}...")

        article = crawler.fetch_article(url)
        if article:
            articles.append(article)
            print(f"✓ 成功: {article['title']}")
            print(f"  公众号: {article['account_name']}")
            print(f"  内容长度: {len(article['content'])} 字符")
        else:
            print(f"✗ 失败")

    print("\n" + "=" * 60)
    print(f"爬取完成: 成功 {len(articles)}/{5} 篇")
    print("=" * 60)

    if articles:
        # 保存结果
        with open('data/raw/test_articles.json', 'w', encoding='utf-8') as f:
            json.dump(articles, f, ensure_ascii=False, indent=2)
        print(f"\n✓ 已保存测试数据: data/raw/test_articles.json")

        # 显示第一篇文章的内容预览
        if len(articles) > 0:
            first = articles[0]
            print(f"\n" + "=" * 60)
            print("第一篇文章内容预览:")
            print("=" * 60)
            print(f"标题: {first['title']}")
            print(f"公众号: {first['account_name']}")
            print(f"发布时间: {first['publish_time']}")
            print(f"\n正文（前500字）:")
            print("-" * 60)
            print(first['content'][:500])
            print("-" * 60)

        # 测试AI总结（如果启用）
        if config['ai_summary']['enabled']:
            print(f"\n" + "=" * 60)
            print("测试AI总结功能...")
            print("=" * 60)

            summarizer = ArticleSummarizer(config)

            # 只对第一个公众号的文章进行测试
            test_account = articles[0]['account_name']
            test_articles = [a for a in articles if a['account_name'] == test_account]

            print(f"\n正在为公众号 [{test_account}] 生成总结...")
            print(f"文章数量: {len(test_articles)}")

            summary = summarizer.summarize_account_articles(test_account, test_articles)

            if summary:
                print(f"\n✓ 总结生成成功！\n")
                print("=" * 60)
                print("总结内容预览（前1000字符）:")
                print("=" * 60)
                print(summary[:1000])
                print("=" * 60)

                # 保存总结
                with open('output/test_summary.md', 'w', encoding='utf-8') as f:
                    f.write(f"# {test_account} 测试总结\n\n")
                    f.write(summary)
                print(f"\n✓ 完整总结已保存: output/test_summary.md")
            else:
                print(f"\n✗ 总结生成失败")
                print("  请检查:")
                print("  1. API配置是否正确")
                print("  2. 网络连接是否正常")
                print("  3. 查看日志: logs/main.log")

        print(f"\n" + "=" * 60)
        print("测试完成！")
        print("=" * 60)
        print("\n如果测试成功，可以运行完整爬虫:")
        print("  python main.py --mode full")

        return True
    else:
        print("\n✗ 没有成功爬取任何文章")
        print("\n可能原因:")
        print("  1. 文章链接已过期或被删除")
        print("  2. 网络连接问题")
        print("  3. 微信公众号访问限制")
        print("\n建议:")
        print("  1. 检查网络连接")
        print("  2. 稍后重试")
        print("  3. 查看日志: logs/crawler.log")

        return False

if __name__ == "__main__":
    test_small_batch()

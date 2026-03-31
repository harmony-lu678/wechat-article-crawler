#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信公众号文章解析模块
"""

import re
import logging
from typing import Dict, Optional
from bs4 import BeautifulSoup
from datetime import datetime

logger = logging.getLogger(__name__)


class WechatArticleParser:
    """微信公众号文章解析器"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def parse_article(self, html: str, url: str) -> Optional[Dict]:
        """
        解析微信文章HTML，提取完整信息

        Args:
            html: 文章HTML内容
            url: 文章URL

        Returns:
            文章信息字典，包含标题、作者、发布时间、正文等
        """
        try:
            soup = BeautifulSoup(html, 'lxml')

            # 提取文章信息
            article = {
                'url': url,
                'title': self._extract_title(soup),
                'author': self._extract_author(soup),
                'account_name': self._extract_account_name(soup),
                'publish_time': self._extract_publish_time(soup),
                'content': self._extract_content(soup),
                'content_html': self._extract_content_html(soup),
                'digest': self._extract_digest(soup),
                'cover_image': self._extract_cover_image(soup),
                'crawl_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

            # 验证必要字段
            if not article['title'] or not article['content']:
                self.logger.warning(f"文章缺少必要信息: {url}")
                return None

            self.logger.info(f"成功解析文章: {article['title']}")
            return article

        except Exception as e:
            self.logger.error(f"解析文章失败: {url}, 错误: {e}")
            return None

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """提取文章标题"""
        # 尝试多种方式提取标题
        selectors = [
            {'id': 'activity-name'},
            {'class': 'rich_media_title'},
            {'property': 'og:title'},
            {'name': 'twitter:title'}
        ]

        for selector in selectors:
            if 'id' in selector:
                elem = soup.find(id=selector['id'])
            elif 'class' in selector:
                elem = soup.find(class_=selector['class'])
            elif 'property' in selector:
                elem = soup.find('meta', property=selector['property'])
                if elem:
                    return elem.get('content', '').strip()
            elif 'name' in selector:
                elem = soup.find('meta', attrs={'name': selector['name']})
                if elem:
                    return elem.get('content', '').strip()

            if elem:
                return elem.get_text().strip()

        # 最后尝试title标签
        title_tag = soup.find('title')
        if title_tag:
            return title_tag.get_text().strip()

        return "未知标题"

    def _extract_author(self, soup: BeautifulSoup) -> str:
        """提取作者"""
        selectors = [
            {'id': 'js_author_name'},
            {'class': 'rich_media_meta_text'},
            {'id': 'profileBt'}
        ]

        for selector in selectors:
            if 'id' in selector:
                elem = soup.find(id=selector['id'])
            elif 'class' in selector:
                elem = soup.find(class_=selector['class'])

            if elem:
                author = elem.get_text().strip()
                if author and author != '':
                    return author

        return "未知作者"

    def _extract_account_name(self, soup: BeautifulSoup) -> str:
        """提取公众号名称"""
        # 尝试从多个位置提取公众号名称
        selectors = [
            {'id': 'js_name'},
            {'class': 'profile_nickname'},
            {'id': 'profileBt'}
        ]

        for selector in selectors:
            if 'id' in selector:
                elem = soup.find(id=selector['id'])
            elif 'class' in selector:
                elem = soup.find(class_=selector['class'])

            if elem:
                name = elem.get_text().strip()
                if name:
                    return name

        return "未知公众号"

    def _extract_publish_time(self, soup: BeautifulSoup) -> str:
        """提取发布时间"""
        # 尝试从多个位置提取发布时间
        selectors = [
            {'id': 'publish_time'},
            {'class': 'rich_media_meta_text'},
            {'id': 'post-date'}
        ]

        for selector in selectors:
            if 'id' in selector:
                elem = soup.find(id=selector['id'])
            elif 'class' in selector:
                elem = soup.find(class_=selector['class'])

            if elem:
                time_text = elem.get_text().strip()
                # 尝试提取日期格式
                date_match = re.search(r'\d{4}-\d{2}-\d{2}', time_text)
                if date_match:
                    return date_match.group()

        # 尝试从meta标签提取
        meta_time = soup.find('meta', property='article:published_time')
        if meta_time:
            time_content = meta_time.get('content', '')
            if time_content:
                return time_content[:10]  # 取前10位日期

        return datetime.now().strftime('%Y-%m-%d')

    def _extract_content(self, soup: BeautifulSoup) -> str:
        """
        提取文章正文（纯文本）
        保留完整内容，不遗漏任何段落
        """
        # 查找文章内容容器
        content_elem = soup.find(id='js_content')
        if not content_elem:
            content_elem = soup.find(class_='rich_media_content')

        if not content_elem:
            self.logger.warning("未找到文章内容容器")
            return ""

        # 移除不需要的元素
        for tag in content_elem.find_all(['script', 'style', 'iframe']):
            tag.decompose()

        # 只抽取块级节点：勿同时包含 section/div 与其子节点 p，否则父容器 get_text 与子节点 p
        # 会各抽一遍，导致「新智元报道」等短句重复多行。
        paragraphs: list[str] = []
        # 不含 blockquote：其中子节点 p 会单独匹配，再取 blockquote 会整段重复
        block_tags = ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li']
        for elem in content_elem.find_all(block_tags):
            text = elem.get_text().strip()
            if not text:
                continue
            if elem.name == 'li':
                text = '• ' + text
            elif elem.name in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
                text = '## ' + text
            paragraphs.append(text)

        # 无 <p> 等的老模板：整段文本兜底
        if not paragraphs:
            raw = content_elem.get_text(separator='\n', strip=True)
            if raw:
                paragraphs = [ln.strip() for ln in raw.split('\n') if ln.strip()]

        paragraphs = self._dedupe_consecutive_paragraphs(paragraphs)

        content = '\n\n'.join(paragraphs)
        content = re.sub(r'\n{3,}', '\n\n', content)

        return content.strip()

    @staticmethod
    def _dedupe_consecutive_paragraphs(paragraphs: list[str]) -> list[str]:
        """去掉连续完全相同的段落（解析异常或版式嵌套时的保险）。"""
        out: list[str] = []
        for t in paragraphs:
            if out and out[-1] == t:
                continue
            out.append(t)
        return out

    def _extract_content_html(self, soup: BeautifulSoup) -> str:
        """提取文章HTML内容（保留格式）"""
        content_elem = soup.find(id='js_content')
        if not content_elem:
            content_elem = soup.find(class_='rich_media_content')

        if content_elem:
            return str(content_elem)

        return ""

    def _extract_digest(self, soup: BeautifulSoup) -> str:
        """提取文章摘要"""
        # 尝试从meta标签提取
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc:
            return meta_desc.get('content', '').strip()

        # 从正文提取前200字作为摘要
        content = self._extract_content(soup)
        if content:
            return content[:200] + '...' if len(content) > 200 else content

        return ""

    def _extract_cover_image(self, soup: BeautifulSoup) -> str:
        """提取封面图"""
        # 尝试多种方式提取封面图
        img_selectors = [
            {'property': 'og:image'},
            {'name': 'twitter:image'},
            {'id': 'js_cover'}
        ]

        for selector in img_selectors:
            if 'property' in selector:
                elem = soup.find('meta', property=selector['property'])
            elif 'name' in selector:
                elem = soup.find('meta', attrs={'name': selector['name']})
            elif 'id' in selector:
                elem = soup.find(id=selector['id'])

            if elem:
                img_url = elem.get('content') or elem.get('src')
                if img_url:
                    return img_url

        # 从内容中查找第一张图片
        content_elem = soup.find(id='js_content')
        if content_elem:
            first_img = content_elem.find('img')
            if first_img:
                return first_img.get('data-src') or first_img.get('src', '')

        return ""

    def extract_key_points(self, content: str) -> list:
        """
        从文章内容中提取关键要点
        识别标题、列表、数据等关键信息

        Args:
            content: 文章正文

        Returns:
            关键要点列表
        """
        key_points = []

        # 提取标题
        headings = re.findall(r'^##\s+(.+)$', content, re.MULTILINE)
        if headings:
            key_points.extend([f"标题: {h}" for h in headings])

        # 提取列表项
        list_items = re.findall(r'^[•\-\*]\s+(.+)$', content, re.MULTILINE)
        if list_items:
            key_points.extend([f"要点: {item}" for item in list_items[:5]])  # 取前5项

        # 提取数字相关信息（数据、统计等）
        numbers = re.findall(r'(\d+(?:\.\d+)?%|\d+(?:,\d{3})*(?:\.\d+)?(?:万|亿|千|百)?)', content)
        if numbers:
            key_points.append(f"关键数据: {', '.join(set(numbers[:10]))}")

        return key_points


if __name__ == "__main__":
    # 测试代码
    parser = WechatArticleParser()
    print("WechatArticleParser initialized")

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
为 articles_by_account.json 中尚未缓存摘要的文章调用 AI 接口生成摘要，
结果追加写入 output/summaries.json。
只处理最近 days_range 天（取自 config.yaml）的文章，避免重复消耗。
"""

import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import requests
import yaml

CFG_PATH  = os.path.join(ROOT, 'config.yaml')
PROC_PATH = os.path.join(ROOT, 'data', 'processed', 'articles_by_account.json')
SUMS_PATH = os.path.join(ROOT, 'output', 'summaries.json')


def main():
    with open(CFG_PATH, encoding='utf-8') as f:
        cfg = yaml.safe_load(f)

    ai_cfg = cfg.get('ai_summary', {})
    if not ai_cfg.get('enabled', False):
        print('[summarize_new] AI 摘要未启用，跳过')
        return
    if ai_cfg.get('cache_only', False):
        print('[summarize_new] cache_only 模式，跳过')
        return

    api_key  = ai_cfg['api_key']
    base_url = ai_cfg['base_url'].rstrip('/')
    model    = ai_cfg['model']
    max_tok  = int(ai_cfg.get('max_tokens', 4000))
    temp     = float(ai_cfg.get('temperature', 0.3))
    sys_prompt  = ai_cfg.get('system_prompt', '')
    user_tmpl   = ai_cfg.get('user_prompt_template', '请总结以下文章：\n\n{content}')
    max_chars   = int(ai_cfg.get('summary_max_chars_per_article', 12000))
    interval    = float(cfg.get('crawler', {}).get('request_interval', 1.5))

    with open(PROC_PATH, encoding='utf-8') as f:
        raw = json.load(f)
    if os.path.exists(SUMS_PATH):
        with open(SUMS_PATH, encoding='utf-8') as f:
            summaries = json.load(f)
    else:
        summaries = {}

    # 收集需要摘要的文章（URL 不在缓存里）
    to_process = []
    for acc_key, arts in raw.items():
        for a in arts:
            url = a.get('url', '')
            if url and url not in summaries:
                to_process.append(a)

    if not to_process:
        print('[summarize_new] 无新文章需要摘要，跳过')
        return

    print(f'[summarize_new] 需要摘要 {len(to_process)} 篇')

    def call_api(title: str, body_text: str) -> str:
        body_text = body_text[:max_chars]
        content = f'标题：{title}\n\n正文：\n{body_text}'
        prompt = user_tmpl.replace('{content}', content) if '{content}' in user_tmpl else content
        resp = requests.post(
            f'{base_url}/chat/completions',
            headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
            json={'model': model, 'messages': [
                {'role': 'system', 'content': sys_prompt},
                {'role': 'user',   'content': prompt},
            ], 'max_tokens': max_tok, 'temperature': temp},
            timeout=90,
        )
        resp.raise_for_status()
        return resp.json()['choices'][0]['message']['content'].strip()

    ok = fail = 0
    for i, a in enumerate(to_process):
        title     = a.get('title', '')
        url       = a.get('url', '')
        body_html = a.get('content_html', '') or ''
        body_text = (a.get('content') or a.get('body') or
                     re.sub(r'<[^>]+>', '', body_html)).strip()

        print(f'  [{i+1}/{len(to_process)}] {title[:50]}...', flush=True)
        try:
            s = call_api(title, body_text)
            summaries[url] = {'summary': s, 'title': title}
            ok += 1
            print('    ✓ 完成', flush=True)
        except Exception as e:
            print(f'    ✗ 失败: {e}', flush=True)
            fail += 1

        # 每隔 5 篇写一次缓存，防止中途崩溃丢数据
        if (i + 1) % 5 == 0:
            with open(SUMS_PATH, 'w', encoding='utf-8') as f:
                json.dump(summaries, f, ensure_ascii=False, indent=2)

        time.sleep(interval)

    with open(SUMS_PATH, 'w', encoding='utf-8') as f:
        json.dump(summaries, f, ensure_ascii=False, indent=2)
    print(f'[summarize_new] 完成：成功 {ok} / {len(to_process)} 篇，失败 {fail} 篇')


if __name__ == '__main__':
    main()

# -*- coding: utf-8 -*-
"""统计各基线的拒答率（回答 I don't know 的比例）。"""
import json

RUNS = [
    ('B1 全量上下文', 'results/01_fullctx_s50.jsonl'),
    ('B2 窗口K=20', 'results/02_sliding_k20.jsonl'),
    ('B2 窗口K=10', 'results/02_sliding_k10.jsonl'),
]
PREFIX = ("i don't know", "i do not know", "unknown", "i cannot")
print(f'{"方法":<16}{"题数":>6}{"拒答":>6}{"拒答率":>9}')
print('-' * 40)
for name, path in RUNS:
    rows = [json.loads(l) for l in open(path, encoding='utf-8') if l.strip()]
    n = len(rows)
    refusal = sum(1 for r in rows
                  if r['hypothesis'].strip().lower().startswith(PREFIX))
    print(f'{name:<16}{n:>6}{refusal:>6}{refusal / n * 100:>8.0f}%')

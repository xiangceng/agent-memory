# -*- coding: utf-8 -*-
"""生成判分人工抽检清单（20 条），并检查弃答题覆盖情况。"""
import json
import os
import random
from collections import Counter, defaultdict

RUNS = [
    ('B1 全量上下文', 'results/01_fullctx_s50.jsonl.eval-results-deepseek-chat'),
    ('B2 窗口K=20', 'results/02_sliding_k20.jsonl.eval-results-deepseek-chat'),
    ('B2 窗口K=10', 'results/02_sliding_k10.jsonl.eval-results-deepseek-chat'),
]
TYPES = ['multi-session', 'temporal-reasoning', 'knowledge-update',
         'single-session-user', 'single-session-assistant', 'single-session-preference']

ref = {x['question_id']: x for x in json.load(open('data/longmemeval_oracle.json', encoding='utf-8'))}

# ---------- 弃答题覆盖检查 ----------
all_abs = [x['question_id'] for x in ref.values() if '_abs' in x['question_id']]
ids50 = set()
for _, path in RUNS:
    for line in open(path, encoding='utf-8'):
        if line.strip():
            ids50.add(json.loads(line)['question_id'])
covered_abs = [q for q in ids50 if '_abs' in q]

print('=' * 90)
print('弃答题（abstention）覆盖检查')
print('=' * 90)
print(f'  全量 500 题中弃答题: {len(all_abs)} 题（{len(all_abs)/len(ref)*100:.1f}%）')
print(f'  题型分布          : {dict(Counter(x["question_type"] for x in ref.values() if "_abs" in x["question_id"]))}')
print(f'  50 题样本中弃答题 : {len(covered_abs)} 题  ← '
      f'{"⚠️ 完全未覆盖，Abstention 指标测不到" if not covered_abs else "已覆盖"}')

# ---------- 抽检样本 ----------
cand = defaultdict(list)
for run_name, path in RUNS:
    for line in open(path, encoding='utf-8'):
        if not line.strip():
            continue
        e = json.loads(line)
        qid = e['question_id']
        r = ref.get(qid)
        if not r:
            continue
        cand[r['question_type']].append({
            'run': run_name, 'qid': qid, 'qtype': r['question_type'],
            'question': r['question'], 'answer': r['answer'],
            'hyp': e['hypothesis'], 'label': bool(e['autoeval_label']['label']),
        })

random.seed(42)
picked, used = [], set()
# 第一轮：每类取 2 错 + 1 对（优先不同 run）
for t in TYPES:
    items = cand.get(t, [])
    wrong = [x for x in items if not x['label']]
    right = [x for x in items if x['label']]
    for group, quota in ((wrong, 2), (right, 1)):
        n = 0
        for x in group:
            if n >= quota:
                break
            key = (x['run'], x['qid'])
            if key in used:
                continue
            picked.append(x)
            used.add(key)
            n += 1

# 第二轮：补齐到 20，尽量覆盖不同 run 与两类判定
for t in TYPES:
    if len(picked) >= 20:
        break
    for x in cand.get(t, []):
        if len(picked) >= 20:
            break
        key = (x['run'], x['qid'])
        if key in used:
            continue
        picked.append(x)
        used.add(key)

picked = picked[:20]

# ---------- 输出 ----------
lines = ['# 判分人工抽检（20 条）', '',
         '> 生成时间：2026-10-24　判分模型：deepseek-chat',
         '> 用途：核对 DeepSeek 自动判分是否可靠。请在「人工判断」处填 ✓（判分对）或 ✗（判分错）。',
         '> 判分标准（官方）：模型回答**包含**正确答案即算对；知识更新允许"旧信息 + 新答案"并存；'
         '时间题不算差一天的错。', '']

print()
print('=' * 90)
print(f'判分人工抽检 · {len(picked)} 条 · 判分模型 deepseek-chat')
print('=' * 90)
for i, x in enumerate(picked, 1):
    tag = '✅ 判为正确' if x['label'] else '❌ 判为错误'
    print(f'\n【{i:2d}】{x["qtype"]:<26} 来源 {x["run"]:<14} 自动判分: {tag}')
    print(f'   问题    : {x["question"]}')
    print(f'   标准答案: {x["answer"]}')
    print(f'   模型回答: {x["hyp"]}')
    print('   ' + '-' * 86)

    lines += [f'### {i}. [{x["qtype"]}]　{x["run"]}',
              '', f'- **问题**：{x["question"]}',
              f'- **标准答案**：{x["answer"]}',
              f'- **模型回答**：{x["hyp"]}',
              f'- **自动判分**：{tag}',
              '- **人工判断**：＿＿＿＿（✓ / ✗）', '']

os.makedirs('docs', exist_ok=True)
out = 'docs/判分抽检_2026-10-24.md'
open(out, 'w', encoding='utf-8').write('\n'.join(lines))

n_wrong = sum(1 for x in picked if not x['label'])
print()
print(f'已保存: {out}')
print(f'抽检构成: 判为错误 {n_wrong} 条 / 判为正确 {len(picked) - n_wrong} 条')
print(f'题型覆盖: {dict(Counter(x["qtype"] for x in picked))}')

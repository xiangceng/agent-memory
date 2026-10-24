# -*- coding: utf-8 -*-
"""汇总多个实验的对比表（准确率 + 分题型 + token 消耗 + 拒答率）。

用法：
    python scripts/compare.py
    python scripts/compare.py --runs "B1:results/01_fullctx_s50.jsonl" "K20:results/02_sliding_k20.jsonl"
"""
import argparse
import csv
import json
import os
import sys

TYPES = ['single-session-user', 'single-session-preference', 'single-session-assistant',
         'multi-session', 'temporal-reasoning', 'knowledge-update']
SHORT = {
    'single-session-user': 'SS-User',
    'single-session-preference': 'SS-Pref',
    'single-session-assistant': 'SS-Asst',
    'multi-session': 'Multi-Sess',
    'temporal-reasoning': 'Temporal',
    'knowledge-update': 'Know-Update',
}
REFUSAL = ("i don't know", "i do not know", "unknown", "i cannot")

DEFAULT_RUNS = [
    ('B1 全量上下文', 'results/01_fullctx_s50.jsonl'),
    ('B1 全量 + CoT', 'results/01_fullctx_s50_cot.jsonl'),
    ('B2 窗口 K=20', 'results/02_sliding_k20.jsonl'),
    ('B2 窗口 K=10', 'results/02_sliding_k10.jsonl'),
]


def load_run(hyp_path):
    if not os.path.exists(hyp_path):
        return None
    usage_path = os.path.splitext(hyp_path)[0] + '_usage.csv'
    eval_path = hyp_path + '.eval-results-deepseek-chat'

    hyps = [json.loads(l) for l in open(hyp_path, encoding='utf-8') if l.strip()]
    refusal = sum(1 for h in hyps
                  if (h.get('hypothesis') or '').strip().lower().startswith(REFUSAL))

    toks, types = [], {}
    if os.path.exists(usage_path):
        for row in csv.DictReader(open(usage_path, encoding='utf-8')):
            toks.append(int(row['total_tokens']))
            types[row['question_id']] = row['question_type']

    if not os.path.exists(eval_path):
        return {'n': len(hyps), 'refusal': refusal, 'toks': toks,
                'overall': None, 'per_type': {}, 'task_avg': None, 'abst': None, 'n_abs': 0}

    rows = [json.loads(l) for l in open(eval_path, encoding='utf-8') if l.strip()]
    per, abst, allacc = {}, [], []
    for r in rows:
        lab = 1 if r['autoeval_label']['label'] else 0
        t = types.get(r['question_id'], '?')
        per.setdefault(t, []).append(lab)
        allacc.append(lab)
        if '_abs' in r['question_id']:
            abst.append(lab)

    per_type = {t: (sum(v) / len(v), len(v)) for t, v in per.items()}
    task_avg = (sum(a for a, _ in per_type.values()) / len(per_type)) if per_type else None
    return {
        'n': len(rows), 'refusal': refusal, 'toks': toks,
        'overall': sum(allacc) / len(allacc) if allacc else None,
        'per_type': per_type, 'task_avg': task_avg,
        'abst': (sum(abst) / len(abst)) if abst else None, 'n_abs': len(abst),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--runs', nargs='*', default=None,
                    help='格式 "名称:路径"；不传则用默认四组')
    args = ap.parse_args()

    runs = DEFAULT_RUNS
    if args.runs:
        runs = [(s.split(':', 1)[0], s.split(':', 1)[1]) for s in args.runs]

    print('=' * 132)
    print('LongMemEval · oracle 设置 · 50 题分层抽样 · deepseek-chat · prompt 对齐官方')
    print('=' * 132)

    hdr = (f'{"方法":<18}{"Overall":>9}{"Task-avg":>10}{"Abst":>7}{"题数":>6}'
           f'{"均Token":>9}{"总Token":>11}{"拒答":>6}   ')
    hdr += ' '.join(f'{SHORT[t]:>10}' for t in TYPES)
    print(hdr)
    print('-' * 132)

    for name, path in runs:
        r = load_run(path)
        if r is None:
            print(f'{name:<18}  （文件不存在: {path}）')
            continue
        avg_tok = sum(r['toks']) / len(r['toks']) if r['toks'] else 0
        tot_tok = sum(r['toks'])
        overall = f'{r["overall"]:.4f}' if r['overall'] is not None else '待判分'
        tavg = f'{r["task_avg"]:.4f}' if r['task_avg'] else '—'
        abst = f'{r["abst"]:.2f}' if r['abst'] is not None else '—'
        line = (f'{name:<18}{overall:>9}{tavg:>10}{abst:>7}{r["n"]:>6}'
                f'{avg_tok:>9.0f}{tot_tok:>11,}{r["refusal"]:>6}   ')
        for t in TYPES:
            if t in r['per_type']:
                v, cnt = r['per_type'][t]
                line += f'{v:>10.2f}'
            else:
                line += f'{"—":>10}'
        print(line)

    print('-' * 132)
    print('说明：Abst 为弃答题准确率（括号内为样本量见上表题数）；拒答 = 回答以 "I don\'t know" 开头的题数。')
    print('      oracle 设置仅提供证据会话，属检索上限条件；论文主表需在 S 设置上重跑。')
    print('=' * 132)


if __name__ == '__main__':
    main()

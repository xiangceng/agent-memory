# -*- coding: utf-8 -*-
"""汇总 LongMemEval 判分结果。

与官方 print_qa_metrics.py 的聚合逻辑一致，但去掉了
`assert entry['autoeval_label']['model'] == 'gpt-4o-2024-08-06'` 这一硬编码，
使得用 DeepSeek 等替代判分模型时也能正常统计。

用法：
    python scripts/report_metrics.py results/01_fullctx.jsonl.eval-results-deepseek-chat data/longmemeval_oracle.json
"""
import json
import sys
from collections import OrderedDict

TYPES = ['single-session-user', 'single-session-preference', 'single-session-assistant',
         'multi-session', 'temporal-reasoning', 'knowledge-update']


def main():
    if len(sys.argv) != 3:
        print('Usage: python scripts/report_metrics.py <eval_results_file> <ref_file>')
        sys.exit(1)

    in_file, ref_file = sys.argv[1], sys.argv[2]
    rows = [json.loads(l) for l in open(in_file, encoding='utf-8') if l.strip()]
    ref = {x['question_id']: x for x in json.load(open(ref_file, encoding='utf-8'))}

    type2acc = OrderedDict((t, []) for t in TYPES)
    abst = []
    models = set()

    for e in rows:
        qid = e['question_id']
        if qid not in ref:
            print(f'  警告：{qid} 不在参考数据中，跳过')
            continue
        lab = bool(e.get('autoeval_label', {}).get('label'))
        models.add(e.get('autoeval_label', {}).get('model', '?'))
        t = ref[qid]['question_type']
        type2acc.setdefault(t, []).append(1 if lab else 0)
        if '_abs' in qid:
            abst.append(1 if lab else 0)

    print('=' * 62)
    print(f'判分文件: {in_file}')
    print(f'判分模型: {", ".join(sorted(models))}')
    print(f'题目数量: {len(rows)}')
    print('=' * 62)
    print(f'{"题型":<28}{"准确率":>10}{"题数":>8}')
    print('-' * 62)

    task_acc, all_acc = [], []
    for t in TYPES:
        v = type2acc.get(t, [])
        if v:
            acc = sum(v) / len(v)
            task_acc.append(acc)
            all_acc.extend(v)
            print(f'{t:<28}{acc:>10.4f}{len(v):>8}')
        else:
            print(f'{t:<28}{"—":>10}{0:>8}')

    print('-' * 62)
    if task_acc:
        print(f'{"Task-averaged Accuracy":<28}{sum(task_acc)/len(task_acc):>10.4f}')
    if all_acc:
        print(f'{"Overall Accuracy":<28}{sum(all_acc)/len(all_acc):>10.4f}  ({len(all_acc)} 题)')
    if abst:
        print(f'{"Abstention Accuracy":<28}{sum(abst)/len(abst):>10.4f}  ({len(abst)} 题)')
    else:
        print(f'{"Abstention Accuracy":<28}{"—":>10}  (0 题，本批次无弃答题)')
    print('=' * 62)


if __name__ == '__main__':
    main()

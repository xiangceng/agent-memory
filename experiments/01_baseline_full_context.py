# -*- coding: utf-8 -*-
"""B1 全量上下文基线：把全部历史会话拼进 prompt，单次调用生成答案。

用法：
    python experiments/01_baseline_full_context.py --subset 5          # 冒烟
    python experiments/01_baseline_full_context.py --subset 50         # 跑 50 题
    python experiments/01_baseline_full_context.py                     # 全量

输出：
    results/01_fullctx.jsonl        每行 {"question_id", "hypothesis"}
    results/01_fullctx_usage.csv    每题 token 与耗时

说明：
    - 支持断点续跑（已完成的 question_id 会跳过）
    - 每题只调用 1 次模型（这是基线，不做任何记忆机制）
"""
import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime

from dotenv import load_dotenv
from openai import OpenAI

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT, '.env'))

SYSTEM_PROMPT = (
    "You are a helpful assistant that answers questions based on a long chat history "
    "between a user and you. Answer concisely with the exact answer phrase when possible."
)

PROMPT_TEMPLATE = """Below is the history of our previous conversations, ordered by time.

{history}

Today's date is {question_date}.

Based on the history above, answer the following question.
If the information is not mentioned in the history, answer "I don't know".

Question: {question}
Answer:"""


def build_history(instance):
    """把 haystack_sessions 按时间拼成文本。返回 (history_text, n_sessions, n_turns)."""
    sessions = instance.get('haystack_sessions') or []
    dates = instance.get('haystack_dates') or []
    lines = []
    n_turns = 0
    for i, sess in enumerate(sessions):
        d = dates[i] if i < len(dates) else 'unknown date'
        lines.append(f"### Session {i + 1} — {d}")
        for turn in sess:
            role = turn.get('role', 'user')
            content = (turn.get('content') or '').strip()
            if not content:
                continue
            lines.append(f"[{role}] {content}")
            n_turns += 1
        lines.append('')
    return '\n'.join(lines), len(sessions), n_turns


def load_done(out_path):
    done = set()
    if os.path.exists(out_path):
        with open(out_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    done.add(json.loads(line)['question_id'])
                except Exception:
                    continue
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', default=os.path.join(ROOT, 'data', 'longmemeval_oracle.json'))
    ap.add_argument('--subset', type=int, default=0, help='只跑前 N 题；0 表示全量')
    ap.add_argument('--stratified', action='store_true',
                    help='按题型分层抽样（强烈建议与 --subset 同用：数据按题型排序，直接取前 N 题会全是 temporal-reasoning）')
    ap.add_argument('--out', default=os.path.join(ROOT, 'results', '01_fullctx.jsonl'))
    ap.add_argument('--sleep', type=float, default=0.2, help='每次调用后的间隔秒数，防止限流')
    args = ap.parse_args()

    if not os.path.exists(args.data):
        sys.exit(f'数据文件不存在：{args.data}\n请先运行 scripts/download_data.ps1')

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    usage_path = os.path.splitext(args.out)[0] + '_usage.csv'
    usage_new = not os.path.exists(usage_path)

    client = OpenAI(
        api_key=os.getenv('LLM_API_KEY'),
        base_url=os.getenv('LLM_BASE_URL', 'https://api.deepseek.com/v1'),
    )
    model = os.getenv('LLM_MODEL', 'deepseek-chat')

    with open(args.data, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # ⚠️ 数据按题型排序，直接取前 N 题会全是 temporal-reasoning。
    # --stratified 时必须先在全量数据上分层抽样，再截断到 N；
    # 顺序反了就会在已截断的单一题型子集上"分层"，等于没分。
    if args.stratified and args.subset and args.subset > 0:
        from collections import Counter, defaultdict
        buckets = defaultdict(list)
        for x in data:
            buckets[x.get('question_type', '?')].append(x)
        total = len(data)
        picked = []
        for t in sorted(buckets):
            k = max(1, round(args.subset * len(buckets[t]) / total))
            picked.extend(buckets[t][:k])
        data = picked[:args.subset]
        print('分层抽样题型分布:', dict(sorted(Counter(x['question_type'] for x in data).items())))
    elif args.subset and args.subset > 0:
        data = data[:args.subset]
        from collections import Counter
        print('⚠️ 未启用 --stratified，取前 N 题；题型分布:',
              dict(sorted(Counter(x['question_type'] for x in data).items())))

    done = load_done(args.out)
    todo = [x for x in data if x['question_id'] not in done]
    print(f'数据文件 : {os.path.basename(args.data)}')
    print(f'题目总数 : {len(data)}   已完成 : {len(done)}   待跑 : {len(todo)}')
    print(f'模型     : {model}')
    print('-' * 70)

    usage_f = open(usage_path, 'a', newline='', encoding='utf-8')
    writer = csv.writer(usage_f)
    if usage_new:
        writer.writerow(['question_id', 'question_type', 'prompt_tokens',
                         'completion_tokens', 'total_tokens', 'latency_ms', 'history_chars'])

    ok, fail = 0, 0
    for idx, inst in enumerate(todo, 1):
        qid = inst['question_id']
        qtype = inst.get('question_type', '')
        history, n_sess, n_turns = build_history(inst)
        prompt = PROMPT_TEMPLATE.format(
            history=history,
            question_date=inst.get('question_date', 'unknown'),
            question=inst.get('question', ''),
        )

        t0 = time.time()
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {'role': 'system', 'content': SYSTEM_PROMPT},
                    {'role': 'user', 'content': prompt},
                ],
                temperature=0,
                max_tokens=512,
            )
            hyp = (resp.choices[0].message.content or '').strip()
            u = resp.usage
            pt = getattr(u, 'prompt_tokens', 0) or 0
            ct = getattr(u, 'completion_tokens', 0) or 0
            tt = getattr(u, 'total_tokens', 0) or (pt + ct)
            cost_ms = int((time.time() - t0) * 1000)

            with open(args.out, 'a', encoding='utf-8') as f:
                f.write(json.dumps({'question_id': qid, 'hypothesis': hyp},
                                   ensure_ascii=False) + '\n')
            writer.writerow([qid, qtype, pt, ct, tt, cost_ms, len(history)])
            usage_f.flush()
            ok += 1
            print(f'[{idx}/{len(todo)}] {qid[:28]:<28} {qtype:<24} '
                  f'tok={tt:<7} {cost_ms}ms')
        except Exception as e:
            fail += 1
            print(f'[{idx}/{len(todo)}] {qid[:28]:<28} FAILED: {type(e).__name__}: {e}')
            time.sleep(3)
        time.sleep(args.sleep)

    usage_f.close()
    print('-' * 70)
    print(f'完成 {ok} 题，失败 {fail} 题')
    print(f'结果 : {args.out}')
    print(f'用量 : {usage_path}')
    print()
    print('下一步：用官方脚本判分（见 docs/两周执行清单.md Day 5）')


if __name__ == '__main__':
    main()

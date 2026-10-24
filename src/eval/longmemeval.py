# -*- coding: utf-8 -*-
"""LongMemEval 的公共实现：数据加载、分层抽样、历史拼接、生成循环。

被 experiments/ 下的各基线脚本复用，保证：
    - prompt 模板完全一致（否则结果不可比）
    - 断点续跑逻辑一致
    - usage 记录格式一致
"""
import csv
import json
import os
import time
from collections import Counter, defaultdict

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

USAGE_FIELDS = ['question_id', 'question_type', 'prompt_tokens',
                'completion_tokens', 'total_tokens', 'latency_ms', 'history_chars']


# ---------------------------------------------------------------- 数据

def load_instances(path, subset=0, stratified=False):
    """读数据；subset>0 时截断。

    ⚠️ LongMemEval 数据按题型排序，直接取前 N 题会全是 temporal-reasoning。
    stratified=True 时先在**全量**上按题型比例抽样，再截断。
    """
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if stratified and subset and subset > 0:
        buckets = defaultdict(list)
        for x in data:
            buckets[x.get('question_type', '?')].append(x)
        total = len(data)
        picked = []
        for t in sorted(buckets):
            k = max(1, round(subset * len(buckets[t]) / total))
            picked.extend(buckets[t][:k])
        data = picked[:subset]
        print('分层抽样题型分布:', dict(sorted(Counter(x['question_type'] for x in data).items())))
    elif subset and subset > 0:
        data = data[:subset]
        print('⚠️ 未启用 --stratified，题型分布:',
              dict(sorted(Counter(x['question_type'] for x in data).items())))

    return data


# ---------------------------------------------------------------- 历史拼接

def flatten_turns(inst):
    """把 haystack_sessions 展平成 [(date, role, content), ...] 按时间顺序。"""
    sessions = inst.get('haystack_sessions') or []
    dates = inst.get('haystack_dates') or []
    out = []
    for i, sess in enumerate(sessions):
        d = dates[i] if i < len(dates) else 'unknown date'
        for turn in sess:
            content = (turn.get('content') or '').strip()
            if content:
                out.append((d, turn.get('role', 'user'), content))
    return out


def _format_grouped(groups):
    """groups: [(key, [(date, role, content), ...]), ...] -> 文本"""
    lines = []
    for key, turns in groups:
        lines.append(f'### {key}')
        for _, role, content in turns:
            lines.append(f'[{role}] {content}')
        lines.append('')
    return '\n'.join(lines)


def build_history_full(inst):
    """B1：全部会话，按会话分组。返回 (text, n_sessions, n_turns)。"""
    sessions = inst.get('haystack_sessions') or []
    dates = inst.get('haystack_dates') or []
    groups, n_turns = [], 0
    for i, sess in enumerate(sessions):
        d = dates[i] if i < len(dates) else 'unknown date'
        turns = []
        for turn in sess:
            content = (turn.get('content') or '').strip()
            if content:
                turns.append((d, turn.get('role', 'user'), content))
                n_turns += 1
        if turns:
            groups.append((f'Session {i + 1} — {d}', turns))
    return _format_grouped(groups), len(groups), n_turns


def build_history_window(inst, k):
    """B2：只保留最近 k 轮（turn 级滑动窗口）。返回 (text, n_sessions, n_turns)。

    不保留更早的会话，用来检验"只看最近上下文"的能力上限。
    """
    flat = flatten_turns(inst)
    kept = flat[-k:] if k and k > 0 else flat
    # 按日期重新分组，保持时间顺序
    groups, cur_key, cur_turns = [], None, []
    for d, role, content in kept:
        if d != cur_key:
            if cur_turns:
                groups.append((f'Session @ {cur_key}', cur_turns))
            cur_key, cur_turns = d, []
        cur_turns.append((d, role, content))
    if cur_turns:
        groups.append((f'Session @ {cur_key}', cur_turns))
    return _format_grouped(groups), len(groups), len(kept)


# ---------------------------------------------------------------- 生成

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


def make_prompt(inst, history):
    return PROMPT_TEMPLATE.format(
        history=history,
        question_date=inst.get('question_date', 'unknown'),
        question=inst.get('question', ''),
    )


def run_generation(client, model, instances, build_fn, out_path, usage_path,
                   sleep=0.2, max_tokens=512, verbose=True):
    """逐题调用模型并写结果。build_fn(inst) -> (history_text, n_sess, n_turns)。"""
    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
    usage_new = not os.path.exists(usage_path)
    done = load_done(out_path)
    todo = [x for x in instances if x['question_id'] not in done]

    print(f'题目总数 : {len(instances)}   已完成 : {len(done)}   待跑 : {len(todo)}')
    print(f'模型     : {model}')
    print('-' * 70)

    usage_f = open(usage_path, 'a', newline='', encoding='utf-8')
    writer = csv.writer(usage_f)
    if usage_new:
        writer.writerow(USAGE_FIELDS)

    ok, fail = 0, 0
    for idx, inst in enumerate(todo, 1):
        qid = inst['question_id']
        qtype = inst.get('question_type', '')
        history, n_sess, n_turns = build_fn(inst)
        prompt = make_prompt(inst, history)

        t0 = time.time()
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {'role': 'system', 'content': SYSTEM_PROMPT},
                    {'role': 'user', 'content': prompt},
                ],
                temperature=0,
                max_tokens=max_tokens,
            )
            hyp = (resp.choices[0].message.content or '').strip()
            u = resp.usage
            pt = getattr(u, 'prompt_tokens', 0) or 0
            ct = getattr(u, 'completion_tokens', 0) or 0
            tt = getattr(u, 'total_tokens', 0) or (pt + ct)
            cost_ms = int((time.time() - t0) * 1000)

            with open(out_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps({'question_id': qid, 'hypothesis': hyp},
                                   ensure_ascii=False) + '\n')
            writer.writerow([qid, qtype, pt, ct, tt, cost_ms, len(history)])
            usage_f.flush()
            ok += 1
            if verbose:
                print(f'[{idx}/{len(todo)}] {qid[:28]:<28} {qtype:<24} '
                      f'tok={tt:<7} {cost_ms}ms')
        except Exception as e:
            fail += 1
            print(f'[{idx}/{len(todo)}] {qid[:28]:<28} FAILED: {type(e).__name__}: {e}')
            time.sleep(3)
        time.sleep(sleep)

    usage_f.close()
    print('-' * 70)
    print(f'完成 {ok} 题，失败 {fail} 题')
    print(f'结果 : {out_path}')
    print(f'用量 : {usage_path}')
    return ok, fail

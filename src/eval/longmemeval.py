# -*- coding: utf-8 -*-
"""LongMemEval 的公共实现：数据加载、分层抽样、历史拼接、生成循环。

⚠️ 本文件严格对齐官方 src/generation/run_generation.py 的口径，
   以保证与论文报告的数字可比。任何改动都会破坏可比性。

对齐要点（2026-10-24 修订）：
    1. **单条 user 消息，无 system 消息**（官方 line 362-364）
    2. **prompt 措辞与官方完全一致**（官方 line 55-57，非 CoT / CoT 两版）
    3. **历史格式**：`\\n### Session {i+1}:\\nSession Date: {date}\\nSession Content:\\n{turns}\\n`
       每个 turn 为 `\\n\\n{role}: {content}`（官方 line 243-245, 252）
    4. **生成参数**：temperature=0, n=1, max_tokens=500（非 CoT）/ 800（CoT）（官方 line 342, 365-367）
    5. **不含"信息不存在就回答 I don't know"这类指令** —— 旧版本曾加过，
       导致模型过度拒答（实测 14%~52%），严重压低基线且与原文不可比。
"""
import csv
import json
import os
import time
from collections import Counter, defaultdict

# ---- 官方 prompt 模板（run_generation.py line 55-57）----
PROMPT_NOCOT = (
    'I will give you several history chats between you and a user. '
    'Please answer the question based on the relevant chat history.'
    '\n\n\nHistory Chats:\n\n{}\n\nCurrent Date: {}\nQuestion: {}\nAnswer:'
)
PROMPT_COT = (
    'I will give you several history chats between you and a user. '
    'Please answer the question based on the relevant chat history. '
    'Answer the question step by step: first extract all the relevant information, '
    'and then reason over the information to get the answer.'
    '\n\n\nHistory Chats:\n\n{}\n\nCurrent Date: {}\nQuestion: {}\nAnswer (step by step):'
)

GEN_LEN_NOCOT = 500
GEN_LEN_COT = 800

USAGE_FIELDS = ['question_id', 'question_type', 'is_abs', 'prompt_tokens',
                'completion_tokens', 'total_tokens', 'latency_ms', 'history_chars']


# ---------------------------------------------------------------- 数据

def is_abs(qid):
    """LongMemEval 用 question_id 是否含 '_abs' 标记弃答题。"""
    return '_abs' in qid


def load_instances(path, subset=0, stratified=False, include_abs=True):
    """读数据；subset>0 时截断。

    ⚠️ 数据按题型排序，直接取前 N 题会全是 temporal-reasoning。
    stratified=True 时在**全量**上按 (题型, 是否弃答) 分层抽样，再截断，
    这样 30 道弃答题（占比 6%）也能按比例进入子集。
    """
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if stratified and subset and subset > 0:
        buckets = defaultdict(list)
        for x in data:
            qid = x['question_id']
            key = (x.get('question_type', '?'), is_abs(qid) if include_abs else False)
            buckets[key].append(x)
        total = len(data)
        picked = []
        for key in sorted(buckets):
            k = max(1, round(subset * len(buckets[key]) / total))
            picked.extend(buckets[key][:k])
        data = picked[:subset]
        types = Counter(x['question_type'] for x in data)
        n_abs = sum(1 for x in data if is_abs(x['question_id']))
        print('分层抽样题型分布:', dict(sorted(types.items())))
        print(f'其中弃答题: {n_abs} 题（全量共 {sum(1 for x in json.load(open(path, encoding="utf-8")) if is_abs(x["question_id"]))} 题）')
    elif subset and subset > 0:
        data = data[:subset]
        print('⚠️ 未启用 --stratified，题型分布:',
              dict(sorted(Counter(x['question_type'] for x in data).items())))

    return data


# ---------------------------------------------------------------- 历史拼接（官方 nl 格式）

def _session_block(idx, date, turns):
    """官方格式：\\n### Session {i}:\\nSession Date: {d}\\nSession Content:\\n{turns}\\n"""
    sess = ''.join(f'\n\n{t["role"]}: {t["content"].strip()}' for t in turns)
    return f'\n### Session {idx}:\nSession Date: {date}\nSession Content:\n{sess}\n'


def build_history_full(inst):
    """B1：全部会话（session 粒度）。返回 (text, n_sessions, n_turns)。"""
    sessions = inst.get('haystack_sessions') or []
    dates = inst.get('haystack_dates') or []
    out, n_sess, n_turns = '', 0, 0
    for i, sess in enumerate(sessions):
        d = dates[i] if i < len(dates) else ''
        turns = [t for t in sess if (t.get('content') or '').strip()]
        if not turns:
            continue
        n_sess += 1
        n_turns += len(turns)
        out += _session_block(i + 1, d, turns)
    return out, n_sess, n_turns


def build_history_window(inst, k):
    """B2：只保留最近 k 轮（turn 级窗口），按原会话边界分组。返回 (text, n_sessions, n_turns)。"""
    sessions = inst.get('haystack_sessions') or []
    dates = inst.get('haystack_dates') or []

    flat = []   # (session_idx, date, turn)
    for i, sess in enumerate(sessions):
        d = dates[i] if i < len(dates) else ''
        for t in sess:
            if (t.get('content') or '').strip():
                flat.append((i, d, t))
    kept = flat[-k:] if k and k > 0 else flat

    groups, cur_idx = [], None
    for sid, d, t in kept:
        if sid != cur_idx:
            groups.append([sid, d, []])
            cur_idx = sid
        groups[-1][2].append(t)

    out, n_turns = '', 0
    for idx, (sid, d, turns) in enumerate(groups, 1):
        n_turns += len(turns)
        out += _session_block(idx, d, turns)
    return out, len(groups), n_turns


# ---------------------------------------------------------------- 生成

def make_prompt(inst, history, cot=False):
    tpl = PROMPT_COT if cot else PROMPT_NOCOT
    return tpl.format(history,
                      inst.get('question_date', ''),
                      inst.get('question', ''))


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


def run_generation(client, model, instances, build_fn, out_path, usage_path,
                   sleep=0.2, cot=False, verbose=True):
    """逐题调用模型并写结果。build_fn(inst) -> (history, n_sess, n_turns)。

    严格对齐官方调用方式：单条 user 消息、temperature=0、n=1、
    max_tokens=500（非 CoT）/ 800（CoT）。
    """
    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
    usage_new = not os.path.exists(usage_path)
    done = load_done(out_path)
    todo = [x for x in instances if x['question_id'] not in done]
    gen_len = GEN_LEN_COT if cot else GEN_LEN_NOCOT

    print(f'题目总数 : {len(instances)}   已完成 : {len(done)}   待跑 : {len(todo)}')
    print(f'模型     : {model}    CoT: {cot}    max_tokens: {gen_len}')
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
        prompt = make_prompt(inst, history, cot=cot)

        t0 = time.time()
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{'role': 'user', 'content': prompt}],
                n=1,
                temperature=0,
                max_tokens=gen_len,
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
            writer.writerow([qid, qtype, is_abs(qid), pt, ct, tt, cost_ms, len(history)])
            usage_f.flush()
            ok += 1
            if verbose:
                print(f'[{idx}/{len(todo)}] {qid[:30]:<30} {qtype:<24} '
                      f'tok={tt:<7} {cost_ms}ms')
        except Exception as e:
            fail += 1
            print(f'[{idx}/{len(todo)}] {qid[:30]:<30} FAILED: {type(e).__name__}: {e}')
            time.sleep(3)
        time.sleep(sleep)

    usage_f.close()
    print('-' * 70)
    print(f'完成 {ok} 题，失败 {fail} 题')
    print(f'结果 : {out_path}')
    print(f'用量 : {usage_path}')
    return ok, fail

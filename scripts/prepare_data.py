# -*- coding: utf-8 -*-
"""Day 1 数据准备：查询体积、下载所需文件、校验格式。

用法：
    python scripts/prepare_data.py              # 下载 oracle + s（默认）
    python scripts/prepare_data.py --with-m     # 额外下载 m（体积很大，慎用）
"""
import argparse
import json
import os
import ssl
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')

# 国内直连 huggingface.co 经常超时，按顺序尝试镜像
BASES = [
    'https://hf-mirror.com/datasets/xiaowu0162/longmemeval-cleaned/resolve/main',
    'https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/resolve/main',
]
BASE = None  # 由 pick_base() 选定

FILES = {
    'longmemeval_oracle.json': 'oracle（仅证据会话，最省 token）',
    'longmemeval_s_cleaned.json': 'S（约 11.5 万 token/题，主实验）',
    'longmemeval_m_cleaned.json': 'M（约 500 会话/题，很贵）',
}

CTX = ssl.create_default_context()
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}


def pick_base():
    """选一个可达的源（镜像优先）。"""
    global BASE
    for b in BASES:
        host = b.split('/')[2]
        t0 = time.time()
        try:
            req = urllib.request.Request(f'{b}/longmemeval_oracle.json',
                                         headers=UA, method='HEAD')
            with urllib.request.urlopen(req, timeout=25, context=CTX) as r:
                size = int(r.headers.get('Content-Length', 0))
            print(f'  选用源：{host}（{size/1048576:.1f} MB，{(time.time()-t0)*1000:.0f} ms）')
            BASE = b
            return True
        except Exception as e:
            print(f'  {host} 不可用：{type(e).__name__}')
    return False


def head_size(fname):
    req = urllib.request.Request(f'{BASE}/{fname}', headers=UA, method='HEAD')
    try:
        with urllib.request.urlopen(req, timeout=60, context=CTX) as r:
            return int(r.headers.get('Content-Length', 0))
    except Exception as e:
        print(f'    HEAD 失败：{type(e).__name__}: {e}')
        return 0


def download(fname, expect=0):
    out = os.path.join(DATA, fname)
    if os.path.exists(out) and os.path.getsize(out) > 100_000:
        print(f'  SKIP  {fname}  已存在 {os.path.getsize(out)/1048576:.1f} MB')
        return True
    url = f'{BASE}/{fname}'
    print(f'  DOWN  {fname}' + (f'  ({expect/1048576:.1f} MB)' if expect else ''))
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=1800, context=CTX) as r, open(out, 'wb') as f:
            total, last = 0, 0
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
                total += len(chunk)
                if total - last > 50 * 1048576:
                    last = total
                    print(f'        ... {total/1048576:.0f} MB')
        dt = time.time() - t0
        print(f'  OK    {fname}  {os.path.getsize(out)/1048576:.1f} MB  ({dt:.0f}s)')
        return True
    except Exception as e:
        print(f'  FAIL  {fname}: {type(e).__name__}: {e}')
        if os.path.exists(out):
            os.remove(out)
        return False


def validate(fname):
    path = os.path.join(DATA, fname)
    if not os.path.exists(path):
        return
    print(f'\n  校验 {fname}:')
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f'    JSON 解析失败：{type(e).__name__}: {e}')
        return
    print(f'    题数：{len(data)}')
    if not data:
        return
    inst = data[0]
    need = ['question_id', 'question_type', 'question', 'answer', 'question_date',
            'haystack_sessions', 'haystack_dates', 'answer_session_ids']
    miss = [k for k in need if k not in inst]
    print(f'    字段齐全：{"是" if not miss else "否，缺 " + str(miss)}')
    print(f'    示例题目：{inst.get("question", "")[:60]}')
    print(f'    示例类型：{inst.get("question_type", "")}')
    sess = inst.get('haystack_sessions') or []
    turns = sum(len(s) for s in sess)
    print(f'    示例历史：{len(sess)} 个会话 / {turns} 轮')
    # 类型分布
    from collections import Counter
    c = Counter(x.get('question_type', '?') for x in data)
    print(f'    类型分布：{dict(sorted(c.items()))}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--with-m', action='store_true', help='同时下载 M 文件（很大）')
    args = ap.parse_args()

    os.makedirs(DATA, exist_ok=True)

    print('=' * 66)
    print('〇、选择下载源')
    print('=' * 66)
    if not pick_base():
        sys.exit('所有源均不可达，请检查网络或手动下载：\n'
                 '  https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned')

    print()
    print('=' * 66)
    print('一、查询文件体积')
    print('=' * 66)
    sizes = {}
    for fn, desc in FILES.items():
        s = head_size(fn)
        sizes[fn] = s
        print(f'  {fn:<34} {s/1048576:>8.1f} MB   {desc}')

    targets = ['longmemeval_oracle.json', 'longmemeval_s_cleaned.json']
    if args.with_m:
        targets.append('longmemeval_m_cleaned.json')

    print()
    print('=' * 66)
    print('二、下载')
    print('=' * 66)
    ok = all(download(fn, sizes.get(fn, 0)) for fn in targets)

    print()
    print('=' * 66)
    print('三、格式校验')
    print('=' * 66)
    for fn in targets:
        validate(fn)

    print()
    print('=' * 66)
    if ok:
        print('数据准备完成 ✓')
    else:
        print('部分文件下载失败，请重试或手动从 HuggingFace 下载')
    print('=' * 66)


if __name__ == '__main__':
    main()

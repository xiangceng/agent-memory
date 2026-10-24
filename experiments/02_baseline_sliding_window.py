# -*- coding: utf-8 -*-
"""B2 滑动窗口基线：只保留最近 K 轮对话，丢弃更早的历史。

用途：回答"只看最近上下文能做到什么程度"，是判断记忆机制是否必要的下界参照。

用法：
    python experiments/02_baseline_sliding_window.py --window 10 --subset 50 --stratified
    python experiments/02_baseline_sliding_window.py --window 20 --subset 50 --stratified

输出：
    results/02_sliding_k{K}.jsonl
    results/02_sliding_k{K}_usage.csv
"""
import argparse
import os
import sys

from dotenv import load_dotenv
from openai import OpenAI

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from src.eval.longmemeval import load_instances, build_history_window, run_generation  # noqa: E402

load_dotenv(os.path.join(ROOT, '.env'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', default=os.path.join(ROOT, 'data', 'longmemeval_oracle.json'))
    ap.add_argument('--window', type=int, required=True, help='保留最近 K 轮')
    ap.add_argument('--subset', type=int, default=0)
    ap.add_argument('--stratified', action='store_true')
    ap.add_argument('--sleep', type=float, default=0.2)
    args = ap.parse_args()

    if not os.path.exists(args.data):
        sys.exit(f'数据文件不存在：{args.data}')

    out = os.path.join(ROOT, 'results', f'02_sliding_k{args.window}.jsonl')
    usage = os.path.join(ROOT, 'results', f'02_sliding_k{args.window}_usage.csv')

    client = OpenAI(
        api_key=os.getenv('LLM_API_KEY'),
        base_url=os.getenv('LLM_BASE_URL', 'https://api.deepseek.com/v1'),
    )
    model = os.getenv('LLM_MODEL', 'deepseek-chat')

    data = load_instances(args.data, args.subset, args.stratified)
    print(f'数据文件 : {os.path.basename(args.data)}')
    print(f'窗口大小 : 最近 {args.window} 轮')

    run_generation(
        client, model, data,
        build_fn=lambda inst: build_history_window(inst, args.window),
        out_path=out, usage_path=usage, sleep=args.sleep,
    )


if __name__ == '__main__':
    main()

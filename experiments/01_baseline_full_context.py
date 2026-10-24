# -*- coding: utf-8 -*-
"""B1 全量上下文基线：把全部历史会话拼进 prompt，单次调用生成答案。

⚠️ prompt 与历史格式严格对齐 LongMemEval 官方 run_generation.py（见 src/eval/longmemeval.py）。

用法：
    python experiments/01_baseline_full_context.py --subset 5                       # 冒烟
    python experiments/01_baseline_full_context.py --subset 50 --stratified         # 分层基线
    python experiments/01_baseline_full_context.py --subset 50 --stratified --cot   # CoT 版本

输出：
    results/01_fullctx_s{N}[_cot].jsonl
    results/01_fullctx_s{N}[_cot]_usage.csv
"""
import argparse
import os
import sys

from dotenv import load_dotenv
from openai import OpenAI

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from src.eval.longmemeval import load_instances, build_history_full, run_generation  # noqa: E402

load_dotenv(os.path.join(ROOT, '.env'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', default=os.path.join(ROOT, 'data', 'longmemeval_oracle.json'))
    ap.add_argument('--subset', type=int, default=0, help='只跑 N 题；0 表示全量')
    ap.add_argument('--stratified', action='store_true',
                    help='按 (题型, 弃答) 分层抽样——强烈建议与 --subset 同用')
    ap.add_argument('--cot', action='store_true', help='使用官方 CoT 模板（max_tokens=800）')
    ap.add_argument('--out', default=None)
    ap.add_argument('--sleep', type=float, default=0.2)
    args = ap.parse_args()

    if not os.path.exists(args.data):
        sys.exit(f'数据文件不存在：{args.data}\n请先运行 scripts/prepare_data.py')

    if args.out:
        out = args.out
    else:
        tag = f's{args.subset}' if args.subset else 'all'
        out = os.path.join(ROOT, 'results', f'01_fullctx_{tag}{"_cot" if args.cot else ""}.jsonl')
    usage = os.path.splitext(out)[0] + '_usage.csv'

    client = OpenAI(
        api_key=os.getenv('LLM_API_KEY'),
        base_url=os.getenv('LLM_BASE_URL', 'https://api.deepseek.com/v1'),
    )
    model = os.getenv('LLM_MODEL', 'deepseek-chat')

    data = load_instances(args.data, args.subset, args.stratified)
    print(f'数据文件 : {os.path.basename(args.data)}')

    run_generation(client, model, data, build_fn=build_history_full,
                   out_path=out, usage_path=usage, sleep=args.sleep, cot=args.cot)


if __name__ == '__main__':
    main()

# -*- coding: utf-8 -*-
"""给 LongMemEval 官方 evaluate_qa.py 打补丁，使其支持任意 OpenAI 兼容端点判分。

背景：
    官方脚本的 model_zoo 只支持 gpt-4o / gpt-4o-mini（走 OPENAI_API_KEY）
    和 llama（走本地 vLLM:8001）。要换成 DeepSeek 等国产模型，
    需要新增一个 'compat' 源，从环境变量读 key 与 base_url。

设计：
    - 幂等：重复运行不会重复插入
    - 不改官方逻辑，只做加法
    - 打补丁后可随时 `git -C third_party/LongMemEval checkout -- .` 还原

用法：
    python scripts/patch_official.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, 'third_party', 'LongMemEval', 'src', 'evaluation', 'evaluate_qa.py')

MARK_ZOO = '# [patched] compat sources'
MARK_CLIENT = '# [patched] compat client branch'

OLD_ZOO = "    'gpt-4o': ('gpt-4o-2024-08-06', 'openai'),\n}"
NEW_ZOO = ("    'gpt-4o': ('gpt-4o-2024-08-06', 'openai'),\n"
           "    " + MARK_ZOO + "\n"
           "    'deepseek-chat': ('deepseek-chat', 'compat'),\n"
           "    'deepseek-reasoner': ('deepseek-reasoner', 'compat'),\n"
           "    'qwen-plus': ('qwen-plus', 'compat'),\n"
           "    'qwen-max': ('qwen-max', 'compat'),\n"
           "}")

OLD_CLIENT = ('    else:\n'
              '        openai_api_key = "EMPTY"\n'
              '        openai_api_base = "http://localhost:8001/v1"\n')
NEW_CLIENT = ('    ' + MARK_CLIENT + '\n'
              '    elif metric_model_source == "compat":\n'
              '        openai_api_key = os.getenv("JUDGE_API_KEY") or os.getenv("OPENAI_API_KEY")\n'
              '        openai_api_base = os.getenv("JUDGE_BASE_URL") or os.getenv("OPENAI_BASE_URL")\n'
              '        if not openai_api_key:\n'
              '            raise RuntimeError("请设置 JUDGE_API_KEY 环境变量")\n'
              '        if not openai_api_base:\n'
              '            raise RuntimeError("请设置 JUDGE_BASE_URL 环境变量，例如 https://api.deepseek.com/v1")\n'
              '    else:\n'
              '        openai_api_key = "EMPTY"\n'
              '        openai_api_base = "http://localhost:8001/v1"\n')


def main():
    if not os.path.exists(TARGET):
        sys.exit(f'未找到官方脚本：{TARGET}\n请先克隆：\n'
                 f'  git clone --depth 1 git@github.com:xiaowu0162/LongMemEval.git third_party/LongMemEval')

    src = open(TARGET, encoding='utf-8').read()
    changed = []

    if MARK_ZOO in src:
        print('model_zoo 已打过补丁，跳过')
    elif OLD_ZOO in src:
        src = src.replace(OLD_ZOO, NEW_ZOO, 1)
        changed.append('model_zoo')
    else:
        sys.exit('model_zoo 定位失败：官方文件结构可能已变化，请手动检查')

    if MARK_CLIENT in src:
        print('client 分支已打过补丁，跳过')
    elif OLD_CLIENT in src:
        src = src.replace(OLD_CLIENT, NEW_CLIENT, 1)
        changed.append('client')
    else:
        sys.exit('client 分支定位失败：官方文件结构可能已变化，请手动检查')

    if changed:
        open(TARGET, 'w', encoding='utf-8', newline='\n').write(src)
        print('已打补丁:', ', '.join(changed))
    print('\n补丁后可用模型: gpt-4o / gpt-4o-mini / deepseek-chat / deepseek-reasoner / qwen-plus / qwen-max')
    print('\n使用方式（先设环境变量）:')
    print('  $env:JUDGE_BASE_URL="https://api.deepseek.com/v1"')
    print('  $env:JUDGE_API_KEY="sk-..."')
    print('  python third_party/LongMemEval/src/evaluation/evaluate_qa.py deepseek-chat '
          'results/01_fullctx.jsonl data/longmemeval_oracle.json')


if __name__ == '__main__':
    main()

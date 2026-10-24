# -*- coding: utf-8 -*-
"""校验 prompt 与官方模板一致（不调 API）。"""
import json
import sys

sys.path.insert(0, '.')
from src.eval.longmemeval import build_history_full, make_prompt  # noqa: E402

REFUSAL = "I don't know"

data = json.load(open('data/longmemeval_oracle.json', encoding='utf-8'))
inst = data[0]
h, ns, nt = build_history_full(inst)
p = make_prompt(inst, h, cot=False)

print('=' * 80)
print('历史片段（前 500 字符）')
print('=' * 80)
print(repr(h[:500]))
print(f'\n会话数 {ns}  轮数 {nt}  字符 {len(h)}')

print()
print('=' * 80)
print('Prompt 开头 380 字符')
print('=' * 80)
print(repr(p[:380]))

print()
print('=' * 80)
print('Prompt 结尾 260 字符')
print('=' * 80)
print(repr(p[-260:]))

print()
print('=' * 80)
print('与官方口径一致性断言')
print('=' * 80)
checks = [
    ('开头与官方模板逐字一致',
     p.startswith('I will give you several history chats between you and a user. '
                  'Please answer the question based on the relevant chat history.'
                  '\n\n\nHistory Chats:\n\n')),
    ('含 Current Date 段', '\n\nCurrent Date: ' in p),
    ('以 Answer: 结尾', p.rstrip().endswith('Answer:')),
    ('无 system 提示', 'You are a helpful assistant' not in p),
    ('无拒答指令', REFUSAL not in p),
    ('含 Session 分段', '### Session 1:' in h),
    ('历史用 role: 格式', '\n\nuser: ' in h or '\n\nassistant: ' in h),
]
for name, ok in checks:
    print(f'  [{"OK" if ok else "FAIL"}] {name}')

# CoT 版本
pc = make_prompt(inst, h, cot=True)
print()
print('  CoT 版本结尾:', repr(pc[-60:]))
print('  [%s] CoT 以 step by step 结尾' %
      ('OK' if pc.rstrip().endswith('Answer (step by step):') else 'FAIL'))

ok_all = all(ok for _, ok in checks) and pc.rstrip().endswith('Answer (step by step):')
print()
print('总体:', '全部通过 ✅' if ok_all else '存在不一致 ❌')

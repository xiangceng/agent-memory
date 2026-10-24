# -*- coding: utf-8 -*-
"""基础健全性测试：不联网、不花钱，只验证代码与配置结构。

运行：
    python -m pytest tests -v
"""
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.eval.longmemeval import (  # noqa: E402
    build_history_full, build_history_window, make_prompt, is_abs,
    PROMPT_NOCOT, PROMPT_COT,
)


# ---------------------------------------------------------------- 配置

def test_env_example_exists():
    """配置模板必须存在，且包含关键字段。"""
    p = os.path.join(ROOT, '.env.example')
    assert os.path.exists(p), '.env.example 缺失'
    text = open(p, encoding='utf-8').read()
    for key in ['LLM_API_KEY', 'LLM_BASE_URL', 'LLM_MODEL', 'JUDGE_MODEL']:
        assert key in text, f'.env.example 缺少 {key}'


def test_gitignore_covers_sensitive():
    """.gitignore 必须覆盖密钥与大数据目录。"""
    p = os.path.join(ROOT, '.gitignore')
    text = open(p, encoding='utf-8').read()
    for pat in ['.env', 'data/', '.venv']:
        assert pat in text, f'.gitignore 未忽略 {pat}'


# ---------------------------------------------------------------- 历史拼接

def test_build_history_handles_empty():
    """空会话不应抛异常。"""
    text, n_sess, n_turns = build_history_full({'haystack_sessions': [], 'haystack_dates': []})
    assert text == '' and n_sess == 0 and n_turns == 0


def test_build_history_official_format():
    """历史格式必须与官方一致：### Session / Session Date / Session Content / role: content。"""
    inst = {
        'haystack_sessions': [
            [{'role': 'user', 'content': 'I live in Guangzhou'},
             {'role': 'assistant', 'content': 'Noted.'}],
        ],
        'haystack_dates': ['2026-03-05'],
    }
    text, n_sess, n_turns = build_history_full(inst)
    assert n_sess == 1 and n_turns == 2
    assert '### Session 1:' in text
    assert 'Session Date: 2026-03-05' in text
    assert 'Session Content:' in text
    assert '\n\nuser: I live in Guangzhou' in text
    assert '\n\nassistant: Noted.' in text
    # 不应出现旧版自定义格式
    assert '[user]' not in text


def test_build_history_window_keeps_last_k():
    """窗口基线只保留最近 k 轮。"""
    inst = {
        'haystack_sessions': [
            [{'role': 'user', 'content': f'msg{i}'} for i in range(10)],
            [{'role': 'user', 'content': f'msg{i}'} for i in range(10, 20)],
        ],
        'haystack_dates': ['2026-01-01', '2026-02-01'],
    }
    text, n_sess, n_turns = build_history_window(inst, 5)
    assert n_turns == 5
    assert 'msg19' in text
    assert 'msg15' in text
    assert 'msg14' not in text   # 被窗口截掉
    assert 'msg0' not in text


# ---------------------------------------------------------------- Prompt 口径

def test_prompt_matches_official():
    """prompt 必须与官方模板一致：无 system 文案、无拒答指令、以 Answer: 结尾。"""
    inst = {'question': 'Q?', 'question_date': '2026-01-01'}
    p = make_prompt(inst, 'HISTORY', cot=False)
    assert p.startswith('I will give you several history chats between you and a user. '
                        'Please answer the question based on the relevant chat history.')
    assert '\n\n\nHistory Chats:\n\nHISTORY\n\nCurrent Date: 2026-01-01\nQuestion: Q?\nAnswer:' in p
    assert p.rstrip().endswith('Answer:')
    assert "I don't know" not in p
    assert 'You are a helpful assistant' not in p


def test_prompt_cot_variant():
    """CoT 版本结尾应为 Answer (step by step):。"""
    p = make_prompt({'question': 'Q?', 'question_date': 'D'}, 'H', cot=True)
    assert p.rstrip().endswith('Answer (step by step):')
    assert 'step by step' in p


def test_prompt_templates_have_three_placeholders():
    """两个模板都必须恰好有 3 个占位符（history / date / question）。"""
    for tpl in (PROMPT_NOCOT, PROMPT_COT):
        assert tpl.count('{}') == 3


def test_is_abs():
    """弃答题用 _abs 标记。"""
    assert is_abs('0a995998_abs')
    assert not is_abs('0a995998')


# ---------------------------------------------------------------- 数据

def test_data_optional_but_valid_if_present():
    """数据若已下载，应能被解析且字段齐全（未下载则跳过）。"""
    p = os.path.join(ROOT, 'data', 'longmemeval_oracle.json')
    if not os.path.exists(p):
        pytest.skip('数据未下载，跳过')
    data = json.load(open(p, encoding='utf-8'))
    assert len(data) == 500
    need = {'question_id', 'question_type', 'question', 'answer',
            'question_date', 'haystack_sessions', 'haystack_dates', 'answer_session_ids'}
    assert need.issubset(data[0].keys()), f'缺少字段: {need - set(data[0].keys())}'
    n_abs = sum(1 for x in data if is_abs(x['question_id']))
    assert n_abs == 30, f'弃答题数量应为 30，实际 {n_abs}'

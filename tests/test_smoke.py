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
sys.path.insert(0, os.path.join(ROOT, 'experiments'))


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


def test_build_history_handles_empty():
    """history 拼接函数应能处理空会话，不抛异常。"""
    from importlib import import_module
    mod = import_module('01_baseline_full_context')
    text, n_sess, n_turns = mod.build_history({'haystack_sessions': [], 'haystack_dates': []})
    assert text == '' and n_sess == 0 and n_turns == 0


def test_build_history_formats_sessions():
    """history 应包含会话分隔、日期、角色标记。"""
    from importlib import import_module
    mod = import_module('01_baseline_full_context')
    inst = {
        'haystack_sessions': [
            [{'role': 'user', 'content': 'I live in Guangzhou'},
             {'role': 'assistant', 'content': 'Noted.'}],
        ],
        'haystack_dates': ['2026-03-05'],
    }
    text, n_sess, n_turns = mod.build_history(inst)
    assert n_sess == 1 and n_turns == 2
    assert '2026-03-05' in text
    assert '[user]' in text and '[assistant]' in text
    assert 'Guangzhou' in text


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

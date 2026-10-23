# -*- coding: utf-8 -*-
"""记忆机制内核（本项目核心，独立于 Web 层，可单独测试与评测）。

规划模块（对应开题报告"研究的主要内容"）：

- types.py        记忆条目数据结构（含 superseded_by 指针、槽位基数属性）
- working.py      工作记忆
- episodic.py     情景记忆
- semantic.py     语义记忆（槽位—值，单值/多值）
- procedural.py   程序记忆
- gate.py         三级写入门控（创新点 1）
- conflict.py     六类冲突分类学 + 分层消解（创新点 2）
- compressor.py   分层混合粒度上下文治理 + 实体保留检查（创新点 3）
- retriever.py    混合检索与融合打分
- lifecycle.py    遗忘与生命周期管理

实现时间表见 README。
"""

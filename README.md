# Agent Memory · 面向长期交互的智能体记忆系统

> 本科毕业设计 · 华南师范大学 计算机学院
> 题目：**面向长期交互的智能体记忆写入门控与冲突消解系统设计与实现**

[![Python](https://img.shields.io/badge/python-3.9%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Status](https://img.shields.io/badge/status-WIP-orange)]()

---

## 这个项目解决什么问题

大模型对话助手有个通病：**记不住你**。你在上一次会话说过的职业、偏好、长期目标，下一次它就忘了；即使记住了，当你改口（"我搬到深圳了"）时，系统也不知道该信哪一条。

学术界把这个短板量化了：LongMemEval（ICLR 2025）发现商用助手在持续交互中记忆准确率**下降约 30%**，其中 **knowledge-update**（知识更新）一项最弱；MemoryAgentBench（ICLR 2026）进一步显示，**22 个系统在多跳冲突任务上的准确率均不高于 7%**。

本项目针对这个问题的三个具体缺口：

| 缺口 | 现有方案的问题 | 本项目的工作 |
|---|---|---|
| **不知道该记什么** | 要么全量写入（贵、噪声大），要么每次判定都调模型，或依赖反馈闭环 | **三级成本递增写入门控**，前两级零模型调用 |
| **记了矛盾的信息** | 确定性规则只适用"带显式版本标记的当前值冲突" | **分层冲突消解**：规则优先 + 语义加权兜底 + 多值合法判别 |
| **压缩会丢语义** | 结构性裁剪不评估语义重要性；压成孤立事实又损害性能 | **分层混合粒度治理**：结构裁剪 / 轮次保留 / 槽位抽取三层并存 |

---

## 当前进度

| 阶段 | 时间 | 状态 |
|---|---|---|
| 开题答辩 | 2026.10 | ✅ 通过 |
| **评测链路 + 基线数据** | **2026.10–11** | **🟡 进行中** |
| 分层记忆 + 三级写入门控 | 2026.11–12 | ⬜ |
| 冲突消解 + 自建数据集 | 2026.12–2027.01 | ⬜ |
| 上下文治理 + 系统实现 | 2027.01–02 | ⬜ |
| 完整实验 + 论文 | 2027.03 | ⬜ |

> ⚠️ 项目处于早期阶段，仅"评测链路"可用，其余模块在 `src/` 下留有接口规划。

---

## 已完成的实验

**冒烟测试**（2026-10-17）：`LongMemEval-oracle` 子集，5 题，`deepseek-chat`，temperature=0

| 指标 | 值 |
|---|---|
| 成功 / 失败 | 5 / 0 |
| 平均 token | 7,058 / 题 |
| 平均耗时 | 1,060 ms / 题 |
| 回答正确 | 5 / 5（人工核对） |

详见 [`docs/实验记录.md`](docs/实验记录.md)。

---

## 目录结构

```
agent-memory/
├── README.md
├── LICENSE
├── Makefile                       常用命令
├── requirements.txt               完整依赖（锁定版本）
├── requirements-lite.txt          最小依赖
├── .env.example                   配置模板
├── configs/
│   └── experiment.yaml            实验配置（含三项机制参数占位）
├── data/                          数据集（gitignore）
├── docs/
│   ├── 进度日志.md                 每天做了什么
│   ├── 实验记录.md                 每个实验的结果与结论
│   ├── 两周执行清单.md             阶段任务拆解
│   └── 数据说明.md                 数据体积、题型分布、预算估算
├── experiments/
│   └── 01_baseline_full_context.py  B1 全量上下文基线
├── results/                       实验结果（入库，便于追溯）
├── scripts/
│   └── prepare_data.py            数据下载 + 校验（镜像优先）
├── src/
│   ├── memory/                    记忆机制内核（核心）
│   ├── baselines/                 对照基线
│   └── eval/                      评测封装
└── tests/
```

---

## 快速开始

### 1. 环境

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. 配置

```bash
cp .env.example .env
# 编辑 .env，填入 LLM_API_KEY（默认 DeepSeek，任何 OpenAI 兼容端点均可）
```

### 3. 数据

```bash
python scripts/prepare_data.py
```

> 脚本会自动选择可用下载源（国内优先 `hf-mirror.com`，直连 HuggingFace 常超时）。
> 默认只下 `oracle`（14.7 MB）与 `S`（264.5 MB），`M`（2.6 GB）需加 `--with-m`。

### 4. 跑基线

```bash
# 冒烟（5 题，几乎不花钱）
python experiments/01_baseline_full_context.py --subset 5

# 50 题
python experiments/01_baseline_full_context.py --subset 50
```

输出：

- `results/01_fullctx.jsonl` —— 每行 `{"question_id", "hypothesis"}`
- `results/01_fullctx_usage.csv` —— 每题 token 与耗时

---

## 数据与预算

| 数据设置 | 平均历史 | 估算 prompt | 50 题 | 500 题 |
|---|---|---|---|---|
| `oracle` | 1.9 会话 / 22 轮 | **≈6,600 tokens/题** | 0.3 M | 3.3 M |
| `S` | 47.7 会话 / 494 轮 | **≈122,000 tokens/题** | 6.1 M | **61.2 M** |

**oracle 比 S 便宜约 20 倍**，适合写代码、调试、冒烟；主实验才用 S。

---

## 设计原则

1. **同预算对比** —— 所有方法在相同模型调用预算下评测，避免"多花钱换效果"
2. **评测不自己写** —— 判分一律用官方脚本，防止自造标准
3. **判分模型固定** —— 一经确定全程不换，否则历史结果不可比
4. **机制内核与 Web 解耦** —— `src/memory/` 可单独测试与评测，不依赖服务层

---

## 参考文献

本项目相关工作详见论文。核心对照工作：

- **LongMemEval**（ICLR 2025）—— 主评测基准
- **MemoryAgentBench**（ICLR 2026）—— 冲突消解评测
- **Mem0** / **MemGPT** —— 工业界与学术界的代表性记忆系统
- **AdaMem**（2026）—— 写入控制
- **Reliable Post-Retrieval Assembly for Agent Memory**（2026）—— 确定性冲突消解

---

## License

[MIT](LICENSE)

# agent-memory

> 面向长期交互的智能体记忆系统 —— 本科毕业设计
> 华南师范大学 计算机学院 · 曾翔 · 指导教师：柳薇

## 题目

**面向长期交互的智能体记忆写入门控与冲突消解系统设计与实现**

## 当前阶段

| 阶段 | 时间 | 状态 |
|---|---|---|
| 开题 | 2026.10 | ✅ 已提交 |
| **跑通评测 + 基线数据** | **2026.10–11** | **🔴 进行中（当前）** |
| 分层记忆 + 三级写入门控 | 2026.11–12 | ⬜ |
| 冲突消解 + 自建数据集 | 2026.12–2027.01 | ⬜ |
| 上下文治理 + 系统实现 | 2027.01–02 | ⬜ 2 月底前系统完成 |
| 完整实验 + 论文 | 2027.03 | ⬜ 3 月底前论文定稿 |

## 三项核心机制

1. **三级成本递增的写入门控**：向量新颖度过滤 → 规则过滤 → 信息增益打分（前两级零模型调用）
2. **分层冲突消解**：确定性规则（当前值类）+ 语义加权（软性表达/多值并存/来源冲突）+ 六类冲突分类学
3. **分层混合粒度上下文治理**：结构性冗余无损裁剪 + 轮次级保留 + 事实性槽位抽取

## 评测基准

- **主基准**：LongMemEval（ICLR 2025）—— 五类记忆能力分项
  - 官方仓库：https://github.com/xiaowu0162/LongMemEval
  - 数据：https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned
- 补充：MemoryAgentBench（ICLR 2026）、LoCoMo、自建冲突数据集（约 150 条）

## 目录结构

```
agent-memory/
├── README.md
├── requirements-lite.txt      # 只跑评测所需的最小依赖
├── .env.example               # API 配置模板（复制为 .env）
├── data/                      # LongMemEval 数据（不入库）
├── configs/                   # 实验配置
├── src/
│   ├── memory/                # 记忆机制内核（本项目核心）
│   ├── baselines/             # 基线方法
│   └── eval/                  # 评测封装
├── experiments/               # 实验脚本（一个实验一个文件）
├── results/                   # 原始结果（入库，便于追溯）
├── scripts/                   # 环境/数据准备脚本
└── docs/                      # 执行清单、实验记录、笔记
```

## 环境

```powershell
# 1. 创建虚拟环境（推荐 conda，与官方一致用 Python 3.9）
conda create -n longmemeval-lite python=3.9 -y
conda activate longmemeval-lite

# 2. 安装依赖
pip install -r requirements-lite.txt

# 3. 配置 API
copy .env.example .env
# 然后编辑 .env 填入 key

# 4. 下载数据
powershell -ExecutionPolicy Bypass -File scripts/download_data.ps1
```

## 重要说明

- 本仓库**不包含** LongMemEval 官方代码，按需 clone 到 `third_party/`（见 `docs/两周执行清单.md`）
- `data/` 与 `third_party/` 均不入库（见 `.gitignore`）
- 所有实验必须在**相同模型调用预算**下对比，否则结论无效

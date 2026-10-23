# results

**本目录要入库（git 提交）**，便于追溯每一次实验的数字。

## 命名规范

```
{序号}_{方法}_{设置}.jsonl          # 生成的 hypothesis，交官方脚本判分
{序号}_{方法}_{设置}.jsonl.log      # 官方 evaluate_qa.py 的输出
{序号}_{方法}_{设置}_usage.csv      # 每题 token / 耗时 / 调用次数
```

## 当前清单

| 文件 | 方法 | 设置 | 题数 | 状态 |
|---|---|---|---|---|
| `01_fullctx.jsonl` | B1 全量上下文 | oracle | 待跑 | ⬜ |
| `02_sliding_k10.jsonl` | B2 滑动窗口 | K=10 | 待跑 | ⬜ |
| `02_sliding_k20.jsonl` | B2 滑动窗口 | K=20 | 待跑 | ⬜ |
| `03_naive_rag_k5.jsonl` | B3 朴素 RAG | K=5 | 待跑 | ⬜ |
| `03_naive_rag_k10.jsonl` | B3 朴素 RAG | K=10 | 待跑 | ⬜ |

## 规则

1. **同一个对比表里的所有数字，必须用同一个判分模型**——换判分模型则历史结果不可比
2. 每次跑完立刻把数字抄进 `docs/实验记录.md`
3. 不要手改 jsonl 文件；发现问题重跑
4. 大文件（.log 超过 50 MB）加进 `.gitignore`，只保留汇总指标

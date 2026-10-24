# 常用命令（Windows 用户若不装 make，可直接复制下面对应命令）
.PHONY: help setup data smoke run50 test clean commit

help:
	@echo "make setup   安装依赖"
	@echo "make data    下载 LongMemEval 数据"
	@echo "make smoke   跑 5 题冒烟测试"
	@echo "make run50   跑 50 题基线"
	@echo "make test    运行测试"
	@echo "make clean   清理缓存"

setup:
	python -m venv .venv
	.venv/bin/pip install -r requirements.txt

data:
	python scripts/prepare_data.py

smoke:
	python experiments/01_baseline_full_context.py --subset 5

run50:
	python experiments/01_baseline_full_context.py --subset 50

test:
	python -m pytest tests -v

clean:
	rm -rf **/__pycache__ .pytest_cache

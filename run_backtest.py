#!/usr/bin/env python3
"""
离线回测入口脚本：使用 BacktestEngine 对指定策略做绩效计算。

用法示例:
  python run_backtest.py
  python run_backtest.py --strategy_id my_strategy --start 2024-01-01 --end 2024-12-31 --granularity 1d
  python run_backtest.py --strategy_id my_strategy --data_csv strategy_returns.csv
"""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.backtest_engine import BacktestEngine


def _generate_demo_returns(start_date: str, end_date: str, granularity: str, *, seed: int = 42):
    """生成演示用策略与基准收益序列。"""
    freq = "1D" if granularity == "1d" else "1min" if granularity == "1m" else "1s"
    idx = pd.date_range(start=start_date, end=end_date, freq=freq)
    if len(idx) == 0:
        idx = pd.date_range(start=start_date, periods=252, freq="1D")
    rng = __import__("numpy").random.default_rng(seed)
    strategy = pd.Series(0.0005 + 0.01 * rng.standard_normal(len(idx)), index=idx)
    benchmark = pd.Series(0.0003 + 0.008 * rng.standard_normal(len(idx)), index=idx)
    return strategy, benchmark


def _load_returns_from_csv(path: str, strategy_col="strategy_return", benchmark_col="benchmark_return", date_col="date"):
    df = pd.read_csv(path)
    if date_col in df.columns:
        df[date_col] = pd.to_datetime(df[date_col])
        df = df.set_index(date_col)
    return df[strategy_col], df[benchmark_col]


def main():
    parser = argparse.ArgumentParser(description="Web3 策略离线回测")
    parser.add_argument("--strategy_id", type=str, default="demo_strategy")
    parser.add_argument("--start", type=str, default="2024-01-01")
    parser.add_argument("--end", type=str, default="2024-12-31")
    parser.add_argument("--granularity", type=str, choices=["1d", "1m", "tick"], default="1d")
    parser.add_argument("--data_csv", type=str, default=None, help="策略/基准收益 CSV 路径")
    parser.add_argument("--strategy_col", type=str, default="strategy_return")
    parser.add_argument("--benchmark_col", type=str, default="benchmark_return")
    parser.add_argument("--date_col", type=str, default="date")
    parser.add_argument("--output", type=str, default=None, help="指标 JSON 输出路径")
    args = parser.parse_args()

    engine = BacktestEngine(
        strategy_id=args.strategy_id,
        start_date=args.start,
        end_date=args.end,
        granularity=args.granularity,
    )

    if args.data_csv and Path(args.data_csv).exists():
        sr, br = _load_returns_from_csv(
            args.data_csv,
            strategy_col=args.strategy_col,
            benchmark_col=args.benchmark_col,
            date_col=args.date_col,
        )
        engine.load_data(sr, br)
        print(f"📂 已从 CSV 加载: {args.data_csv}")
    else:
        if args.data_csv:
            print(f"⚠️ 未找到 {args.data_csv}，改用模拟数据")
        sr, br = _generate_demo_returns(args.start, args.end, args.granularity)
        engine.load_data(sr, br)
        print("📊 使用模拟收益序列运行回测")

    metrics = engine.compute_metrics()
    print("\n" + "=" * 50 + "\n回测结果\n" + "=" * 50)
    for k, v in metrics.items():
        print(f"  {k}: {v}")
    print("=" * 50)

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(metrics, f, ensure_ascii=False, indent=2)
        print(f"\n✅ 指标已写入: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

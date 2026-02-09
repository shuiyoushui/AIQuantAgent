#!/usr/bin/env python3
"""
回测入口脚本。

支持两种模式:
1. 事件驱动回测 (--mode event): 从 CSV/API 加载历史 K 线，逐 bar 运行策略
2. 收益序列回测 (--mode returns): 从 CSV 加载 strategy_return/benchmark_return，计算指标

用法:
  # 事件驱动回测（需先准备历史数据）
  python scripts/generate_demo_ohlcv.py --output data/demo_ohlcv.csv
  python run_backtest.py --mode event --data data/demo_ohlcv.csv --symbol BTC

  # 或从 OKX API 获取数据
  python run_backtest.py --mode event --source api --symbol BTC --limit 300

  # 收益序列回测（旧方式）
  python run_backtest.py --mode returns --data_csv path/to/returns.csv
"""
import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))


def run_event_driven_backtest(args) -> int:
    """事件驱动回测：策略 + 历史 K 线"""
    from src.data.historical_loader import load_ohlcv_from_csv, HistoricalDataLoader
    from src.event_driven_backtest import EventDrivenBacktestEngine

    df_ohlcv = None
    if args.source == "csv":
        if not args.data or not Path(args.data).exists():
            print(f"❌ CSV 不存在: {args.data}")
            print("提示: 运行 python scripts/generate_demo_ohlcv.py --output data/demo_ohlcv.csv 生成演示数据")
            return 1
        df_ohlcv = load_ohlcv_from_csv(args.data, date_col=args.date_col, symbol=args.symbol)
    elif args.source == "api":
        loader = HistoricalDataLoader()
        df_ohlcv = loader.load("api", symbol=args.symbol, limit=args.limit)
        if df_ohlcv is None or len(df_ohlcv) == 0:
            print("❌ API 获取数据失败，请检查 OKX 配置")
            return 1
    else:
        print("❌ --source 必须是 csv 或 api")
        return 1

    if len(df_ohlcv) < 50:
        print("❌ 数据不足 50 条，无法回测")
        return 1

    engine = EventDrivenBacktestEngine(strategy_config_path="src/config_strategy.yaml")
    result = engine.run(
        df_ohlcv=df_ohlcv,
        symbol=args.symbol,
        initial_balance=args.initial_balance,
    )

    metrics = result["metrics"]
    print("\n" + "=" * 50 + "\n事件驱动回测结果\n" + "=" * 50)
    for k, v in metrics.items():
        print(f"  {k}: {v}")
    print("=" * 50)
    if result["rejections"]:
        print(f"\n🛡️ 风控拒绝次数: {len(result['rejections'])}")

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(metrics, f, ensure_ascii=False, indent=2)
        print(f"\n✅ 指标已写入: {args.output}")

    # 可选：保存收益序列
    if args.save_returns:
        sr = result["strategy_returns"]
        br = result["benchmark_returns"]
        out = Path(args.save_returns)
        out.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({
            "date": sr.index,
            "strategy_return": sr.values,
            "benchmark_return": br.values,
        }).to_csv(out, index=False)
        print(f"✅ 收益序列已写入: {out}")

    return 0


def run_returns_backtest(args) -> int:
    """收益序列回测（原有逻辑）"""
    from src.backtest_engine import BacktestEngine

    def _load_returns_from_csv(path, strategy_col, benchmark_col, date_col):
        df = pd.read_csv(path)
        if date_col in df.columns:
            df[date_col] = pd.to_datetime(df[date_col])
            df = df.set_index(date_col)
        return df[strategy_col], df[benchmark_col]

    def _generate_demo_returns(start, end, granularity, seed=42):
        freq = "1D" if granularity == "1d" else "1min" if granularity == "1m" else "1s"
        idx = pd.date_range(start=start, end=end, freq=freq)
        if len(idx) == 0:
            idx = pd.date_range(start=start, periods=252, freq="1D")
        rng = __import__("numpy").random.default_rng(seed)
        sr = pd.Series(0.0005 + 0.01 * rng.standard_normal(len(idx)), index=idx)
        br = pd.Series(0.0003 + 0.008 * rng.standard_normal(len(idx)), index=idx)
        return sr, br

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


def main():
    parser = argparse.ArgumentParser(description="量化策略回测")
    parser.add_argument("--mode", type=str, choices=["event", "returns"], default="event",
                        help="event=事件驱动(策略+K线), returns=收益序列")
    parser.add_argument("--data", type=str, default="data/demo_ohlcv.csv", help="事件模式: K线 CSV 路径")
    parser.add_argument("--source", type=str, choices=["csv", "api"], default="csv",
                        help="事件模式: 数据来源")
    parser.add_argument("--symbol", type=str, default="BTC")
    parser.add_argument("--limit", type=int, default=500, help="API 模式 K 线数量")
    parser.add_argument("--date_col", type=str, default=None)
    parser.add_argument("--initial_balance", type=float, default=100000.0,
                        help="事件回测初始资金，需足够大以使仓位通过风控")
    parser.add_argument("--save_returns", type=str, default=None, help="保存收益序列到 CSV")

    # returns 模式参数
    parser.add_argument("--data_csv", type=str, default=None, help="returns 模式: 收益 CSV")
    parser.add_argument("--strategy_id", type=str, default="demo_strategy")
    parser.add_argument("--start", type=str, default="2024-01-01")
    parser.add_argument("--end", type=str, default="2024-12-31")
    parser.add_argument("--granularity", type=str, choices=["1d", "1m", "tick"], default="1d")
    parser.add_argument("--strategy_col", type=str, default="strategy_return")
    parser.add_argument("--benchmark_col", type=str, default="benchmark_return")

    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()

    if args.mode == "event":
        return run_event_driven_backtest(args)
    else:
        return run_returns_backtest(args)


if __name__ == "__main__":
    raise SystemExit(main())

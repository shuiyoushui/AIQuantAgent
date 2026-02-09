#!/usr/bin/env python3
"""
生成演示用 OHLCV 数据（无需 API），供回测测试。

用法:
  python scripts/generate_demo_ohlcv.py --output data/demo_ohlcv.csv --days 365
"""
import argparse
import sys
from pathlib import Path

import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main():
    parser = argparse.ArgumentParser(description="生成演示 OHLCV 数据")
    parser.add_argument("--output", type=str, default="data/demo_ohlcv.csv")
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--freq", type=str, default="1h")
    args = parser.parse_args()

    freq_map = {"1h": "1h", "4h": "4h", "1d": "1D"}
    freq = freq_map.get(args.freq, "1h")
    n = args.days * (24 if freq == "1h" else 6 if freq == "4h" else 1)
    idx = pd.date_range(start="2023-01-01", periods=n, freq=freq)
    rng = np.random.default_rng(42)
    base = 40000
    ret = 0.0001 + 0.01 * rng.standard_normal(n)
    close = base * np.cumprod(1 + ret)
    high = close * (1 + np.abs(rng.standard_normal(n) * 0.005))
    low = close * (1 - np.abs(rng.standard_normal(n) * 0.005))
    open_ = np.roll(close, 1)
    open_[0] = base
    volume = rng.integers(100, 1000, n)

    df = pd.DataFrame({
        "timestamp": idx,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    })
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"✅ 已生成 {len(df)} 条演示 K 线到 {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

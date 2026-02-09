#!/usr/bin/env python3
"""
下载历史 OHLCV 数据到 CSV，供事件驱动回测使用。

用法:
  python scripts/download_ohlcv.py --symbol BTC --limit 500 --output data/btc_1h.csv
  python scripts/download_ohlcv.py --symbol ETH --limit 1000 --output data/eth_1h.csv
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data_ingestion import DataIngestion
from src.data_processor import DataProcessor


def main():
    parser = argparse.ArgumentParser(description="下载历史 K 线到 CSV")
    parser.add_argument("--symbol", type=str, default="BTC")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--output", type=str, default="data/ohlcv.csv")
    args = parser.parse_args()

    ingestion = DataIngestion()
    raw = ingestion.fetch_raw_market_data(args.symbol, limit=args.limit)
    if not raw:
        print("❌ 获取数据失败，请检查 OKX API 配置")
        return 1

    proc = DataProcessor()
    df = proc.process_market_data(raw)
    if df is None:
        print("❌ 数据处理失败")
        return 1

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    print(f"✅ 已保存 {len(df)} 条 K 线到 {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

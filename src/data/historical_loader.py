"""
历史数据加载器。

职责：从 CSV 或 OKX API 加载历史 OHLCV 数据，供事件驱动回测使用。
"""
import pandas as pd
from pathlib import Path
from typing import Optional, List
from datetime import datetime, timedelta


def load_ohlcv_from_csv(
    path: str,
    date_col: Optional[str] = None,
    symbol: str = "BTC",
) -> pd.DataFrame:
    """
    从 CSV 加载 OHLCV 数据。
    CSV 需包含列: timestamp/date, open, high, low, close, volume
    """
    df = pd.read_csv(path)
    if date_col and date_col in df.columns:
        df["timestamp"] = pd.to_datetime(df[date_col])
    elif "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
    elif "date" in df.columns:
        df["timestamp"] = pd.to_datetime(df["date"])
    else:
        df["timestamp"] = pd.to_datetime(df.iloc[:, 0])
    required = ["open", "high", "low", "close", "volume"]
    for c in required:
        if c not in df.columns:
            raise ValueError(f"CSV 缺少列: {c}")
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


class HistoricalDataLoader:
    """
    历史数据加载器：支持 CSV 和 OKX API。
    """

    def __init__(self, logger=None):
        self.logger = logger

    def load(
        self,
        source: str,
        symbol: str = "BTC",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 500,
        **kwargs,
    ) -> pd.DataFrame:
        """
        加载历史 OHLCV。
        Args:
            source: "csv" 或 "api"
            symbol: 交易对
            start_date, end_date: 日期范围 (api 模式下 limit 优先)
            limit: API 模式下获取的 K 线数量
            kwargs: csv 时传 path=..., date_col=...
        """
        if source.lower() == "csv":
            path = kwargs.get("path")
            if not path or not Path(path).exists():
                raise FileNotFoundError(f"CSV 不存在: {path}")
            return load_ohlcv_from_csv(
                path,
                date_col=kwargs.get("date_col"),
                symbol=symbol,
            )
        elif source.lower() == "api":
            return self._fetch_from_api(symbol, limit=limit)
        else:
            raise ValueError(f"不支持的数据源: {source}")

    def _fetch_from_api(self, symbol: str, limit: int = 500) -> pd.DataFrame:
        """从 OKX API 获取历史 K 线"""
        from src.data_ingestion import DataIngestion

        ingestion = DataIngestion(logger=self.logger)
        raw = ingestion.fetch_raw_market_data(symbol, limit=limit)
        if not raw:
            return pd.DataFrame()
        from src.data_processor import DataProcessor

        proc = DataProcessor(logger=self.logger)
        df = proc.process_market_data(raw)
        return df if df is not None else pd.DataFrame()

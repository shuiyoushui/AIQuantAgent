"""
数据清洗智能体 (Data Cleaning Agent - 中台)

职责：整合 DataIngestion + DataProcessor，输出标准化 MarketData。
无论数据源是 API (CCXT)、CSV 还是爬虫，get_data() 统一返回 MarketData。
"""
import pandas as pd
from datetime import datetime
from typing import Optional, List, Dict, Any

from src.data_ingestion import DataIngestion
from src.data_processor import DataProcessor
from src.models.market_data import MarketData


class DataAgent:
    """统一数据入口：脏数据 -> 标准 MarketData"""

    def __init__(self, logger=None):
        self.logger = logger
        self._ingestion = DataIngestion(logger=logger)
        self._processor = DataProcessor(logger=logger)

    def get_data(
        self,
        symbol: str,
        limit: int = 100,
        csv_df: Optional[pd.DataFrame] = None,
        csv_news: Optional[List[Dict]] = None,
    ) -> Optional[MarketData]:
        """
        统一入口：无论数据来自 API/CSV，均返回 MarketData。

        Args:
            symbol: 交易对符号
            limit: API 模式下获取的 K 线数量
            csv_df: 回测模式下的历史 K 线 DataFrame（可选）
            csv_news: 回测模式下的历史新闻（可选）

        Returns:
            MarketData 或 None
        """
        # 1. 获取原始数据
        if csv_df is not None:
            df_price = self._process_market_from_csv(csv_df)
            raw_news = csv_news or []
            ticker_data = self._build_ticker_from_df(df_price) if df_price is not None else None
        else:
            raw_market = self._ingestion.fetch_raw_market_data(symbol, limit=limit)
            raw_news = self._ingestion.fetch_raw_news(symbol)
            ticker_data = self._ingestion.fetch_raw_ticker_data(symbol)
            df_price = self._processor.process_market_data(raw_market)

        # 2. 清洗新闻并转为标准格式 [{'time': ..., 'content': ...}]
        news_list = self._to_standard_news(raw_news)

        # 3. 异常处理：缺失值填充、极值过滤
        if df_price is not None and len(df_price) > 0:
            df_price = self._fillna_and_filter_outliers(df_price)

        # 4. 构建 metadata
        metadata = self._build_metadata(symbol, ticker_data, df_price)

        return MarketData(
            df_price=df_price if df_price is not None else pd.DataFrame(),
            news_list=news_list,
            metadata=metadata,
        )

    def _to_standard_news(self, raw_news: List[Dict]) -> List[Dict[str, Any]]:
        """清洗并转换为标准格式 [{'time': ..., 'content': ...}]"""
        if not raw_news:
            return []
        cleaned = self._processor.process_news_data(raw_news)
        result = []
        for item in cleaned:
            ts = item.get("timestamp")
            if isinstance(ts, tuple):
                dt = pd.to_datetime(datetime(*ts[:6]))
            elif isinstance(ts, (int, float)):
                dt = pd.to_datetime(ts, unit="s")
            else:
                dt = pd.to_datetime(ts) if ts else None
            content = item.get("cleaned_content", item.get("title", ""))
            result.append({"time": dt, "content": content})
        return result

    def _fillna_and_filter_outliers(self, df: pd.DataFrame) -> pd.DataFrame:
        """缺失值填充 + 极值过滤"""
        df = df.copy()
        df = df.ffill().bfill()
        df = df[df["volume"] > 0]
        df = df[
            (df["high"] >= df["low"])
            & (df["close"] >= df["low"])
            & (df["close"] <= df["high"])
        ]
        return df.reset_index(drop=True)

    def _build_metadata(
        self,
        symbol: str,
        ticker: Optional[Dict],
        df: Optional[pd.DataFrame],
    ) -> Dict[str, Any]:
        metadata = {"symbol": symbol}
        if ticker and "swap" in ticker:
            metadata["funding_rate"] = ticker["swap"].get("funding_rate", 0)
        else:
            metadata["funding_rate"] = 0
        metadata["contract_multiplier"] = 1
        return metadata

    def _process_market_from_csv(self, df: pd.DataFrame) -> Optional[pd.DataFrame]:
        """回测：从 CSV DataFrame 构建标准 df_price"""
        required = ["open", "high", "low", "close", "volume"]
        for c in required:
            if c not in df.columns:
                if self.logger:
                    print(f"   ⚠️ [DataAgent] CSV 缺少列: {c}")
                return None
        df = df.copy()
        if "timestamp" not in df.columns and df.index.name != "timestamp":
            df = df.reset_index()
        col_ts = "timestamp" if "timestamp" in df.columns else df.columns[0]
        df["timestamp"] = pd.to_datetime(df[col_ts])
        if df["timestamp"].dt.tz is None:
            df["timestamp"] = df["timestamp"].dt.tz_localize("UTC", ambiguous="infer")
        return df[["timestamp", "open", "high", "low", "close", "volume"]]

    def _build_ticker_from_df(self, df: pd.DataFrame) -> Dict:
        if df is None or len(df) == 0:
            return {}
        last = df.iloc[-1]
        return {
            "spot": {"price": last["close"]},
            "swap": {"price": last["close"], "funding_rate": 0},
        }

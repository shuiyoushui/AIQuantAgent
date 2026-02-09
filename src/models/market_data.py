"""
标准市场数据结构 (MarketData)。

职责：供 DataAgent 输出、AnalystGroup 和 StrategyAgent 消费的统一数据格式。
无论数据源是 API (CCXT)、CSV 还是爬虫，均由此结构承载。
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import pandas as pd


@dataclass
class MarketData:
    """
    标准化市场数据结构。
    - df_price: open, high, low, close, volume，时间戳对齐 UTC
    - news_list: 清洗后的新闻 [{'time': ..., 'content': ...}, ...]
    - metadata: 资金费率、合约乘数等元数据
    """
    df_price: pd.DataFrame
    news_list: List[Dict[str, Any]]
    metadata: Dict[str, Any]

    def __post_init__(self):
        if self.df_price is None:
            self.df_price = pd.DataFrame()
        if self.news_list is None:
            self.news_list = []
        if self.metadata is None:
            self.metadata = {}

    @property
    def symbol(self) -> str:
        return self.metadata.get("symbol", "UNKNOWN")

    @property
    def current_price(self) -> float:
        if self.df_price is not None and len(self.df_price) > 0:
            return float(self.df_price.iloc[-1]["close"])
        return 0.0

    @property
    def is_empty(self) -> bool:
        return self.df_price is None or len(self.df_price) == 0

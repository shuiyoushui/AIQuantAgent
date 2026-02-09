"""
多智能体模块 (Multi-Agent Architecture)。

- DataAgent: 数据清洗智能体（中台）
- AnalystGroup: 因子加工智能体组
- StrategyAgent: 策略设计智能体
"""
from .data_agent import DataAgent
from .analysts import (
    BaseAnalyst,
    SentimentAnalyst,
    TechnicalAnalyst,
    FundamentalAnalyst,
    AnalystGroup,
)
from .strategy_agent import StrategyAgent, EventDrivenStrategyAgent

__all__ = [
    "DataAgent",
    "BaseAnalyst",
    "SentimentAnalyst",
    "TechnicalAnalyst",
    "FundamentalAnalyst",
    "AnalystGroup",
    "StrategyAgent",
    "EventDrivenStrategyAgent",
]

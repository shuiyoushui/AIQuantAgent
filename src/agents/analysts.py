"""
因子加工智能体组 (Factor Analyst Agents)

所有分析师由 LLM 驱动，配置见 src/config/agents/*.yaml。
每个 Agent 可配置独立的大模型和提示词。
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import pandas as pd
import numpy as np

from .llm_base import LLMAgentBase


class BaseAnalyst(ABC):
    """因子分析师基类"""

    @abstractmethod
    def produce_factors(self, market_data) -> Dict[str, Any]:
        """输入 MarketData，输出因子字典"""
        pass


class SentimentAnalyst(BaseAnalyst, LLMAgentBase):
    """舆情分析师：由 LLM 根据新闻自主判断情绪，配置见 config/agents/sentiment_analyst.yaml"""

    CONFIG_FILENAME = "sentiment_analyst.yaml"

    def __init__(self, config_path: Optional[str] = None, logger=None, backtest_mode: bool = False):
        BaseAnalyst.__init__(self)
        LLMAgentBase.__init__(self, config_path=config_path, logger=logger, backtest_mode=backtest_mode)

    def produce_factors(self, market_data) -> Dict[str, Any]:
        if self.backtest_mode or self.client is None:
            return {"sentiment_score": 0.0, "hot_topic": "", "confidence": 0.0}
        news_list = getattr(market_data, "news_list", []) or []
        if not news_list:
            return {"sentiment_score": 0.0, "hot_topic": "", "confidence": 0.0}

        news_text = "\n".join(
            f"[{n.get('source', 'news')}] {n.get('content', '')}" for n in news_list
        )
        if len(news_text) < 10:
            return {"sentiment_score": 0.0, "hot_topic": "", "confidence": 0.0}

        instruction = self.config.get("output_format_instruction", "")
        examples = self.config.get("examples", [])
        examples_str = "\n".join(
            f"输入: {ex['input']}\n输出: {ex['output']}" for ex in examples
        )
        symbol = market_data.symbol
        user_prompt = f"{instruction}\n\n【重要】请专注于分析 {symbol} 相关新闻。\n\n参考示例:\n{examples_str}\n\n待分析新闻:\n{news_text}"
        system_prompt = self.config.get("system_prompt", "你是量化分析师，分析新闻情绪并输出 JSON。")

        if self.logger:
            print(f"   🧠 [SentimentAnalyst] 正在分析 {symbol} 新闻...")
        result = self.call_llm(system_prompt, user_prompt)
        if result is None:
            return {"sentiment_score": 0.0, "hot_topic": "", "confidence": 0.0}
        return {
            "sentiment_score": float(result.get("sentiment_score", 0)),
            "hot_topic": str(result.get("summary", result.get("reasoning", "")))[:100],
            "confidence": float(result.get("confidence", 0)),
        }


class TechnicalAnalyst(BaseAnalyst, LLMAgentBase):
    """技术分析师：先计算原始指标，再由 LLM 解读，配置见 config/agents/technical_analyst.yaml"""

    CONFIG_FILENAME = "technical_analyst.yaml"

    def __init__(self, config_path: Optional[str] = None, logger=None, backtest_mode: bool = False,
                 rsi_period: int = 14, macd_fast: int = 12, macd_slow: int = 26):
        BaseAnalyst.__init__(self)
        LLMAgentBase.__init__(self, config_path=config_path, logger=logger, backtest_mode=backtest_mode)
        self.rsi_period = rsi_period
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow

    def _compute_raw_indicators(self, market_data) -> Optional[Dict[str, float]]:
        df = getattr(market_data, "df_price", None)
        if df is None or len(df) < max(self.rsi_period, self.macd_slow) + 5:
            return None
        close = df["close"].astype(float)
        rsi = self._rsi(close, self.rsi_period)
        macd_diff = self._macd_diff(close)
        vol = close.pct_change().rolling(20).std().iloc[-1] if len(close) >= 20 else 0
        return {
            "rsi_14": float(rsi.iloc[-1]) if pd.notna(rsi.iloc[-1]) else 50.0,
            "macd_diff": float(macd_diff.iloc[-1]) if pd.notna(macd_diff.iloc[-1]) else 0.0,
            "volatility": float(vol) if pd.notna(vol) else 0.0,
        }

    def _rsi(self, close: pd.Series, period: int) -> pd.Series:
        delta = close.diff()
        gain = delta.where(delta > 0, 0)
        loss = (-delta).where(delta < 0, 0)
        avg_gain = gain.rolling(period).mean()
        avg_loss = loss.rolling(period).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        return 100 - (100 / (1 + rs))

    def _macd_diff(self, close: pd.Series) -> pd.Series:
        ema_fast = close.ewm(span=self.macd_fast, adjust=False).mean()
        ema_slow = close.ewm(span=self.macd_slow, adjust=False).mean()
        macd = ema_fast - ema_slow
        signal = macd.ewm(span=9, adjust=False).mean()
        return macd - signal

    def produce_factors(self, market_data) -> Dict[str, Any]:
        raw = self._compute_raw_indicators(market_data)
        default = {"rsi_14": 50.0, "macd_diff": 0.0, "volatility": 0.0, "technical_signal": 0.0}
        if raw is None:
            return default

        if self.backtest_mode or self.client is None:
            raw["technical_signal"] = 0.0
            return raw

        system_prompt = self.config.get("system_prompt", "你是技术分析师，解读指标并输出 JSON。")
        instruction = self.config.get("output_format_instruction", "")
        user_prompt = f"{instruction}\n\n当前指标:\n- RSI(14): {raw['rsi_14']:.2f}\n- MACD差值: {raw['macd_diff']:.6f}\n- 波动率: {raw['volatility']:.6f}"

        if self.logger:
            print(f"   🧠 [TechnicalAnalyst] 正在解读技术指标...")
        result = self.call_llm(system_prompt, user_prompt)
        if result is None:
            raw["technical_signal"] = 0.0
            return raw
        raw["technical_signal"] = float(result.get("technical_signal", 0))
        return raw


class FundamentalAnalyst(BaseAnalyst, LLMAgentBase):
    """基本面分析师：由 LLM 根据资金费率等元数据评估，配置见 config/agents/fundamental_analyst.yaml"""

    CONFIG_FILENAME = "fundamental_analyst.yaml"

    def __init__(self, config_path: Optional[str] = None, logger=None, backtest_mode: bool = False):
        BaseAnalyst.__init__(self)
        LLMAgentBase.__init__(self, config_path=config_path, logger=logger, backtest_mode=backtest_mode)

    def produce_factors(self, market_data) -> Dict[str, Any]:
        metadata = getattr(market_data, "metadata", {}) or {}
        fr = metadata.get("funding_rate", 0)
        default = {"funding_rate_factor": float(fr) if isinstance(fr, (int, float)) else 0.0}

        if self.backtest_mode or self.client is None:
            return default

        system_prompt = self.config.get("system_prompt", "你是基本面分析师，评估资金面并输出 JSON。")
        instruction = self.config.get("output_format_instruction", "")
        user_prompt = f"{instruction}\n\n当前数据:\n- 资金费率: {fr}\n- 标的: {market_data.symbol}"

        if self.logger:
            print(f"   🧠 [FundamentalAnalyst] 正在评估资金面...")
        result = self.call_llm(system_prompt, user_prompt)
        if result is None:
            return default
        default["funding_rate_factor"] = float(result.get("funding_rate_factor", default["funding_rate_factor"]))
        return default


class AnalystGroup:
    """因子总线：合并所有分析师输出为 factor_context"""

    def __init__(self, analysts=None, logger=None, backtest_mode: bool = False):
        self.analysts = analysts or [
            SentimentAnalyst(logger=logger, backtest_mode=backtest_mode),
            TechnicalAnalyst(logger=logger, backtest_mode=backtest_mode),
            FundamentalAnalyst(logger=logger, backtest_mode=backtest_mode),
        ]
        self.logger = logger

    def produce_factor_context(self, market_data) -> Dict[str, Any]:
        factor_context = {"symbol": market_data.symbol}
        for a in self.analysts:
            try:
                factors = a.produce_factors(market_data)
                factor_context.update(factors)
            except Exception as e:
                if self.logger:
                    print(f"   ⚠️ [Analyst] {a.__class__.__name__} 异常: {e}")
        return factor_context

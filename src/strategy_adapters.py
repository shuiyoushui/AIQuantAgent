"""
策略适配器模块。

职责：将「接口与主流程不一致」的策略（如 RSI、Hybrid）包装成主流程所需的
generate_trade_decision(ai_signal, market_df, ...) 与 execute(decision) 形式，
并从 config_strategy.yaml 的对应段落读取参数（仓位、止盈止损等）。
"""

import os
from typing import Any, Optional

import yaml


def _load_strategy_config(config_path: Optional[str], section: str) -> dict:
    """从 YAML 中读取指定策略段落，不存在则返回空 dict。"""
    if not config_path or not os.path.exists(config_path):
        return {}
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        return raw.get(section) if isinstance(raw.get(section), dict) else {}
    except Exception:
        return {}


def _position_size(price: float, risk_per_trade: float, stop_loss_pct: float, account_balance: float = 10000) -> float:
    """按风险比例与止损计算仓位数量。"""
    if price <= 0 or stop_loss_pct <= 0:
        return 0
    risk_amount = account_balance * risk_per_trade
    return round(risk_amount / (price * stop_loss_pct), 6)


class RSIStrategyAdapter:
    """
    将 RSI 策略包装成与主流程一致的接口；从 config 的 rsi 段落读取
    rsi_period/oversold/overbought、position_sizing、risk_management。
    """
    def __init__(self, config_path: Optional[str] = None, logger: Optional[Any] = None):
        from src.strategy import RSIStrategy
        self._config = _load_strategy_config(config_path, "rsi")
        pos = self._config.get("position_sizing") or {}
        risk = self._config.get("risk_management") or {}
        self._risk_per_trade = pos.get("risk_per_trade", 0.02)
        self._stop_loss_pct = risk.get("stop_loss_pct", 0.05)
        self._take_profit_pct = risk.get("take_profit_pct", 0.10)
        self._strategy = RSIStrategy(
            period=int(self._config.get("rsi_period", 14)),
            oversold=float(self._config.get("oversold", 30)),
            overbought=float(self._config.get("overbought", 70)),
        )
        self.logger = logger

    def generate_trade_decision(
        self,
        ai_signal: Optional[dict],
        market_df=None,
        ticker_data=None,
        ingestion=None,
    ) -> dict:
        symbol = (ai_signal or {}).get("symbol", "UNKNOWN")
        min_bars = self._strategy.period + 1
        if market_df is None or len(market_df) < min_bars:
            decision = {
                "action": "HOLD",
                "price": 0,
                "quantity": 0,
                "reason": "RSI 策略: K 线数据不足",
                "stop_loss": 0,
                "take_profit": 0,
                "filters_passed": [],
            }
            if self.logger:
                self.logger.log_strategy(symbol, False, None, decision["reason"])
            return decision
        signal = self._strategy.analyze(market_df)
        if not signal:
            decision = {
                "action": "HOLD",
                "price": 0,
                "quantity": 0,
                "reason": "RSI 策略: 无有效信号",
                "stop_loss": 0,
                "take_profit": 0,
                "filters_passed": [],
            }
            if self.logger:
                self.logger.log_strategy(symbol, False, None, decision["reason"])
            return decision
        price = float(signal.get("price", 0) or 0)
        action = signal.get("action", "HOLD")
        reason = signal.get("reason", "")
        stop_loss = price * (1 - self._stop_loss_pct) if action == "BUY" else price * (1 + self._stop_loss_pct)
        take_profit = price * (1 + self._take_profit_pct) if action == "BUY" else price * (1 - self._take_profit_pct)
        quantity = _position_size(price, self._risk_per_trade, self._stop_loss_pct) if action != "HOLD" else 0
        decision = {
            "action": action,
            "price": price,
            "quantity": quantity,
            "reason": reason,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "filters_passed": ["rsi"],
        }
        if self.logger:
            self.logger.log_strategy(
                signal.get("symbol", symbol),
                True,
                {"action": action, "price": price, "reason": reason, "score": signal.get("score", 0), "quantity": quantity, "stop_loss": stop_loss, "take_profit": take_profit},
            )
        return decision

    def execute(self, decision: dict) -> None:
        if decision.get("action") == "HOLD":
            return
        print("   🚀 [策略执行-模拟] RSI 策略 触发信号:", decision.get("action"))
        print("      逻辑依据:", decision.get("reason", ""))
        print("      价格:", decision.get("price", 0))
        print("      ⚠️ 注意: 这是模拟交易，不会消耗真实资金")


class HybridStrategyAdapter:
    """
    混合策略适配器：用主流程的 ai_signal（情绪分、置信度）与 market_df/ticker_data
    做情绪+趋势共振判断，从 config 的 hybrid 段落读取阈值、仓位、止盈止损。
    """
    def __init__(self, config_path: Optional[str] = None, logger: Optional[Any] = None):
        self._config = _load_strategy_config(config_path, "hybrid")
        pos = self._config.get("position_sizing") or {}
        risk = self._config.get("risk_management") or {}
        self._risk_per_trade = pos.get("risk_per_trade", 0.02)
        self._stop_loss_pct = risk.get("stop_loss_pct", 0.05)
        self._take_profit_pct = risk.get("take_profit_pct", 0.10)
        self._long_threshold = float(self._config.get("sentiment_long_threshold", 0.5))
        self._short_threshold = float(self._config.get("sentiment_short_threshold", -0.5))
        self._min_confidence = float(self._config.get("min_confidence", 0.7))
        self.logger = logger

    def _price_change_24h(self, market_df) -> Optional[float]:
        """从 K 线近似 24 周期涨跌幅（如 1h 则 24 根为 24h）。"""
        if market_df is None or len(market_df) < 25:
            return None
        try:
            close = market_df["close"].astype(float)
            return (float(close.iloc[-1]) - float(close.iloc[-25])) / float(close.iloc[-25])
        except Exception:
            return None

    def generate_trade_decision(
        self,
        ai_signal: Optional[dict],
        market_df=None,
        ticker_data=None,
        ingestion=None,
    ) -> dict:
        symbol = (ai_signal or {}).get("symbol", "UNKNOWN")
        decision = {
            "action": "HOLD",
            "price": 0,
            "quantity": 0,
            "reason": "混合策略: 情绪或置信度不足",
            "stop_loss": 0,
            "take_profit": 0,
            "filters_passed": [],
        }
        if ticker_data and (ticker_data.get("spot") or {}).get("price") is not None:
            decision["price"] = float(ticker_data["spot"]["price"])
        elif market_df is not None and len(market_df) > 0:
            decision["price"] = float(market_df.iloc[-1]["close"])

        if not ai_signal or "sentiment_score" not in ai_signal:
            if self.logger:
                self.logger.log_strategy(symbol, False, None, decision["reason"])
            return decision

        score = float(ai_signal.get("sentiment_score", 0))
        confidence = float(ai_signal.get("confidence", 0))
        if confidence < self._min_confidence:
            decision["reason"] = f"混合策略: 置信度 {confidence:.2f} < {self._min_confidence}"
            if self.logger:
                self.logger.log_strategy(symbol, False, None, decision["reason"])
            return decision

        price_change = self._price_change_24h(market_df)
        # 情绪+趋势共振：做多需情绪高且价格在涨，做空需情绪低且价格在跌
        if score >= self._long_threshold:
            if price_change is not None and price_change > 0:
                decision["action"] = "BUY"
                decision["reason"] = f"混合策略: 情绪多 ({score:.2f}) 且趋势向上 ({price_change:.2%})，共振做多"
            else:
                decision["reason"] = f"混合策略: 情绪多 ({score:.2f}) 但趋势未共振，观望"
        elif score <= self._short_threshold:
            if price_change is not None and price_change < 0:
                decision["action"] = "SELL"
                decision["reason"] = f"混合策略: 情绪空 ({score:.2f}) 且趋势向下 ({price_change:.2%})，共振做空"
            else:
                decision["reason"] = f"混合策略: 情绪空 ({score:.2f}) 但趋势未共振，观望"

        decision["filters_passed"] = ["confidence", "hybrid_sentiment_trend"]
        if decision["action"] != "HOLD" and decision["price"] > 0:
            decision["stop_loss"] = decision["price"] * (1 - self._stop_loss_pct) if decision["action"] == "BUY" else decision["price"] * (1 + self._stop_loss_pct)
            decision["take_profit"] = decision["price"] * (1 + self._take_profit_pct) if decision["action"] == "BUY" else decision["price"] * (1 - self._take_profit_pct)
            decision["quantity"] = _position_size(decision["price"], self._risk_per_trade, self._stop_loss_pct)

        if self.logger:
            self.logger.log_strategy(
                symbol,
                True,
                {
                    "action": decision["action"],
                    "sentiment_score": score,
                    "reason": decision["reason"],
                    "price": decision["price"],
                    "quantity": decision["quantity"],
                    "stop_loss": decision["stop_loss"],
                    "take_profit": decision["take_profit"],
                    "filters_passed": decision["filters_passed"],
                },
            )
        return decision

    def execute(self, decision: dict) -> None:
        if decision.get("action") == "HOLD":
            return
        print("   🚀 [策略执行-模拟] 混合策略 触发信号:", decision.get("action"))
        print("      逻辑依据:", decision.get("reason", ""))
        print("      价格:", decision.get("price", 0))
        print("      ⚠️ 注意: 这是模拟交易，不会消耗真实资金")

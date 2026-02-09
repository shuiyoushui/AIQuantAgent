"""
策略设计智能体 (Strategy Agent)

由 LLM 根据完整 factor_context 自主做出交易决策，配置见 config/agents/strategy_agent.yaml。
决策完全由大模型推理得出，不依赖预设阈值规则。
"""
from typing import Dict, Any
from abc import ABC, abstractmethod
import os
import yaml
import json

from .llm_base import LLMAgentBase


class StrategyAgent(ABC):
    """策略智能体基类"""

    @abstractmethod
    def generate_decision(
        self, factor_context: Dict[str, Any], market_data
    ) -> Dict[str, Any]:
        """输入 factor_context + market_data，输出决策"""
        pass


class EventDrivenStrategyAgent(StrategyAgent, LLMAgentBase):
    """事件驱动策略：由 LLM 综合因子后自主决策"""

    CONFIG_FILENAME = "strategy_agent.yaml"

    def __init__(self, config_path: str = None, logger=None, backtest_mode: bool = False):
        StrategyAgent.__init__(self)
        # LLM 配置从 config/agents/strategy_agent.yaml 加载；config_path 仅用于风险/仓位
        LLMAgentBase.__init__(self, config_path=None, logger=logger, backtest_mode=backtest_mode)
        self._risk_config = self._load_risk_config(config_path)

    def _load_risk_config(self, config_path: str = None) -> Dict:
        """加载仓位计算相关配置（price/quantity 由系统计算，决策由 LLM 给出）"""
        default = {"risk_per_trade": 0.02, "stop_loss_pct": 0.05}
        root = LLMAgentBase.CONFIG_DIR.parent.parent  # src/
        paths = [
            config_path,
            "src/config_strategy.yaml",
            str(root / "config_strategy.yaml"),
        ]
        for p in paths:
            if p and os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        raw = yaml.safe_load(f)
                    ed = raw.get("event_driven") or raw
                    ps = ed.get("position_sizing") or {}
                    rm = ed.get("risk_management") or {}
                    default["risk_per_trade"] = ps.get("risk_per_trade", default["risk_per_trade"])
                    default["stop_loss_pct"] = rm.get("stop_loss_pct", default["stop_loss_pct"])
                    break
                except Exception:
                    pass
        return default

    def generate_decision(
        self, factor_context: Dict[str, Any], market_data
    ) -> Dict[str, Any]:
        price = market_data.current_price

        if self.backtest_mode or self.client is None:
            return self._rule_fallback(factor_context, market_data, price)

        system_prompt = self.config.get("system_prompt", "你是策略师，根据因子做交易决策。")
        instruction = self.config.get("output_format_instruction", "")
        fc_str = json.dumps(factor_context, ensure_ascii=False, indent=2)
        user_prompt = f"{instruction}\n\n当前因子报告:\n{fc_str}\n\n当前价格: {price}"

        if self.logger:
            print(f"   🧠 [StrategyAgent] 正在综合因子并决策...")
        result = self.call_llm(system_prompt, user_prompt)
        if result is None:
            return self._rule_fallback(factor_context, market_data, price)

        action = str(result.get("action", "HOLD")).upper()
        if action not in ("BUY", "SELL", "HOLD"):
            action = "HOLD"
        reason = str(result.get("reason", ""))
        conf = float(result.get("confidence", 0))
        qty = self._position_size(price) if action in ("BUY", "SELL") else 0.0

        return {
            "action": action,
            "price": price,
            "quantity": qty,
            "reason": reason,
            "confidence": conf,
        }

    def _rule_fallback(
        self, factor_context: Dict[str, Any], market_data, price: float
    ) -> Dict[str, Any]:
        """回测或无 LLM 时的规则回退（RSI 超买超卖）"""
        rsi = factor_context.get("rsi_14", 50)
        technical_signal = factor_context.get("technical_signal", 0)
        action = "HOLD"
        reason = "观望"
        conf = 0.0
        qty = 0.0
        if rsi < 35 and technical_signal >= 0:
            action, reason = "BUY", f"RSI超卖({rsi:.1f})"
            conf = (35 - rsi) / 35
            qty = self._position_size(price)
        elif rsi > 65 and technical_signal <= 0:
            action, reason = "SELL", f"RSI超买({rsi:.1f})"
            conf = (rsi - 65) / 35
            qty = self._position_size(price)
        return {
            "action": action,
            "price": price,
            "quantity": qty,
            "reason": reason,
            "confidence": conf,
        }

    def _position_size(self, price: float) -> float:
        risk = 10000 * self._risk_config.get("risk_per_trade", 0.02)
        sl = self._risk_config.get("stop_loss_pct", 0.05)
        return round(risk / (price * sl), 6) if price > 0 and sl > 0 else 0

    def execute(self, decision: Dict[str, Any]) -> None:
        """执行决策（模拟模式）"""
        if decision.get("action") == "HOLD":
            return
        print(f"   🚀 [策略执行-模拟] 触发信号: {decision.get('action')}")
        print(f"      逻辑依据: {decision.get('reason', '')}")
        print(f"      价格: {decision.get('price', 0)}")
        print(f"      数量: {decision.get('quantity', 0)}")
        print("      ⚠️ 注意: 这是模拟交易，不会消耗真实资金")

"""
事件驱动回测引擎 (Event-Driven Backtest Engine)

职责：遍历历史 K 线每一行，调用 AnalystGroup -> StrategyAgent -> RiskManager，
更新虚拟账户，记录拒绝事件，产出策略收益序列供 BacktestEngine 计算指标。
"""
from __future__ import annotations

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
from pathlib import Path

from src.models.market_data import MarketData
from src.agents.data_agent import DataAgent
from src.agents.analysts import AnalystGroup
from src.agents.strategy_agent import EventDrivenStrategyAgent
from src.risk_manager import RiskManager


class EventDrivenBacktestEngine:
    """
    事件驱动回测：逐 bar 运行策略，支持风控拦截记录。
    """

    def __init__(
        self,
        data_agent: Optional[DataAgent] = None,
        analyst_group: Optional[AnalystGroup] = None,
        strategy_agent: Optional[EventDrivenStrategyAgent] = None,
        risk_manager: Optional[RiskManager] = None,
        logger=None,
        strategy_config_path: str = "src/config_strategy.yaml",
    ):
        self.data_agent = data_agent or DataAgent(logger=logger)
        self.analyst_group = analyst_group or AnalystGroup(logger=logger, backtest_mode=True)
        self.strategy_agent = strategy_agent or EventDrivenStrategyAgent(
            config_path=strategy_config_path, logger=logger, backtest_mode=True
        )
        self.risk_manager = risk_manager or RiskManager(logger=logger)
        self.logger = logger
        self.rejections: List[Dict[str, Any]] = []
        self.trades: List[Dict[str, Any]] = []

    def run(
        self,
        df_ohlcv: pd.DataFrame,
        symbol: str = "BTC",
        initial_balance: float = 10000.0,
    ) -> Dict[str, Any]:
        """
        在历史 K 线上运行事件驱动回测。
        Args:
            df_ohlcv: 历史 OHLCV DataFrame，列含 timestamp, open, high, low, close, volume
            symbol: 标的
            initial_balance: 初始资金
        Returns:
            {
                "strategy_returns": pd.Series,
                "benchmark_returns": pd.Series,
                "metrics": dict,
                "rejections": list,
                "trades": list,
            }
        """
        self.rejections = []
        self.trades = []

        if df_ohlcv is None or len(df_ohlcv) < 50:
            return self._empty_result(df_ohlcv)

        balance = initial_balance
        position = 0.0  # 持仓数量
        position_value = 0.0
        entry_price = 0.0

        returns_list = []
        benchmark_list = []
        index_list = []

        prev_position_signal = 0  # 上一 bar 的持仓方向，用于计算当期收益
        for i in range(30, len(df_ohlcv)):
            slice_df = df_ohlcv.iloc[: i + 1].copy()
            current_bar = df_ohlcv.iloc[i]
            current_price = float(current_bar["close"])
            ret = float(df_ohlcv["close"].iloc[i] / df_ohlcv["close"].iloc[i - 1] - 1) if i > 0 else 0

            # 1. 构建 MarketData
            market_data = self.data_agent.get_data(symbol, csv_df=slice_df, csv_news=[])

            # 2. 因子
            factor_context = self.analyst_group.produce_factor_context(market_data)

            # 3. 策略决策
            decision = self.strategy_agent.generate_decision(factor_context, market_data)

            # 4. 风控
            account_state = {
                "balance": balance,
                "position": position,
                "current_price": current_price,
                "max_position_pct": self.risk_manager.max_position_pct,
            }
            final_decision, passed, rejection = self.risk_manager.check(decision, account_state)

            if not passed and rejection:
                self.rejections.append({
                    "time": current_bar.get("timestamp", slice_df.index[i]),
                    "reason": rejection,
                    "decision": decision,
                })

            # 5. 策略收益 = 上一期持仓方向 * 当期价格收益（信号滞后一期执行）
            strategy_ret = prev_position_signal * ret

            # 6. 更新持仓方向（风控通过且非 HOLD 时），用于下一 bar
            action = final_decision.get("action", "HOLD")
            if action == "BUY" and passed:
                prev_position_signal = 1
            elif action == "SELL" and passed:
                prev_position_signal = -1
            elif action == "HOLD":
                pass  # 保持 prev_position_signal
            returns_list.append(strategy_ret)
            benchmark_list.append(ret)
            index_list.append(slice_df.index[i] if hasattr(slice_df.index[i], "isoformat") else i)

        strategy_returns = pd.Series(returns_list, index=df_ohlcv.index[30:])
        benchmark_returns = pd.Series(benchmark_list, index=df_ohlcv.index[30:])

        # 与 df 索引对齐
        strategy_returns.index = df_ohlcv.index[30 : 30 + len(strategy_returns)]
        benchmark_returns.index = df_ohlcv.index[30 : 30 + len(benchmark_returns)]

        # 6. 调用 BacktestEngine 计算指标
        from src.backtest_engine import BacktestEngine

        engine = BacktestEngine("event_driven", "2000-01-01", "2030-01-01", "1d")
        engine.load_data(strategy_returns, benchmark_returns)
        metrics = engine.compute_metrics()

        return {
            "strategy_returns": strategy_returns,
            "benchmark_returns": benchmark_returns,
            "metrics": metrics,
            "rejections": self.rejections,
            "trades": self.trades,
        }

    def _empty_result(self, df: Optional[pd.DataFrame]):
        idx = df.index[30:] if df is not None and len(df) >= 30 else []
        return {
            "strategy_returns": pd.Series(dtype=float),
            "benchmark_returns": pd.Series(dtype=float),
            "metrics": {},
            "rejections": [],
            "trades": [],
        }

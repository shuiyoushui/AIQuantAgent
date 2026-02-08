"""
回测引擎模块 (BacktestEngine)。

职责：对给定策略的收益序列与基准做向量化绩效计算，产出年化收益、夏普、最大回撤、
Alpha/Beta、胜率等指标；支持 1d/1m/tick 颗粒度与 strategy_id 标识，供离线回测脚本使用。
"""

from __future__ import annotations

from typing import Literal, Optional

import numpy as np
import pandas as pd


# 颗粒度 -> 每年周期数（用于年化）
# 1d: 365 个交易日/年；1m: 365*24*60 根 K 线/年；tick: 按秒 365*24*3600（可按实际 tick 频率覆盖）
GRANULARITY_ANN_FACTORS: dict[str, float] = {
    "1d": 365.0,
    "1m": 365.0 * 24.0 * 60.0,
    "tick": 365.0 * 24.0 * 3600.0,
}


class BacktestEngine:
    """
    Web3 币圈策略回测引擎。

    通过向量化计算产出收益、风险、回撤、胜率等指标，禁止在核心计算中使用循环。
    """

    def __init__(
        self,
        strategy_id: str,
        start_date: str,
        end_date: str,
        granularity: Literal["1d", "1m", "tick"],
    ) -> None:
        """
        Args:
            strategy_id: 策略唯一标识。
            start_date: 回测开始日期，格式如 'YYYY-MM-DD'。
            end_date: 回测结束日期，格式如 'YYYY-MM-DD'。
            granularity: 数据颗粒度，'1d' | '1m' | 'tick'，用于年化因子。
        """
        self.strategy_id = strategy_id
        self.start_date = start_date
        self.end_date = end_date
        self.granularity = granularity
        self._ann_factor: float = GRANULARITY_ANN_FACTORS.get(
            granularity, GRANULARITY_ANN_FACTORS["1d"]
        )

        # 收益序列：索引为时间，列名在 _load_data 中约定
        self._strategy_returns: Optional[pd.Series] = None
        self._benchmark_returns: Optional[pd.Series] = None

    def _load_data(self) -> tuple[pd.Series, pd.Series]:
        """
        加载策略收益序列与基准（Benchmark）收益序列。

        子类或外部应重写/注入此方法，从数据库或文件中读取数据，
        并按时间索引对齐、填充缺失值后返回。

        Returns:
            strategy_returns: 策略收益序列，索引为 DatetimeIndex。
            benchmark_returns: 基准收益序列，索引与 strategy_returns 对齐。
        """
        # 预留实现：返回空序列或从 self.strategy_id / self.start_date / self.end_date 加载
        empty_idx = pd.DatetimeIndex([], freq="D")
        return (
            pd.Series(dtype=float),
            pd.Series(dtype=float),
        )

    def load_data(self, strategy_returns: pd.Series, benchmark_returns: pd.Series) -> None:
        """
        直接注入已对齐的策略收益与基准收益（供测试或外部流水线使用）。

        Args:
            strategy_returns: 策略收益序列。
            benchmark_returns: 基准收益序列，需与 strategy_returns 索引对齐。
        """
        # 对齐并去除 NaN
        common_idx = strategy_returns.index.union(benchmark_returns.index)
        common_idx = common_idx.drop_duplicates().sort_values()
        self._strategy_returns = strategy_returns.reindex(common_idx).ffill().bfill()
        self._benchmark_returns = benchmark_returns.reindex(common_idx).ffill().bfill()
        valid = self._strategy_returns.notna() & self._benchmark_returns.notna()
        self._strategy_returns = self._strategy_returns.loc[valid]
        self._benchmark_returns = self._benchmark_returns.loc[valid]

    def _ensure_data(self) -> tuple[pd.Series, pd.Series]:
        """若未注入数据则调用 _load_data，并返回对齐后的策略与基准收益。"""
        if self._strategy_returns is None or self._benchmark_returns is None:
            self._strategy_returns, self._benchmark_returns = self._load_data()
        if self._strategy_returns is None or self._benchmark_returns is None:
            raise ValueError("策略或基准收益序列未设置，请实现 _load_data 或调用 load_data")
        return self._strategy_returns, self._benchmark_returns

    def compute_metrics(self) -> dict[str, float | str | int]:
        """
        基于向量化计算回测指标，禁止使用循环。

        Returns:
            包含收益类、风险类、回撤类、胜率类等字段的字典。
        """
        sr, br = self._ensure_data()
        n = len(sr)
        if n == 0:
            return self._empty_metrics()

        ann = self._ann_factor

        # ----- 收益类（向量化） -----
        # 总收益: (1+r1)(1+r2)... - 1
        cum_strategy = (1.0 + sr).cumprod()
        cum_bench = (1.0 + br).cumprod()
        total_return_strategy = float(cum_strategy.iloc[-1] - 1.0)
        total_return_benchmark = float(cum_bench.iloc[-1] - 1.0)
        excess_return_total = total_return_strategy - total_return_benchmark

        # 年化收益: (1+total)^(ann/n) - 1
        ann_return_strategy = float((1.0 + total_return_strategy) ** (ann / n) - 1.0)
        ann_return_benchmark = float((1.0 + total_return_benchmark) ** (ann / n) - 1.0)

        # 超额收益序列（逐期）
        excess_returns = sr - br
        daily_avg_excess = float(excess_returns.mean())

        # ----- 风险类：Alpha / Beta（向量化） -----
        # Beta: 策略对基准的敏感度，回归 R_s = alpha + beta*R_b 中的斜率；
        #       估计式 Beta = Cov(R_s, R_b) / Var(R_b)。
        # Alpha: CAPM 超额收益，无风险利率=0 时 Alpha = E[R_s] - Beta*E[R_b]；
        #        此处用年化收益近似：Alpha_ann = R_s_ann - Beta * R_b_ann。
        cov_sb = float(np.cov(sr.values, br.values)[0, 1])
        var_b = float(np.var(br.values, ddof=0))
        if var_b <= 0:
            beta = 0.0
        else:
            beta = cov_sb / var_b
        alpha = ann_return_strategy - beta * ann_return_benchmark

        # 波动率：std * sqrt(ann)
        vol_strategy = float(sr.std(ddof=0) * np.sqrt(ann))
        vol_benchmark = float(br.std(ddof=0) * np.sqrt(ann))

        # 夏普比率：mean(R)/std(R) * sqrt(ann)，无风险利率=0
        mean_sr = float(sr.mean())
        std_sr = float(sr.std(ddof=0))
        sharpe = (mean_sr / std_sr * np.sqrt(ann)) if std_sr > 0 else 0.0

        # 索提诺：mean(R) / downside_std(R) * sqrt(ann)，downside_std = 仅负收益的标准差
        downside = sr.where(sr < 0)
        downside_std_val = downside.std(ddof=0)
        downside_std = float(downside_std_val) if pd.notna(downside_std_val) and downside_std_val > 0 else 0.0
        sortino = (mean_sr / downside_std * np.sqrt(ann)) if downside_std > 0 else 0.0

        # ----- 回撤类（向量化） -----
        # 策略最大回撤: (cummax - cum) / cummax
        peak = cum_strategy.cummax()
        drawdown_series = (peak - cum_strategy) / peak.replace(0, np.nan)
        max_dd = float(drawdown_series.max())
        # 最大回撤区间：回撤达到最大值时的结束日；向前找峰值日
        if max_dd <= 0:
            max_dd_start, max_dd_end = "", ""
        else:
            end_idx = drawdown_series.idxmax()
            # 区间内峰值 = 到 end_idx 为止的 cummax 首次达到该峰值的时刻
            peak_before = cum_strategy.loc[: end_idx].cummax()
            peak_val = peak_before.iloc[-1]
            start_candidates = peak_before[peak_before >= peak_val * (1 - 1e-9)].index
            start_idx = start_candidates[0] if len(start_candidates) else end_idx
            max_dd_start = str(pd.Timestamp(start_idx).date())
            max_dd_end = str(pd.Timestamp(end_idx).date())

        # 超额收益最大回撤：对超额收益的累计曲线做回撤
        cum_excess = (1.0 + excess_returns).cumprod()
        peak_excess = cum_excess.cummax()
        dd_excess_series = (peak_excess - cum_excess) / peak_excess.replace(0, np.nan)
        max_dd_excess = float(dd_excess_series.max())

        # ----- 胜率类（向量化） -----
        wins = (sr > 0).sum()
        losses = (sr < 0).sum()
        total_trades = wins + losses
        win_rate = float(wins / total_trades) if total_trades > 0 else 0.0

        # 盈亏比：盈利时平均收益 / 亏损时平均亏损（绝对值）
        gains = sr[sr > 0]
        loses = sr[sr < 0]
        avg_gain = float(gains.mean()) if len(gains) > 0 else 0.0
        avg_loss_abs = float((-loses).mean()) if len(loses) > 0 else 1.0
        profit_loss_ratio = (avg_gain / avg_loss_abs) if avg_loss_abs > 0 else 0.0

        # 超额收益日胜率
        excess_wins = (excess_returns > 0).sum()
        excess_total = (excess_returns > 0).sum() + (excess_returns < 0).sum()
        excess_win_rate = float(excess_wins / excess_total) if excess_total > 0 else 0.0

        return {
            # 收益类
            "total_return_strategy": total_return_strategy,
            "annualized_return_strategy": ann_return_strategy,
            "total_return_benchmark": total_return_benchmark,
            "annualized_return_benchmark": ann_return_benchmark,
            "excess_return_total": excess_return_total,
            "daily_avg_excess_return": daily_avg_excess,
            # 风险类
            "alpha": alpha,
            "beta": beta,
            "sharpe_ratio": sharpe,
            "sortino_ratio": sortino,
            "volatility_strategy": vol_strategy,
            "volatility_benchmark": vol_benchmark,
            # 回撤类
            "max_drawdown": max_dd,
            "max_drawdown_start_date": max_dd_start,
            "max_drawdown_end_date": max_dd_end,
            "max_drawdown_excess": max_dd_excess,
            # 胜率类
            "win_rate": win_rate,
            "win_count": int(wins),
            "loss_count": int(losses),
            "profit_loss_ratio": profit_loss_ratio,
            "excess_win_rate": excess_win_rate,
        }

    def _empty_metrics(self) -> dict[str, float | str | int]:
        """无数据时返回的占位指标。"""
        return {
            "total_return_strategy": 0.0,
            "annualized_return_strategy": 0.0,
            "total_return_benchmark": 0.0,
            "annualized_return_benchmark": 0.0,
            "excess_return_total": 0.0,
            "daily_avg_excess_return": 0.0,
            "alpha": 0.0,
            "beta": 0.0,
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0,
            "volatility_strategy": 0.0,
            "volatility_benchmark": 0.0,
            "max_drawdown": 0.0,
            "max_drawdown_start_date": "",
            "max_drawdown_end_date": "",
            "max_drawdown_excess": 0.0,
            "win_rate": 0.0,
            "win_count": 0,
            "loss_count": 0,
            "profit_loss_ratio": 0.0,
            "excess_win_rate": 0.0,
        }

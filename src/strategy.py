"""
单策略实现：RSI 超买超卖。

职责：仅根据 K 线计算 RSI，在超卖(RSI<30)/超买(RSI>70)时给出 BUY/SELL 信号；
不依赖 AI 或新闻。主流程通过 strategy_adapters.RSIStrategyAdapter 使用本策略。
使用纯 pandas 计算 RSI，无 pandas_ta 依赖。
"""

import pandas as pd


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """RSI 指标，纯 pandas 实现。"""
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    return 100 - (100 / (1 + rs))


class RSIStrategy:
    """RSI 超买超卖策略：输入 K 线 DataFrame，输出信号字典。"""

    def __init__(self, period: int = 14, oversold: float = 30, overbought: float = 70):
        self.period = period
        self.oversold = oversold
        self.overbought = overbought

    def analyze(self, df):
        """
        输入: K线 DataFrame
        输出: 信号字典 (Action, Confidence, Reason)
        """
        if df is None or len(df) < self.period + 1:
            return None

        # 1. 计算 RSI（纯 pandas）
        df = df.copy()
        df["rsi"] = _rsi(df["close"], period=self.period)

        current = df.iloc[-1]
        last_rsi = current["rsi"]
        if pd.isna(last_rsi):
            return None
        last_rsi = float(last_rsi)
        price = float(current["close"])

        # 2. 生成信号逻辑（超买超卖阈值从构造参数读）
        signal = {
            "symbol": "BTC/USDT",
            "price": price,
            "action": "HOLD",
            "score": 0.0,
            "reason": f"RSI 中性 {last_rsi:.2f}",
        }

        if last_rsi < self.oversold:
            signal["action"] = "BUY"
            signal["score"] = (self.oversold - last_rsi) / self.oversold
            signal["reason"] = f"RSI 超卖 ({last_rsi:.2f})，存在反弹可能"
        elif last_rsi > self.overbought:
            signal["action"] = "SELL"
            signal["score"] = (last_rsi - self.overbought) / (100 - self.overbought)
            signal["reason"] = f"RSI 超买 ({last_rsi:.2f})，注意回调"

        return signal

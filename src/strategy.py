
#这里是核心逻辑。为了演示，我们写一个简单的 RSI 策略。如果你要接入 AI，就是在这里调用 DeepSeek/ChatGPT 接口

import pandas_ta as ta

class StrategyEngine:
    def analyze(self, df):
        """
        输入: K线 DataFrame
        输出: 信号字典 (Action, Confidence, Reason)
        """
        if df is None or len(df) < 15:
            return None

        # 1. 计算指标 (使用 pandas_ta 库)
        df['rsi'] = ta.rsi(df['close'], length=14)
        
        # 获取最新一行数据
        current = df.iloc[-1]
        last_rsi = current['rsi']
        price = current['close']

        # 2. 生成信号逻辑 (简单的超买超卖策略)
        signal = {
            "symbol": "BTC/USDT",
            "price": price,
            "action": "HOLD",
            "score": 0.0,
            "reason": f"RSI is neutral at {last_rsi:.2f}"
        }

        # RSI < 30 -> 买入
        if last_rsi < 30:
            signal["action"] = "BUY"
            signal["score"] = (30 - last_rsi) / 30  # 越低分越高
            signal["reason"] = f"RSI 超卖 ({last_rsi:.2f})，存在反弹可能"
        
        # RSI > 70 -> 卖出
        elif last_rsi > 70:
            signal["action"] = "SELL"
            signal["score"] = (last_rsi - 70) / 30
            signal["reason"] = f"RSI 超买 ({last_rsi:.2f})，注意回调"

        return signal

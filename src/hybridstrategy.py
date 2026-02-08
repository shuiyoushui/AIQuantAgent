"""
混合策略模块：新闻情绪 + 交易所价格。

职责：结合新闻/舆情与交易所 ticker 做多空判断（如情绪与涨跌共振才发强信号）；
接口为 run_analysis(symbol)。主流程通过 strategy_adapters.HybridStrategyAdapter 接入时可启用。
"""
import ccxt
import pandas as pd
import time

class HybridStrategy:
    def __init__(self):
        self.news_fetcher = NewsFetcher()
        self.ai_agent = SentimentAgent()
        self.exchange = ccxt.okx() # 以币安为例
        
    def run_analysis(self, symbol="BTC/USDT"):
        print(f"--- 开始分析 {symbol} ---")
        
        # 1. 获取硬数据 (交易所价格)
        ticker = self.exchange.fetch_ticker(symbol)
        current_price = ticker['last']
        price_change_24h = ticker['percentage']
        
        # 2. 获取软数据 (新闻)
        # yfinance 的代码通常是 BTC-USD 格式
        yf_symbol = symbol.replace("/", "-") if "USDT" not in symbol else "BTC-USD"
        news_text = self.news_fetcher.get_crypto_news(yf_symbol)
        
        # 3. AI 大脑处理
        ai_result = self.ai_agent.analyze(news_text)
        sentiment = ai_result.get('sentiment_score', 0)
        confidence = ai_result.get('confidence', 0)
        
        print(f"当前价格: {current_price} (24h涨跌: {price_change_24h}%)")
        print(f"AI 情绪分: {sentiment} (置信度: {confidence})")
        print(f"AI 理由: {ai_result.get('reason')}")
        
        # 4. 融合策略逻辑 (示例)
        # 逻辑：只有当 AI 强烈看多 且 价格确实在涨时，才开多 (趋势共振)
        signal = "HOLD"
        
        if sentiment > 0.5 and confidence > 0.7:
            if price_change_24h > 0:
                signal = "STRONG BUY (情绪+趋势共振)"
            else:
                signal = "WATCH (情绪好但价格跌，留意反转)"
        elif sentiment < -0.5 and confidence > 0.7:
            if price_change_24h < 0:
                signal = "STRONG SELL (恐慌抛售)"
                
        print(f"最终指令: {signal}")
        return signal

# --- 运行入口 ---
if __name__ == "__main__":
    bot = HybridStrategy()
    bot.run_analysis("BTC/USDT")

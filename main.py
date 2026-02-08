import sys  # <--- 必须补上这一行
import argparse
import time
from datetime import datetime
from src.config import Config
from src.data_loader import DataLoader
from src.signal_generator import SignalGenerator
from src.strategy_engine import StrategyEngine
from src.logger import SystemLogger


# 定义颜色代码，让状态一目了然
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

class AIQuantAgent:
    def __init__(self):
        print("🤖 系统初始化...")
        # 初始化日志系统
        self.logger = SystemLogger()
        self.session_id = self.logger.start_session()
        
        # 初始化各个模块，并传入 logger
        self.loader = DataLoader(logger=self.logger)
        self.analyst = SignalGenerator("src/config_signal.yaml", logger=self.logger)
        self.trader = StrategyEngine("src/config_strategy.yaml", logger=self.logger)

    def print_status(self, step_name, is_success, details=""):
        """标准化的状态输出函数"""
        mark = f"{GREEN}✅ 成功{RESET}" if is_success else f"{RED}❌ 失败{RESET}"
        print(f"   [{step_name:<10}] {mark} {details}")

    def analyze_single_asset(self, coin):
        print(f"\n{'-'*20} 🛡️ 深度审计: {coin} {'-'*20}")
        print(f"📋 [日志] 会话ID: {self.session_id}")
        
        # --- 步骤 1: 数据源连接和数据获取 ---
        # 日志会在 data_loader 内部自动记录和输出
        print(f"\n{'='*50}")
        print(f"📊 [步骤1] 数据源连接与数据获取")
        print(f"{'='*50}")
        news_text, source_status = self.loader.fetch_news_context(coin)
        
        if not news_text or "No recent news" in news_text:
            print(f"{RED}⚠️ 严重警告: 所有舆情数据源均失效，跳过此币种分析！{RESET}")
            return

        # --- 步骤 2: AI 信号生成和观点输出 ---
        # 日志会在 signal_generator 内部自动记录和输出
        print(f"\n{'='*50}")
        print(f"🤖 [步骤2] AI 大模型分析")
        print(f"{'='*50}")
        ai_signal = self.analyst.analyze_market_sentiment(coin)
        
        # 检查是否生成了有效的 JSON 对象，且包含必要字段
        is_signal_valid = ai_signal is not None and 'sentiment_score' in ai_signal
        
        if not is_signal_valid:
            print(f"{RED}❌ AI 分析失败，跳过策略生成{RESET}")
            return

        # --- 步骤 3: 策略生成 ---
        # 日志会在 strategy_engine 内部自动记录和输出
        print(f"\n{'='*50}")
        print(f"📈 [步骤3] 策略生成")
        print(f"{'='*50}")
        market_data = self.loader.fetch_deep_market_data(coin)
        is_market_data_valid = market_data is not None
        
        if not is_market_data_valid:
            print(f"{YELLOW}⚠️ 市场数据获取失败，策略可能不完整{RESET}")
        
        # 传递 market_data 和 loader 给策略生成方法，以便获取真实价格和技术指标
        trade_order = self.trader.generate_trade_decision(ai_signal, market_data, self.loader)
        
        print(f"\n{'='*50}")
        print(f"✅ [完成] {coin} 分析完成")
        print(f"{'='*50}\n")

    def run_cycle(self):
        targets = Config.TARGET_COINS
        for coin in targets:
            self.analyze_single_asset(coin)
            time.sleep(1)
    

import argparse

if __name__ == "__main__":
    # 1. 定义命令行参数
    import argparse
    parser = argparse.ArgumentParser(description="AI 量化交易机器人")
    parser.add_argument('--symbol', type=str, default=None, help="指定运行的币种 (例如 BTC/USDT)")
    args = parser.parse_args()

    # 2. 【核心修复】优先级覆盖逻辑
    # 如果命令行输入了 --symbol，则强行覆盖 Config 中的列表
    if args.symbol:
        print(f"🎯 [模式切换] 检测到命令行指定币种: {args.symbol}")
        # 注意：这里我们把单个币种变成一个列表，因为程序后续逻辑是按列表循环的
        # 还要注意：如果 Config 是导入的类，需要直接修改类的属性
        Config.TARGET_COINS = [args.symbol] 
    else:
        print(f"📋 [默认模式] 使用配置文件中的币种列表: {Config.TARGET_COINS}")

    # 3. 初始化并运行
    try:
        bot = AIQuantAgent()
        bot.run_cycle()
    except KeyboardInterrupt:
        print("\n🛑 程序已手动停止")
    except Exception as e:
        print(f"\n❌ 程序崩溃: {e}")
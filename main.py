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
        self.loader = DataLoader()
        self.analyst = SignalGenerator("src/config_signal.yaml")
        self.trader = StrategyEngine("src/config_strategy.yaml")

    def print_status(self, step_name, is_success, details=""):
        """标准化的状态输出函数"""
        mark = f"{GREEN}✅ 成功{RESET}" if is_success else f"{RED}❌ 失败{RESET}"
        print(f"   [{step_name:<10}] {mark} {details}")

    def analyze_single_asset(self, coin):
        print(f"\n{'-'*20} 🛡️ 深度审计: {coin} {'-'*20}")
        
        # --- 步骤 1: 数据源健康检查 ---
        # 注意：这里需要配合修改后的 data_loader 返回 (news_text, status_dict)
        news_text, source_status = self.loader.fetch_news_context(coin)
        
        print(f"1. 数据源连接:")
        self.print_status("Yahoo财经", source_status.get('yahoo', False))
        self.print_status("Google新闻", source_status.get('google', False))
        self.print_status("行业RSS", source_status.get('rss', False))
        
        if not news_text:
            print(f"{RED}⚠️ 严重警告: 所有舆情数据源均失效，跳过此币种分析！{RESET}")
            return

        # --- 步骤 2: AI 信号生成检查 ---
        ai_signal = self.analyst.analyze_market_sentiment(coin)
        # 检查是否生成了有效的 JSON 对象，且包含必要字段
        is_signal_valid = ai_signal is not None and 'sentiment_score' in ai_signal
        
        print(f"2. AI大脑状态:")
        self.print_status("信号生成", is_signal_valid, 
                          f"(分值: {ai_signal.get('sentiment_score', 'N/A')})" if is_signal_valid else "解析失败或拒绝回答")
        
        if not is_signal_valid:
            return

        # --- 步骤 3: 策略引擎检查 ---
        market_data = self.loader.fetch_deep_market_data(coin)
        is_market_data_valid = market_data is not None
        
        trade_order = self.trader.generate_trade_decision(ai_signal)
        is_strategy_valid = trade_order.get('action') != "ERROR" # 假设策略出错会返回 ERROR
        
        print(f"3. 决策执行:")
        self.print_status("行情获取", is_market_data_valid)
        self.print_status("策略计算", is_strategy_valid, f"-> {trade_order.get('action')} @ ${trade_order.get('price', 0)}")

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
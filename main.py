"""
主入口模块。

职责：解析命令行、初始化数据/信号/策略/风控/日志等模块，按配置的「已启用策略」
从策略注册表取当前策略并运行分析循环。策略的启用与注释在 config_strategy.yaml 的 strategies 中配置。
"""
import sys
import argparse
import os
import time
import yaml
from datetime import datetime
from src.config import Config
from src.data_ingestion import DataIngestion
from src.data_processor import DataProcessor
from src.signal_generator import SignalGenerator
from src.strategy_registry import get_strategy, get_enabled_strategy_id
from src.risk_manager import RiskManager
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
        print("\n📦 [初始化] 创建核心模块...")
        self.ingestion = DataIngestion(logger=self.logger)
        self.processor = DataProcessor(logger=self.logger)
        self.analyst = SignalGenerator("src/config_signal.yaml", logger=self.logger)
        # 从配置中取当前启用的策略 ID，从注册表创建策略实例
        strategy_config_path = "src/config_strategy.yaml"
        with open(strategy_config_path, "r", encoding="utf-8") as f:
            strategy_config = yaml.safe_load(f)
        enabled_id = get_enabled_strategy_id(strategy_config)
        if not enabled_id:
            raise ValueError("config_strategy.yaml 中未配置任何 enabled: true 的策略")
        self.trader = get_strategy(enabled_id, config_path=strategy_config_path, logger=self.logger)
        print(f"   ⚙️ [策略] 当前使用策略: {enabled_id}")
        self.risk_manager = RiskManager(logger=self.logger)
        
        print("✅ [初始化] 所有模块初始化完成\n")

    def analyze_single_asset(self, coin):
        """
        分析单个资产（重构后的流程）
        """
        print(f"\n{'-'*20} 🛡️ 深度审计: {coin} {'-'*20}")
        print(f"📋 [日志] 会话ID: {self.session_id}")
        
        # ============================================
        # Step 1: 数据采集 (Data Ingestion)
        # ============================================
        print(f"\n{'='*50}")
        print(f"📊 [Step 1] 数据采集")
        print(f"{'='*50}")
        
        # 采集原始市场数据
        raw_market_data = self.ingestion.fetch_raw_market_data(coin, limit=100)
        if not raw_market_data:
            print(f"{YELLOW}⚠️ [数据采集] 市场数据获取失败，将跳过技术指标分析{RESET}")
        
        # 采集原始新闻数据
        raw_news_list = self.ingestion.fetch_raw_news(coin)
        if not raw_news_list:
            print(f"{RED}⚠️ [数据采集] 所有舆情数据源均失效，跳过此币种分析！{RESET}")
            return
        
        # 采集当前 ticker 数据（用于获取实时价格）
        ticker_data = self.ingestion.fetch_raw_ticker_data(coin)
        
        # ============================================
        # Step 2: 数据清洗 (Data Processing)
        # ============================================
        print(f"\n{'='*50}")
        print(f"🧹 [Step 2] 数据清洗与对齐")
        print(f"{'='*50}")
        
        # 清洗市场数据
        market_df = self.processor.process_market_data(raw_market_data)
        
        # 清洗新闻数据
        cleaned_news_list = self.processor.process_news_data(raw_news_list)
        
        if not cleaned_news_list:
            print(f"{RED}⚠️ [数据清洗] 新闻数据清洗后为空，跳过此币种分析！{RESET}")
            return
        
        # 数据对齐
        aligned_data = self.processor.align_data(market_df, cleaned_news_list)
        
        # ============================================
        # Step 3: AI 分析与信号生成
        # ============================================
        print(f"\n{'='*50}")
        print(f"🤖 [Step 3] AI 大模型分析")
        print(f"{'='*50}")
        
        ai_signal = self.analyst.analyze_market_sentiment(coin, cleaned_news_list)
        
        # 检查是否生成了有效的 JSON 对象，且包含必要字段
        is_signal_valid = ai_signal is not None and 'sentiment_score' in ai_signal
        
        if not is_signal_valid:
            print(f"{RED}❌ [AI分析] AI 分析失败，跳过策略生成{RESET}")
            return
        
        # ============================================
        # Step 4: 策略生成
        # ============================================
        print(f"\n{'='*50}")
        print(f"📈 [Step 4] 策略生成")
        print(f"{'='*50}")
        
        if market_df is None or (hasattr(market_df, 'empty') and market_df.empty):
            print(f"{YELLOW}⚠️ [策略生成] 市场数据缺失，策略可能不完整{RESET}")
        
        # 生成交易决策
        raw_decision = self.trader.generate_trade_decision(
            ai_signal, 
            market_df=market_df,
            ticker_data=ticker_data,
            ingestion=self.ingestion
        )
        
        # ============================================
        # Step 5: 风控检查 (新增)
        # ============================================
        print(f"\n{'='*50}")
        print(f"🛡️ [Step 5] 风控检查")
        print(f"{'='*50}")
        
        # 准备市场数据用于风控检查
        current_market_data = {}
        if ticker_data:
            current_market_data = ticker_data
        elif market_df is not None and not market_df.empty:
            current_market_data = {
                'close': float(market_df.iloc[-1]['close']),
                'timestamp': str(market_df.iloc[-1]['timestamp'])
            } 
            
        # 风控检查
        final_decision, risk_passed = self.risk_manager.check_risk(
            raw_decision,
            current_market_data,
            account_balance=10000.0  # 默认账户余额，实际应该从配置或交易所获取
        )
        
        if not risk_passed:
            print(f"{RED}🚫 [风控] 风控检查未通过，交易被拦截{RESET}")
            print(f"   原因: {final_decision.get('reason', '未知')}")
        
        # ============================================
        # Step 6: 执行决策 (模拟模式)
        # ============================================
        if risk_passed and final_decision.get('action') != 'HOLD':
            print(f"\n{'='*50}")
            print(f"🚀 [Step 6] 执行决策 (模拟模式)")
            print(f"{'='*50}")
            self.trader.execute(final_decision)
        
        print(f"\n{'='*50}")
        print(f"✅ [完成] {coin} 分析完成")
        print(f"{'='*50}\n")

    def run_cycle(self):
        """运行分析循环"""
        targets = Config.TARGET_COINS
        print(f"🎯 [运行] 开始分析币种列表: {targets}\n")
        
        for coin in targets:
            try:
                self.analyze_single_asset(coin)
                time.sleep(1)  # 避免请求过快
            except Exception as e:
                print(f"{RED}❌ [错误] 分析 {coin} 时发生异常: {e}{RESET}")
                continue


if __name__ == "__main__":
    # 1. 定义命令行参数
    parser = argparse.ArgumentParser(description="AI 量化交易机器人")
    parser.add_argument('--symbol', type=str, default=None, help="指定运行的币种 (例如 BTC/USDT)")
    args = parser.parse_args()

    # 2. 优先级覆盖逻辑
    if args.symbol:
        print(f"🎯 [模式切换] 检测到命令行指定币种: {args.symbol}")
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
        import traceback
        traceback.print_exc()

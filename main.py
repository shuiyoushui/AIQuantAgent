"""
主入口模块。

多智能体架构：DataAgent -> AnalystGroup -> StrategyAgent -> RiskManager -> Execution
"""
import sys
import argparse
import time
import yaml
from src.config import Config
from src.logger import SystemLogger

# 多智能体模块
from src.agents import DataAgent, AnalystGroup, EventDrivenStrategyAgent
from src.risk_manager import RiskManager

# 颜色
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"


class AIQuantAgent:
    def __init__(self, use_legacy: bool = False):
        print("🤖 系统初始化...")
        self.logger = SystemLogger()
        self.session_id = self.logger.start_session()
        self.use_legacy = use_legacy

        print("\n📦 [初始化] 创建多智能体模块...")
        self.data_agent = DataAgent(logger=self.logger)
        self.analyst_group = AnalystGroup(logger=self.logger, backtest_mode=False)
        self.strategy_agent = EventDrivenStrategyAgent(
            config_path=None, logger=self.logger, backtest_mode=False
        )
        self.risk_manager = RiskManager(logger=self.logger)
        print("✅ [初始化] 多智能体架构就绪\n")

    def analyze_single_asset(self, coin: str):
        """多智能体分析流程"""
        print(f"\n{'-'*20} 🛡️ 深度审计: {coin} {'-'*20}")
        print(f"📋 [日志] 会话ID: {self.session_id}")

        # Step 1: DataAgent 获取数据
        print(f"\n{'='*50}")
        print("📊 [Step 1] DataAgent 获取数据")
        print(f"{'='*50}")
        market_data = self.data_agent.get_data(coin, limit=100)
        if market_data is None:
            print(f"{RED}❌ [DataAgent] 获取数据失败{RESET}")
            return
        if market_data.is_empty:
            print(f"{YELLOW}⚠️ [DataAgent] 市场数据为空{RESET}")
        if not market_data.news_list:
            print(f"{YELLOW}⚠️ [DataAgent] 新闻数据为空，舆情因子将为中性{RESET}")

        # Step 2: AnalystGroup 生产因子
        print(f"\n{'='*50}")
        print("🔬 [Step 2] AnalystGroup 生产因子")
        print(f"{'='*50}")
        factor_context = self.analyst_group.produce_factor_context(market_data)
        print(f"   因子: sentiment={factor_context.get('sentiment_score', 0):.2f}, "
              f"rsi={factor_context.get('rsi_14', 50):.1f}")

        # Step 3: StrategyAgent 产生决策
        print(f"\n{'='*50}")
        print("📈 [Step 3] StrategyAgent 产生决策")
        print(f"{'='*50}")
        decision = self.strategy_agent.generate_decision(factor_context, market_data)
        print(f"   决策: {decision.get('action')} | {decision.get('reason')}")

        # Step 4: RiskManager 审核
        print(f"\n{'='*50}")
        print("🛡️ [Step 4] RiskManager 审核")
        print(f"{'='*50}")
        account_state = {
            "balance": 10000.0,
            "position": 0,
            "current_price": market_data.current_price,
            "max_position_pct": self.risk_manager.max_position_pct,
        }
        final_decision, passed, rejection = self.risk_manager.check(decision, account_state)

        if not passed and rejection:
            print(f"{RED}🚫 [风控] 交易被拦截: {rejection}{RESET}")

        # Step 5: 执行
        if passed and final_decision.get("action") != "HOLD":
            print(f"\n{'='*50}")
            print("🚀 [Step 5] 执行决策 (模拟模式)")
            print(f"{'='*50}")
            self.strategy_agent.execute(final_decision)

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
                time.sleep(1)
            except Exception as e:
                print(f"{RED}❌ [错误] 分析 {coin} 时发生异常: {e}{RESET}")
                continue


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI 量化交易机器人 (多智能体架构)")
    parser.add_argument("--symbol", type=str, default=None, help="指定币种 (例如 BTC)")
    parser.add_argument("--legacy", action="store_true", help="使用旧版流程 (策略注册表)")
    args = parser.parse_args()

    if args.symbol:
        print(f"🎯 [模式] 指定币种: {args.symbol}")
        Config.TARGET_COINS = [args.symbol]
    else:
        print(f"📋 [模式] 使用配置币种列表: {Config.TARGET_COINS}")

    if args.legacy:
        # 旧版流程（策略注册表）
        from src.data_ingestion import DataIngestion
        from src.data_processor import DataProcessor
        from src.signal_generator import SignalGenerator
        from src.strategy_registry import get_strategy, get_enabled_strategy_id

        with open("src/config_strategy.yaml", "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        enabled_id = get_enabled_strategy_id(cfg)
        if not enabled_id:
            raise ValueError("config_strategy.yaml 中未配置 enabled: true 的策略")
        ingestion = DataIngestion()
        processor = DataProcessor()
        analyst = SignalGenerator("src/config_signal.yaml")
        trader = get_strategy(enabled_id, config_path="src/config_strategy.yaml")
        risk_manager = RiskManager()
        for coin in Config.TARGET_COINS:
            raw_market = ingestion.fetch_raw_market_data(coin, limit=100)
            raw_news = ingestion.fetch_raw_news(coin)
            ticker = ingestion.fetch_raw_ticker_data(coin)
            market_df = processor.process_market_data(raw_market)
            cleaned_news = processor.process_news_data(raw_news)
            if not cleaned_news:
                continue
            ai_signal = analyst.analyze_market_sentiment(coin, cleaned_news)
            if not ai_signal:
                continue
            raw_decision = trader.generate_trade_decision(
                ai_signal, market_df=market_df, ticker_data=ticker, ingestion=ingestion
            )
            cm = ticker or ({"spot": {"price": market_df.iloc[-1]["close"]}} if market_df is not None else {})
            final, passed = risk_manager.check_risk(raw_decision, cm, 10000.0)
            if passed and final.get("action") != "HOLD":
                trader.execute(final)
            time.sleep(1)
    else:
        try:
            bot = AIQuantAgent()
            bot.run_cycle()
        except KeyboardInterrupt:
            print("\n🛑 程序已手动停止")
        except Exception as e:
            print(f"\n❌ 程序崩溃: {e}")
            import traceback
            traceback.print_exc()

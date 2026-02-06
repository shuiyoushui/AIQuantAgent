import ccxt
import time
import os

# 尝试导入配置，防止报错
try:
    from .config import Config
except ImportError:
    class Config:
        USE_MOCK_DATA = True
        OKX_API_KEY = ""
        OKX_SECRET = ""
        OKX_PASSWORD = ""

class StrategyEngine:
    # ✅ 核心修改：增加了 config_path=None 参数
    # 这样 main.py 传入 "src/config_strategy.yaml" 时，这里就能接住了，不会报错
    def __init__(self, config_path=None):
        print(f"   ⚙️ [策略] 初始化策略引擎... (兼容模式，忽略外部配置: {config_path})")
        self.exchange = None
        
        # 如果配置了实盘模式，尝试初始化交易所连接用于下单
        # 注意：这里只用于下单，行情获取在 DataLoader 里
        if not getattr(Config, 'USE_MOCK_DATA', True):
            try:
                # 检查 Config 是否有必要的属性
                api_key = getattr(Config, 'OKX_API_KEY', '')
                secret = getattr(Config, 'OKX_SECRET', '')
                password = getattr(Config, 'OKX_PASSWORD', '')

                if api_key and secret and password:
                    print("   🔗 [策略] 正在建立交易通道 (实盘)...")
                    self.exchange = ccxt.okx({
                        'apiKey': api_key,
                        'secret': secret,
                        'password': password,
                        'options': {'defaultType': 'swap'}
                    })
                else:
                    print("   ⚠️ [策略] 实盘凭证缺失，降级为模拟执行")
            except Exception as e:
                print(f"   ⚠️ [策略] 无法初始化交易接口: {e}")

    def generate_trade_decision(self, ai_signal):
        """
        输入: AI 分析结果 (包含 sentiment_score)
        输出: 具体的买卖指令 (Decision)
        """
        # 1. 初始化默认决策
        decision = {
            "action": "HOLD",
            "price": 0,
            "quantity": 0,
            "reason": "观望: 信号强度不足"
        }

        if not ai_signal or 'sentiment_score' not in ai_signal:
            decision["reason"] = "数据无效: 缺失 AI 信号"
            return decision

        try:
            score = float(ai_signal.get("sentiment_score", 0))
        except:
            score = 0
        
        # 2. 简单的阈值策略逻辑
        # 阈值可以根据回测结果调整，这里设为 0.6 和 -0.6
        if score >= 0.6:
            decision["action"] = "BUY"
            decision["reason"] = f"看涨: 情绪分 {score} > 0.6"
        elif score <= -0.6:
            decision["action"] = "SELL"
            decision["reason"] = f"看跌: 情绪分 {score} < -0.6"
        else:
            decision["reason"] = f"震荡: 情绪分 {score} 处于中性区间"
            
        return decision

    def execute(self, decision):
        """
        【核心修复】执行下单 (目前为模拟模式)
        """
        action = decision.get("action", "HOLD")
        reason = decision.get("reason", "")
        
        # 1. 如果是 HOLD，直接返回
        if action == "HOLD":
            # print("   ✋ [策略] 保持观望") 
            return

        # 2. 模拟下单打印
        print(f"   🚀 [策略执行] 触发信号: {action}")
        print(f"      逻辑依据: {reason}")
        
        # 3. 实盘下单逻辑 (默认注释，确保安全)
        # 警告：取消注释下方代码将消耗真实资金！
        """
        if self.exchange:
            try:
                # 注意：实盘需要动态获取正确的 symbol，这里仅作示例
                # 建议从 decision 中传入 symbol
                symbol = "BTC/USDT:USDT" 
                amount = 0.01 # 下单数量
                side = 'buy' if action == 'BUY' else 'sell'
                
                # order = self.exchange.create_market_order(symbol, side, amount)
                # print(f"   ✅ 实盘下单成功: {order['id']}")
            except Exception as e:
                print(f"   ❌ 实盘下单失败: {e}")
        """
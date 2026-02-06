#负责真正的下单。注意：这里一定要有风控检查！
import ccxt
from .config import Config

class TradeExecutor:
    def __init__(self):
        self.exchange = ccxt.okx({
            'apiKey': Config.OKX_API_KEY,
            'secret': Config.OKX_SECRET,
            'password': Config.OKX_PASSWORD,
            'options': {'defaultType': 'spot'}  # 这里演示现货，合约改为 'swap'
        })

    def check_risk(self, amount):
        """事前风控：检查金额是否过大"""
        if amount > Config.RISK_LIMIT:
            print(f"⚠️ 风控拦截: 下单金额 {amount} 超过限制 {Config.RISK_LIMIT}")
            return False
        return True

    def execute(self, signal):
        """执行下单"""
        if signal['action'] == "HOLD":
            return None

        symbol = signal['symbol']
        side = signal['action'].lower() # 'buy' or 'sell'
        amount = 0.001 # 演示用的固定数量 (BTC)

        if not self.check_risk(amount * signal['price']):
            return {"status": "REJECTED", "reason": "Risk check failed"}

        try:
            # 真实下单 (注意：实盘请谨慎开启！)
            # order = self.exchange.create_market_order(symbol, side, amount)
            
            # 这里先用模拟打印代替
            print(f"🚀 [模拟交易] {side.upper()} {symbol}, 数量: {amount}")
            return {"status": "FILLED", "price": signal['price']}
            
        except Exception as e:
            print(f"❌ 下单失败: {e}")
            return {"status": "ERROR", "reason": str(e)}

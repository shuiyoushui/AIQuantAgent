#这个模块假装去下单，实际上只是打印日志。这能防止你在测试逻辑时意外把钱亏光。
import time

class MockTradeExecutor:
    def __init__(self):
        print("👻 [Mock Mode] 使用模拟交易执行器 (不会消耗真实资金)")

    def execute(self, signal):
        """
        模拟下单过程，始终返回成功
        """
        if signal['action'] == "HOLD":
            return None

        print(f"🔄 [Mock Execution] 正在提交订单: {signal['action']} {signal['symbol']} @ {signal['price']:.2f}")
        
        # 模拟网络延迟
        time.sleep(0.5) 
        
        # 模拟成交结果
        return {
            "status": "FILLED",
            "symbol": signal['symbol'],
            "side": signal['action'],
            "price": signal['price'],
            "amount": 0.001,
            "timestamp": time.time(),
            "info": "This is a mock trade"
        }

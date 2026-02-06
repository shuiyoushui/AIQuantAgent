#这个模块的作用是生成看似真实的 K 线数据（OHLCV），让你的策略引擎有东西可算。
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

class MockDataLoader:
    def __init__(self):
        # 初始化一个起始价格，模拟 BTC
        self.current_price = 60000.0 
        print("👻 [Mock Mode] 使用模拟数据加载器")

    def fetch_market_data(self, symbol="BTC/USDT", limit=100):
        """
        生成 100 条随机漫步的 K 线数据
        """
        data = []
        # 从过去的时间推算
        start_time = datetime.now() - timedelta(hours=limit)
        
        price = self.current_price
        
        for i in range(limit):
            # 随机波动 -0.5% 到 +0.5%
            change_pct = random.uniform(-0.005, 0.005) 
            close_price = price * (1 + change_pct)
            open_price = price
            high_price = max(open_price, close_price) * (1 + random.uniform(0, 0.002))
            low_price = min(open_price, close_price) * (1 - random.uniform(0, 0.002))
            volume = random.uniform(100, 1000)
            
            timestamp = start_time + timedelta(hours=i)
            
            data.append([
                timestamp, 
                open_price, high_price, low_price, close_price, 
                volume
            ])
            
            price = close_price # 下一根K线的基准
            
        # 更新当前价格，制造“实时”感
        self.current_price = price 

        # 转为 DataFrame，格式与真实 CCXT 返回的一致
        df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        return df

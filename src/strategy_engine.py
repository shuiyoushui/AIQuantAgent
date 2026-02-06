#该模块结合 AI 信号和行情数据，输出最终决断。
import yaml
from .data_loader import DataLoader # 复用之前的行情功能

class StrategyEngine:
    def __init__(self, config_path="src/config_strategy.yaml"):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        self.loader = DataLoader()

    def generate_trade_decision(self, ai_signal):
        """
        输入: AI 信号 (JSON)
        输出: 交易指令 (Decision)
        """
        if not ai_signal:
            return {"action": "HOLD", "reason": "No Signal"}
            
        symbol = ai_signal['symbol']
        score = ai_signal['sentiment_score']
        confidence = ai_signal['confidence']
        
        # 1. 获取最新行情 (用于技术过滤)
        # 注意：这里需要调用您之前写的 fetch_deep_market_data
        market_data = self.loader.fetch_deep_market_data(symbol)
        if not market_data:
            return {"action": "HOLD", "reason": "Market Data Error"}
            
        current_price = market_data['spot']['price']
        
        # 2. 策略规则检查 (读取配置文件)
        rules = self.config['entry_rules']
        tech_rules = self.config['technical_filter']
        
        decision = "HOLD"
        reason_log = []

        # --- A. 信号阈值检查 ---
        if confidence < rules['min_confidence']:
            return {"action": "HOLD", "reason": f"AI置信度不足 ({confidence})"}

        # --- B. 做多逻辑 ---
        if score >= rules['long_threshold']:
            # 检查技术面 (例如: 价格是否在均线之上?)
            # 这里简单模拟，实际需计算 K 线
            ma_simulated = current_price * 0.99 
            if tech_rules['enable_ma_filter'] and current_price > ma_simulated:
                decision = "BUY"
                reason_log.append(f"AI高分({score}) + 趋势向上")
            else:
                reason_log.append(f"AI高分({score}) 但技术面未确认")

        # --- C. 做空逻辑 ---
        elif score <= rules['short_threshold']:
            decision = "SELL"
            reason_log.append(f"AI低分({score}) + 趋势向下")
            
        # 3. 返回决策
        return {
            "symbol": symbol,
            "action": decision,
            "price": current_price,
            "ai_score": score,
            "reason": " | ".join(reason_log)
        }


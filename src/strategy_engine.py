import ccxt
import time
import os
import yaml
import pandas as pd
import numpy as np

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
    def __init__(self, config_path=None, logger=None):
        self.logger = logger
        self.exchange = None
        self.config = None
        
        # 加载策略配置文件
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    self.config = yaml.safe_load(f)
                print(f"   ⚙️ [策略] 已加载策略配置: {self.config.get('strategy_name', 'Unknown')}")
            except Exception as e:
                print(f"   ⚠️ [策略] 配置文件加载失败: {e}，使用默认配置")
                self.config = self._get_default_config()
        else:
            print(f"   ⚙️ [策略] 未找到配置文件，使用默认配置")
            self.config = self._get_default_config()
        
        # 确保不进行实盘交易（始终使用模拟模式）
        # 即使配置了实盘模式，也不初始化交易所连接
        print("   🔒 [策略] 策略引擎运行在模拟模式（不进行实盘交易）")
        
    def _get_default_config(self):
        """获取默认策略配置"""
        return {
            'strategy_name': 'Event_Driven_Trend_Following',
            'entry_rules': {
                'long_threshold': 0.6,
                'short_threshold': -0.6,
                'min_confidence': 0.8
            },
            'technical_filter': {
                'enable_ma_filter': True,
                'ma_period': 20
            },
            'position_sizing': {
                'risk_per_trade': 0.02,
                'max_leverage': 1
            },
            'risk_management': {
                'stop_loss_pct': 0.05,
                'take_profit_pct': 0.10
            }
        }

    def _calculate_rsi(self, prices, period=14):
        """
        计算 RSI 指标（相对强弱指数）
        使用 pandas 原生方法实现
        """
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def _calculate_technical_indicators(self, market_data, loader):
        """
        计算技术指标（使用真实数据源）
        返回包含技术指标的字典
        """
        indicators = {}
        
        if not market_data or not loader or not loader.exchange:
            return indicators
        
        try:
            symbol = market_data.get('symbol', 'BTC')
            base_coin = loader._normalize_symbol(symbol)
            target_symbol = f"{base_coin}/USDT:USDT"
            
            # 获取 K 线数据（用于计算技术指标）
            ohlcv = loader.exchange.fetch_ohlcv(target_symbol, timeframe='1h', limit=100)
            if not ohlcv:
                return indicators
            
            # 转换为 DataFrame
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            # 计算移动平均线（MA）- 使用 pandas 原生方法
            ma_period = self.config['technical_filter'].get('ma_period', 20)
            df['ma'] = df['close'].rolling(window=ma_period).mean()
            
            # 获取当前价格和 MA 值
            current_price = df['close'].iloc[-1]
            current_ma = df['ma'].iloc[-1]
            
            indicators['current_price'] = current_price
            indicators['ma'] = current_ma
            indicators['ma_period'] = ma_period
            indicators['price_above_ma'] = current_price > current_ma if pd.notna(current_ma) else None
            
            # 计算 RSI（使用自定义函数）
            df['rsi'] = self._calculate_rsi(df['close'], period=14)
            indicators['rsi'] = df['rsi'].iloc[-1]
            
        except Exception as e:
            if self.logger:
                print(f"   ⚠️ [技术指标] 计算失败: {e}")
        
        return indicators

    def _check_confidence_filter(self, ai_signal):
        """检查置信度过滤器"""
        min_confidence = self.config['entry_rules'].get('min_confidence', 0.8)
        ai_confidence = ai_signal.get('confidence', 0)
        
        if ai_confidence < min_confidence:
            return False, f"置信度 {ai_confidence:.2f} < 最低要求 {min_confidence:.2f}"
        return True, None

    def _check_technical_filter(self, indicators, action):
        """检查技术指标过滤器"""
        if not self.config['technical_filter'].get('enable_ma_filter', True):
            return True, None
        
        if not indicators or 'price_above_ma' not in indicators:
            return False, "无法获取技术指标数据"
        
        price_above_ma = indicators.get('price_above_ma')
        current_price = indicators.get('current_price')
        ma_value = indicators.get('ma')
        
        # 做多时，价格必须在 MA 之上
        if action == "BUY":
            if price_above_ma is None:
                return False, "MA 数据无效"
            if not price_above_ma:
                return False, f"价格 {current_price:.2f} 低于 MA{indicators.get('ma_period', 20)} {ma_value:.2f}，不满足做多条件"
        
        # 做空时，价格应该在 MA 之下（可选，这里简化处理）
        elif action == "SELL":
            if price_above_ma is None:
                return False, "MA 数据无效"
            if price_above_ma:
                return False, f"价格 {current_price:.2f} 高于 MA{indicators.get('ma_period', 20)} {ma_value:.2f}，不满足做空条件"
        
        return True, None

    def _calculate_position_size(self, price, risk_per_trade=0.02, account_balance=10000):
        """
        计算仓位大小
        risk_per_trade: 每次交易的风险比例（默认 2%）
        account_balance: 账户余额（默认 10000，实际应该从交易所获取）
        """
        risk_amount = account_balance * risk_per_trade
        # 假设止损为 5%，计算应该买入的数量
        stop_loss_pct = self.config['risk_management'].get('stop_loss_pct', 0.05)
        quantity = risk_amount / (price * stop_loss_pct)
        return round(quantity, 6)

    def generate_trade_decision(self, ai_signal, market_data=None, loader=None):
        """
        输入: AI 分析结果 (包含 sentiment_score) 和 市场数据
        输出: 具体的买卖指令 (Decision)
        """
        symbol = ai_signal.get('symbol', 'UNKNOWN') if ai_signal else 'UNKNOWN'
        
        # 1. 初始化默认决策
        decision = {
            "action": "HOLD",
            "price": 0,
            "quantity": 0,
            "reason": "观望: 信号强度不足",
            "stop_loss": 0,
            "take_profit": 0,
            "filters_passed": []
        }
        
        # 从市场数据中提取价格
        if market_data:
            if 'spot' in market_data and 'price' in market_data['spot']:
                decision["price"] = market_data['spot']['price']
            elif 'swap' in market_data and 'price' in market_data['swap']:
                decision["price"] = market_data['swap']['price']

        if not ai_signal or 'sentiment_score' not in ai_signal:
            decision["reason"] = "数据无效: 缺失 AI 信号"
            if self.logger:
                self.logger.log_strategy(symbol, False, None, "数据无效: 缺失 AI 信号")
            return decision

        try:
            score = float(ai_signal.get("sentiment_score", 0))
        except:
            score = 0
        
        # 2. 根据情绪分数初步判断方向
        long_threshold = self.config['entry_rules'].get('long_threshold', 0.6)
        short_threshold = self.config['entry_rules'].get('short_threshold', -0.6)
        
        preliminary_action = None
        if score >= long_threshold:
            preliminary_action = "BUY"
        elif score <= short_threshold:
            preliminary_action = "SELL"
        
        # 如果没有达到阈值，直接返回 HOLD
        if not preliminary_action:
            decision["reason"] = f"震荡: 情绪分 {score:.2f} 处于中性区间 (阈值: {short_threshold} ~ {long_threshold})"
            if self.logger:
                strategy_details = {
                    "action": "HOLD",
                    "sentiment_score": score,
                    "reason": decision["reason"],
                    "price": decision["price"],
                    "quantity": 0,
                    "filters_passed": []
                }
                self.logger.log_strategy(symbol, True, strategy_details)
            return decision
        
        # 3. 置信度过滤器
        confidence_passed, confidence_reason = self._check_confidence_filter(ai_signal)
        if not confidence_passed:
            decision["reason"] = f"置信度过滤失败: {confidence_reason}"
            if self.logger:
                strategy_details = {
                    "action": "HOLD",
                    "sentiment_score": score,
                    "reason": decision["reason"],
                    "price": decision["price"],
                    "quantity": 0,
                    "filters_passed": ["sentiment_score"]
                }
                self.logger.log_strategy(symbol, True, strategy_details)
            return decision
        decision["filters_passed"].append("confidence")
        
        # 4. 技术指标过滤器
        indicators = self._calculate_technical_indicators(market_data, loader)
        tech_passed, tech_reason = self._check_technical_filter(indicators, preliminary_action)
        if not tech_passed:
            decision["reason"] = f"技术指标过滤失败: {tech_reason}"
            if self.logger:
                strategy_details = {
                    "action": "HOLD",
                    "sentiment_score": score,
                    "reason": decision["reason"],
                    "price": decision["price"],
                    "quantity": 0,
                    "filters_passed": ["sentiment_score", "confidence"],
                    "indicators": indicators
                }
                self.logger.log_strategy(symbol, True, strategy_details)
            return decision
        decision["filters_passed"].append("technical")
        
        # 5. 所有过滤器通过，生成交易决策
        decision["action"] = preliminary_action
        decision["reason"] = f"{preliminary_action}: 情绪分 {score:.2f}, 置信度 {ai_signal.get('confidence', 0):.2f}, 技术指标通过"
        
        # 6. 计算仓位大小
        if decision["price"] > 0:
            risk_per_trade = self.config['position_sizing'].get('risk_per_trade', 0.02)
            decision["quantity"] = self._calculate_position_size(decision["price"], risk_per_trade)
        
        # 7. 计算止损和止盈
        stop_loss_pct = self.config['risk_management'].get('stop_loss_pct', 0.05)
        take_profit_pct = self.config['risk_management'].get('take_profit_pct', 0.10)
        
        if decision["action"] == "BUY":
            decision["stop_loss"] = decision["price"] * (1 - stop_loss_pct)
            decision["take_profit"] = decision["price"] * (1 + take_profit_pct)
        elif decision["action"] == "SELL":
            decision["stop_loss"] = decision["price"] * (1 + stop_loss_pct)
            decision["take_profit"] = decision["price"] * (1 - take_profit_pct)
        
        # 8. 记录策略生成日志
        if self.logger:
            strategy_details = {
                "action": decision["action"],
                "sentiment_score": score,
                "reason": decision["reason"],
                "price": decision["price"],
                "quantity": decision["quantity"],
                "stop_loss": decision["stop_loss"],
                "take_profit": decision["take_profit"],
                "ai_confidence": ai_signal.get("confidence"),
                "ai_event_type": ai_signal.get("event_type"),
                "ai_impact_duration": ai_signal.get("impact_duration"),
                "filters_passed": decision["filters_passed"],
                "indicators": indicators
            }
            self.logger.log_strategy(symbol, True, strategy_details)
            
        return decision

    def execute(self, decision):
        """
        执行下单 (模拟模式，不进行实盘交易)
        """
        action = decision.get("action", "HOLD")
        reason = decision.get("reason", "")
        
        # 如果是 HOLD，直接返回
        if action == "HOLD":
            return
        
        # 模拟下单打印（不进行实盘交易）
        print(f"   🚀 [策略执行-模拟] 触发信号: {action}")
        print(f"      逻辑依据: {reason}")
        print(f"      价格: {decision.get('price', 0):.2f}")
        print(f"      数量: {decision.get('quantity', 0)}")
        print(f"      止损: {decision.get('stop_loss', 0):.2f}")
        print(f"      止盈: {decision.get('take_profit', 0):.2f}")
        print(f"      ⚠️ 注意: 这是模拟交易，不会消耗真实资金")

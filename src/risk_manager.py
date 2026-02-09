"""
风控管理器 (Risk Management System)
职责：对交易决策进行风险检查和修正
"""
from typing import Dict, Any, Optional, Tuple
from .config import Config


class RiskManager:
    """风控管理器：检查交易决策的风险并修正"""
    
    def __init__(self, logger=None):
        print("🛡️ [风控] 初始化风控管理器...")
        self.logger = logger
        
        # 从配置中读取风控参数
        self.max_position_pct = getattr(Config, 'MAX_POSITION_PCT', 0.1)
        self.max_drawdown_pct = getattr(Config, 'MAX_DRAWDOWN_PCT', 0.05)
        self.price_deviation_limit = getattr(Config, 'PRICE_DEVIATION_LIMIT', 0.02)
        
        print(f"   📋 [风控] 配置参数:")
        print(f"      - 最大持仓比例: {self.max_position_pct * 100}%")
        print(f"      - 最大回撤阈值: {self.max_drawdown_pct * 100}%")
        print(f"      - 价格偏离限制: {self.price_deviation_limit * 100}%")

    def check(
        self, decision: Dict[str, Any], account_state: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], bool, Optional[str]]:
        """
        统一风控入口：实盘和回测共用。
        Args:
            decision: 策略决策
            account_state: 账户状态，如 {"balance": float, "position": float, "current_price": float, "max_position_pct": float(可选)}
        Returns:
            (final_decision, passed, rejection_reason)
        """
        balance = account_state.get("balance", 10000.0)
        current_price = account_state.get("current_price", decision.get("price", 0))
        max_pct = account_state.get("max_position_pct", self.max_position_pct)

        final = decision.copy()
        passed = True
        rejection = None

        if final.get("action") == "HOLD":
            return final, True, None

        price = final.get("price", 0) or current_price
        quantity = final.get("quantity", 0)
        if price > 0 and quantity > 0:
            est_amount = price * quantity
            max_allowed = balance * max_pct
            if est_amount > max_allowed:
                rejection = f"持仓超限: {est_amount:.2f} > {max_allowed:.2f}"
                passed = False
                final["action"] = "HOLD"
                final["reason"] = f"风控拒绝: {rejection}"

        if passed and current_price and price > 0:
            dev = abs(price - current_price) / current_price
            if dev > self.price_deviation_limit:
                rejection = f"价格偏离: {dev*100:.2f}%"
                passed = False
                final["action"] = "HOLD"
                final["reason"] = f"风控拒绝: {rejection}"

        final["risk_checked"] = True
        return final, passed, rejection

    def check_risk(self, decision: Dict[str, Any], current_market_data: Optional[Dict[str, Any]], 
                   account_balance: float = 10000.0) -> Tuple[Dict[str, Any], bool]:
        """
        检查交易决策的风险
        
        Args:
            decision: 策略引擎生成的决策字典
            current_market_data: 当前市场数据（包含价格信息）
            account_balance: 账户余额（默认 10000）
            
        Returns:
            (final_decision, is_passed): 修正后的决策和是否通过风控
        """
        # 复制决策，避免修改原始对象
        final_decision = decision.copy()
        is_passed = True
        risk_reasons = []

        # 如果决策是 HOLD，直接通过
        if final_decision.get('action') == 'HOLD':
            return final_decision, True

        # 1. 硬风控：检查持仓比例
        if final_decision.get('action') in ['BUY', 'SELL']:
            price = final_decision.get('price', 0)
            quantity = final_decision.get('quantity', 0)
            
            if price > 0 and quantity > 0:
                estimated_amount = price * quantity
                max_allowed_amount = account_balance * self.max_position_pct
                
                if estimated_amount > max_allowed_amount:
                    # 强制修正数量
                    corrected_quantity = max_allowed_amount / price
                    final_decision['quantity'] = round(corrected_quantity, 6)
                    risk_reasons.append(f"持仓超限，已修正数量: {quantity:.6f} → {final_decision['quantity']:.6f}")
                    
                    if self.logger:
                        print(f"   ⚠️ [风控] 持仓比例超限: {estimated_amount:.2f} > {max_allowed_amount:.2f}")

        # 2. 价格保护：检查价格偏离
        if current_market_data:
            decision_price = final_decision.get('price', 0)
            
            # 获取当前市场价格
            current_price = None
            if 'spot' in current_market_data and 'price' in current_market_data['spot']:
                current_price = current_market_data['spot']['price']
            elif 'swap' in current_market_data and 'price' in current_market_data['swap']:
                current_price = current_market_data['swap']['price']
            elif 'close' in current_market_data:
                current_price = current_market_data['close']
            
            if current_price and decision_price > 0:
                price_deviation = abs(decision_price - current_price) / current_price
                
                if price_deviation > self.price_deviation_limit:
                    # 价格偏离过大，视为异常信号，强制置为 HOLD
                    final_decision['action'] = 'HOLD'
                    final_decision['reason'] = f"价格偏离过大 ({price_deviation * 100:.2f}% > {self.price_deviation_limit * 100}%)，风控拦截"
                    is_passed = False
                    risk_reasons.append(f"价格偏离: {price_deviation * 100:.2f}%")
                    
                    if self.logger:
                        print(f"   🚫 [风控] 价格偏离过大: 决策价格 {decision_price:.2f} vs 当前价格 {current_price:.2f} (偏离 {price_deviation * 100:.2f}%)")
                else:
                    # 价格正常，使用当前市场价格
                    final_decision['price'] = current_price
                    if self.logger:
                        print(f"   ✅ [风控] 价格检查通过: {current_price:.2f}")

        # 3. 熔断检查（可选）：检查当日亏损
        # 这里可以添加更复杂的熔断逻辑，比如检查当日累计亏损
        # 目前先预留接口
        
        # 更新决策原因
        if risk_reasons:
            original_reason = final_decision.get('reason', '')
            final_decision['reason'] = f"{original_reason} | 风控修正: {', '.join(risk_reasons)}"
            final_decision['risk_checked'] = True
            final_decision['risk_reasons'] = risk_reasons
        else:
            final_decision['risk_checked'] = True
            final_decision['risk_reasons'] = []

        if self.logger:
            if is_passed:
                print(f"   ✅ [风控] 风控检查通过: {final_decision.get('action')}")
            else:
                print(f"   🚫 [风控] 风控检查未通过: {final_decision.get('reason')}")

        return final_decision, is_passed

    def check_drawdown(self, current_balance: float, initial_balance: float) -> bool:
        """
        检查回撤是否超过阈值（熔断检查）
        
        Args:
            current_balance: 当前余额
            initial_balance: 初始余额
            
        Returns:
            是否触发熔断（True 表示正常，False 表示触发熔断）
        """
        if initial_balance <= 0:
            return True
        
        drawdown = (initial_balance - current_balance) / initial_balance
        
        if drawdown > self.max_drawdown_pct:
            if self.logger:
                print(f"   🚨 [风控] 触发熔断: 回撤 {drawdown * 100:.2f}% > 阈值 {self.max_drawdown_pct * 100}%")
            return False
        
        return True

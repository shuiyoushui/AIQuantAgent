import csv
import json
import os
import uuid
import pandas as pd
from datetime import datetime

class SystemLogger:
    def __init__(self, log_dir="logs"):
        self.log_dir = log_dir
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        # 定义文件名 (按日期分文件)
        date_str = datetime.now().strftime("%Y-%m-%d")
        self.market_log_file = os.path.join(log_dir, f"market_data_{date_str}.csv")
        self.ai_log_file = os.path.join(log_dir, f"ai_thoughts_{date_str}.jsonl")
        self.signal_log_file = os.path.join(log_dir, f"signals_{date_str}.csv")
        self.data_source_log_file = os.path.join(log_dir, f"data_source_{date_str}.jsonl")
        self.data_cleaning_log_file = os.path.join(log_dir, f"data_cleaning_{date_str}.jsonl")
        self.ai_opinion_log_file = os.path.join(log_dir, f"ai_opinion_{date_str}.jsonl")
        self.strategy_log_file = os.path.join(log_dir, f"strategy_{date_str}.jsonl")
        
        # 初始化 CSV 表头
        self._init_csv(self.market_log_file, ["session_id", "timestamp", "symbol", "price", "volume", "rsi", "ma_trend"])
        self._init_csv(self.signal_log_file, ["session_id", "timestamp", "symbol", "ai_score", "action", "exec_price", "risk_passed", "reason"])

    def _init_csv(self, filepath, headers):
        """如果文件不存在，写入表头"""
        if not os.path.exists(filepath):
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(headers)

    def start_session(self):
        """生成唯一的会话ID，用于串联单次循环的所有日志"""
        return str(uuid.uuid4())

    def log_market(self, session_id, symbol, market_data, indicators=None):
        """1. 记录行情快照 (用于回测)"""
        if indicators is None: indicators = {}
        with open(self.market_log_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                session_id,
                datetime.now().isoformat(),
                symbol,
                market_data.get('close', 0),
                market_data.get('volume', 0),
                indicators.get('rsi', 0),
                indicators.get('trend', 'N/A')
            ])

    def log_ai_thought(self, session_id, symbol, news_content, prompt, raw_response, structured_output):
        """2. 记录 AI 思考过程 (用于排查幻觉)"""
        log_entry = {
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol,
            "input_news_summary": news_content[:200] + "...", # 只存摘要防止文件过大
            "full_prompt": prompt,
            "deepseek_raw_thinking": raw_response, # 这里记录 <think> 内容
            "final_json": structured_output
        }
        # 使用 JSONL 格式，一行一个 JSON，方便追加和读取
        with open(self.ai_log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

    def log_signal(self, session_id, symbol, ai_score, decision):
        """3. 记录最终决策 (用于归因分析)"""
        with open(self.signal_log_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                session_id,
                datetime.now().isoformat(),
                symbol,
                ai_score,
                decision.get('action', 'HOLD'),
                decision.get('price', 0),
                decision.get('risk_check', True),
                decision.get('reason', '')
            ])

    def log_data_source(self, symbol, source_name, is_connected, data_count, error=None):
        """记录数据源连接状态和获取的数据条数"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol,
            "source_name": source_name,
            "is_connected": is_connected,
            "data_count": data_count,
            "error": error if error else None
        }
        with open(self.data_source_log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        
        # 同时输出到控制台
        status = "✅ 成功" if is_connected else "❌ 失败"
        print(f"   📊 [数据源] {source_name}: {status} | 获取 {data_count} 条数据" + (f" | 错误: {error}" if error else ""))

    def log_data_cleaning(self, symbol, source_name, is_success, raw_count, cleaned_count, error=None):
        """记录数据清洗状态和清洗的数据条数"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol,
            "source_name": source_name,
            "is_success": is_success,
            "raw_count": raw_count,
            "cleaned_count": cleaned_count,
            "error": error if error else None
        }
        with open(self.data_cleaning_log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        
        # 同时输出到控制台
        status = "✅ 成功" if is_success else "❌ 失败"
        print(f"   🧹 [数据清洗] {source_name}: {status} | 原始 {raw_count} 条 → 清洗后 {cleaned_count} 条" + (f" | 错误: {error}" if error else ""))

    def log_ai_opinion(self, symbol, opinion_data):
        """记录 AI 大模型对每个币总结的观点"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol,
            "sentiment_score": opinion_data.get('sentiment_score'),
            "event_type": opinion_data.get('event_type'),
            "impact_duration": opinion_data.get('impact_duration'),
            "confidence": opinion_data.get('confidence'),
            "reasoning": opinion_data.get('reasoning'),
            "summary": opinion_data.get('summary'),
            "full_data": opinion_data
        }
        with open(self.ai_opinion_log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        
        # 同时输出到控制台
        print(f"   🤖 [AI观点] {symbol}:")
        print(f"      情绪分数: {opinion_data.get('sentiment_score', 'N/A')}")
        print(f"      事件类型: {opinion_data.get('event_type', 'N/A')}")
        print(f"      影响时长: {opinion_data.get('impact_duration', 'N/A')}")
        print(f"      置信度: {opinion_data.get('confidence', 'N/A')}")
        print(f"      观点摘要: {opinion_data.get('summary', 'N/A')}")
        if opinion_data.get('reasoning'):
            print(f"      详细推理: {opinion_data.get('reasoning', 'N/A')}")

    def log_strategy(self, symbol, is_generated, strategy_details, error=None):
        """记录策略生成状态和策略明细"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol,
            "is_generated": is_generated,
            "strategy_details": strategy_details,
            "error": error if error else None
        }
        with open(self.strategy_log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        
        # 同时输出到控制台
        status = "✅ 已生成" if is_generated else "❌ 生成失败"
        print(f"   📈 [策略生成] {symbol}: {status}")
        if is_generated and strategy_details:
            print(f"      策略明细:")
            # 优先显示关键信息
            if 'action' in strategy_details:
                print(f"        动作: {strategy_details['action']}")
            if 'sentiment_score' in strategy_details:
                print(f"        情绪分数: {strategy_details['sentiment_score']:.4f}")
            if 'price' in strategy_details and strategy_details['price'] > 0:
                print(f"        价格: ${strategy_details['price']:.2f}")
            if 'quantity' in strategy_details and strategy_details['quantity'] > 0:
                print(f"        数量: {strategy_details['quantity']:.6f}")
            if 'stop_loss' in strategy_details and strategy_details['stop_loss'] > 0:
                print(f"        止损: ${strategy_details['stop_loss']:.2f}")
            if 'take_profit' in strategy_details and strategy_details['take_profit'] > 0:
                print(f"        止盈: ${strategy_details['take_profit']:.2f}")
            if 'filters_passed' in strategy_details:
                filters = strategy_details['filters_passed']
                print(f"        通过的过滤器: {', '.join(filters) if filters else '无'}")
            if 'indicators' in strategy_details and strategy_details['indicators']:
                indicators = strategy_details['indicators']
                if 'current_price' in indicators:
                    print(f"        当前价格: ${indicators['current_price']:.2f}")
                if 'ma' in indicators and pd.notna(indicators.get('ma')):
                    print(f"        MA{indicators.get('ma_period', 20)}: ${indicators['ma']:.2f}")
                if 'rsi' in indicators and pd.notna(indicators.get('rsi')):
                    print(f"        RSI: {indicators['rsi']:.2f}")
            if 'reason' in strategy_details:
                print(f"        原因: {strategy_details['reason']}")
            # 显示其他信息
            for key, value in strategy_details.items():
                if key not in ['action', 'sentiment_score', 'price', 'quantity', 'stop_loss', 
                              'take_profit', 'filters_passed', 'indicators', 'reason']:
                    if value is not None:
                        print(f"        {key}: {value}")
        if error:
            print(f"      错误: {error}")

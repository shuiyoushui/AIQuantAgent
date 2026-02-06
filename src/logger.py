import csv
import json
import os
import uuid
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

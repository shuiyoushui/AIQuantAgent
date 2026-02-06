#这是 Python 与 Lovable 网页端对话的“电话线”。
from supabase import create_client, Client
from .config import Config
from datetime import datetime

class SupabaseConnector:
    def __init__(self):
        self.client: Client = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)

    def send_heartbeat(self):
        """告诉前端 Python 还活着"""
        try:
            data = {
                "id": "local_worker_01",
                "last_beat_time": datetime.utcnow().isoformat(),
                "status": "RUNNING"
            }
            # upsert 表示存在则更新，不存在则插入
            self.client.table("system_heartbeats").upsert(data).execute()
        except Exception as e:
            print(f"心跳发送失败: {e}")

    def write_signal(self, signal_data):
        """将策略生成的信号写入数据库，供前端展示"""
        try:
            self.client.table("market_signals").insert(signal_data).execute()
            print(f"✅ 信号已上报: {signal_data['symbol']} - {signal_data['action']}")
        except Exception as e:
            print(f"❌ 信号上报失败: {e}")

    def log_message(self, level, message):
        """写日志到云端"""
        try:
            self.client.table("system_logs").insert({
                "level": level,
                "message": message,
                "component": "PythonEngine"
            }).execute()
        except Exception as e:
            print(f"日志写入失败: {e}")

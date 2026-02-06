import os
from pathlib import Path
from dotenv import load_dotenv

# ================= 核心修复 =================
# 1. 动态计算项目根目录的绝对路径
# logic: 当前文件(config.py) -> 父目录(src) -> 父目录(项目根目录)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"

# 2. 强制加载 .env 文件，并开启 override=True 以覆盖可能存在的系统变量
if ENV_PATH.exists():
    print(f"📖 [配置加载] 正在读取环境变量: {ENV_PATH}")
    load_dotenv(dotenv_path=ENV_PATH, override=True)
else:
    print(f"⚠️ [配置警告] 未找到 .env 文件，预期路径: {ENV_PATH}")
    print("   请确保文件名是 .env (注意前面的点)，而不是 env.txt")
# ===========================================

class Config:
    # --- 1. 交易所配置 ---
    # 使用 strip() 去除可能复制粘贴带来的空格
    OKX_API_KEY = os.getenv("OKX_API_KEY", "").strip()
    OKX_SECRET = os.getenv("OKX_SECRET", "").strip()
    OKX_PASSWORD = os.getenv("OKX_PASSWORD", "").strip()
    
    # --- 2. 交易基础配置 ---
    # 优先读取命令行或环境变量，默认为 BTC/USDT
    SYMBOL = os.getenv("SYMBOL", "BTC/USDT") 
    TIMEFRAME = "1h"
    
    # 运行模式: True=模拟数据, False=实盘
    # 只有当 .env 里明确写了 USE_MOCK_DATA=False 时才切到实盘
    USE_MOCK_DATA = os.getenv("USE_MOCK_DATA", "True").lower() == "true"

    # --- 3. 交易标的池 ---
    TARGET_COINS = ["BTC","BNB","ETH","XRP","SOL","DOGE","OKB"]

    # --- 4. 数据源配置 ---
    GOOGLE_NEWS_TEMPLATE = "https://news.google.com/rss/search?q={}+crypto+when:1d&hl=en-US&gl=US&ceid=US:en"
    RSS_STATIC_FEEDS = {
        "CoinDesk": "https://www.coindesk.com/arc/outboundfeeds/rss",
        "CoinTelegraph": "https://cointelegraph.com/rss"
    }
    
    # --- 5. 大模型配置 ---
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "deepseek")
    
    # 【关键】获取 DeepSeek Key
    _deepseek_key = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_API_KEY = _deepseek_key.strip() if _deepseek_key else None
    
    DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
    
    # 模型名称: 建议使用 deepseek-chat (V3) 进行快速分析
    LLM_MODEL_NAME = "deepseek-chat" 

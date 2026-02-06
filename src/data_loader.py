import ccxt
import yfinance as yf
import pandas as pd
import feedparser
import time
import re
import os 
import ssl
import warnings
from datetime import datetime
from bs4 import BeautifulSoup
from dotenv import load_dotenv


# 忽略 pandas 的一些无关紧要的警告
warnings.simplefilter(action='ignore', category=FutureWarning)

# --- 1. 全局网络补丁 (解决 RSS 抓取报 SSL 错误) ---
if hasattr(ssl, '_create_unverified_context'):
    ssl._create_default_https_context = ssl._create_unverified_context

# --- 2. 尝试导入配置 ---
try:
    from .config import Config
except ImportError:
    class Config:
        OKX_API_KEY = ""
        OKX_SECRET = ""
        OKX_PASSWORD = ""
        TARGET_COINS = ""
        GOOGLE_NEWS_TEMPLATE = "https://news.google.com/rss/search?q={}+crypto+when:1d&hl=en-US&gl=US&ceid=US:en"
        RSS_STATIC_FEEDS = {
            "CoinDesk": "https://www.coindesk.com/arc/outboundfeeds/rss",
            "CoinTelegraph": "https://cointelegraph.com/rss"
        }

        
class DataLoader:
    def __init__(self):
        print("🔌 [系统] 初始化数据连接模块...")
        
        # =========================================================
        # 1. 【核心修复】先定义所有变量，防止 AttributeError
        # =========================================================
        # 无论后续初始化是否成功，这些变量必须存在
        self.exchange = None
        # 读取 RSS 配置，如果没有则给空字典
        self.static_rss = getattr(Config, 'RSS_STATIC_FEEDS', {}) 
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
        }
        
        # =========================================================
        # 2. 环境变量清洗 (解决 latin-1 报错)
        # =========================================================
        # 强制删除可能包含中文的代理配置
        proxy_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY']
        for key in proxy_vars:
            if key in os.environ:
                del os.environ[key]

        # =========================================================
        # 3. 交易所连接尝试
        # =========================================================
        try:
            # 获取凭证
            api_key = str(getattr(Config, 'OKX_API_KEY', '')).strip()
            secret = str(getattr(Config, 'OKX_SECRET', '')).strip()
            password = str(getattr(Config, 'OKX_PASSWORD', '')).strip()

            # 预检：如果 Key 为空，直接跳过连接，但不报错
            if not api_key or not secret or not password:
                print("   ⚠️ [提示] 未检测到 OKX API 凭证，将仅运行新闻分析模式。")
                return 

            # 预检：如果 Key 包含非法字符，打印警告并跳过
            if not self._is_safe_ascii(api_key) or not self._is_safe_ascii(password):
                print("   ❌ [配置警告] API Key 或密码包含非法字符(中文/全角)，已跳过连接。")
                return

            print("   ⏳ 正在连接 OKX 交易所...")
            self.exchange = ccxt.okx({
                'apiKey': api_key,
                'secret': secret,
                'password': password,
                'enableRateLimit': True,
                'timeout': 30000,
                'options': {'defaultType': 'swap'}
            })
            
            # 验证连接
            self.exchange.load_markets()
            print("   ✅ OKX 连接成功！")
            
        except Exception as e:
            print(f"   ❌ [连接失败] 交易所初始化未完成: {e}")
            print("   👉 系统将以降级模式运行（仅分析新闻，不获取行情）。")
            self.exchange = None

    def _is_safe_ascii(self, s):
        """辅助函数：检查字符串是否安全"""
        try:
            s.encode('latin-1')
            return True
        except:
            return False

    def fetch_news_context(self, symbol=""):
        """获取新闻上下文"""
        # 这里使用了 self.static_rss，现在它一定存在，不会报错
        if not self.static_rss:
            # 如果没配置 RSS，返回默认值
            return f"Analyzing market sentiment for {symbol}...", "System Default"
            
        # 模拟新闻获取逻辑（您可以保留您原来的 RSS 代码）
        #return f"Market update for {symbol}: Sentiment analysis in progress.", "RSS Feed" 这里改了，下一行的 symbol 改了

    def get_market_data(self, symbol="", limit=100):
        """获取行情数据"""
        # 1. 检查交易所是否连接
        if self.exchange is None:
            print("   ⚠️ [跳过] 交易所未连接，无法获取 K 线数据。")
            return None

        # 2. 符号适配
        target_symbol = symbol
        if self.exchange.id == 'okx' and ':' not in symbol:
            target_symbol = f"{symbol}:USDT"

        try:
            ohlcv = self.exchange.fetch_ohlcv(target_symbol, timeframe='1h', limit=limit)
            if not ohlcv:
                return None
                
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            ticker = self.exchange.fetch_ticker(target_symbol)
            print(f"   💰 {symbol} 最新价: {ticker['last']}")
            
            return df
            
        except Exception as e:
            print(f"   ❌ [数据错误] {e}")
            return None
            
    # ================= 工具函数: 文本清洗 =================
    def _clean_text(self, raw_html):
        if not raw_html: return ""
        try:
            soup = BeautifulSoup(raw_html, "html.parser")
            text = soup.get_text(separator=" ")
        except:
            text = str(raw_html)
        
        # 正则清洗广告词和多余空格
        text = re.sub(r'View Full Coverage on Google News', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    # ================= 核心功能 A: 深度行情获取 =================下2行改了
    def fetch_deep_market_data(self, symbol=""):
        if not symbol: symbol = ""
        symbol = str(symbol).upper()
        
        spot_symbol = f"{symbol}/USDT"
        swap_symbol = f"{symbol}/USDT:USDT"
        
        market_snapshot = {
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "symbol": symbol
        }

        try:
            # 1. 现货
            spot_ticker = self.exchange.fetch_ticker(spot_symbol)
            market_snapshot['spot'] = {
                'price': spot_ticker['last'],
                'volume_24h': spot_ticker['baseVolume'],
            }

            # 2. 合约与资金费率
            swap_ticker = self.exchange.fetch_ticker(swap_symbol)
            funding = self.exchange.fetch_funding_rate(swap_symbol)
            
            market_snapshot['swap'] = {
                'price': swap_ticker['last'],
                'funding_rate': funding['fundingRate'],
            }

            # 3. 价差分析
            price_diff = market_snapshot['swap']['price'] - market_snapshot['spot']['price']
            spread_pct = (price_diff / market_snapshot['spot']['price']) * 100
            
            market_snapshot['analysis'] = {
                'spread_price': round(price_diff, 4),
                'spread_pct': round(spread_pct, 4),
                'funding_rate_pct': round(funding['fundingRate'] * 100, 6)
            }
            return market_snapshot

        except Exception as e:
            print(f"❌ [CCXT] 获取 {symbol} 深度行情失败: {e}")
            return None

    # ================= 核心功能 B: 多源舆情获取 (带状态返回) =================下一行改了，211 改了
    def fetch_news_context(self, symbol=""):
        """
        返回: (news_text, status_dict)
        """
        if not symbol: symbol = ""
        symbol = str(symbol).upper()
        
        combined_news = []
        # 初始化状态字典：默认都为 False
        status = {"yahoo": False, "google": False, "rss": False}
        
        # --- 1. Yahoo Finance ---
        try:
            yf_symbol = f"{symbol}-USD"
            ticker = yf.Ticker(yf_symbol)
            if hasattr(ticker, 'news') and ticker.news:
                status["yahoo"] = True # 标记成功
                for item in ticker.news[:5]: 
                    # 兼容性处理：不同版本的 yfinance 返回结构可能不同
                    content = item.get('content', item)
                    title = content.get('title', 'No Title')
                    clean_title = self._clean_text(title)
                    
                    pub_time = content.get('providerPublishTime')
                    time_str = datetime.fromtimestamp(pub_time).strftime('%Y-%m-%d') if pub_time else "Unknown"
                    combined_news.append(f"[Yahoo] [{time_str}] {clean_title}")
        except Exception:
            pass # 忽略单个源的报错，不影响整体

        # --- 2. Google News RSS ---
        try:
            if hasattr(Config, 'GOOGLE_NEWS_TEMPLATE'):
                rss_url = Config.GOOGLE_NEWS_TEMPLATE.format(symbol)
                feed = feedparser.parse(rss_url, agent=self.headers['User-Agent'])
                
                if feed.entries:
                    status["google"] = True # 标记成功
                    for entry in feed.entries[:5]: 
                        clean_title = self._clean_text(entry.title)
                        pub_date = entry.get('published', '')[:16]
                        combined_news.append(f"[Google] [{pub_date}] {clean_title}")
        except Exception:
            pass

        # --- 3. 行业静态 RSS (CoinDesk等) ---
        major_coins = ["BTC", "ETH", "SOL", "BNB", "DOGE", "XPR"]
        if symbol in major_coins and self.static_rss:
            for source_name, url in self.static_rss.items():
                try:
                    feed = feedparser.parse(url, agent=self.headers['User-Agent'])
                    if feed.entries:
                        status["rss"] = True # 标记成功
                        # 修复缩进错误的重点在这里：
                        for entry in feed.entries[:5]:
                            clean_title = self._clean_text(entry.title)
                            combined_news.append(f"[{source_name}] {clean_title}")
                except Exception:
                    pass

        # 构造返回结果
        final_text = "\n".join(combined_news) if combined_news else f"暂无关于 {symbol} 的新闻。"
        return final_text, status

# ================= 本地测试入口 =================
if __name__ == "__main__":
    loader = DataLoader()
    targets = getattr(Config, 'TARGET_COINS', [''])
    
    for coin in targets:
        print(f"====== 测试 {coin} ======")
        
        # 注意：现在 fetch_news_context 返回两个值
        news_text, source_status = loader.fetch_news_context(coin)
        
        print(f"1. 数据源状态: {source_status}")
        print(f"2. 新闻条数: {len(news_text.splitlines())}")
        
        # 测试行情
        data = loader.fetch_deep_market_data(coin)
        if data:
            print(f"3. 行情获取成功: 资金费率 {data['analysis']['funding_rate_pct']}%")
        else:
            print("3. 行情获取失败")
            
        print("-" * 30)
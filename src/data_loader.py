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

warnings.simplefilter(action='ignore', category=FutureWarning)

# 全局网络补丁
if hasattr(ssl, '_create_unverified_context'):
    ssl._create_default_https_context = ssl._create_unverified_context

# 尝试导入配置
try:
    from .config import Config
except ImportError:
    class Config:
        RSS_STATIC_FEEDS = {}
        OKX_API_KEY = ""
        OKX_SECRET = ""
        OKX_PASSWORD = ""
        GOOGLE_NEWS_TEMPLATE = ""

class DataLoader:
    def __init__(self):
        print("🔌 [系统] 初始化数据连接模块...")
        
        self.exchange = None
        self.static_rss = getattr(Config, 'RSS_STATIC_FEEDS', {})
        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

        # 1. 环境变量清洗
        for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY']:
            if key in os.environ: del os.environ[key]

        # 2. 连接交易所
        try:
            api_key = str(getattr(Config, 'OKX_API_KEY', '')).strip()
            secret = str(getattr(Config, 'OKX_SECRET', '')).strip()
            password = str(getattr(Config, 'OKX_PASSWORD', '')).strip()

            if not api_key or not secret or not password:
                print("   ⚠️ [提示] 未检测到 API 凭证，仅运行新闻分析模式。")
                return

            self.exchange = ccxt.okx({
                'apiKey': api_key,
                'secret': secret,
                'password': password,
                'enableRateLimit': True,
                'timeout': 30000,
                'options': {'defaultType': 'swap'} 
            })
            self.exchange.load_markets()
            print("   ✅ OKX 连接成功！")
            
        except Exception as e:
            print(f"   ❌ [连接失败] {e}")
            self.exchange = None

    # ========================================================
    # 🔧 核心新增：符号标准化工具
    # ========================================================
    def _normalize_symbol(self, input_symbol):
        """
        无论输入是 "BTC", "BTC/USDT", "BTC-USDT" 还是 "BTC/USDT:USDT"
        统一提取出基础币种 "BTC"
        """
        if not input_symbol: return "BTC"
        s = str(input_symbol).upper()
        # 移除 :USDT 后缀
        if ':' in s: s = s.split(':')
        # 移除 /USDT 或 -USDT
        s = s.replace('/USDT', '').replace('-USDT', '')
        # 再次兜底清洗
        return s.strip()

    def _clean_text(self, raw_html):
        """清洗 HTML 标签"""
        if not raw_html: return ""
        try:
            soup = BeautifulSoup(raw_html, "html.parser")
            text = soup.get_text(separator=" ")
            text = re.sub(r'View Full Coverage on Google News', '', text, flags=re.IGNORECASE)
            return re.sub(r'\s+', ' ', text).strip()
        except:
            return str(raw_html)

    # ========================================================
    # 1. 获取深度行情 (自动适配现货与合约)
    # ========================================================
    def fetch_deep_market_data(self, symbol="BTC"):
        """
        同时抓取现货和合约数据，计算价差
        """
        if not self.exchange: return None
        
        # 1. 标准化币种 (例如: BTC/USDT -> BTC)
        base_coin = self._normalize_symbol(symbol)
        
        # 2. 自动构建 OKX 标准格式
        # 现货: BTC/USDT
        # 合约: BTC/USDT:USDT
        spot_symbol = f"{base_coin}/USDT"
        swap_symbol = f"{base_coin}/USDT:USDT"

        market_snapshot = {
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "symbol": base_coin
        }

        try:
            # 3. 获取现货数据
            # print(f"   🔍 抓取现货: {spot_symbol}")
            spot_ticker = self.exchange.fetch_ticker(spot_symbol)
            market_snapshot['spot'] = {
                'price': spot_ticker['last'],
                'volume': spot_ticker['baseVolume'],
            }

            # 4. 获取合约与资金费率
            # print(f"   🔍 抓取合约: {swap_symbol}")
            swap_ticker = self.exchange.fetch_ticker(swap_symbol)
            funding = self.exchange.fetch_funding_rate(swap_symbol)
            
            market_snapshot['swap'] = {
                'price': swap_ticker['last'],
                'funding_rate': funding['fundingRate'],
            }
            
            # 5. 计算价差 (Spread)
            price_diff = market_snapshot['swap']['price'] - market_snapshot['spot']['price']
            spread_pct = (price_diff / market_snapshot['spot']['price']) * 100
            
            market_snapshot['analysis'] = {
                'spread_price': round(price_diff, 4),
                'spread_pct': round(spread_pct, 4),
                'funding_rate_pct': round(funding['fundingRate'] * 100, 6)
            }
            
            return market_snapshot

        except Exception as e:
            # 如果报错，很有可能是某个币没有合约或现货，打印具体信息
            # print(f"   ⚠️ [数据缺失] {base_coin}: {e}")
            return None

    # ========================================================
    # 2. 获取 K 线数据 (用于回测或绘图)
    # ========================================================
    def get_market_data(self, symbol="BTC", limit=100):
        if not self.exchange: return None
        
        # 默认优先获取合约数据 (量化常用)
        base_coin = self._normalize_symbol(symbol)
        target_symbol = f"{base_coin}/USDT:USDT"

        try:
            ohlcv = self.exchange.fetch_ohlcv(target_symbol, timeframe='1h', limit=limit)
            if not ohlcv: return None
            
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            # 打印一下确认拿到了数据
            # print(f"   💰 {target_symbol} 收盘价: {df.iloc[-1]['close']}")
            return df
        except Exception:
            return None

    # ========================================================
    # 3. 获取新闻舆情
    # ========================================================
    def fetch_news_context(self, symbol="BTC"):
        # 使用基础币种去搜索新闻 (例如搜 "BTC" 而不是 "BTC/USDT")
        base_coin = self._normalize_symbol(symbol)
        
        combined_news = []
        status = {"yahoo": False, "google": False, "rss": False}

        # Yahoo Finance (需要 symbol-USD 格式)
        try:
            yf_ticker = yf.Ticker(f"{base_coin}-USD")
            if hasattr(yf_ticker, 'news') and yf_ticker.news:
                status['yahoo'] = True
                for item in yf_ticker.news[:3]:
                    title = item.get('content', {}).get('title', item.get('title'))
                    if title: combined_news.append(f"[Yahoo] {title}")
        except: pass

        # Google RSS
        try:
            rss_url = Config.GOOGLE_NEWS_TEMPLATE.format(base_coin)
            feed = feedparser.parse(rss_url)
            if feed.entries:
                status['google'] = True
                for entry in feed.entries[:3]:
                    combined_news.append(f"[Google] {entry.title}")
        except: pass

        # 静态 RSS (仅对主流币有效)
        if base_coin in ["BTC", "ETH", "SOL"]:
            if self.static_rss:
                status['rss'] = True
                # 这里只简单模拟，实际需遍历 self.static_rss
                combined_news.append(f"[RSS] {base_coin} market maintains high volatility.")

        final_text = "\n".join(combined_news) if combined_news else f"No recent news for {base_coin}."
        return final_text, status
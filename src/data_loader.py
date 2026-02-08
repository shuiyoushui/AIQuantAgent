"""
数据加载器（备用/兼容层）。

职责：从交易所、yfinance、RSS 等拉取并组装市场与新闻数据，提供统一接口；
若项目以 DataIngestion 为主数据源，本模块可作为备用或测试用。
"""
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
    def __init__(self, logger=None):
        print("🔌 [系统] 初始化数据连接模块...")
        
        self.exchange = None
        self.static_rss = getattr(Config, 'RSS_STATIC_FEEDS', {})
        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        self.logger = logger

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

    def _clean_text(self, raw_text):
        """清洗文本内容（去除 HTML 标签、多余空格等）"""
        if not raw_text: 
            return ""
        
        try:
            # 尝试解析 HTML（如果包含 HTML 标签）
            if '<' in raw_text and '>' in raw_text:
                soup = BeautifulSoup(raw_text, "html.parser")
                text = soup.get_text(separator=" ")
            else:
                text = raw_text
            
            # 去除 Google News 特有的噪音
            text = re.sub(r'View Full Coverage on Google News', '', text, flags=re.IGNORECASE)
            # 去除多余空格
            cleaned_text = re.sub(r'\s+', ' ', text).strip()
            
            return cleaned_text
        except Exception as e:
            # 如果清洗失败，返回原始文本
            return str(raw_text)

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
        raw_news_items = {"yahoo": [], "google": [], "rss": []}  # 用于记录原始数据

        # Yahoo Finance (需要 symbol-USD 格式)
        yahoo_count = 0
        try:
            yf_ticker = yf.Ticker(f"{base_coin}-USD")
            if hasattr(yf_ticker, 'news') and yf_ticker.news:
                status['yahoo'] = True
                for item in yf_ticker.news[:3]:
                    title = item.get('content', {}).get('title', item.get('title'))
                    if title: 
                        raw_news_items['yahoo'].append(title)
                        combined_news.append(f"[Yahoo] {title}")
                        yahoo_count += 1
                if self.logger:
                    self.logger.log_data_source(base_coin, "Yahoo财经", True, yahoo_count)
            else:
                if self.logger:
                    self.logger.log_data_source(base_coin, "Yahoo财经", False, 0, "无新闻数据")
        except Exception as e:
            if self.logger:
                self.logger.log_data_source(base_coin, "Yahoo财经", False, 0, str(e))

        # Google RSS
        google_count = 0
        try:
            rss_url = Config.GOOGLE_NEWS_TEMPLATE.format(base_coin)
            feed = feedparser.parse(rss_url)
            if feed.entries:
                status['google'] = True
                for entry in feed.entries[:3]:
                    raw_news_items['google'].append(entry.title)
                    combined_news.append(f"[Google] {entry.title}")
                    google_count += 1
                if self.logger:
                    self.logger.log_data_source(base_coin, "Google新闻", True, google_count)
            else:
                if self.logger:
                    self.logger.log_data_source(base_coin, "Google新闻", False, 0, "RSS 无条目")
        except Exception as e:
            if self.logger:
                self.logger.log_data_source(base_coin, "Google新闻", False, 0, str(e))

        # 静态 RSS (对所有币种都尝试，但会过滤包含币种名称的新闻)
        rss_count = 0
        if self.static_rss:
            try:
                # 遍历所有静态 RSS 源
                for rss_name, rss_url in self.static_rss.items():
                    feed = feedparser.parse(rss_url)
                    if feed.entries:
                        # 对每个币种，只选择包含该币种名称的新闻，确保新闻相关性
                        for entry in feed.entries[:5]:  # 扩大搜索范围
                            title = entry.get('title', '')
                            # 检查标题中是否包含币种名称（不区分大小写）
                            if base_coin.upper() in title.upper():
                                raw_news_items['rss'].append(title)
                                combined_news.append(f"[RSS-{rss_name}] {title}")
                                rss_count += 1
                                if rss_count >= 3:  # 每个币种最多3条RSS新闻
                                    break
                if rss_count > 0:
                    status['rss'] = True
                    if self.logger:
                        self.logger.log_data_source(base_coin, "行业RSS", True, rss_count)
                else:
                    if self.logger:
                        self.logger.log_data_source(base_coin, "行业RSS", False, 0, f"未找到包含 {base_coin} 的新闻")
            except Exception as e:
                if self.logger:
                    self.logger.log_data_source(base_coin, "行业RSS", False, 0, str(e))

        # 数据清洗：对每条新闻进行清洗，并按数据源记录日志
        cleaned_news = []
        
        # 按数据源分组清洗，以便准确记录日志
        yahoo_raw = [item for item in combined_news if "[Yahoo]" in item]
        google_raw = [item for item in combined_news if "[Google]" in item]
        rss_raw = [item for item in combined_news if "[RSS" in item]
        
        # 清洗 Yahoo 数据
        yahoo_cleaned_count = 0
        for news_item in yahoo_raw:
            cleaned_item = self._clean_text(news_item)
            if cleaned_item:
                cleaned_news.append(cleaned_item)
                yahoo_cleaned_count += 1
        if self.logger and len(yahoo_raw) > 0:
            self.logger.log_data_cleaning(base_coin, "Yahoo财经", True, len(yahoo_raw), yahoo_cleaned_count)
        
        # 清洗 Google 数据
        google_cleaned_count = 0
        for news_item in google_raw:
            cleaned_item = self._clean_text(news_item)
            if cleaned_item:
                cleaned_news.append(cleaned_item)
                google_cleaned_count += 1
        if self.logger and len(google_raw) > 0:
            self.logger.log_data_cleaning(base_coin, "Google新闻", True, len(google_raw), google_cleaned_count)
        
        # 清洗 RSS 数据
        rss_cleaned_count = 0
        for news_item in rss_raw:
            cleaned_item = self._clean_text(news_item)
            if cleaned_item:
                cleaned_news.append(cleaned_item)
                rss_cleaned_count += 1
        if self.logger and len(rss_raw) > 0:
            self.logger.log_data_cleaning(base_coin, "行业RSS", True, len(rss_raw), rss_cleaned_count)

        final_text = "\n".join(cleaned_news) if cleaned_news else f"No recent news for {base_coin}."
        return final_text, status
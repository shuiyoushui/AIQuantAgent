"""
数据采集器 (Data Ingestion Layer)
职责：仅负责连接外部数据源并获取原始数据，不进行数据清洗和处理
"""
import ccxt
import yfinance as yf
import feedparser
import os
import ssl
import warnings
from datetime import datetime
from typing import List, Dict, Optional, Any

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


class DataIngestion:
    """数据采集器：负责从外部数据源获取原始数据"""
    
    def __init__(self, logger=None):
        print("🔌 [数据采集] 初始化数据采集器...")
        
        self.exchange = None
        self.static_rss = getattr(Config, 'RSS_STATIC_FEEDS', {})
        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        self.logger = logger

        # 环境变量清洗
        for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY']:
            if key in os.environ:
                del os.environ[key]

        # 连接交易所
        self._init_exchange()

    def _init_exchange(self):
        """初始化交易所连接"""
        try:
            api_key = str(getattr(Config, 'OKX_API_KEY', '')).strip()
            secret = str(getattr(Config, 'OKX_SECRET', '')).strip()
            password = str(getattr(Config, 'OKX_PASSWORD', '')).strip()

            if not api_key or not secret or not password:
                print("   ⚠️ [数据采集] 未检测到 API 凭证，仅运行新闻分析模式。")
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
            print("   ✅ [数据采集] OKX 连接成功！")
            
        except Exception as e:
            print(f"   ❌ [数据采集] 连接失败: {e}")
            self.exchange = None

    def _normalize_symbol(self, input_symbol: str) -> str:
        """
        符号标准化工具
        无论输入是 "BTC", "BTC/USDT", "BTC-USDT" 还是 "BTC/USDT:USDT"
        统一提取出基础币种 "BTC"
        """
        if not input_symbol:
            return "BTC"
        s = str(input_symbol).upper()
        # 移除 :USDT 后缀
        if ':' in s:
            s = s.split(':')[0]
        # 移除 /USDT 或 -USDT
        s = s.replace('/USDT', '').replace('-USDT', '')
        # 再次兜底清洗
        return s.strip()

    def fetch_raw_market_data(self, symbol: str, limit: int = 100) -> Optional[List[List]]:
        """
        获取原始 OHLCV 数据（不进行 DataFrame 处理）
        
        Args:
            symbol: 交易对符号
            limit: 获取的 K 线数量
            
        Returns:
            原始 OHLCV 数据列表，格式: [[timestamp, open, high, low, close, volume], ...]
            如果失败返回 None
        """
        if not self.exchange:
            if self.logger:
                print("   ⚠️ [数据采集] 交易所未连接，无法获取市场数据")
            return None
        
        base_coin = self._normalize_symbol(symbol)
        target_symbol = f"{base_coin}/USDT:USDT"

        try:
            ohlcv = self.exchange.fetch_ohlcv(target_symbol, timeframe='1h', limit=limit)
            if not ohlcv:
                return None
            
            if self.logger:
                print(f"   ✅ [数据采集] 成功获取 {target_symbol} 原始 K 线数据: {len(ohlcv)} 条")
            
            return ohlcv
        except Exception as e:
            if self.logger:
                print(f"   ❌ [数据采集] 获取市场数据失败: {e}")
            return None

    def fetch_raw_news(self, symbol: str) -> List[Dict[str, Any]]:
        """
        获取各渠道的新闻原始内容
        
        Args:
            symbol: 交易对符号
            
        Returns:
            新闻列表，每个元素为字典，包含：
            - title: 标题
            - source: 来源 (yahoo/google/rss)
            - timestamp: 原始时间戳
            - raw_content: 原始内容
        """
        base_coin = self._normalize_symbol(symbol)
        raw_news_list = []
        source_status = {"yahoo": False, "google": False, "rss": False}

        # Yahoo Finance
        try:
            yf_ticker = yf.Ticker(f"{base_coin}-USD")
            if hasattr(yf_ticker, 'news') and yf_ticker.news:
                source_status['yahoo'] = True
                for item in yf_ticker.news[:3]:
                    title = item.get('content', {}).get('title', item.get('title', ''))
                    if title:
                        raw_news_list.append({
                            'title': title,
                            'source': 'yahoo',
                            'timestamp': item.get('providerPublishTime', datetime.now().timestamp()),
                            'raw_content': title,
                            'url': item.get('link', '')
                        })
                if self.logger:
                    self.logger.log_data_source(base_coin, "Yahoo财经", True, len([n for n in raw_news_list if n['source'] == 'yahoo']))
        except Exception as e:
            if self.logger:
                self.logger.log_data_source(base_coin, "Yahoo财经", False, 0, str(e))

        # Google RSS
        try:
            rss_url = Config.GOOGLE_NEWS_TEMPLATE.format(base_coin)
            feed = feedparser.parse(rss_url)
            if feed.entries:
                source_status['google'] = True
                for entry in feed.entries[:3]:
                    raw_news_list.append({
                        'title': entry.get('title', ''),
                        'source': 'google',
                        'timestamp': entry.get('published_parsed', datetime.now().timetuple()),
                        'raw_content': entry.get('title', ''),
                        'url': entry.get('link', '')
                    })
                if self.logger:
                    self.logger.log_data_source(base_coin, "Google新闻", True, len([n for n in raw_news_list if n['source'] == 'google']))
        except Exception as e:
            if self.logger:
                self.logger.log_data_source(base_coin, "Google新闻", False, 0, str(e))

        # 静态 RSS
        if self.static_rss:
            try:
                for rss_name, rss_url in self.static_rss.items():
                    feed = feedparser.parse(rss_url)
                    if feed.entries:
                        for entry in feed.entries[:5]:
                            title = entry.get('title', '')
                            if base_coin.upper() in title.upper():
                                raw_news_list.append({
                                    'title': title,
                                    'source': f'rss_{rss_name.lower()}',
                                    'timestamp': entry.get('published_parsed', datetime.now().timetuple()),
                                    'raw_content': title,
                                    'url': entry.get('link', '')
                                })
                                if len([n for n in raw_news_list if n['source'].startswith('rss_')]) >= 3:
                                    break
                rss_count = len([n for n in raw_news_list if n['source'].startswith('rss_')])
                if rss_count > 0:
                    source_status['rss'] = True
                    if self.logger:
                        self.logger.log_data_source(base_coin, "行业RSS", True, rss_count)
            except Exception as e:
                if self.logger:
                    self.logger.log_data_source(base_coin, "行业RSS", False, 0, str(e))

        if self.logger:
            print(f"   ✅ [数据采集] 成功获取 {base_coin} 原始新闻数据: {len(raw_news_list)} 条")
        
        return raw_news_list

    def fetch_raw_ticker_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        获取原始 ticker 数据（用于获取当前价格）
        
        Args:
            symbol: 交易对符号
            
        Returns:
            包含现货和合约价格的字典，如果失败返回 None
        """
        if not self.exchange:
            return None
        
        base_coin = self._normalize_symbol(symbol)
        spot_symbol = f"{base_coin}/USDT"
        swap_symbol = f"{base_coin}/USDT:USDT"

        try:
            spot_ticker = self.exchange.fetch_ticker(spot_symbol)
            swap_ticker = self.exchange.fetch_ticker(swap_symbol)
            funding = self.exchange.fetch_funding_rate(swap_symbol)
            
            return {
                'spot': {
                    'price': spot_ticker['last'],
                    'volume': spot_ticker['baseVolume'],
                },
                'swap': {
                    'price': swap_ticker['last'],
                    'funding_rate': funding['fundingRate'],
                },
                'timestamp': datetime.now().isoformat(),
                'symbol': base_coin
            }
        except Exception as e:
            if self.logger:
                print(f"   ❌ [数据采集] 获取 ticker 数据失败: {e}")
            return None

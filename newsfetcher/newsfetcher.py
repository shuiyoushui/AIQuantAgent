import yfinance as yf
import requests
from bs4 import BeautifulSoup

class NewsFetcher:
    def get_crypto_news(self, symbol="BTC-USD"):
        """
        获取指定标的的新闻标题和摘要
        """
        try:
            # yfinance 获取新闻非常方便
            ticker = yf.Ticker(symbol)
            news_list = ticker.news
            
            cleaned_news = []
            for item in news_list:
                # 简单清洗，提取标题和发布时间
                title = item.get('title', '')
                link = item.get('link', '')
                # 如果需要正文，可以用 requests + BeautifulSoup 进一步爬取 link
                # 这里为了速度仅演示标题分析
                cleaned_news.append(f"时间: {item.get('providerPublishTime')} | 标题: {title}")
            
            return "\n".join(cleaned_news[:5]) # 只取最新的5条
        except Exception as e:
            print(f"新闻获取失败: {e}")
            return ""

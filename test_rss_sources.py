# 文件名: test_rss_pro.py

import feedparser
from bs4 import BeautifulSoup
import re
import time
import ssl

# 全局 SSL 补丁（解决部分网络环境下的证书报错）
if hasattr(ssl, '_create_unverified_context'):
    ssl._create_default_https_context = ssl._create_unverified_context

class RSSOptimizer:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
    def clean_text(self, html_content):
        """
        深度清洗函数：
        1. 去除 HTML 标签
        2. 去除 Google News 特有的噪音 (如 'View Full Coverage')
        3. 去除多余空格和换行
        """
        if not html_content: return ""
        
        # 1. BS4 去除 HTML 标签
        soup = BeautifulSoup(html_content, "html.parser")
        text = soup.get_text(separator=" ") # 用空格替代标签换行
        
        # 2. 正则清洗
        # 去除 Google News 常见的尾部链接文字
        text = re.sub(r'View Full Coverage on Google News', '', text, flags=re.IGNORECASE)
        # 去除多余的空白字符
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text

    def analyze_source(self, name, url_template, symbol="BTC"):
        print(f"\n{'='*20} 正在深度分析: {name} {'='*20}")
        
        # 处理动态 URL (如果有 {} 占位符)
        target_url = url_template.format(symbol) if "{}" in url_template else url_template
        print(f"🔗 目标 URL: {target_url}")
        
        try:
            # 记录耗时
            start_time = time.time()
            feed = feedparser.parse(target_url, agent=self.headers['User-Agent'])
            duration = time.time() - start_time
            
            print(f"⏱️ 请求耗时: {duration:.2f}秒")
            print(f"📦 获取条目: {len(feed.entries)} 条")
            
            if not feed.entries:
                print("❌ 警告: 未获取到数据，请检查网络或 URL。")
                return

            # 取前 3 条进行详细的数据质量体检
            print("\n🧐 --- 数据质量抽检 (前3条) ---")
            for i, entry in enumerate(feed.entries[:3]):
                print(f"\n[第 {i+1} 条]")
                
                # 1. 标题清洗对比
                raw_title = entry.title
                clean_title = self.clean_text(raw_title)
                
                # 2. 摘要清洗对比 (Google News 的摘要通常很脏)
                # 尝试获取 summary 或 description
                raw_summary = entry.get('summary', entry.get('description', ''))
                clean_summary = self.clean_text(raw_summary)
                
                # 3. 发布时间
                pub_date = entry.get('published', 'N/A')

                print(f"  📅 时间: {pub_date}")
                print(f"  📝 标题 (清洗后): {clean_title}")
                
                # 对比摘要质量
                print(f"  🔍 摘要分析:")
                if len(raw_summary) > 0:
                    print(f"     - 原始长度: {len(raw_summary)} 字符 (含HTML)")
                    print(f"     - 清洗后内容: {clean_summary[:100]}... (已去除HTML)")
                    if "View Full Coverage" in raw_summary:
                        print("     - ✅ 成功检测并移除了 Google News 广告词")
                else:
                    print("     - ⚠️ 此条目无摘要")

        except Exception as e:
            print(f"❌ 发生异常: {e}")

if __name__ == "__main__":
    optimizer = RSSOptimizer()
    
    # 1. 配置源
    sources = {
        "Google_News": "https://news.google.com/rss/search?q={}+crypto+when:1d&hl=en-US&gl=US&ceid=US:en",
        "CoinDesk": "https://www.coindesk.com/arc/outboundfeeds/rss",
        "CoinTelegraph": "https://cointelegraph.com/rss"
    }
    
    # 2. 执行测试
    # 重点测试 Google News 的清洗效果
    optimizer.analyze_source("Google_News (BTC)", sources["Google_News"], "BTC")
    
    # 稍微停顿
    time.sleep(1)
    
    # 测试一个静态源
    optimizer.analyze_source("CoinDesk", sources["CoinDesk"])
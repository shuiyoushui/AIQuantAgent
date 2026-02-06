#这段代码涵盖了 加密货币 和 美股 两种标的，同时获取 价格 和 新闻。
import yfinance as yf
import pandas as pd
from datetime import datetime

def verify_market_data(symbol):
    print(f"\n{'='*10} 正在获取 {symbol} 的行情数据 {'='*10}")
    
    try:
        ticker = yf.Ticker(symbol)
        
        # --- 1. 获取价格 (尝试多种字段) ---
        price = None
        # 尝试 fast_info (通常更快更准)
        if hasattr(ticker, 'fast_info'):
            price = ticker.fast_info.last_price
        # 如果失败，尝试 info
        if price is None:
            price = ticker.info.get('regularMarketPrice') or ticker.info.get('currentPrice')
            
        print(f"💰 当前价格: {price}")

        # --- 2. 获取新闻 (增强鲁棒性) ---
        news_list = ticker.news
        
        if news_list and isinstance(news_list, list):
            print(f"📰 成功获取原始新闻列表，共 {len(news_list)} 条 (展示前 3 条):")
            
            for i, item in enumerate(news_list[:3]):
                try:
                    # 兼容不同层级结构
                    content = item.get('content', item)
                    if content is None: continue # 跳过空数据

                    # A. 安全获取标题
                    title = content.get('title', '无标题')

                    # B. 安全获取链接 (多层级防爆处理)
                    link = content.get('link')
                    if not link:
                        click_info = content.get('clickThroughUrl')
                        if click_info and isinstance(click_info, dict):
                            link = click_info.get('url')
                    
                    # C. 安全获取时间 (尝试多个可能的字段名)
                    pub_time = content.get('providerPublishTime')
                    if not pub_time:
                        pub_time = content.get('pubDate') # 有些源用 pubDate
                    
                    # 时间格式化
                    time_str = "未知时间"
                    if pub_time:
                        try:
                            # 如果是时间戳 (int/float)
                            if isinstance(pub_time, (int, float)):
                                time_str = datetime.fromtimestamp(pub_time).strftime('%Y-%m-%d %H:%M')
                            # 如果是字符串 (ISO格式等)，这里暂简略处理
                            else:
                                time_str = str(pub_time)
                        except:
                            pass

                    print(f"   [{i+1}] 时间: {time_str}")
                    print(f"       标题: {title}")
                    print(f"       链接: {link}\n")
                    
                except Exception as e:
                    print(f"   ⚠️ 第 {i+1} 条新闻解析出错: {e}")
                    # 只有调试时才打开下面这行，看看到底是什么奇葩数据结构
                    # print(f"       原始数据: {item}")
                    continue
        else:
            print("⚠️ 未获取到新闻数据 (列表为空或格式错误)")
            
    except Exception as e:
        print(f"❌ 整体流程异常: {e}")

if __name__ == "__main__":
    # 加密货币
    verify_market_data("BTC-USD")
    # 美股
    verify_market_data("NVDA")

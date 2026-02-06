import os
import ccxt
from dotenv import load_dotenv

# 1. 加载环境变量
load_dotenv()

print("="*50)
print("🔍 OKX 连接诊断 (CCXT)")
print("="*50)

# 2. 检查代理 (这是连接成功的关键)
http_proxy = os.getenv("HTTP_PROXY")
https_proxy = os.getenv("HTTPS_PROXY")
print(f"📡 代理配置:")
print(f"   HTTP_PROXY:  {http_proxy if http_proxy else '❌ 未设置 (国内直连通常会失败)'}")
print(f"   HTTPS_PROXY: {https_proxy if https_proxy else '❌ 未设置'}")

# 3. 初始化 OKX
try:
    print("\n🔌 正在初始化 OKX 客户端...")
    
    # 构造代理字典
    proxies = {}
    if http_proxy:
        proxies['http'] = http_proxy
    if https_proxy:
        proxies['https'] = https_proxy

    # 实例化 OKX (注意: defaultType='swap' 代表永续合约)
    exchange = ccxt.okx({
        'timeout': 30000,
        'enableRateLimit': True,
        'proxies': proxies,  # 显式注入代理
        'options': {'defaultType': 'swap'} 
    })
    
    # 4. 发起网络请求
    print(f"🚀 发送请求: 获取 BTC/USDT 永续合约行情...")
    
    # 获取市场概况 (这一步会真正联网)
    ticker = exchange.fetch_ticker('BTC/USDT:USDT')
    
    print("\n✅ 连接成功！")
    print(f"   交易对: {ticker['symbol']}")
    print(f"   最新价: {ticker['last']}")
    print(f"   24h量:  {ticker['quoteVolume']}")
    
    # 尝试获取深度
    print("\n📚 正在获取深度数据...")
    orderbook = exchange.fetch_order_book('BTC/USDT:USDT', limit=5)
    print(f"   买一价: {orderbook['bids']} (数量: {orderbook['bids'][1]})")
    print(f"   卖一价: {orderbook['asks']} (数量: {orderbook['asks'][1]})")

except ccxt.ExchangeNotAvailable as e:
    print(f"\n❌ [网络/地区限制] 无法连接交易所。原因: {e}")
    print("👉 建议: 请检查 VPN 是否开启，以及 .env 中的端口号是否正确。")
except ccxt.NetworkError as e:
    print(f"\n❌ [网络错误] 连接超时或失败。原因: {e}")
except Exception as e:
    print(f"\n❌ [未知错误] {e}")

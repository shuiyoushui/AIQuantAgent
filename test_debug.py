import os
from openai import OpenAI
from dotenv import load_dotenv

# 1. 加载环境变量
load_dotenv()

# 2. 配置客户端
api_key = os.getenv("DEEPSEEK_API_KEY")
base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

print(f"🔍 [诊断] 正在连接: {base_url}")
client = OpenAI(api_key=api_key, base_url=base_url)

try:
    # 3. 发送最简单的请求
    print("🚀 [诊断] 发送测试请求...")
    response = client.chat.completions.create(
        model="deepseek-chat", # 或者是 deepseek-reasoner
        messages=[{"role": "user", "content": "Hi"}],
        max_tokens=5
    )

    # 4. 【核心诊断】解剖数据结构
    print("\n" + "="*40)
    print("📊 数据结构解剖报告")
    print("="*40)
    
    # 检查 response 本身
    print(f"1. response 的类型: {type(response)}")
    
    # 检查 choices
    choices = getattr(response, 'choices', None)
    print(f"2. response.choices 的类型: {type(choices)}")
    print(f"3. response.choices 的原始内容: {choices}")

    # 5. 模拟报错场景（还原现场）
    print("\n💥 [模拟] 正在重现错误...")
    if isinstance(choices, list):
        print(f"   检测到 choices 是一个列表 (List)，长度为: {len(choices)}")
        print("   ❌ 错误操作: response.choices.message")
        try:
            # 这行代码就是导致你报错的元凶
            print(response.choices.message) 
        except AttributeError as e:
            print(f"   ✅ 成功捕获预期错误: {e}")
            print("   👉 结论: 你不能对列表直接调用 .message")
    
    # 6. 展示正确写法
    print("\n✨ [修复] 正确的访问方式:")
    print("   ✅ 正确操作: response.choices.message.content")
    if choices and len(choices) > 0:
        content = choices.message.content
        print(f"   📝 提取结果: {content}")

except Exception as e:
    print(f"\n❌ [严重错误] 请求失败: {e}")

import os
from openai import OpenAI
from dotenv import load_dotenv

# 加载环境配置
load_dotenv()

api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
base_url = os.getenv("DEEPSEEK_BASE_URL")

print("="*50)
print("🔍 深度结构诊断启动")
print(f"API Key: {api_key[:5]}****" if api_key else "未找到 Key")
print(f"Base URL: {base_url}")

client = OpenAI(api_key=api_key, base_url=base_url)

try:
    print("\n🚀 发送请求中...")
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": "Hi"}],
        max_tokens=10
    )
    
    print("\n✅ 请求成功！开始解剖数据结构：")
    print(f"1. response 类型: {type(response)}")
    
    # 检查 choices
    if hasattr(response, 'choices'):
        choices = response.choices
        print(f"2. choices 类型: {type(choices)}")
        print(f"3. choices 内容: {choices}")
        
        # 关键验证：是否为列表
        if isinstance(choices, list):
            print("\n👉 确认：choices 是一个列表 (List)")
            print(f"   列表长度: {len(choices)}")
            if len(choices) > 0:
                first_item = choices
                print(f"   第0个元素类型: {type(first_item)}")
                print(f"   尝试访问 choices.message: {getattr(first_item, 'message', '无 message 属性')}")
                # 尝试提取内容
                content = first_item.message.content
                print(f"\n🎉 成功提取内容: {content}")
            else:
                print("❌ 列表为空")
        else:
            print("❌ 异常：choices 竟然不是列表？")
    else:
        print("❌ 致命：response 对象没有 choices 属性")

except Exception as e:
    print(f"\n❌ 诊断过程中发生错误: {e}")

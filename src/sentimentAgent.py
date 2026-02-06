import os
from langchain_openai import ChatOpenAI # 或者使用 langchain_ollama
from langchain.prompts import ChatPromptTemplate

class SentimentAgent:
    def __init__(self):
        # 这里配置您的 DeepSeek API 或本地模型
        # 如果是本地 Ollama: base_url="http://localhost:11434/v1", api_key="ollama"
        self.llm = ChatOpenAI(
            model="deepseek-chat", 
            api_key="YOUR_DEEPSEEK_API_KEY", 
            base_url="https://api.deepseek.com/v1",
            temperature=0.1 # 降低随机性
        )

    def analyze(self, news_text):
        if not news_text:
            return 0  # 无新闻则中性

        # 核心 Prompt：强制要求输出分数
        template = """
        你是一名专业的加密货币量化交易员。请根据以下新闻快讯，分析市场情绪。
        
        新闻内容：
        {news}
        
        请严格遵循以下输出格式，只输出一个 JSON 对象，不要有其他废话：
        {{
            "sentiment_score": float,  // 范围 -1.0 (极度利空) 到 1.0 (极度利好)
            "reason": "string",        // 简短理由 (50字以内)
            "confidence": float        // 置信度 0.0 - 1.0
        }}
        """
        
        prompt = ChatPromptTemplate.from_template(template)
        chain = prompt | self.llm
        
        try:
            response = chain.invoke({"news": news_text})
            # 这里通常需要加一个 JSON 解析器，这里简化处理
            import json
            # 清洗一下可能存在的 markdown 符号
            content = response.content.replace("```json", "").replace("```", "")
            data = json.loads(content)
            return data
        except Exception as e:
            print(f"AI 分析失败: {e}")
            return {"sentiment_score": 0, "confidence": 0}

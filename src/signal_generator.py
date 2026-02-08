"""
信号生成模块（AI 分析层）。

职责：调用大模型对新闻/舆情做情感与事件分析，产出 sentiment_score、confidence、
reason 等字段，供策略引擎生成交易决策。配置见 config_signal.yaml。
"""
import yaml
import json
import re
from openai import OpenAI
from .config import Config


class SignalGenerator:
    def __init__(self, config_path="src/config_signal.yaml", logger=None):
        # 1. 加载配置
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
        except Exception as e:
            print(f"❌ 配置文件加载失败: {e}")
            raise

        self.logger = logger
        
        # 2. 初始化客户端
        api_key = Config.DEEPSEEK_API_KEY or Config.OPENAI_API_KEY
        base_url = Config.DEEPSEEK_BASE_URL if Config.DEEPSEEK_API_KEY else "https://api.openai.com/v1"
        
        if not api_key:
            print("⚠️ [警告] 未检测到 API Key，AI 分析将无法进行")
        else:
            print(f"🔌 信号生成器已连接: {Config.LLM_MODEL_NAME}")
            
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def _construct_prompt(self, news_text, symbol):
        """构建提示词，明确指定币种名称以确保分析准确性"""
        instruction = self.config['sentiment_analysis'].get('output_format_instruction', '')
        examples = self.config['sentiment_analysis'].get('examples', [])
        examples_str = "\n".join([f"输入: {ex['input']}\n输出: {ex['output']}" for ex in examples])
        
        # 在 prompt 中明确强调币种名称，确保 AI 知道正在分析哪个币
        symbol_emphasis = f"\n\n【重要提示】请专注于分析 {symbol} (或 {symbol}-USD) 相关的新闻内容，忽略其他币种的新闻。"
            
        return f"{instruction}{symbol_emphasis}\n\n### 参考示例:\n{examples_str}\n\n### 待分析新闻:\n{news_text}"

    def analyze_market_sentiment(self, symbol="BTC", cleaned_news_list=None):
        """
        分析市场情绪
        
        Args:
            symbol: 交易对符号
            cleaned_news_list: 清洗后的新闻列表（来自 DataProcessor）
            
        Returns:
            结构化信号字典
        """
        # 1. 处理新闻数据
        if not cleaned_news_list:
            print(f"   ⚠️ {symbol} 新闻数据为空，跳过 AI 分析")
            return None
        
        # 将新闻列表转换为文本格式
        news_text_parts = []
        for news in cleaned_news_list:
            source = news.get('source', 'unknown')
            title = news.get('title', '')
            content = news.get('cleaned_content', title)
            news_text_parts.append(f"[{source.upper()}] {content}")
        
        news_text = "\n".join(news_text_parts)
        
        if len(news_text) < 10:
            print(f"   ⚠️ {symbol} 新闻数据不足，跳过 AI 分析")
            return None
            
        # 2. 构建 Prompt（传入 symbol 以确保 AI 知道正在分析哪个币）
        system_prompt = self.config['sentiment_analysis']['system_prompt']
        user_prompt = self._construct_prompt(news_text, symbol)
        
        print(f"   🧠 [AI 分析师] 正在阅读 {symbol} 的新闻并思考...")
        
        try:
            # 3. 调用 LLM
            response = self.client.chat.completions.create(
                model=Config.LLM_MODEL_NAME, 
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={'type': 'json_object'}, 
                temperature=0.1,
                max_tokens=1024
            )
            
            # =========== 【核心修复】 ===========
            # 之前的错误是因为写成了 response.choices.message
            # 正确写法必须加 ，因为 choices 是一个列表！
            
            if not response.choices:
                print("   ❌ API 返回了空列表")
                return None
                
            # ✅ 这里加了 
            content = response.choices[0].message.content
            # ===================================
            
            # 4. 结果清洗与解析
            clean_json = re.sub(r'```json\s*|\s*```', '', content).strip()
            signal_data = json.loads(clean_json)
            
            signal_data['symbol'] = symbol
            # 统计数据源状态
            sources = {}
            for news in cleaned_news_list:
                source = news.get('source', 'unknown')
                sources[source] = sources.get(source, 0) + 1
            signal_data['source_status'] = sources
            
            # 5. 记录 AI 观点日志
            if self.logger:
                self.logger.log_ai_opinion(symbol, signal_data)
            
            return signal_data

        except json.JSONDecodeError:
            print(f"   ❌ [解析错误] LLM 返回了非 JSON 格式: {content[:50]}...")
            return None
        except AttributeError as e:
            print(f"   ❌ [代码错误] 属性访问失败: {e}")
            print(f"   🔍 调试: response.choices 类型是 {type(response.choices)}")
            return None
        except Exception as e:
            print(f"   ❌ [未知错误] {e}")
            return None
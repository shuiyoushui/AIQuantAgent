import yaml
import json
import re
from openai import OpenAI
from .config import Config
from .data_loader import DataLoader

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
        self.loader = DataLoader(logger=logger)
        
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

    def analyze_market_sentiment(self, symbol="BTC"):
        """获取新闻 -> 调用LLM -> 返回结构化信号"""
        # 1. 获取新闻
        raw_news, source_status = self.loader.fetch_news_context(symbol)
        
        if len(raw_news) < 10 or "暂无" in raw_news:
            print(f"   ⚠️ {symbol} 新闻数据不足，跳过 AI 分析")
            return None
            
        # 2. 构建 Prompt（传入 symbol 以确保 AI 知道正在分析哪个币）
        system_prompt = self.config['sentiment_analysis']['system_prompt']
        user_prompt = self._construct_prompt(raw_news, symbol)
        
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
            signal_data['source_status'] = source_status
            
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
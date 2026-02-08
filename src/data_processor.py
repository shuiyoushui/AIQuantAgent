"""
数据处理器 (Data Processor Layer)
职责：负责数据格式归一、对齐、去噪
"""
import pandas as pd
import re
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple
from bs4 import BeautifulSoup


class DataProcessor:
    """数据处理器：负责数据清洗、格式归一和对齐"""
    
    def __init__(self, logger=None):
        print("🧹 [数据清洗] 初始化数据处理器...")
        self.logger = logger

    def process_market_data(self, raw_data: Optional[List[List]]) -> Optional[pd.DataFrame]:
        """
        将原始 K 线数据转为标准 Pandas DataFrame
        
        Args:
            raw_data: 原始 OHLCV 数据，格式: [[timestamp, open, high, low, close, volume], ...]
            
        Returns:
            清洗后的 DataFrame，包含列: timestamp, open, high, low, close, volume
            如果输入为 None 或空，返回 None
        """
        if not raw_data or len(raw_data) == 0:
            if self.logger:
                print("   ⚠️ [数据清洗] 原始市场数据为空")
            return None

        try:
            # 转换为 DataFrame
            df = pd.DataFrame(raw_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # 转换时间戳为 datetime
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            # 去噪：剔除异常数据
            initial_count = len(df)
            
            # 剔除 Volume 为 0 的行
            df = df[df['volume'] > 0]
            
            # 剔除价格为负或为 0 的行
            df = df[(df['open'] > 0) & (df['high'] > 0) & (df['low'] > 0) & (df['close'] > 0)]
            
            # 剔除异常价格（high < low 或 close 不在 [low, high] 范围内）
            df = df[df['high'] >= df['low']]
            df = df[(df['close'] >= df['low']) & (df['close'] <= df['high'])]
            df = df[(df['open'] >= df['low']) & (df['open'] <= df['high'])]
            
            # 按时间升序排列
            df = df.sort_values('timestamp').reset_index(drop=True)
            
            cleaned_count = len(df)
            removed_count = initial_count - cleaned_count
            
            if self.logger:
                if removed_count > 0:
                    print(f"   ✅ [数据清洗] 市场数据清洗完成: 原始 {initial_count} 条 → 清洗后 {cleaned_count} 条 (移除 {removed_count} 条异常数据)")
                else:
                    print(f"   ✅ [数据清洗] 市场数据清洗完成: {cleaned_count} 条数据，无异常")
            
            return df
            
        except Exception as e:
            if self.logger:
                print(f"   ❌ [数据清洗] 处理市场数据失败: {e}")
            return None

    def process_news_data(self, raw_news_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        清洗新闻数据
        
        Args:
            raw_news_list: 原始新闻列表
            
        Returns:
            清洗后的新闻列表
        """
        if not raw_news_list:
            return []

        cleaned_news = []
        
        for news_item in raw_news_list:
            try:
                # 提取原始内容
                raw_content = news_item.get('raw_content', news_item.get('title', ''))
                
                # 清洗文本
                cleaned_content = self._clean_text(raw_content)
                
                # AI 预处理（提取关键实体）
                normalized_content = self._ai_normalize_content(cleaned_content)
                
                # 构建清洗后的新闻项
                cleaned_item = {
                    'title': news_item.get('title', ''),
                    'source': news_item.get('source', 'unknown'),
                    'timestamp': news_item.get('timestamp'),
                    'cleaned_content': cleaned_content,
                    'normalized_content': normalized_content,
                    'url': news_item.get('url', '')
                }
                
                if cleaned_content:  # 只保留有内容的新闻
                    cleaned_news.append(cleaned_item)
                    
            except Exception as e:
                if self.logger:
                    print(f"   ⚠️ [数据清洗] 清洗单条新闻失败: {e}")
                continue

        # 按数据源分组记录日志
        if self.logger:
            sources = {}
            for item in cleaned_news:
                source = item['source']
                sources[source] = sources.get(source, 0) + 1
            
            for source, count in sources.items():
                source_name_map = {
                    'yahoo': 'Yahoo财经',
                    'google': 'Google新闻',
                    'rss_coindesk': '行业RSS',
                    'rss_cointelegraph': '行业RSS'
                }
                source_name = source_name_map.get(source, source)
                self.logger.log_data_cleaning(
                    cleaned_news[0].get('title', '')[:10] if cleaned_news else 'UNKNOWN',
                    source_name,
                    True,
                    len(raw_news_list),
                    count
                )

        return cleaned_news

    def _clean_text(self, raw_text: str) -> str:
        """
        清洗文本内容（去除 HTML 标签、URL、多余空格）
        
        Args:
            raw_text: 原始文本
            
        Returns:
            清洗后的文本
        """
        if not raw_text:
            return ""
        
        try:
            text = str(raw_text)
            
            # 尝试解析 HTML（如果包含 HTML 标签）
            if '<' in text and '>' in text:
                soup = BeautifulSoup(text, "html.parser")
                text = soup.get_text(separator=" ")
            
            # 去除 URL
            text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
            
            # 去除 Google News 特有的噪音
            text = re.sub(r'View Full Coverage on Google News', '', text, flags=re.IGNORECASE)
            
            # 去除多余空格和换行
            text = re.sub(r'\s+', ' ', text).strip()
            
            return text
            
        except Exception as e:
            # 如果清洗失败，返回原始文本
            return str(raw_text)

    def _ai_normalize_content(self, text: str) -> str:
        """
        AI 预处理接口：用于未来接入 LLM 提取关键实体
        目前先用简单逻辑实现
        
        Args:
            text: 清洗后的文本
            
        Returns:
            归一化后的内容
        """
        if not text:
            return ""
        
        # 当前实现：简单的大小写归一和标点处理
        # 未来可以接入 LLM 提取关键实体（币种、事件类型等）
        normalized = text.lower()
        
        # 移除特殊字符，保留字母数字和基本标点
        normalized = re.sub(r'[^\w\s.,!?]', '', normalized)
        
        return normalized

    def align_data(self, market_df: Optional[pd.DataFrame], news_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        数据对齐：将新闻的时间戳映射到最近的一根 K 线时间上（Forward Fill）
        
        Args:
            market_df: 市场数据 DataFrame
            news_list: 清洗后的新闻列表
            
        Returns:
            对齐后的数据集，包含：
            - market_data: DataFrame（可能包含新闻列）
            - news_mapping: 新闻到 K 线的映射关系
        """
        result = {
            'market_data': market_df,
            'news_mapping': {},
            'aligned_news': []
        }
        
        if market_df is None or len(market_df) == 0:
            if self.logger:
                print("   ⚠️ [数据对齐] 市场数据为空，无法对齐")
            return result
        
        if not news_list:
            if self.logger:
                print("   ⚠️ [数据对齐] 新闻数据为空，无需对齐")
            return result

        try:
            # 转换新闻时间戳为 datetime
            news_with_dt = []
            for news in news_list:
                timestamp = news.get('timestamp')
                if timestamp:
                    if isinstance(timestamp, (int, float)):
                        dt = pd.to_datetime(timestamp, unit='s')
                    elif isinstance(timestamp, tuple):  # RSS 的 published_parsed
                        dt = pd.to_datetime(datetime(*timestamp[:6]))
                    else:
                        dt = pd.to_datetime(timestamp)
                    news_with_dt.append({
                        **news,
                        'datetime': dt
                    })
            
            if not news_with_dt:
                return result
            
            # 为每条新闻找到最近的 K 线时间（Forward Fill）
            market_timestamps = market_df['timestamp'].values
            
            for news in news_with_dt:
                news_dt = news['datetime']
                
                # 找到最近的 K 线时间（新闻时间 <= K 线时间）
                # 如果新闻时间晚于所有 K 线，则映射到最后一根 K 线
                matching_indices = market_df[market_df['timestamp'] >= news_dt].index
                
                if len(matching_indices) > 0:
                    # 找到第一个 >= 新闻时间的 K 线
                    kline_idx = matching_indices[0]
                    kline_timestamp = market_df.loc[kline_idx, 'timestamp']
                else:
                    # 如果新闻时间晚于所有 K 线，映射到最后一根
                    kline_idx = len(market_df) - 1
                    kline_timestamp = market_df.iloc[-1]['timestamp']
                
                # 记录映射关系
                kline_key = str(kline_timestamp)
                if kline_key not in result['news_mapping']:
                    result['news_mapping'][kline_key] = []
                
                result['news_mapping'][kline_key].append(news)
                result['aligned_news'].append({
                    'news': news,
                    'kline_index': kline_idx,
                    'kline_timestamp': kline_timestamp
                })
            
            if self.logger:
                print(f"   ✅ [数据对齐] 成功对齐 {len(news_with_dt)} 条新闻到 {len(result['news_mapping'])} 根 K 线")
            
            return result
            
        except Exception as e:
            if self.logger:
                print(f"   ❌ [数据对齐] 数据对齐失败: {e}")
            return result

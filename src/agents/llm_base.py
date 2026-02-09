"""
LLM 驱动基类：为不同 Agent 提供独立的大模型和提示词配置。

每个 Agent 的 config YAML 可指定：
- llm.model_name: 模型名称
- llm.api_key_env: 环境变量名（如 DEEPSEEK_API_KEY、OPENAI_API_KEY）
- llm.base_url: API 地址（可选，默认根据 provider）
- llm.temperature, max_tokens
- system_prompt, user_prompt_template 等
"""
import os
import re
import json
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from openai import OpenAI


def _get_api_key(env_name: str) -> Optional[str]:
    """从环境变量获取 API Key"""
    val = os.getenv(env_name, "")
    return val.strip() if val else None


def _get_base_url(config: Dict, api_key_env: str) -> str:
    """根据配置或 api_key_env 推断 base_url"""
    if config.get("base_url"):
        return config["base_url"]
    if "DEEPSEEK" in api_key_env.upper():
        return os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    if "OPENAI" in api_key_env.upper():
        return "https://api.openai.com/v1"
    return "https://api.openai.com/v1"


class LLMAgentBase:
    """LLM 驱动 Agent 基类：从独立配置文件加载模型和提示词"""

    CONFIG_DIR = Path(__file__).resolve().parent.parent / "config" / "agents"
    CONFIG_FILENAME: Optional[str] = None  # 子类覆盖，如 "sentiment_analyst.yaml"

    def __init__(self, config_path: Optional[str] = None, logger=None, backtest_mode: bool = False):
        self.logger = logger
        self.backtest_mode = backtest_mode
        self.client: Optional[OpenAI] = None
        self.config: Dict[str, Any] = {}

        path = config_path
        if not path and self.CONFIG_FILENAME and self.CONFIG_DIR.exists():
            path = str(self.CONFIG_DIR / self.CONFIG_FILENAME)
        if path and Path(path).exists():
            self._load_config(path)
            if not backtest_mode:
                self._init_client()

    def _load_config(self, path: str) -> None:
        with open(path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f) or {}

    def _init_client(self) -> None:
        llm_cfg = self.config.get("llm", {})
        api_key_env = llm_cfg.get("api_key_env", "DEEPSEEK_API_KEY")
        api_key = _get_api_key(api_key_env) or _get_api_key("OPENAI_API_KEY")
        if not api_key:
            if self.logger:
                print(f"   ⚠️ [{self.__class__.__name__}] 未检测到 API Key ({api_key_env})，LLM 将不可用")
            return
        base_url = llm_cfg.get("base_url") or _get_base_url(llm_cfg, api_key_env)
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        model = llm_cfg.get("model_name", "deepseek-chat")
        if self.logger:
            print(f"   🔌 [{self.__class__.__name__}] 已连接: {model}")

    def call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        response_format: Optional[Dict] = None,
    ) -> Optional[Dict[str, Any]]:
        """调用 LLM，返回解析后的 JSON（若指定 response_format）或原始文本"""
        if self.backtest_mode or self.client is None:
            return None
        llm_cfg = self.config.get("llm", {})
        model = llm_cfg.get("model_name", "deepseek-chat")
        temp = temperature if temperature is not None else llm_cfg.get("temperature", 0.1)
        max_tok = max_tokens if max_tokens is not None else llm_cfg.get("max_tokens", 1024)
        kwargs = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temp,
            "max_tokens": max_tok,
        }
        if response_format is None and self.config.get("llm", {}).get("response_format") != "text":
            kwargs["response_format"] = {"type": "json_object"}
        elif response_format:
            kwargs["response_format"] = response_format

        try:
            resp = self.client.chat.completions.create(**kwargs)
            content = resp.choices[0].message.content
            if kwargs.get("response_format", {}).get("type") == "json_object":
                content = re.sub(r"```json\s*|\s*```", "", content).strip()
                return json.loads(content)
            return {"raw": content}
        except Exception as e:
            if self.logger:
                print(f"   ❌ [{self.__class__.__name__}] LLM 调用失败: {e}")
            return None

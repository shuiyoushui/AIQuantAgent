"""
策略注册表与工厂模块。

职责：维护 strategy_id -> 策略类的映射；根据配置中的「已启用策略」列表，
返回当前应使用的策略实例，供主流程（main）调用。新增策略时在此注册，
注释掉策略时在 config_strategy.yaml 中将对应项设为 enabled: false。
"""

import os
from typing import Any, Optional

import yaml

# 延迟导入，避免循环依赖
def _get_event_driven_class():
    from src.strategy_engine import StrategyEngine
    return StrategyEngine

def _get_rsi_adapter_class():
    from src.strategy_adapters import RSIStrategyAdapter
    return RSIStrategyAdapter

def _get_hybrid_adapter_class():
    from src.strategy_adapters import HybridStrategyAdapter
    return HybridStrategyAdapter


# strategy_id -> 策略类 + 默认配置路径（可选）
REGISTRY: dict[str, dict[str, Any]] = {
    "event_driven": {
        "class_factory": _get_event_driven_class,
        "default_config_path": "src/config_strategy.yaml",
        "description": "事件驱动趋势跟踪：AI 情绪分 + 技术指标过滤",
    },
    "rsi": {
        "class_factory": _get_rsi_adapter_class,
        "default_config_path": None,
        "description": "RSI 超买超卖：仅技术面",
    },
    "hybrid": {
        "class_factory": _get_hybrid_adapter_class,
        "default_config_path": None,
        "description": "混合策略：新闻 + 交易所价格共振",
    },
}


def get_strategy(
    strategy_id: str,
    config_path: Optional[str] = None,
    logger: Optional[Any] = None,
) -> Any:
    """
    根据 strategy_id 创建策略实例。

    Args:
        strategy_id: 策略唯一 ID，需已在 REGISTRY 中注册。
        config_path: 策略配置文件路径；不传则使用该策略的 default_config_path。
        logger: 日志器，传给需要 logger 的策略。

    Returns:
        策略实例（具备 generate_trade_decision / execute 等主流程所需接口）。
    """
    if strategy_id not in REGISTRY:
        raise ValueError(f"未知策略 ID: {strategy_id}，已注册: {list(REGISTRY.keys())}")
    entry = REGISTRY[strategy_id]
    cls_factory = entry["class_factory"]
    cls = cls_factory()
    default_path = entry.get("default_config_path")
    path = config_path if config_path is not None else default_path
    if path and os.path.exists(path):
        return cls(config_path=path, logger=logger)
    return cls(config_path=None, logger=logger)


def get_enabled_strategy_id(config: dict) -> Optional[str]:
    """
    从策略配置中取第一个 enabled: true 的策略 ID，供主流程使用。

    Args:
        config: 来自 config_strategy.yaml 的完整配置（含 strategies 列表）。

    Returns:
        第一个启用策略的 id；若无则返回 None。
    """
    strategies = config.get("strategies") or []
    for s in strategies:
        if isinstance(s, dict) and s.get("enabled", True):
            return s.get("id")
    return None

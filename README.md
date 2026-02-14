# AIQuantAgent

AI 驱动的量化交易系统：**多智能体架构**，支持舆情/技术/基本面因子、LLM 驱动决策、风控中台与事件驱动回测。默认模拟运行，不进行实盘交易。

---

## 目录

- [快速开始](#快速开始)
- [系统架构图](#系统架构图)
- [项目路径与模块说明](#项目路径与模块说明)
- [使用方法](#使用方法)
- [LLM 模型配置](#llm-模型配置)
- [回测使用说明](#回测使用说明)
- [环境与依赖](#环境与依赖)
- [注意事项](#注意事项)

---

## 快速开始

```bash
git clone <repository-url>
cd AIQuantAgent
pip install -r requirements.txt
```

在项目根目录创建 `.env`，配置 API Key：

```env
# 至少配置一个（多智能体架构依赖）
DEEPSEEK_API_KEY=sk-xxx
# 或 OPENAI_API_KEY=sk-xxx
# 或 OPENROUTER_API_KEY=sk-or-v1-xxx  # 用于 Gemini 等
```

运行主流程：

```bash
python main.py
python main.py --symbol BNB        # 指定单币种
python main.py --legacy            # 使用旧版策略注册表流程
```

---

## 系统架构图

### 多智能体架构（当前主流程）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              main.py (主入口)                                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Step 1: DataAgent (数据清洗中台)                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  整合 DataIngestion + DataProcessor                                   │   │
│  │  输出: MarketData (df_price, news_list, metadata)                     │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Step 2: AnalystGroup (因子总线)                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐                     │
│  │ Sentiment   │  │ Technical   │  │ Fundamental     │  → factor_context   │
│  │ Analyst     │  │ Analyst     │  │ Analyst         │                     │
│  │ (LLM)       │  │ (LLM)       │  │ (LLM)           │                     │
│  └─────────────┘  └─────────────┘  └─────────────────┘                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Step 3: StrategyAgent (策略智能体 - LLM 驱动)                                │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  generate_decision(factor_context, market_data) → action, price, qty │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Step 4: RiskManager (风控中台)                                               │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  check(decision, account_state) → passed / rejection                  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Step 5: Execution (模拟执行)                                                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 数据流示意

```
API/CSV 原始数据  →  DataAgent.get_data()  →  MarketData
                                                    │
                                                    ├── df_price (OHLCV)
                                                    ├── news_list
                                                    └── metadata
                                                    │
                                                    ▼
                                          AnalystGroup.produce_factor_context()
                                                    │
                                                    ├── sentiment_score, hot_topic, confidence
                                                    ├── rsi_14, macd_diff, volatility, technical_signal
                                                    └── funding_rate_factor
                                                    │
                                                    ▼
                                          StrategyAgent.generate_decision()
                                                    │
                                                    ▼
                                          RiskManager.check()  →  最终决策
```

---

## 项目路径与模块说明

### 目录结构

```
AIQuantAgent/
├── main.py                    # 主入口
├── run_backtest.py            # 回测入口
├── .env                       # 环境变量（API Key 等）
├── requirements.txt
├── scripts/
│   ├── generate_demo_ohlcv.py # 生成演示 K 线数据
│   └── download_ohlcv.py      # 从 OKX 下载历史 K 线
├── data/                      # 历史数据目录
│   └── demo_ohlcv.csv
├── logs/                      # 日志输出
└── src/
    ├── config.py              # 全局配置（从 .env 读取）
    ├── config_strategy.yaml   # 策略参数（仓位、止盈止损等）
    ├── config_signal.yaml     # 旧版信号配置（部分兼容）
    ├── config/
    │   └── agents/            # 各 Agent 的 LLM 与提示词配置
    │       ├── sentiment_analyst.yaml
    │       ├── technical_analyst.yaml
    │       ├── fundamental_analyst.yaml
    │       └── strategy_agent.yaml
    ├── models/
    │   └── market_data.py     # 标准 MarketData 数据结构
    ├── agents/                # 多智能体
    │   ├── llm_base.py        # LLM 驱动基类
    │   ├── data_agent.py      # 数据清洗智能体
    │   ├── analysts.py        # 因子分析师组
    │   └── strategy_agent.py  # 策略智能体
    ├── data/
    │   └── historical_loader.py  # 历史数据加载
    ├── data_ingestion.py      # 数据采集（OKX、Yahoo、RSS）
    ├── data_processor.py      # 数据清洗
    ├── event_driven_backtest.py  # 事件驱动回测引擎
    ├── backtest_engine.py     # 收益序列绩效计算
    ├── risk_manager.py        # 风控
    ├── strategy_registry.py   # 策略注册表（旧版）
    ├── strategy_adapters.py   # RSI、Hybrid 适配器
    └── ...
```

### 核心模块与路径

| 模块 | 路径 | 说明 |
|------|------|------|
| MarketData | `src/models/market_data.py` | 标准数据结构 |
| DataAgent | `src/agents/data_agent.py` | 数据清洗中台 |
| AnalystGroup | `src/agents/analysts.py` | 因子总线 |
| StrategyAgent | `src/agents/strategy_agent.py` | 策略智能体 |
| RiskManager | `src/risk_manager.py` | 风控中台 |
| EventDrivenBacktest | `src/event_driven_backtest.py` | 事件驱动回测 |
| BacktestEngine | `src/backtest_engine.py` | 收益序列绩效计算 |

---

## 使用方法

### 1. 运行主流程（多智能体）

```bash
# 分析配置中的全部币种
python main.py

# 指定单币种
python main.py --symbol BTC
python main.py --symbol BNB
```

### 2. 使用旧版策略流程

```bash
python main.py --legacy
```

旧版使用 `config_strategy.yaml` 中的 `strategies`，取第一个 `enabled: true` 的策略（event_driven / rsi / hybrid）。

### 3. 修改目标币种

编辑 `src/config.py` 或通过环境变量：

```env
# .env
TARGET_COINS=BTC,ETH,SOL
```

---

## LLM 模型配置

每个 Agent 可**独立配置**大模型和提示词，配置位于 `src/config/agents/`。

### 配置项说明

每个 YAML 的 `llm` 段落：

| 配置项 | 说明 | 示例 |
|--------|------|------|
| model_name | 模型名称 | deepseek-chat、gpt-4、google/gemini-1.5-pro |
| api_key_env | 环境变量名 | DEEPSEEK_API_KEY、OPENAI_API_KEY、OPENROUTER_API_KEY |
| base_url | API 地址 | 留空则按 api_key_env 自动推断 |
| temperature | 温度 | 0.1 |
| max_tokens | 最大 token | 1024 |

### 方案一：DeepSeek

`.env`：

```env
DEEPSEEK_API_KEY=sk-xxx
```

`src/config/agents/sentiment_analyst.yaml`：

```yaml
llm:
  model_name: "deepseek-chat"
  api_key_env: "DEEPSEEK_API_KEY"
  base_url: null
  temperature: 0.1
  max_tokens: 1024
```

### 方案二：OpenAI

`.env`：

```env
OPENAI_API_KEY=sk-xxx
```

YAML 中：

```yaml
llm:
  model_name: "gpt-4"
  api_key_env: "OPENAI_API_KEY"
  base_url: null
```

### 方案三：OpenRouter（Gemini 等）

OpenRouter 提供 OpenAI 兼容接口，可调用 Gemini、Claude 等。Key 需在 [OpenRouter](https://openrouter.ai/keys) 获取，**不是** Google AI Studio 的 Key。

`.env`：

```env
OPENROUTER_API_KEY=sk-or-v1-xxx
```

YAML 中：

```yaml
llm:
  model_name: "google/gemini-1.5-pro"   # 或 gemini-1.5-flash
  api_key_env: "OPENROUTER_API_KEY"
  base_url: "https://openrouter.ai/api/v1"
  temperature: 0.1
  max_tokens: 1024
```

### 各 Agent 配置文件

| 文件 | 对应 Agent |
|------|------------|
| `src/config/agents/sentiment_analyst.yaml` | 舆情分析师 |
| `src/config/agents/technical_analyst.yaml` | 技术分析师 |
| `src/config/agents/fundamental_analyst.yaml` | 基本面分析师 |
| `src/config/agents/strategy_agent.yaml` | 策略智能体 |

可分别为不同 Agent 指定不同模型（如舆情用 Gemini、策略用 DeepSeek）。

### 自定义提示词

每个 YAML 还包含 `system_prompt`、`output_format_instruction`、`examples` 等，可直接编辑以调整 Agent 行为。

---

## 回测使用说明

### 模式一：事件驱动回测（策略 + 历史 K 线）

逐 bar 运行多智能体策略，支持风控拒绝记录。

**1. 准备历史数据**

```bash
# 方式 A：生成演示数据（无需 API）
python scripts/generate_demo_ohlcv.py --output data/demo_ohlcv.csv --days 90

# 方式 B：从 OKX 下载（需配置 OKX API）
python scripts/download_ohlcv.py --symbol BTC --limit 500 --output data/btc_ohlcv.csv
```

**2. 运行回测**

```bash
# 使用 CSV 数据
python run_backtest.py --mode event --data data/demo_ohlcv.csv --symbol BTC

# 从 API 获取数据
python run_backtest.py --mode event --source api --symbol BTC --limit 300

# 指定初始资金、输出指标 JSON、保存收益序列
python run_backtest.py --mode event --data data/demo_ohlcv.csv --symbol BTC \
  --initial_balance 100000 --output results/metrics.json --save_returns data/returns.csv
```

**事件回测参数：**

| 参数 | 说明 | 默认 |
|------|------|------|
| --mode | event / returns | event |
| --data | K 线 CSV 路径 | data/demo_ohlcv.csv |
| --source | csv / api | csv |
| --symbol | 标的 | BTC |
| --limit | API 模式 K 线数量 | 500 |
| --initial_balance | 初始资金 | 100000 |
| --output | 指标 JSON 输出路径 | - |
| --save_returns | 收益序列 CSV 路径 | - |

### 模式二：收益序列回测

对已有策略/基准收益序列计算绩效指标。

**CSV 格式要求：** 含 `date`、`strategy_return`、`benchmark_return` 列（列名可用参数覆盖）。

```bash
python run_backtest.py --mode returns --data_csv path/to/returns.csv

# 指定列名
python run_backtest.py --mode returns --data_csv returns.csv \
  --strategy_col strategy_return --benchmark_col benchmark_return --date_col date

# 无 CSV 时使用模拟数据
python run_backtest.py --mode returns --start 2024-01-01 --end 2024-12-31
```

**returns 模式参数：**

| 参数 | 说明 |
|------|------|
| --data_csv | 收益 CSV 路径 |
| --strategy_col | 策略收益列名 |
| --benchmark_col | 基准收益列名 |
| --date_col | 日期列名 |
| --start, --end | 时间范围 |
| --granularity | 1d / 1m / tick |

### 回测输出指标

- 收益：总收益、年化收益、超额收益
- 风险：夏普、索提诺、波动率、Alpha、Beta
- 回撤：最大回撤及区间
- 胜率：胜率、盈亏比

---

## 环境与依赖

- **Python**：3.10+
- **依赖**：见 `requirements.txt`（pandas、numpy、ccxt、yfinance、openai、pyyaml 等）

---

## 注意事项

1. **模拟模式**：当前不进行实盘交易，仅输出决策与模拟执行信息。
2. **API Key**：至少配置一个 LLM 的 API Key，推荐 DeepSeek 或 OpenRouter。
3. **网络**：数据采集与 AI 调用需访问外网。
4. **回测数据**：事件驱动回测需至少 50 条 K 线；可先用 `generate_demo_ohlcv.py` 生成演示数据。
5. **Gemini 直接接入**：Google AI Studio 的 Key（`AIzaSy...`）不能直接用于 OpenAI 客户端，需通过 OpenRouter 等 OpenAI 兼容代理。

---
##许可证信息
MIT License

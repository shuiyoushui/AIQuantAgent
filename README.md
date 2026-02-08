# AIQuantAgent

AI 驱动的量化交易系统：**模块化架构**，支持多策略切换（事件驱动 / RSI / 混合）、多层过滤与风控，以及离线回测。默认模拟运行，不进行实盘交易。

---

## 快速开始

```bash
git clone <repository-url>
cd AIQuantAgent
pip install -r requirements.txt
```

在项目根目录创建 `.env`，至少配置 AI API（事件驱动/混合策略依赖）：

```env
DEEPSEEK_API_KEY=your_key
# 或 OPENAI_API_KEY=your_key
```

运行主流程（按 `src/config_strategy.yaml` 中第一个 `enabled: true` 的策略分析目标币种）：

```bash
python main.py
python main.py --symbol BNB/USDT   # 指定单币种
```

运行离线回测（默认使用模拟收益序列）：

```bash
python run_backtest.py
```

---

## 架构概览

系统采用**分层 + 可插拔策略**的设计：数据层 → 信号层 → 策略层 → 风控层 → 日志，策略通过注册表按配置启用，便于扩展与切换。

```
                    ┌─────────────────────────────────────┐
                    │         main.py (AIQuantAgent)       │
                    │  协调流程 · 会话 · 策略选择           │
                    └─────────────────┬───────────────────┘
                                      │
    ┌─────────────────────────────────┼─────────────────────────────────┐
    │                                 │                                 │
    ▼                                 ▼                                 ▼
┌───────────────┐            ┌─────────────────┐            ┌─────────────────┐
│  数据层       │            │  信号层         │            │  策略层         │
│ DataIngestion │───────────▶│ SignalGenerator │───────────▶│ StrategyRegistry│
│ DataProcessor │  市场+新闻  │ (AI 情绪分析)   │  ai_signal │ (按配置取策略)   │
└───────────────┘            └─────────────────┘            └────────┬────────┘
                                                                     │
    ┌────────────────────────────────────────────────────────────────┤
    │                        StrategyEngine / Adapters               │
    │  event_driven │ rsi │ hybrid  → generate_trade_decision        │
    └────────────────────────────────────────────────────────────────┘
                                      │
    ┌─────────────────────────────────┼─────────────────────────────────┐
    │                                 ▼                                 │
    │                    ┌─────────────────────┐                         │
    │                    │  风控层             │                         │
    │                    │  RiskManager        │                         │
    │                    │  check_risk()       │                         │
    │                    └──────────┬─────────┘                         │
    │                                │                                  │
    │                                ▼                                  │
    │                    ┌─────────────────────┐                         │
    │                    │  日志层             │  配置层                  │
    │                    │  SystemLogger       │  Config + YAML          │
    │                    └─────────────────────┘                         │
    └───────────────────────────────────────────────────────────────────┘
```

---

## 模块说明与使用

每个模块**职责单一**，通过主流程或脚本组合使用；下表给出「价值」与「如何使用」。

| 模块 | 文件 | 价值 | 如何使用 |
|------|------|------|----------|
| **配置** | `src/config.py` | 统一从 `.env` 读 API、交易对、风控等常量 | 各模块在初始化或运行时读取 `Config.XXX`，无需改代码即可调参 |
| **数据采集** | `src/data_ingestion.py` | 对接交易所(OKX)、yfinance、RSS 等，拉取原始行情与新闻 | 主流程在 `analyze_single_asset` 中调用 `fetch_raw_market_data`、`fetch_raw_news`、`fetch_raw_ticker_data`，仅负责「拿数据」 |
| **数据清洗** | `src/data_processor.py` | 将原始数据转为标准 DataFrame、清洗新闻、对齐时间 | 主流程调用 `process_market_data`、`process_news_data`、`align_data`，为下游提供干净输入 |
| **AI 信号** | `src/signal_generator.py` | 用大模型对新闻做情绪与事件分析，输出情绪分、置信度等 | 主流程调用 `analyze_market_sentiment(coin, cleaned_news)`，供事件驱动/混合策略使用；配置见 `src/config_signal.yaml` |
| **策略注册表** | `src/strategy_registry.py` | 按 ID 注册策略类，按配置返回「当前启用」的策略实例 | 主流程启动时读 `config_strategy.yaml` 的 `strategies`，取第一个 `enabled: true` 的 id，调用 `get_strategy(id, config_path, logger)` 得到 `self.trader` |
| **策略引擎** | `src/strategy_engine.py` | 事件驱动趋势跟踪：情绪分 + 置信度 + MA/RSI 过滤，算仓位与止损止盈 | 注册为 `event_driven`；主流程调用 `trader.generate_trade_decision(ai_signal, market_df, ticker_data, ingestion)` 与 `trader.execute(decision)` |
| **策略实现** | `src/strategy.py` | 纯 RSI 超买超卖逻辑，无 AI、无 pandas_ta | 被 `RSIStrategyAdapter` 包装后以 `rsi` 注册；仅依赖 K 线，适合技术面回测或无 API 环境 |
| **策略适配器** | `src/strategy_adapters.py` | 将 RSI、Hybrid 等不同接口统一成主流程需要的 `generate_trade_decision` / `execute`，并读各自配置 | RSI/Hybrid 通过适配器注册；主流程无差别调用 `trader.generate_trade_decision(...)`；各策略参数在 `config_strategy.yaml` 的 `rsi` / `hybrid` 段落配置 |
| **风控** | `src/risk_manager.py` | 对策略输出做持仓比例、回撤、价格偏离等检查，决定是否放行 | 主流程在策略生成后调用 `check_risk(decision, current_market_data, account_balance)`，未通过则拦截并打日志 |
| **日志** | `src/logger.py` | 按日期分文件记录数据源、清洗、AI、策略、市场等 | 各模块接收 `logger` 并调用 `log_strategy` 等；日志目录 `logs/`，便于排查与回放 |
| **回测引擎** | `src/backtest_engine.py` | 对策略/基准收益序列做向量化绩效计算（夏普、回撤、Alpha/Beta 等） | 独立于主流程；通过 `BacktestEngine(strategy_id, start_date, end_date, granularity)` + `load_data(strategy_returns, benchmark_returns)` 或子类 `_load_data()`，再 `compute_metrics()` |
| **回测脚本** | `run_backtest.py` | 命令行入口：支持模拟数据或 CSV 收益序列，输出指标 JSON | 单独执行 `python run_backtest.py [--strategy_id ...] [--data_csv ...] [--output ...]`，不依赖主流程 |

**备用/可选模块**（不参与主流程默认链路）：

- `src/data_loader.py`：备用数据加载接口，可与 DataIngestion 二选一或并存。
- `src/mock_data_loader.py`：无实盘时生成模拟 K 线，用于联调或演示。
- `src/hybridstrategy.py`：混合策略的原始实现（新闻+价格）；主流程通过 `strategy_adapters.HybridStrategyAdapter` 使用主流程已有的 AI 信号与 K 线，不直接依赖此类。

---

## 如何使用

### 1. 运行主流程（单币种或列表）

- 默认：分析 `Config.TARGET_COINS` 中的每个币种（数据采集 → 清洗 → AI 分析 → 策略生成 → 风控 → 模拟执行 + 日志）。
- 指定币种：`python main.py --symbol BNB/USDT`。

主流程会从 `src/config_strategy.yaml` 的 `strategies` 里取**第一个 `enabled: true`** 的策略，通过注册表实例化并用于该次运行。

### 2. 切换策略（启用/注释）

编辑 `src/config_strategy.yaml`：

```yaml
strategies:
  - id: event_driven
    enabled: true   # 当前使用
    name: "事件驱动趋势跟踪"
  - id: rsi
    enabled: false
    name: "RSI 超买超卖"
  - id: hybrid
    enabled: false
    name: "混合新闻+价格"
```

- 只保留一个 `enabled: true`（或把要用的策略放在第一个），即可切换策略。
- 每个策略有独立配置块（`event_driven` / `rsi` / `hybrid`），可单独调整仓位、止盈止损等。

### 3. 策略配置说明（节选）

- **event_driven**：`entry_rules`（情绪阈值、置信度）、`technical_filter`（MA）、`position_sizing`、`risk_management`。
- **rsi**：`rsi_period`、`oversold`、`overbought`，以及 `position_sizing`、`risk_management`。
- **hybrid**：`sentiment_long_threshold`、`sentiment_short_threshold`、`min_confidence`，以及 `position_sizing`、`risk_management`。

完整示例见 `src/config_strategy.yaml`。

### 4. 离线回测

- **仅跑通/演示**：  
  `python run_backtest.py`  
  使用脚本内生成的模拟收益序列。

- **指定区间与颗粒度**：  
  `python run_backtest.py --strategy_id my_strategy --start 2024-01-01 --end 2024-12-31 --granularity 1d`

- **用自有收益数据**：  
  CSV 需包含日期列与策略/基准收益列（默认列名 `date`、`strategy_return`、`benchmark_return`，可用 `--strategy_col`/`--benchmark_col`/`--date_col` 覆盖）。  
  `python run_backtest.py --data_csv path/to/returns.csv --output results/metrics.json`

回测指标包括：总收益、年化收益、超额收益、夏普/索提诺、最大回撤及区间、Alpha/Beta、胜率与盈亏比等（见 `src/backtest_engine.py` 的 `compute_metrics` 返回值）。

### 5. 扩展新策略

1. 在 `src/strategy_registry.py` 的 `REGISTRY` 中增加一项（`strategy_id` → 类工厂 + 可选 `default_config_path`）。
2. 在 `src/config_strategy.yaml` 的 `strategies` 中增加对应 id，并设置 `enabled`。
3. 若新策略接口与主流程不一致，在 `src/strategy_adapters.py` 中写适配器，实现 `generate_trade_decision` 与 `execute`，并在注册表中指向该适配器类。

---

## 环境与依赖

- **Python**：3.10+（推荐 3.13）。策略层使用纯 pandas 计算 RSI，无 pandas_ta 依赖。
- **依赖**：见 `requirements.txt`（含 pandas、numpy、ccxt、yfinance、openai、pyyaml 等）。

---

## 日志目录

日志写入 `logs/`，按日期分文件，例如：

- `strategy_YYYY-MM-DD.jsonl` — 策略生成记录  
- `ai_opinion_YYYY-MM-DD.jsonl` — AI 观点  
- `data_source_YYYY-MM-DD.jsonl` — 数据源  
- `market_data_YYYY-MM-DD.csv`、`signals_YYYY-MM-DD.csv` — 市场与信号快照  

---

## 注意事项

1. **模拟模式**：当前不进行实盘交易，仅输出决策与模拟执行信息。
2. **AI 依赖**：事件驱动与混合策略依赖 `SignalGenerator` 的情绪分析，需配置 `DEEPSEEK_API_KEY` 或 `OPENAI_API_KEY`。
3. **策略切换**：修改 `config_strategy.yaml` 中 `strategies` 的 `enabled` 即可，无需改代码。
4. **网络**：数据采集与 AI 调用需访问外网，请保证网络可用。

---

## 许可证

[添加许可证信息]

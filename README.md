# AIQuantAgent

AI 驱动的量化交易系统，结合事件驱动和趋势跟随策略，通过多层过滤机制生成交易决策。

## 系统架构

### 整体架构设计

采用模块化分层架构，包含以下核心模块：

```
┌─────────────────────────────────────────────────┐
│           AIQuantAgent (主控制器)                │
│  - 协调各模块工作流程                            │
│  - 管理会话和日志                                │
└─────────────────────────────────────────────────┘
           │
    ┌──────┼──────┬──────────┬──────────┐
    │      │      │          │          │
    ▼      ▼      ▼          ▼          ▼
┌──────┐ ┌──────┐ ┌────────┐ ┌────────┐ ┌──────┐
│数据  │ │AI    │ │策略    │ │日志    │ │配置  │
│加载  │ │分析  │ │引擎    │ │系统    │ │管理  │
│模块  │ │模块  │ │模块    │ │模块    │ │模块  │
└──────┘ └──────┘ └────────┘ └────────┘ └──────┘
```

### 核心模块说明

#### 1. DataLoader（数据加载模块）
- **职责**：多源数据获取与清洗
- **数据源**：
  - Yahoo Finance（新闻数据）
  - Google News RSS（新闻数据）
  - 行业 RSS（CoinDesk、CoinTelegraph）
  - OKX 交易所（行情数据、K线数据）
- **功能**：
  - 连接状态监控
  - 数据清洗与标准化
  - 符号标准化（BTC/USDT → BTC）

#### 2. SignalGenerator（AI 信号生成模块）
- **职责**：基于新闻生成情绪信号
- **流程**：
  - 获取新闻文本
  - 构建 Prompt（包含币种标识）
  - 调用 LLM API（DeepSeek/OpenAI）
  - 解析 JSON 输出
- **输出**：
  - `sentiment_score`（-1.0 到 +1.0）
  - `confidence`（置信度）
  - `event_type`（事件类型）
  - `reasoning`（推理过程）
  - `summary`（观点摘要）

#### 3. 策略注册表与多策略（Strategy Registry）
- **职责**：按配置启用/注释策略，统一创建当前使用的策略实例
- **文件**：`src/strategy_registry.py`、`src/config_strategy.yaml` 中的 `strategies` 列表
- **功能**：
  - 支持三种策略：**event_driven**（事件驱动趋势跟踪）、**rsi**（RSI 超买超卖）、**hybrid**（混合新闻+价格共振）
  - 在配置中通过 `enabled: true/false` 切换或「注释掉」某个策略（取第一个 enabled 的策略运行）
  - 每个策略有独立配置段落：仓位比例、止盈止损等

#### 4. StrategyEngine / 策略适配器（策略引擎与适配层）
- **职责**：生成交易决策，提供 `generate_trade_decision` 与 `execute`
- **event_driven**（`src/strategy_engine.py`）：多层过滤器（情绪分、置信度、MA/RSI）、仓位与止损止盈
- **rsi**（`src/strategy.py` + `src/strategy_adapters.py`）：纯 K 线 RSI 超买超卖，无 AI 依赖，无 pandas_ta 依赖
- **hybrid**（`src/strategy_adapters.py`）：主流程的 AI 情绪分 + K 线 24 周期涨跌幅共振做多/做空
- **特点**：模拟模式，不进行实盘交易

#### 5. SystemLogger（日志系统模块）
- **职责**：全流程日志记录与输出
- **日志类型**：
  - 数据源连接日志
  - 数据清洗日志
  - AI 观点日志
  - 策略生成日志
- **存储**：JSONL/CSV 格式，按日期分类

#### 6. Config（配置管理模块）
- **职责**：统一配置管理
- **配置来源**：`.env` 文件 + 代码默认值

## 策略机制

### 策略类型：事件驱动 + 趋势跟随（Event-Driven Trend Following）

### 决策流程（多层过滤）

```
┌─────────────────────────────────────────┐
│  步骤 1: AI 情绪分数判断                │
│  sentiment_score >= 0.6  → BUY         │
│  sentiment_score <= -0.6 → SELL        │
│  否则 → HOLD                            │
└──────────────┬──────────────────────────┘
               │ 通过
               ▼
┌─────────────────────────────────────────┐
│  步骤 2: 置信度过滤器                    │
│  confidence >= 0.8  → 通过              │
│  否则 → HOLD                            │
└──────────────┬──────────────────────────┘
               │ 通过
               ▼
┌─────────────────────────────────────────┐
│  步骤 3: 技术指标过滤器                  │
│  BUY: 价格 > MA20  → 通过                │
│  SELL: 价格 < MA20 → 通过                │
│  否则 → HOLD                            │
└──────────────┬──────────────────────────┘
               │ 通过
               ▼
┌─────────────────────────────────────────┐
│  步骤 4: 生成交易决策                    │
│  - 计算仓位大小                          │
│  - 计算止损/止盈价格                     │
│  - 输出完整策略明细                      │
└─────────────────────────────────────────┘
```

### 策略配置参数（多策略、可启用/注释）

配置文件：`src/config_strategy.yaml`

- **策略列表**：在 `strategies` 中通过 `enabled: true/false` 选择当前使用的策略（取第一个 `enabled: true` 的项）。
- **每个策略有独立配置块**：`event_driven`、`rsi`、`hybrid` 各自包含 `position_sizing`、`risk_management`（以及各自特有参数）。

```yaml
strategies:
  - id: event_driven
    enabled: true
    name: "事件驱动趋势跟踪"
  - id: rsi
    enabled: false
    name: "RSI 超买超卖"
  - id: hybrid
    enabled: false
    name: "混合新闻+价格"

# event_driven 专用
event_driven:
  entry_rules:
    long_threshold: 0.6
    short_threshold: -0.6
    min_confidence: 0.8
  technical_filter:
    enable_ma_filter: true
    ma_period: 20
  position_sizing: { risk_per_trade: 0.02, max_leverage: 1 }
  risk_management: { stop_loss_pct: 0.05, take_profit_pct: 0.10 }

# rsi 专用（RSI 周期与阈值 + 仓位/风控）
rsi:
  rsi_period: 14
  oversold: 30
  overbought: 70
  position_sizing: { risk_per_trade: 0.02, max_leverage: 1 }
  risk_management: { stop_loss_pct: 0.05, take_profit_pct: 0.10 }

# hybrid 专用（情绪阈值 + 仓位/风控）
hybrid:
  sentiment_long_threshold: 0.5
  sentiment_short_threshold: -0.5
  min_confidence: 0.7
  position_sizing: { risk_per_trade: 0.02, max_leverage: 1 }
  risk_management: { stop_loss_pct: 0.05, take_profit_pct: 0.10 }
```

### 技术指标计算

使用真实数据源（OKX 交易所）计算：

1. **移动平均线（MA）**
   - 方法：`df['close'].rolling(window=20).mean()`
   - 用途：趋势判断

2. **RSI（相对强弱指数）**
   - 方法：自定义函数计算
   - 周期：14
   - 用途：超买超卖判断

### 仓位管理

- **风险比例**：每次交易风险 2%
- **计算公式**：
  ```
  风险金额 = 账户余额 × 风险比例（2%）
  仓位大小 = 风险金额 / (价格 × 止损比例)
  ```
- **示例**：账户 10000，价格 50000，止损 5%
  - 风险金额 = 10000 × 0.02 = 200
  - 仓位 = 200 / (50000 × 0.05) = 0.08 BTC

### 风险管理

- **止损**：5%（自动计算止损价格）
- **止盈**：10%（自动计算止盈价格）
- **执行**：模拟模式，不进行实盘交易

## 数据流

```
1. 启动系统
   ↓
2. 初始化各模块（DataLoader, SignalGenerator, StrategyEngine, Logger）
   ↓
3. 遍历目标币种列表（BTC, ETH, SOL...）
   ↓
4. 对每个币种：
   ├─ 步骤1: 获取新闻数据（多数据源）
   │   ├─ Yahoo Finance
   │   ├─ Google News
   │   └─ 行业 RSS
   │   ↓
   ├─ 步骤2: AI 分析新闻
   │   ├─ 构建 Prompt
   │   ├─ 调用 LLM API
   │   └─ 解析情绪分数
   │   ↓
   ├─ 步骤3: 获取市场数据
   │   ├─ 现货价格
   │   ├─ 合约价格
   │   └─ K 线数据
   │   ↓
   └─ 步骤4: 生成交易策略
       ├─ 情绪分数过滤
       ├─ 置信度过滤
       ├─ 技术指标过滤
       ├─ 计算仓位
       └─ 计算止损/止盈
   ↓
5. 输出策略决策（模拟模式）
   ↓
6. 记录日志（文件 + 控制台）
```

## 系统特点

### 优势
1. **模块化设计**：各模块职责清晰，易于扩展
2. **多层过滤**：降低误判风险，提高决策质量
3. **完整日志**：全流程记录，便于追踪和调试
4. **模拟模式**：安全测试，不消耗真实资金
5. **真实数据源**：使用真实市场数据，结果可靠

### 安全机制
1. **模拟模式**：不进行实盘交易
2. **多层验证**：情绪分 + 置信度 + 技术指标
3. **风险管理**：止损/止盈自动计算
4. **仓位控制**：固定风险比例

### 可扩展性
- 可添加更多数据源
- 可添加更多技术指标
- 可调整策略参数
- 可接入更多 AI 模型
- **策略可组装**：在 `strategy_registry.py` 注册新 strategy_id，在 `config_strategy.yaml` 的 `strategies` 中增加一项并设置 `enabled` 即可新增或注释策略

---

## 离线回测（BacktestEngine + run_backtest）

### 回测引擎（BacktestEngine）

- **文件**：`src/backtest_engine.py`
- **职责**：对给定策略的收益序列与基准做**向量化**绩效计算，无循环，适合 Web3/币圈策略回测。
- **输入**：`strategy_id`、`start_date`、`end_date`、`granularity`（`1d` / `1m` / `tick`），以及策略收益序列与基准收益序列（通过 `load_data(...)` 注入或子类重写 `_load_data()`）。
- **输出指标**（示例）：
  - 收益：策略总收益、年化收益、超额收益、基准收益、日均超额收益
  - 风险：Alpha、Beta、夏普比率、索提诺比率、策略/基准波动率
  - 回撤：最大回撤、最大回撤区间（起止日期）、超额收益最大回撤
  - 胜率：胜率、盈利/亏损次数、盈亏比、超额收益日胜率

### 回测脚本（run_backtest.py）

- **用途**：单独运行离线回测，不依赖主流程。
- **用法**：
  ```bash
  # 使用默认时间区间 + 模拟收益序列
  python run_backtest.py

  # 指定策略 ID、时间、颗粒度
  python run_backtest.py --strategy_id my_strategy --start 2024-01-01 --end 2024-12-31 --granularity 1d

  # 从 CSV 加载策略/基准收益（需含 date、strategy_return、benchmark_return 列或通过参数指定列名）
  python run_backtest.py --data_csv path/to/returns.csv --output results/metrics.json
  ```
- **说明**：未提供 `--data_csv` 或文件不存在时，会使用脚本内生成的模拟收益序列，便于快速验证。

---

## 安装与使用

### 环境要求
- Python 3.10+ (推荐 3.13，不支持 3.14+)
- 依赖包见 `requirements.txt`

### 安装步骤

1. 克隆项目
```bash
git clone <repository-url>
cd AIQuantAgent
```

2. 安装依赖
```bash
pip install -r requirements.txt
```

3. 配置环境变量
创建 `.env` 文件，配置以下内容：
```env
# 交易所 API（可选，用于获取真实市场数据）
OKX_API_KEY=your_api_key
OKX_SECRET=your_secret
OKX_PASSWORD=your_password

# AI 模型 API（必需）
DEEPSEEK_API_KEY=your_deepseek_key
# 或
OPENAI_API_KEY=your_openai_key

# 其他配置
LLM_PROVIDER=deepseek
USE_MOCK_DATA=True
```

4. 运行程序
```bash
# 使用默认币种列表
python main.py

# 指定单个币种
python main.py --symbol BTC
```

## 日志系统

所有日志保存在 `logs/` 目录下，按日期分类：

- `data_source_YYYY-MM-DD.jsonl` - 数据源连接日志
- `data_cleaning_YYYY-MM-DD.jsonl` - 数据清洗日志
- `ai_opinion_YYYY-MM-DD.jsonl` - AI 观点日志
- `strategy_YYYY-MM-DD.jsonl` - 策略生成日志
- `market_data_YYYY-MM-DD.csv` - 市场数据快照
- `signals_YYYY-MM-DD.csv` - 交易信号记录

## 注意事项

1. **Python 版本**：推荐 Python 3.10+（如 3.13）；策略层已去除 pandas_ta 依赖，使用纯 pandas 计算 RSI
2. **模拟模式**：系统默认运行在模拟模式，不会进行实盘交易
3. **API 配置**：需要配置 AI 模型 API Key 才能进行情绪分析（event_driven / hybrid 依赖 AI 信号）
4. **数据源**：部分数据源可能需要网络访问，确保网络连接正常
5. **策略切换**：在 `src/config_strategy.yaml` 的 `strategies` 中将目标策略的 `enabled` 设为 `true`，并保证其为当前唯一启用的策略（或排在首位）即可

## 许可证

[添加许可证信息]

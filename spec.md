
# AI 基金理财助手 V1

## Technical Specification / Codex Implementation Spec

**版本：** V1.0
**产品类型：** Personal AI Fund & ETF Portfolio Advisor
**核心原则：** Research & Recommendation Only；V1 不自动交易
**默认运行频率：** 每日一次
**目标用户：** 单一用户、自有基金/ETF 投资组合
**主要语言：** Python
**开发方式：** Codex 分阶段实现，每个阶段必须通过测试后再进入下一阶段

---

# 1. 产品目标与边界

V1 的目标不是预测“明天什么基金一定上涨”，而是每天自动完成以下工作：

1. 获取用户当前基金/ETF 持仓与现金余额。
2. 更新持仓及候选基金的最新价格、NAV、历史行情、基本资料。
3. 获取影响当前组合和候选资产的过去 24–72 小时重要财经信息。
4. 获取主要宏观经济数据。
5. 使用 Python 计算量化指标和组合风险。
6. 将市场环境划分为不同 regime。
7. 对现有持仓生成：

   * BUY
   * HOLD
   * REDUCE
   * WATCH
8. 对候选基金生成：

   * Tactical / 短期机会
   * Strategic / 长期机会
9. 根据当前现金、风险限制、已有仓位给出建议投资金额。
10. 生成带证据、风险因素、失效条件和置信度的每日投资报告。
11. 保存所有历史推荐。
12. 自动跟踪推荐之后 1D / 5D / 20D / 60D 的真实结果，以便评估系统有效性。

V1 **禁止**：

* 自动提交券商订单
* Margin / leverage
* Short selling
* Options
* Crypto
* 高频交易
* 日内交易
* 根据单篇新闻直接产生交易指令
* LLM 自己计算收益率、波动率、Sharpe 等关键数字
* LLM 自己猜测价格或基金持仓
* 没有来源的数据进入推荐流程

---

# 2. 核心设计原则

系统必须遵守：

### 2.1 Data First

任何 BUY / REDUCE 建议必须来自以下三层：

```text
Structured Data
        +
Quantitative Signals
        +
Evidence-backed Research
```

不能只来自 LLM。

### 2.2 Python calculates, LLM interprets

Python 负责：

```text
return
momentum
moving average
volatility
drawdown
Sharpe
Sortino
correlation
portfolio exposure
position concentration
risk contribution
ranking
allocation limits
```

LLM 负责：

```text
新闻解释
宏观解释
事件影响
投资 thesis
风险分析
不同时间周期判断
建议理由
失效条件
最终自然语言报告
```

### 2.3 Risk engine has veto power

LLM 可以提出：

```text
BUY QQQ
```

但 Risk Engine 可以强制改成：

```text
HOLD
```

例如：

```text
cash buffer violation
position concentration
portfolio risk too high
data stale
insufficient evidence
signal conflict
```

### 2.4 Recommendation ≠ Order

Recommendation 必须保存为数据库对象。

禁止：

```python
recommendation -> broker API
```

V1 必须：

```text
recommendation
    ↓
database
    ↓
human review
```

---

# 3. 系统总体架构

```text
                          ┌─────────────────────┐
                          │     Scheduler       │
                          │   GitHub Actions    │
                          └──────────┬──────────┘
                                     │
                                     ▼
                         ┌──────────────────────┐
                         │   Daily Run Engine   │
                         └──────────┬───────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              │                     │                     │
              ▼                     ▼                     ▼
     ┌────────────────┐    ┌────────────────┐    ┌────────────────┐
     │ Portfolio Data │    │ Market Data    │    │ Macro / News   │
     │ positions/cash │    │ NAV/prices     │    │ Search / APIs  │
     └───────┬────────┘    └───────┬────────┘    └───────┬────────┘
             │                     │                     │
             └──────────────┬──────┴─────────────┬───────┘
                            │                    │
                            ▼                    ▼
                  ┌────────────────┐    ┌────────────────┐
                  │   Quant Engine │    │ Research Layer │
                  │ Python only    │    │ LLM + Search   │
                  └───────┬────────┘    └───────┬────────┘
                          │                     │
                          └──────────┬──────────┘
                                     ▼
                          ┌────────────────────┐
                          │   Signal Engine    │
                          │ Tactical/Strategic │
                          └──────────┬─────────┘
                                     │
                                     ▼
                          ┌────────────────────┐
                          │ Portfolio Engine   │
                          │ allocation sizing  │
                          └──────────┬─────────┘
                                     │
                                     ▼
                          ┌────────────────────┐
                          │    Risk Engine     │
                          │ deterministic veto │
                          └──────────┬─────────┘
                                     │
                                     ▼
                          ┌────────────────────┐
                          │ Recommendation DB  │
                          └──────────┬─────────┘
                                     │
                          ┌──────────┴──────────┐
                          ▼                     ▼
                ┌────────────────┐     ┌────────────────┐
                │ LLM Report     │     │ Streamlit UI   │
                │ Daily Brief    │     │ Dashboard      │
                └───────┬────────┘     └────────────────┘
                        │
                        ▼
                 Email / Telegram
                 / other notification
```

重要：

**Research Layer 不直接控制 Portfolio Engine。**

流程必须是：

```text
research
→ structured signals
→ deterministic scoring
→ allocation
→ risk validation
→ recommendation
```

而不是：

```text
LLM → BUY
```

---

# 4. 技术栈

建议 V1：

| Layer                  | Technology                                         |
| ---------------------- | -------------------------------------------------- |
| Language               | Python 3.12                                        |
| API                    | FastAPI                                            |
| Models / validation    | Pydantic v2                                        |
| ORM                    | SQLAlchemy 2.x                                     |
| Database               | PostgreSQL                                         |
| Local database         | Docker PostgreSQL                                  |
| Hosted DB              | Supabase / Neon Postgres                           |
| Data analysis          | pandas / numpy                                     |
| Statistics             | scipy                                              |
| Portfolio optimization | PyPortfolioOpt                                     |
| Market data            | provider abstraction                               |
| US ETF/Fund            | OpenBB / Alpha Vantage / other configured provider |
| China fund adapter     | AKShare                                            |
| Macro                  | FRED + official data sources where possible        |
| LLM                    | OpenAI Responses API                               |
| Web research           | OpenAI Web Search tool                             |
| UI                     | Streamlit                                          |
| Scheduler              | GitHub Actions                                     |
| Testing                | pytest                                             |
| HTTP                   | httpx                                              |
| Logging                | structlog or standard logging                      |
| Retry                  | tenacity                                           |
| Configuration          | pydantic-settings                                  |
| Dependency manager     | uv                                                 |
| Formatting             | ruff                                               |
| Type checking          | mypy or pyright                                    |

不要在业务代码中写死某个模型 ID。

使用：

```text
LLM_FAST_MODEL
LLM_REASONING_MODEL
LLM_REVIEW_MODEL
```

环境变量。

这样以后换模型无需改代码。

---

# 5. Repository Structure

Codex 创建：

```text
fund-advisor/
│
├── README.md
├── pyproject.toml
├── .env.example
├── docker-compose.yml
├── Makefile
│
├── app/
│   ├── __init__.py
│   │
│   ├── config.py
│   │
│   ├── main.py
│   │
│   ├── cli.py
│   │
│   ├── logging.py
│   │
│   ├── enums.py
│   │
│   ├── exceptions.py
│   │
│   ├── schemas.py
│   │
│   ├── constants.py
│   │
│   ├── api/
│   │   ├── health.py
│   │   ├── portfolio.py
│   │   ├── instruments.py
│   │   ├── recommendations.py
│   │   └── runs.py
│   │
│   ├── db/
│   │   ├── base.py
│   │   ├── session.py
│   │   ├── models/
│   │   └── migrations/
│   │
│   ├── providers/
│   │   ├── base.py
│   │   ├── market/
│   │   │   ├── base.py
│   │   │   ├── openbb.py
│   │   │   ├── alpha_vantage.py
│   │   │   └── akshare.py
│   │   ├── macro/
│   │   │   ├── base.py
│   │   │   └── fred.py
│   │   └── research/
│   │       └── openai_web.py
│   │
│   ├── portfolio/
│   │   ├── service.py
│   │   ├── snapshot.py
│   │   └── allocation.py
│   │
│   ├── quant/
│   │   ├── returns.py
│   │   ├── momentum.py
│   │   ├── volatility.py
│   │   ├── drawdown.py
│   │   ├── correlation.py
│   │   ├── risk.py
│   │   ├── trend.py
│   │   ├── optimizer.py
│   │   └── regime.py
│   │
│   ├── signals/
│   │   ├── tactical.py
│   │   ├── strategic.py
│   │   ├── macro.py
│   │   ├── news.py
│   │   └── scoring.py
│   │
│   ├── llm/
│   │   ├── client.py
│   │   ├── schemas.py
│   │   ├── prompts/
│   │   │   ├── news_research.md
│   │   │   ├── news_analysis.md
│   │   │   ├── portfolio_analysis.md
│   │   │   └── daily_report.md
│   │   └── services/
│   │       ├── research.py
│   │       ├── analyst.py
│   │       └── reporter.py
│   │
│   ├── recommendations/
│   │   ├── engine.py
│   │   ├── sizing.py
│   │   ├── risk_gate.py
│   │   └── outcome_tracker.py
│   │
│   ├── jobs/
│   │   ├── daily.py
│   │   ├── market_update.py
│   │   └── outcome_update.py
│   │
│   └── notifications/
│       ├── base.py
│       ├── email.py
│       └── telegram.py
│
├── dashboard/
│   ├── Home.py
│   └── pages/
│       ├── portfolio.py
│       ├── daily_report.py
│       ├── recommendations.py
│       ├── performance.py
│       ├── data_health.py
│       └── settings.py
│
├── config/
│   ├── default.yaml
│   └── fund_universe.csv
│
├── scripts/
│   ├── seed.py
│   ├── import_portfolio.py
│   └── run_daily.py
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
│
└── .github/
    └── workflows/
        ├── daily.yml
        └── tests.yml
```

---

# 6. Database Design

使用 PostgreSQL。

所有金额保存：

```text
NUMERIC
```

不要使用 float 保存真实金额。

所有时间：

```text
TIMESTAMPTZ
```

## instruments

```text
id UUID PK
symbol VARCHAR
name VARCHAR
asset_type ENUM
market VARCHAR
currency VARCHAR
provider_symbol VARCHAR
benchmark_symbol VARCHAR NULL
expense_ratio NUMERIC NULL
aum NUMERIC NULL
is_active BOOLEAN
created_at
updated_at
```

asset_type：

```text
ETF
MUTUAL_FUND
INDEX_FUND
```

唯一键：

```text
(symbol, market)
```

---

## accounts

```text
id UUID
name
base_currency
created_at
```

---

## positions

```text
id UUID
account_id FK
instrument_id FK
quantity NUMERIC
average_cost NUMERIC NULL
market_value NUMERIC
as_of TIMESTAMPTZ
```

---

## cash_balances

```text
id UUID
account_id FK
currency
amount NUMERIC
as_of
```

---

## portfolio_snapshots

保存每天完整组合状态。

```text
id UUID
account_id
snapshot_date DATE
total_value
cash_value
invested_value
created_at
```

---

## portfolio_snapshot_positions

```text
snapshot_id
instrument_id
quantity
price
market_value
portfolio_weight
```

---

## price_history

```text
instrument_id
date
open
high
low
close
adjusted_close
volume
source
```

唯一键：

```text
(instrument_id, date)
```

---

## instrument_metrics

每日计算后的量化数据。

```text
instrument_id
date

return_1d
return_5d
return_20d
return_60d
return_252d

volatility_20d
volatility_60d

max_drawdown_252d

ma_20
ma_50
ma_200

distance_ma_20
distance_ma_50
distance_ma_200

momentum_score
trend_score
risk_score

sharpe_252d
sortino_252d

created_at
```

---

## portfolio_metrics

```text
snapshot_date

volatility
max_drawdown
sharpe
cash_ratio
largest_position_weight

risk_score
```

---

## news_items

```text
id UUID

title
summary
source_name
source_url
published_at
retrieved_at

topic
region

raw_relevance_score
credibility_score

content_hash

created_at
```

必须基于：

```text
content_hash
```

去重。

---

## news_instrument_links

```text
news_id
instrument_id

relevance_score
impact_score
impact_direction

time_horizon
confidence
```

impact_direction：

```text
POSITIVE
NEGATIVE
MIXED
NEUTRAL
```

---

## macro_observations

```text
series
date
value
unit
source
```

例如：

```text
US_CPI
US_CORE_CPI
US_UNEMPLOYMENT
US_10Y
US_2Y
FED_FUNDS
VIX
DXY
WTI
```

---

## daily_runs

```text
id UUID
started_at
finished_at
status

portfolio_snapshot_id

market_data_status
research_status
llm_status

error_message NULL

pipeline_version
```

status：

```text
RUNNING
SUCCESS
PARTIAL
FAILED
```

---

## signals

```text
id UUID
daily_run_id
instrument_id

signal_type

score
confidence

metadata JSONB

created_at
```

signal_type：

```text
TACTICAL
STRATEGIC
NEWS
MACRO
PORTFOLIO_FIT
```

---

## recommendations

这是系统中最重要的表。

```text
id UUID

daily_run_id
instrument_id

recommendation_type
action

current_price

current_weight
target_weight

proposed_amount
proposed_weight_change

score
confidence

time_horizon_days_min
time_horizon_days_max

thesis TEXT
risk_summary TEXT
invalidation_conditions JSONB

evidence_ids JSONB

risk_gate_status

created_at
```

action：

```text
BUY
HOLD
REDUCE
WATCH
```

V1 不使用：

```text
STRONG BUY
STRONG SELL
```

因为这种标签会制造虚假的确定性。

---

## recommendation_outcomes

```text
recommendation_id

return_1d
return_5d
return_20d
return_60d

benchmark_return_1d
benchmark_return_5d
benchmark_return_20d
benchmark_return_60d

excess_return_5d
excess_return_20d
excess_return_60d

max_drawdown_20d
max_drawdown_60d

updated_at
```

---

# 7. Market Data Provider Abstraction

必须建立统一接口：

```python
class MarketDataProvider(Protocol):
    async def get_instrument(
        self,
        symbol: str,
    ) -> InstrumentData: ...

    async def get_history(
        self,
        symbol: str,
        start: date,
        end: date,
    ) -> list[PriceBar]: ...

    async def get_fund_profile(
        self,
        symbol: str,
    ) -> FundProfile: ...

    async def get_holdings(
        self,
        symbol: str,
    ) -> list[FundHolding]: ...
```

业务逻辑绝不能：

```python
import akshare
```

或者：

```python
import alpha_vantage
```

必须通过 provider abstraction。

这样以后可以：

```text
AKShare → provider failure
↓
switch provider
```

而不用改 Signal Engine。

每一条数据必须包含：

```text
source
retrieved_at
as_of
```

---

# 8. Fund Universe

不要允许 LLM 在整个互联网随意找基金。

使用：

```text
config/fund_universe.csv
```

作为候选池。

例如：

```text
symbol,name,market,category,enabled
VTI,Vanguard Total Stock Market ETF,US,broad_market,true
VOO,Vanguard S&P 500 ETF,US,broad_market,true
QQQ,Invesco QQQ Trust,US,growth,true
SCHD,Schwab US Dividend Equity ETF,US,dividend,true
TLT,iShares 20+ Year Treasury Bond ETF,US,bond,true
IEF,iShares 7-10 Year Treasury Bond ETF,US,bond,true
GLD,SPDR Gold Shares,US,gold,true
XLK,Technology Select Sector SPDR Fund,US,sector,true
SMH,VanEck Semiconductor ETF,US,sector,true
```

V1 推荐范围：

```text
current holdings
+
approved universe
```

禁止 LLM 推荐：

```text
unknown symbol
```

除非：

```text
recommendation_type = DISCOVERY
```

而 V1 默认关闭 discovery。

建议初始 universe：

```text
30–80 instruments
```

不要一开始做 3000 个基金。

---

# 9. Quant Engine

量化计算全部由 Python 完成。

至少需要实现：

## Returns

```text
1D
5D
20D
60D
126D
252D
```

公式：

```text
return = current_price / previous_price - 1
```

---

## Moving averages

```text
MA20
MA50
MA200
```

以及：

```text
price / MA20
price / MA50
price / MA200
```

---

## Volatility

20D / 60D annualized volatility：

```text
std(daily_returns) * sqrt(252)
```

---

## Drawdown

```text
drawdown = price / rolling_max - 1
```

计算：

```text
max_drawdown_60
max_drawdown_252
```

---

## Sharpe

V1 可以先：

```text
annual_return - risk_free_rate
--------------------------------
annual_volatility
```

risk free rate 从 macro provider 获取。

如果缺失：

```text
fallback config value
```

并标记：

```text
data_quality = DEGRADED
```

---

# 10. Tactical Signal

短期信号目标：

```text
5–20 trading days
```

不做日内预测。

Tactical Score：

```text
0–100
```

建议权重：

| Factor                | Weight |
| --------------------- | -----: |
| Trend                 |     20 |
| Momentum              |     20 |
| Relative Strength     |     10 |
| Volatility / Drawdown |     15 |
| Macro Regime Fit      |     10 |
| News Impact           |     10 |
| Portfolio Fit         |     10 |
| Liquidity             |      5 |

总计：

```text
100
```

示例：

```python
tactical_score = (
    trend * 0.20
    + momentum * 0.20
    + relative_strength * 0.10
    + risk_adjusted_signal * 0.15
    + macro_fit * 0.10
    + news_score * 0.10
    + portfolio_fit * 0.10
    + liquidity * 0.05
)
```

所有 component：

```text
0–100
```

---

# 11. Strategic Signal

长期推荐目标：

```text
6–36 months
```

Strategic Score：

| Factor                        | Weight |
| ----------------------------- | -----: |
| Diversification               |     20 |
| Portfolio Fit                 |     20 |
| Historical Risk               |     15 |
| Long-term Trend               |     10 |
| Fund Cost                     |     10 |
| Fund Size / Liquidity         |     10 |
| Fundamental / Valuation Proxy |     10 |
| Tracking Quality              |      5 |

如果某项数据不存在：

不要随便设置：

```text
50
```

应该计算：

```text
data_coverage
```

如果：

```text
coverage < 0.70
```

则：

```text
eligible_for_buy = false
```

只允许：

```text
WATCH
```

---

# 12. Macro Regime

V1 不让 LLM自由定义宏观环境。

由 Python 计算基础 regime。

至少定义：

```text
RISK_ON
RISK_OFF
INFLATIONARY
DISINFLATIONARY
RATE_RISING
RATE_FALLING
UNCERTAIN
```

可以同时存在多个状态，例如：

```json
{
  "risk_regime": "RISK_ON",
  "inflation_regime": "DISINFLATIONARY",
  "rate_regime": "RATE_FALLING",
  "confidence": 0.74
}
```

LLM 负责解释。

Python 负责分类。

---

# 13. News / Research Pipeline

每日搜索只关注：

```text
过去 24–72 小时
```

特殊周末运行可以扩展。

搜索主题：

```text
Federal Reserve
US inflation
US employment
Treasury yields
ECB
China economy
China central bank
USD
oil
gold
major geopolitical risk

+

current portfolio exposure

+

fund universe sectors
```

例如持仓包含：

```text
SMH
QQQ
```

自动追加：

```text
semiconductor
AI capex
Nvidia / AMD / TSMC
US semiconductor policy
```

研究来源优先：

```text
official central banks
government statistics
SEC
fund issuer
Reuters
Financial Times
WSJ
Bloomberg
CNBC
recognized financial publications
```

必须保存：

```text
title
url
publisher
published_at
summary
```

没有 URL 的研究不能进入最终报告 Evidence。

---

# 14. News LLM Stage

这一阶段使用低成本模型。

它不能输出：

```text
BUY
SELL
```

只允许：

```json
{
  "topic": "semiconductor",
  "affected_assets": ["SMH", "QQQ"],
  "impact_direction": "POSITIVE",
  "impact_score": 71,
  "time_horizon": "DAYS_TO_WEEKS",
  "confidence": 0.68,
  "reason": "...",
  "source_ids": ["news-123"]
}
```

system prompt 必须包含：

```text
You are a financial research classification component.

You do not make investment recommendations.

Only analyze supplied evidence.

Never invent:
- prices
- returns
- fund holdings
- statistics
- events
- sources

If evidence is insufficient, return LOW confidence.

Separate:
fact
interpretation
uncertainty.
```

必须通过 Pydantic structured output 验证。

失败时：

```text
retry <= 2
```

仍失败：

```text
skip item
log error
```

不能因为 LLM failure 导致整个 daily run fail。

---

# 15. Portfolio Fit

这是 V1 很关键的一层。

推荐不能只看资产自身表现。

例如用户：

```text
QQQ 35%
SMH 20%
XLK 15%
```

即使 SMH Tactical Score = 90，也可能：

```text
WATCH
```

因为科技仓位已经过度集中。

计算：

```text
current weight
category exposure
sector exposure
correlation
risk contribution
```

Portfolio Fit score：

```text
0–100
```

高相关 + 已重仓：

```text
lower score
```

可以改善 diversification：

```text
higher score
```

---

# 16. Position Sizing

V1 禁止 LLM 给金额。

金额完全由 Python 决定。

用户设置：

```yaml
portfolio:
  minimum_cash_ratio: 0.10

  max_single_position: 0.20

  max_sector_exposure: 0.35

  max_new_position: 0.05

  max_daily_total_buy: 0.10

  min_trade_amount: 200
```

假设：

```text
portfolio = $100,000
cash = $20,000
minimum_cash_ratio = 10%
```

真正可投资现金：

```text
20,000 - 10,000 = $10,000
```

不能把全部现金视为 available capital。

单个建议：

```python
proposed_amount = min(
    target_position_gap,
    max_new_position_limit,
    available_cash,
    risk_budget,
)
```

---

# 17. Risk Gate

所有建议最后必须经过：

```python
RiskGate.validate()
```

RiskGate 是 deterministic。

规则至少包括：

```text
DATA_STALE
INSUFFICIENT_DATA
LOW_CONFIDENCE
MIN_CASH_BREACH
MAX_POSITION_BREACH
MAX_SECTOR_BREACH
MAX_DAILY_BUY_BREACH
EXCESS_CORRELATION
CONFLICTING_SIGNALS
PORTFOLIO_RISK_TOO_HIGH
```

示例：

```python
if data_age_hours > max_age:
    return WATCH

if recommendation.confidence < min_confidence:
    return WATCH

if new_position_weight > max_single_position:
    reduce_size()

if remaining_cash_ratio < minimum_cash_ratio:
    reject_buy()
```

RiskGate 的结果：

```json
{
  "status": "APPROVED",
  "original_action": "BUY",
  "final_action": "BUY",
  "original_amount": 3000,
  "approved_amount": 1800,
  "rules_triggered": [
    "MAX_NEW_POSITION"
  ]
}
```

---

# 18. Recommendation Engine

推荐动作只有：

```text
BUY
HOLD
REDUCE
WATCH
```

建议规则第一版可以：

### BUY

必须同时满足：

```text
score >= 70
confidence >= 0.65
data_coverage >= 0.80
RiskGate approved
```

### HOLD

例如：

```text
45 <= score < 70
```

或：

```text
existing position
+
no compelling rebalance requirement
```

### REDUCE

例如：

```text
concentration violation

OR

strategic score < 40
AND
tactical score < 40

OR

portfolio risk limit breached
```

### WATCH

用于：

```text
interesting asset
but confidence insufficient

OR

insufficient data

OR

risk gate rejects purchase

OR

mixed signals
```

---

# 19. Confidence Score

Confidence 不允许由 LLM凭感觉直接输出最终值。

最终：

```text
confidence =
data_quality
× signal_consistency
× evidence_quality
× model_confidence
```

建议：

```python
final_confidence = (
    data_quality * 0.35
    + signal_consistency * 0.30
    + evidence_quality * 0.20
    + llm_confidence * 0.15
)
```

---

# 20. Recommendation Schema

使用 Pydantic：

```python
class Recommendation(BaseModel):
    instrument_id: UUID

    action: Literal[
        "BUY",
        "HOLD",
        "REDUCE",
        "WATCH",
    ]

    recommendation_type: Literal[
        "TACTICAL",
        "STRATEGIC",
    ]

    score: float
    confidence: float

    current_weight: float
    target_weight: float | None

    proposed_amount: Decimal

    time_horizon_days_min: int
    time_horizon_days_max: int

    thesis: str
    risks: list[str]
    invalidation_conditions: list[str]

    evidence_ids: list[UUID]

    data_coverage: float
```

---

# 21. Portfolio Analyst LLM

Portfolio Analyst 接收的输入只能是结构化数据。

不要塞几十篇完整新闻进去。

输入类似：

```json
{
  "portfolio": {...},

  "macro_regime": {...},

  "instrument": {
    "symbol": "QQQ",

    "tactical": {...},
    "strategic": {...},

    "news_signals": [...]
  }
}
```

任务：

```text
Explain:
- why the signals matter
- upside case
- downside case
- important uncertainty
- invalidation conditions
```

不允许：

```text
change score
change price
change allocation
change proposed_amount
```

Quant Engine / Risk Engine 才拥有这些字段的控制权。

---

# 22. Daily Report Generator

日报格式固定。

```text
AI PORTFOLIO DAILY BRIEF
YYYY-MM-DD
```

包含：

## Portfolio Snapshot

```text
Portfolio value
Cash
Invested
Cash ratio
Portfolio risk
Largest position
```

## Market Regime

例如：

```text
Risk: Moderate
Equity regime: Risk-on
Rates: Falling
Inflation: Disinflationary
```

## Existing Holdings

表格：

```text
Symbol
Weight
Tactical
Strategic
Action
Proposed amount
Confidence
```

## Tactical Opportunities

最多：

```text
3
```

不要每天推荐 20 个基金。

## Strategic Opportunities

最多：

```text
3
```

## Risk Alerts

例如：

```text
Technology exposure 43%
Cash below target
High correlation between QQQ and XLK
```

## Major News

只显示：

```text
5–10
```

真正与投资组合相关的信息。

## Recommendation Explanation

每个 BUY / REDUCE：

必须展示：

```text
Action
Amount
Reason
Evidence
Risks
Invalidation
Confidence
```

---

# 23. Evidence

最终报告必须让用户能够追踪：

```text
结论来自哪里？
```

例如：

```text
QQQ BUY

Evidence:
[E123] Federal Reserve statement
[E129] Reuters semiconductor demand report
[E141] QQQ price trend signal
```

不能写：

```text
据市场消息
```

或者：

```text
分析认为
```

必须明确来源。

---

# 24. Daily Pipeline

入口：

```bash
python -m app.jobs.daily
```

流程必须严格：

```text
START

1 create daily_run

2 load portfolio

3 fetch market data

4 validate market data

5 save portfolio snapshot

6 update historical metrics

7 calculate portfolio metrics

8 fetch macro data

9 calculate macro regime

10 build research queries

11 web research

12 store evidence

13 classify news impact

14 calculate tactical signals

15 calculate strategic signals

16 calculate portfolio fit

17 rank universe

18 generate preliminary actions

19 calculate position sizing

20 run risk gate

21 save recommendations

22 run LLM explanatory analysis

23 generate daily report

24 send notification

25 mark daily_run SUCCESS

END
```

任何非关键模块失败：

```text
daily_run = PARTIAL
```

例如新闻 API 失败：

价格、量化和组合风险仍然应该运行。

---

# 25. Data Freshness Rules

市场数据：

```text
<= 36h trading day
```

新闻：

```text
<= 72h
```

宏观数据：

根据 series frequency 判断。

如果数据 stale：

禁止：

```text
BUY
```

降级：

```text
WATCH
```

---

# 26. Daily Scheduler

GitHub Actions：

```text
.github/workflows/daily.yml
```

必须支持：

```text
schedule
workflow_dispatch
```

不要只允许 cron，因为开发期间需要手动运行。

workflow：

```text
checkout
setup python
install uv
install deps
run migrations
run daily job
```

secrets：

```text
DATABASE_URL

OPENAI_API_KEY

MARKET_DATA_API_KEY

FRED_API_KEY

TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
```

所有 secret 禁止进入日志。

---

# 27. Default Configuration

```yaml
app:
  timezone: "America/Los_Angeles"

research:
  news_lookback_hours: 48
  max_news_items: 30
  max_news_per_topic: 5

models:
  fast_model_env: "LLM_FAST_MODEL"
  reasoning_model_env: "LLM_REASONING_MODEL"
  review_model_env: "LLM_REVIEW_MODEL"

portfolio:
  minimum_cash_ratio: 0.10
  max_single_position: 0.20
  max_sector_exposure: 0.35
  max_new_position: 0.05
  max_daily_total_buy: 0.10

recommendations:
  min_buy_score: 70
  min_buy_confidence: 0.65
  minimum_data_coverage: 0.80

tactical:
  horizon_min_days: 5
  horizon_max_days: 20

strategic:
  horizon_min_days: 180
  horizon_max_days: 1095
```

---

# 28. Streamlit Dashboard

首页：

```text
Portfolio Value
Cash
Invested
Risk Score

Today's recommendation count

BUY
HOLD
REDUCE
WATCH
```

页面：

## Portfolio

显示：

```text
holdings
market value
weight
cost
return
portfolio contribution
```

支持：

```text
manual edit
CSV import
```

---

## Daily Report

显示当前日报。

---

## Recommendations

支持：

```text
date filter
instrument filter
action filter
tactical / strategic filter
```

---

## Performance

必须显示：

```text
recommendation hit rate

5D return
20D return
60D return

benchmark excess return

BUY recommendation performance
REDUCE recommendation performance
```

---

## Data Health

显示：

```text
Market Data: OK
Macro Data: OK
Research: OK
LLM: OK

Last successful run
Last market update
Last research update
```

这是一个非常重要的页面。

---

# 29. Notification

V1 推荐 Telegram。

消息不需要发完整报告。

只发：

```text
Daily Portfolio Brief

Portfolio risk: MODERATE

BUY:
QQQ $1,500
Confidence 71%

REDUCE:
XLK $800
Confidence 76%

WATCH:
TLT

3 important risk alerts.

Full report:
<dashboard url>
```

---

# 30. Recommendation Outcome Tracking

每天运行：

```text
outcome_update.py
```

检查旧 recommendations。

例如 recommendation 已过去：

```text
5 trading days
```

就更新：

```text
return_5d
benchmark_return_5d
excess_return_5d
```

这一步不能省。

否则整个项目只能回答：

```text
AI 今天说了什么
```

却无法回答：

```text
AI 过去说得对不对
```

---

# 31. Evaluation Metrics

V1 至少统计：

```text
recommendation count
BUY hit rate
REDUCE hit rate

average 5D return
average 20D return
average 60D return

average excess return

median return

max drawdown after recommendation

confidence calibration
```

Confidence calibration 示例：

```text
70–80% confidence recommendations

actual success rate = ?
```

如果只有：

```text
51%
```

说明 confidence calibration 有问题。

---

# 32. Backtesting

V1 不尝试完整回测 LLM 新闻判断。

因为历史新闻数据容易产生：

```text
look-ahead bias
survivorship bias
```

V1 只回测：

```text
price-based tactical signals
portfolio sizing
risk limits
```

LLM Research Layer 使用：

```text
forward evaluation
```

也就是从软件正式开始运行之后累积结果。

---

# 33. Tests

目标：

```text
pytest
```

必须包含。

## Quant

测试：

```text
returns
moving average
volatility
drawdown
Sharpe
ranking
```

全部用固定 fixture。

---

## Risk Gate

至少测试：

```text
cash violation
position concentration
sector concentration
low confidence
stale data
missing price
```

---

## Recommendation

测试：

```text
BUY → risk rejected → WATCH

BUY → oversized → smaller BUY

existing concentrated position → REDUCE

insufficient data → WATCH
```

---

## Providers

所有 provider 使用 mocked HTTP。

CI 不允许真实调用付费 API。

---

## LLM

使用 fake client：

```python
class FakeLLMClient: ...
```

CI 禁止真实消费 token。

---

# 34. API Endpoints

FastAPI：

```text
GET  /health

GET  /portfolio
POST /portfolio/import

GET  /instruments
GET  /instruments/{symbol}

GET  /recommendations/latest
GET  /recommendations/history

GET  /runs
GET  /runs/{id}

POST /runs/daily
```

`POST /runs/daily`：

生产环境应该受：

```text
API token
```

保护。

---

# 35. Error Handling

禁止：

```python
except Exception:
    pass
```

所有 provider error：

```text
provider
operation
symbol
timestamp
retry count
error
```

必须进入日志。

外部 API：

```text
timeout
retry with exponential backoff
```

建议：

```text
3 retries max
```

---

# 36. Observability

每个 Daily Run 使用：

```text
run_id
```

日志：

```text
run_id
stage
duration
status
```

例如：

```text
run_id=abc
stage=market_data
duration=4.3
status=SUCCESS
```

最终记录：

```text
total runtime
number market requests
number web searches
number LLM calls
LLM input tokens
LLM output tokens
estimated LLM cost
```

建立：

```text
daily API cost
```

统计。

---

# 37. Cost Control

每次 Daily Run：

Web Search：

```text
5–15 targeted searches
```

不要：

```text
one search per fund
```

先根据 sector / macro / holdings 聚合 query。

News classifier：

尽可能 batch。

例如一次请求：

```text
10 articles
```

而不是：

```text
10 separate calls
```

Research → cheap model。

Daily analytical report → general reasoning model。

只有：

```text
signal conflict
high portfolio risk
large proposed allocation change
```

才调用更强 review model。

---

# 38. Security

`.env`：

永远不 commit。

`.gitignore`：

```text
.env
*.db
credentials*
```

所有 API key：

```text
environment variables
GitHub Secrets
```

禁止在 DB 里存 OpenAI API key。

日志禁止：

```text
print(os.environ)
```

---

# 39. README

Codex 最后必须生成 README。

必须包含：

```text
What it does

Architecture

Requirements

Local setup

Database setup

API key setup

Portfolio import

Run daily analysis

Launch dashboard

GitHub Actions setup

Configuration

Tests

Known limitations

Disclaimer
```

---

# 40. V1 UX 示例

最终用户每天看到：

```text
AI Portfolio Brief
2026-09-15

Portfolio
Value        $100,000
Invested      $82,000
Cash          $18,000

Risk          MODERATE

Macro
Risk regime   Risk-on
Rates         Falling
Inflation     Disinflationary

--------------------------------

QQQ

Action:
BUY

Current:
12%

Target:
14%

Suggested:
$2,000

Tactical:
78 / 100

Strategic:
72 / 100

Confidence:
71%

Why:

Momentum remains positive while recent macro
conditions remain supportive for growth assets.

Relevant semiconductor and AI infrastructure
evidence remains constructive.

Portfolio concentration remains within configured
limits.

Risks:

- valuation
- long-duration rate sensitivity
- technology concentration

Invalidation:

- trend score falls below 45
- macro regime changes to risk-off
- portfolio tech exposure exceeds 35%

Evidence:

Federal Reserve
Reuters
QQQ price series

--------------------------------

Important:

This is investment research and decision support.
No trades have been executed.
```

---

# 41. Codex Implementation Order

Codex **不得一次性实现整个项目**。

按以下 milestones：

## Milestone 1 — Project Foundation

完成：

```text
repository structure
pyproject
config
logging
PostgreSQL
SQLAlchemy
migrations
health API
CI
```

验收：

```bash
pytest
```

通过。

---

## Milestone 2 — Portfolio

完成：

```text
accounts
positions
cash
portfolio snapshot
CSV import
```

能够输入：

```text
QQQ 10 shares
VTI 20 shares
cash $10,000
```

生成 portfolio snapshot。

---

## Milestone 3 — Market Data

完成：

```text
provider abstraction
one functioning provider
price history
fund profile
cache
retry
```

不要先实现 3 个 providers。

先实现 1 个。

---

## Milestone 4 — Quant Engine

完成：

```text
returns
momentum
MA
volatility
drawdown
Sharpe
portfolio risk
```

大量 unit tests。

---

## Milestone 5 — Signals

实现：

```text
tactical score
strategic score
portfolio fit
ranking
```

此时 **完全不使用 LLM**。

系统已经应该能够输出：

```text
quantitative WATCH / BUY candidates
```

---

## Milestone 6 — Research

实现：

```text
OpenAI client
web research
news database
news classification
source tracking
```

不产生投资建议。

---

## Milestone 7 — Recommendation Engine

实现：

```text
combine scores
position sizing
risk gate
save recommendation
```

---

## Milestone 8 — LLM Analyst

添加：

```text
thesis
risks
invalidation
explanation
```

---

## Milestone 9 — Daily Report

实现：

```text
daily report
Telegram
```

---

## Milestone 10 — Dashboard

实现 Streamlit。

---

## Milestone 11 — Scheduler

GitHub Actions。

---

## Milestone 12 — Outcome Tracking

实现：

```text
1D
5D
20D
60D
```

评估推荐表现。

---

# 42. Codex Rules

给 Codex 的总指令：

```text
Implement incrementally.

Never skip tests.

Never call an LLM for deterministic numerical work.

Never let an LLM directly control portfolio sizing.

Never let an LLM bypass RiskGate.

Never invent financial data.

Every external financial fact must include its source.

Every recommendation must be reproducible from
stored inputs.

All LLM outputs must use structured schemas.

All money calculations must use Decimal.

All datetime values must be timezone-aware.

External APIs must have retry, timeout and error handling.

Never expose API keys.

Do not add broker execution in V1.

Do not add unnecessary abstractions before they are needed.
```

---

# 43. Definition of Done

V1 完成必须满足：

每天可以通过：

```bash
python -m app.jobs.daily
```

自动完成：

```text
portfolio load
↓
price update
↓
quant analysis
↓
macro analysis
↓
news research
↓
signal calculation
↓
recommendation generation
↓
risk validation
↓
daily report
↓
database save
↓
notification
```

同时：

```bash
pytest
```

全部通过。

用户能够在 Dashboard：

```text
查看当前组合

查看今日建议

查看推荐理由

查看信息来源

查看风险

查看历史推荐

查看过去推荐表现

查看系统数据健康状态
```

并且系统在任何情况下都不能：

```text
自动下单。
```

---

# 44. V1 成功标准

不要用：

```text
赚了多少钱
```

作为最初唯一指标。

最初 60–90 天先看工程和预测质量：

```text
>95% daily run success

>95% market data completeness

100% recommendations traceable to data

0 hallucinated source

0 unauthorized trade

recommendation outcome tracking >95%

reasonable confidence calibration

risk constraints never bypassed
```

运行一段时间之后再评估：

```text
5D excess return
20D excess return
60D excess return

hit rate

drawdown

Sharpe

benchmark comparison
```

如果长期不能超过：

```text
simple benchmark
```

则不要增加系统复杂度。

应优先：

```text
改 signal
改数据
改 portfolio construction
```

而不是：

```text
换一个更大的 LLM。
```

---

# 45. V1 之后再考虑的功能

以下明确属于 V2+：

```text
broker integration

automatic trading

multiple users

multiple portfolios

tax optimization

tax loss harvesting

real-time market monitoring

intraday trading

advanced factor models

historical news backtesting

RAG investment research database

SEC filing analysis

earnings call analysis

fund holdings look-through

Black-Litterman allocation

Monte Carlo portfolio simulation

scenario stress testing

mobile app
```

第一版全部不要做。

---

# Final Architecture Principle

整个系统最终应该满足：

```text
DATA
 ↓
QUANT
 ↓
SIGNAL
 ↓
PORTFOLIO
 ↓
RISK
 ↓
LLM EXPLANATION
 ↓
HUMAN
 ↓
DECISION
```

而不是：

```text
NEWS
 ↓
LLM
 ↓
BUY
```

前者是一个可以持续测试、改进和审计的投资研究系统。

后者只是一个会聊天的预测机器人。

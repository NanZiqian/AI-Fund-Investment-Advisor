# 知基 · 中国公募基金研究助手

面向单人、人民币基金账户的本地研究系统。每天更新基金净值、计算风险、整理有来源的研究证据，经过确定性风控生成建议，并保存后续表现。**不自动交易，无任何券商下单接口。**

## 现在如何使用

本项目按需在本机运行，不需要常驻服务器或云端部署。代码、本地数据库和截图导入记录已保留；Python 环境和第三方包由用户自行安装与管理。

完成下方“一次性手动准备”后，每天早晨在项目目录执行：

```powershell
.\scripts\dashboard.ps1
```

然后打开 **[本地仪表盘](http://127.0.0.1:8501)**。使用结束后在 PowerShell 按 `Ctrl+C` 停止；服务只监听 `127.0.0.1`，不会在后台持续运行，也不会向手机或局域网开放。

“持仓管理”中补充现金、核对时间，核对基金代码及 A/C 份额后确认记录。份额缺失可以保留，但无法自动重估资产金额；日期不明的截图不会生成加减仓金额。当前截图导入记录的来源与匹配依据在 [截图核对说明](docs/screenshot-import.md) 中（个人文件，默认不提交）。

## 功能

- 持仓 CSV 导入、手动编辑、现金记录、历史快照；金额以 Decimal 计算。
- 东方财富公开源：基金身份和历史单位净值；同源日增长率链式生成总回报指数；缓存、超时与最多 3 次请求尝试。
- 1/5/20/60/126/252 期收益、MA20/50/200、波动率、回撤、Sharpe、Sortino、相关性和风险贡献。
- 短期观察 / 长期配置双评分；缺失分量降低覆盖率；已批准候选池限定研究范围。
- 可选 FRED 宏观源与带来源的中国宏观 CSV；按地区、频率和时效计算宏观状态。
- 可选 OpenAI Responses API + Web Search；结构化输出、来源核对、时间窗过滤、去重、调用预算。
- 现金缓冲、单基金/行业/每日买入上限、相关性、低置信度、信号冲突和鲜度否决；基金申购限额、持有期、赎回费用检查。
- 中文 Markdown 日报、Streamlit 工作台、受 token 保护的 API、可选 Telegram 通知。
- 每次运行保存输入、配置、原始研究响应、评分和建议；支持不联网重放确定性决策。
- 1/5/20/60 个净值观测期结果跟踪、同日期基准超额收益、方向命中率、置信度校准；同基金同日仅统计最终版本。
- 价格信号基线回测，使用下一期执行与显式费用假设；不回放历史 LLM 新闻。

## 架构与规格取舍

```mermaid
flowchart LR
  A[持仓/净值/宏观/新闻] --> B[Python 量化]
  B --> C[评分与覆盖率]
  C --> D[金额预算]
  D --> E[确定性风控]
  E --> F[数据库与审计]
  F --> G[LLM 受限解释]
  G --> H[中文报告 / 人工判断]
  F --> I[后续净值表现]
```

保留 spec.md 的数据优先、风控最终否决、分阶段测试与结果跟踪。采用模块化 Python 单体；用运行记录中的 JSON 保存相关输入、指标、信号和解释，避免第一版过多表和服务。单 CNY 账户的最新现金放在 accounts，完整历史随快照保存。金额、净值、建议、结果仍有独立持久化模型。

默认 SQLite 方便本地启动，正式运行使用 PostgreSQL；SQLite 金额使用十进制字符串而非 REAL，PostgreSQL 使用 NUMERIC(24,8)，时间使用 TIMESTAMPTZ。公募基金特有的处理和接口依据见 [架构决策](docs/architecture.md)。阶段验收见 [milestones](docs/milestones.md)。

## 环境与安装

项目要求 Python 3.12+。仓库不自带 Python，也不会自动安装 Python 或第三方包。以下命令必须由用户在项目目录中手动执行一次：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

现有 `data/advisor.db` 已初始化并包含截图导入记录。只有删除或重建数据库时才需要执行：

```powershell
.\.venv\Scripts\python.exe -m app.cli init-db
```

也可自行选择 uv，`uv.lock` 已锁定依赖。项目根目录是运行目录，配置和数据路径相对于此目录。

## 数据库

默认：`sqlite:///data/advisor.db`。数据、报告和原始截图都在 `.gitignore` 中。

PostgreSQL：设置 `POSTGRES_PASSWORD` 后执行 `docker compose up -d db`，在 `.env` 中设置：

```dotenv
DATABASE_URL=postgresql+psycopg://advisor:YOUR_PASSWORD@localhost:5432/advisor
```

然后 `uv run alembic upgrade head`。将本地 SQLite 切换到 PostgreSQL 不会自动复制持仓，需重新导入。正式实例应配置自己的数据库备份与 HTTPS 接入。

## API key 与配置

复制 `.env.example` 为 `.env`，填入所需值；不要提交密钥。没有密钥也能运行持仓、净值、量化、风控与本地报告。

| 配置 | 用途 |
|---|---|
| `OPENAI_API_KEY` | OpenAI API 密钥，代码和日志不记录该值 |
| `RESEARCH_ENABLED=true` | 开启外部新闻研究和 LLM 解释，默认关闭 |
| `LLM_FAST_MODEL` | 具有 Web Search 与结构化输出能力的研究模型 ID |
| `LLM_REASONING_MODEL` | 解释模型 ID |
| `LLM_REVIEW_MODEL` | 可选，风险高或信号冲突时复核解释 |
| `FRED_API_KEY` | FRED 宏观数据；部分中国序列发布滞后，会被时效规则拦截 |
| `API_TOKEN` | 配置后保护全部业务 API；未配置时 API 写入关闭 |
| `TELEGRAM_ENABLED` | 默认 false；明确开启才发送通知 |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | 通知目标 |

模型 ID 全部从环境变量读取，没有硬编码的生产模型。启用外部研究后，搜索请求包括基金代码和主题；分析请求包括结构化组合、建议和证据。请在自己确认可发送这些信息的环境中开启。

风控环境变量与默认值：`MIN_CASH_RATIO=0.10`、`MAX_POSITION=0.20`、`MAX_SECTOR=0.35`、`MAX_NEW_POSITION=0.05`、`MAX_DAILY_BUY=0.10`、`MIN_TRADE_AMOUNT=100`、`MIN_BUY_SCORE=70`、`MIN_CONFIDENCE=0.65`、`MIN_COVERAGE=0.80`。这些是初始研究约束，不是已优化的投资参数。

`MAX_RESEARCH_QUERIES` 默认 5，`MAX_LLM_CALLS` 默认 12；每次 Web Search 响应最多 2 次工具调用。调用量和 token 数写入运行记录。只有填写 `LLM_INPUT_USD_PER_MILLION`、`LLM_OUTPUT_USD_PER_MILLION`、`WEB_SEARCH_USD_PER_CALL` 后才估算成本；这是统一费率近似，多模型/缓存等实际账单以服务商为准。

## 持仓、候选池与资料

```bash
uv run python -m app.cli import-portfolio config/portfolio.private.csv
# 已确认的现金记录必须附日期，例如：
uv run python -m app.cli import-portfolio YOUR_PORTFOLIO.csv --cash 1000 --as-of 2026-09-15T20:00:00+08:00
```

CSV 模板在 `config/portfolio.example.csv`。必填列为 `symbol,name,market_value,source`。`quantity`、`average_cost`、`holding_profit`、`as_of`、`acquired_on` 可缺失；`confirmed=true` 必须有合法基金代码和带时区日期。CLI 的 `--as-of` 记录现金时间，确认持仓时每行也须填写 `as_of`。未知现金留空，已知零现金填 `0`。导入是完整替换当前持仓，历史快照不变；JSON/API 额外支持 merge（账户现金仍采用本次提交值）。

初始候选池为空。编辑 `config/fund_universe.csv`，填写可追溯 source、合法 6 位代码与 `enabled=true`，再执行：

```bash
uv run python -m app.cli import-universe config/fund_universe.csv
```

`benchmark_symbol` 必须指向数据库中的另一只已核对基金，不接受将指数代码伪装成基金代码。若基准不在推荐池中，可将它以 `enabled=false` 导入；流水线仍会为相关基金加载基准数据。

在“设置”页保存基金资料与申赎规则，或执行 `python -m app.cli import-profile CODE profile.json`。字段格式见 [基金资料模板](config/profile.example.json)。示例是空白模板，必须依据真实公告填写；不能靠填写主观高分凑齐覆盖率。资料用于解释/评分，交易规则超过 7 天需重核；赎回费是当前持仓实际适用费率，多笔持仓不确定时应留空。

`config/macro_observations.csv` 可以录入来自统计局、央行等官方资料的数据；必须填写 series/date/value/region/kind/max_age_days/unit/source。kind 为 inflation/rates/risk；通胀使用 percent_yoy、利率使用 percent、风险指标使用 index。不相容的单位不生成 regime。

## 日常运行

推荐通过仪表盘手动运行：进入“组合总览”，展开“运行每日分析”；需要获取当天基金净值时取消勾选“只使用本地数据（不联网）”，再点击“生成新的研究简报”。运行完成后查看“每日简报”和“数据健康”。没有 OpenAI API 密钥时，净值更新、量化指标、确定性风控和本地报告仍可运行，外部新闻研究与 LLM 解释会跳过。

命令行等价操作：

```bash
uv run python -m app.jobs.daily
uv run python -m app.jobs.daily --offline
uv run python -m app.jobs.daily --refresh
uv run python -m app.jobs.outcome_update --offline
uv run python -m app.replay RUN_ID
uv run python -m app.backtest FUND_CODE
```

`--offline` 只读取本地行情和证据，不填充模拟市场数据。相同日期、模式和输入的运行默认复用；`--refresh` 新增研究版本。**不同版本是替代方案，不可叠加成多笔交易计划。** 中断遗留 RUNNING 的记录可用 `--refresh` 新建版本。

每日流程会更新已有净值的跟踪结果；独立 outcome_update 还会为已离开持仓的历史推荐补取净值。报告存储在数据库与 `reports/YYYY-MM-DD-RUN_ID.md`。导出或通知失败不删除已保存的建议。

## API 与仪表盘

```bash
uv run streamlit run dashboard/Home.py --server.address 127.0.0.1
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

仪表盘含组合总览、持仓管理、每日简报、历史建议、表现评估、数据健康和设置。API 文档在 [本地 API Docs](http://127.0.0.1:8000/docs)。`Authorization: Bearer YOUR_API_TOKEN` 用于受保护接口。`POST /runs/daily` 是同步长请求。默认仅绑定本机；Streamlit 没有多用户登录功能。

## 测试与验证

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

测试覆盖金额精度、迁移往返、CSV、净值解析、分红调整、量化计算、风险否决和缩量、fake LLM 权限边界、来源过滤、API 权限、Streamlit 页面、流水线降级、结果对齐、回测前视偏差和建议重放。这些测试不调用真实付费服务。

本地 PostgreSQL 专项测试在没有 PostgreSQL 服务时跳过。公开行情适配器已对截图中的 7 只基金完成一次联网验证。OpenAI、FRED、Telegram 目前只做了 mock 验证，未使用真实密钥调用，也未发送通知。

## 已知限制

- 需要定期维护持仓、现金与公告规则；没有基金账户自动同步。未填账户信息时可以看行情，但建议保持 WATCH。
- 公募基金短期信号为 5–20 个净值观测期的观察信息；金额方案只使用长期配置通道，降低赎回费与净值滞后影响。
- 当前行业标签是人工粗分类，不是持仓穿透；人民币份额的净值已经体现对应的汇率影响。
- 默认以工作日近似净值披露日历；QDII 容许更长延迟。可在 `config/holidays.json` 填写 `YYYY-MM-DD` 字符串列表，维护明确的非估值日；未知节假日可能保守地阻止建议。未自动维护中、美、港跨市场假日。
- 总回报指数来自数据源日增长率，源数据错误/修订会影响结果；本地 run 保存当时输入以供审计。单位净值和总回报指数不可互换。
- 组合历史波动与回撤为当前权重的静态代理，不是账户真实收益率；缺少可对齐数据时不计算。无风险利率使用显式配置回退并标记降级。
- 缺少费率、规模、估值、跟踪资料时长期评分覆盖率较低，系统可能长期输出 WATCH；不应为获得 BUY 而人为补高分。
- 引用 URL 来自搜索工具，发布时间与内容由模型抽取；来源匹配不能保证模型摘要完全正确。报告将摘要与解释标明，需阅读原文核查。
- 结果使用建议日之后首个可用净值作为研究参考起点，按之后的净值记录计数，并非按场外成交确认日；不含实际手续费、赎回到账、申购限制执行情况。缺少基准时不输出超额收益。
- 置信度是工程评分，不是获利概率；需积累 60–90 天以上真实前向样本，再评估参数是否有效。

## 声明

仅用于个人研究和决策支持。投资有风险，基金净值可能下跌。最终申赎由用户自行在销售平台核对并决定；本系统不保证收益，不自动下单。

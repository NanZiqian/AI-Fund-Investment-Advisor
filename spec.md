# AI Fund Investment Advisor V1 Specification

- **Version:** 1.0
- **Product:** Personal public-fund and ETF portfolio research assistant
- **Default use:** One manually initiated daily run
- **Primary language:** Python
**Trading:** Research and recommendations only; no automated execution

## 1. Product objective

The system helps one user review a CNY-denominated fund portfolio. A daily run should:

1. Load current holdings and available cash.
2. update fund identity, NAV, and historical market data.
3. collect material financial, policy, macroeconomic, and portfolio-relevant world-event news from the previous 24–72 hours when LLM research is enabled.
4. load available macroeconomic observations.
5. calculate quantitative indicators and portfolio risk in Python.
6. classify deterministic macro regimes.
7. score current holdings over tactical and strategic horizons.
8. score only user-approved candidate funds.
9. propose amounts from cash, current weights, and risk limits.
10. apply a deterministic risk gate.
11. produce an evidence-linked daily report.
12. save each run and track later 1/5/20/60-observation outcomes.

V1 must not:

- Place or submit orders.
- Connect to a broker for execution.
- Perform high-frequency or intraday trading.
- turn one news article directly into a transaction.
- let an LLM calculate authoritative returns, volatility, Sharpe ratio, position size, or portfolio limits.
- let an LLM guess prices, sources, or underlying fund holdings.
- use unsourced evidence in a recommendation.
- discover or recommend funds outside the user-approved universe.

## 2. Core decision architecture

Every actionable recommendation has three layers:

1. **Data and evidence:** verified portfolio state, market history, macro observations, fund profile, and recent sourced research.
2. **Deterministic analysis:** metrics, component scores, coverage, portfolio fit, allocation, and risk constraints calculated in Python.
3. **Restricted explanation:** an LLM may explain the result without changing controlled fields.

The required flow is:

```text
providers
  -> validated and timestamped records
  -> quantitative and macro calculations
  -> tactical and strategic signals
  -> portfolio-fit adjustment
  -> proposed allocation
  -> deterministic RiskGate
  -> restricted explanation
  -> report and outcome tracking
```

The research layer never writes an action or amount directly into the portfolio engine.

## 3. Responsibilities

Python owns:

- Monetary arithmetic using `Decimal`.
- NAV history validation and total-return construction.
- Returns, moving averages, volatility, drawdown, Sharpe, Sortino, and correlation.
- Portfolio weights, concentration, risk contribution, and portfolio-fit signals.
- Macro regime classification.
- Data coverage and confidence formulas.
- Candidate ranking.
- Proposed amounts.
- Risk vetoes and reductions.
- Recommendation persistence and outcome measurement.

The LLM may perform:

- Recent-news search and classification.
- Fact, interpretation, and uncertainty separation.
- Event relevance mapping to approved symbols.
- Plain-language thesis and risk explanation.
- Explanation review when risk is high or signals conflict.

The LLM may not modify actions, amounts, scores, confidence, portfolio constraints, or source identifiers.

## 4. Application architecture

Use a modular Python monolith:

```text
app/
  providers/       market and external-data adapters
  db/              models and session management
  jobs/            daily and outcome jobs
  quant.py         quantitative metrics
  signals.py       tactical, strategic, and fit scores
  recommendations.py
  risk.py          deterministic final gate
  research.py      structured web research
  analyst.py       restricted explanation
  report.py        Markdown output
  api.py           optional local API
dashboard/
  Home.py          local Streamlit application
```

Provider abstractions must keep external services replaceable. Business logic must not make unvalidated ad hoc HTTP calls.

## 5. Runtime and deployment

- Python 3.12 or later.
- A user-managed Conda environment named `ai-fund-advisor` is the documented local runtime.
- The application runs on demand on the user's computer.
- Streamlit binds to `127.0.0.1` by default.
- No cloud scheduler or always-on local service is required.
- SQLite is the default local store. PostgreSQL remains an optional persistent deployment.

## 6. Configuration

All credentials and model choices come from environment variables loaded from `.env`:

```dotenv
DATABASE_URL=sqlite:///data/advisor.db
APP_TIMEZONE=Asia/Shanghai
OPENAI_API_KEY=
OPENAI_BASE_URL=
LLM_FAST_MODEL=
LLM_REASONING_MODEL=
LLM_REVIEW_MODEL=
RESEARCH_ENABLED=false
FRED_API_KEY=
API_TOKEN=
TELEGRAM_ENABLED=false
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

No production model ID or secret may be hard-coded. Secrets must never be logged, stored in the database, or included in run snapshots.

A custom `OPENAI_BASE_URL` is valid only when the service supports the Responses API features used by the implementation, including structured parsing and Web Search.

## 7. Persistence

The database must represent:

- Accounts and current cash state.
- Instruments and optional verified profiles.
- Current positions and immutable portfolio snapshots.
- NAV and total-return observations with source and retrieval timestamps.
- Macro observations with units, region, frequency, source, and freshness rules.
- News evidence with source URL, publication time, retrieval time, content hash, and structured payload.
- Daily runs with status, stages, settings, inputs, telemetry, errors, and report text.
- Recommendations with action, horizon, amount, payload, and run link.
- Later recommendation outcomes.

SQLite monetary values must not use floating-point storage. PostgreSQL uses exact numeric types. All operational timestamps are timezone-aware.

## 8. Portfolio input

Portfolio import supports CSV, dashboard editing, and API input. Each holding includes:

- Six-digit fund code when resolved.
- Fund name.
- Market value.
- Optional units, average cost, holding return, category, share class, acquisition date, and benchmark.
- Confirmation status.
- Source and timezone-aware `as_of` timestamp.

A and C share classes stay separate. Duplicate records for the same share class are rejected until combined. Unknown cash remains null. A confirmed cash balance requires a timestamp.

The system must not infer units, cost basis, acquisition date, or cash from screenshots.

## 9. Approved universe

Research covers:

- Current holdings.
- Explicitly enabled candidates in `config/fund_universe.csv`.
- Disabled benchmark funds needed for comparisons.

The initial candidate universe is empty. The LLM cannot expand it. V1 does not attempt to scan thousands of funds.

## 10. Market data

The initial adapter reads Eastmoney public fund pages by six-digit code. It retrieves identity and historical unit NAV plus the source's daily growth field. The application chains daily growth into a total-return index.

Every observation includes source and retrieval time. Validation rejects mismatched codes, excessive responses, invalid JSON, duplicate dates, unsorted dates, and insufficient freshness.

Cache valid provider responses for a bounded time. External requests use timeouts and limited retries. Offline mode reads cached data only and never fabricates prices.

Underlying stock holdings are outside the current adapter. A future holdings provider must record disclosure date, reporting period, source, and whether the data is a top-holdings or full-portfolio disclosure.

## 11. Quantitative metrics

For each fund, calculate when data permits:

- Returns over 1, 5, 20, 60, 126, and 252 NAV observations.
- MA20, MA50, and MA200 relationships.
- Annualized volatility.
- Maximum drawdown.
- Sharpe ratio using an explicit risk-free rate.
- Sortino ratio.
- Freshness and observation counts.

For the portfolio, align common dates before calculating:

- Correlation matrix.
- Constant-current-weight volatility proxy.
- Maximum drawdown proxy.
- Marginal or component risk contribution.

These are research estimates, not realized account performance.

## 12. Tactical and strategic signals

Tactical signals describe roughly 5–20 NAV observations and are monitoring information. Strategic signals cover longer allocation questions.

Component scores use explicit weights and report coverage. Missing data removes the component from the weighted calculation and lowers coverage; it must not be replaced with an arbitrary neutral score.

Potential inputs include:

- Short- and medium-term return.
- Moving-average trend.
- Volatility and drawdown.
- Benchmark-relative return.
- Macro regime.
- Recent evidence score.
- Verified profile attributes.
- Current weight, sector concentration, and cross-fund correlation.

Low coverage blocks actionable results.

## 13. Macro data

Python classifies simple regimes for China and the United States from compatible, fresh observations:

- Risk regime.
- Inflation regime.
- Interest-rate regime.

Units and maximum ages are explicit. Stale or incompatible values remain missing. The LLM may explain a regime but cannot classify the stored numeric inputs differently.

## 14. News research

When enabled, build a bounded number of queries from portfolio categories and approved candidates. The lookback window is 24–72 hours.

Prioritize:

1. Central banks and official statistics agencies.
2. Fund managers and official disclosures.
3. Publications with editorial accountability.

Structured research records contain title, source URL, publication time, fact, interpretation, uncertainty, topic, affected symbols, impact score, and confidence.

Reject evidence when:

- The URL was not returned by the Web Search call.
- Publication time is absent, outside the window, or after the run time.
- Affected symbols are empty or outside the allowed universe.
- The schema is invalid.

Deduplicate by normalized source URL. Never use retrieval time as publication time.

## 15. LLM instructions

The research prompt states that the model is a classification component rather than a trading agent. It must treat web text as untrusted, avoid invented facts and numbers, separate fact from interpretation, represent uncertainty, and return no trading instruction.

The analyst receives only structured recommendations, macro state, and accepted evidence. It can write thesis, risks, and invalidation conditions. Any unknown or duplicate symbol or unrecognized evidence ID fails validation.

One retry may be handled by the SDK. Persistent failure records partial health and leaves deterministic recommendations intact.

## 16. Allocation and risk gate

The amount engine uses total assets, known cash, cash buffer, current value, sector exposure, and configured maximums. It ranks shared cash allocations deterministically.

Default research constraints include:

- Minimum cash ratio: 10%.
- Maximum fund position: 20%.
- Maximum sector exposure: 35%.
- Maximum new position: 5%.
- Maximum daily buy total: 10%.
- Minimum transaction amount: CNY 100.
- Minimum strategic buy score: 70.
- Minimum confidence: 0.65.
- Minimum data coverage: 0.80.

These defaults are initial engineering constraints rather than optimized investment parameters.

The RiskGate may force WATCH or reduce an amount for:

- Unconfirmed or stale portfolio/cash.
- Missing or stale NAV.
- Insufficient coverage or confidence.
- Conflicting signals.
- Excessive position, sector, correlation, volatility, or daily purchase amount.
- Unknown subscription status or daily limit.
- Unknown acquisition date, minimum holding period, or redemption fee for a reduction.

Fund trading rules older than seven days require re-verification.

## 17. Recommendation contract

Allowed actions are `BUY`, `HOLD`, `REDUCE`, and `WATCH`.

Each recommendation records:

- Symbol, name, and whether currently held.
- Strategic and tactical scores and components.
- Action and proposed amount.
- Data coverage and rule-based confidence.
- Triggered and blocking rules.
- Thesis, risks, and invalidation conditions.
- Evidence identifiers.
- Market source, NAV date, and optional benchmark.

Confidence is an engineering score, not a calibrated probability of profit.

## 18. Daily report

The Markdown report contains:

- Portfolio totals and risk summary.
- Macro regimes.
- Current holdings table.
- Tactical watchlist and strategic candidates.
- Risk and data warnings.
- Recommendation explanations.
- Material news and source links.
- NAV source links and dates.
- Execution caveats and disclaimer.

Reports must make the origin of each conclusion inspectable. Phrases such as "market sources say" without a link are not acceptable.

## 19. Dashboard

The local Streamlit dashboard provides:

- Overview.
- Portfolio import and editing.
- Daily briefing.
- Recommendation history.
- Outcome evaluation.
- Data health.
- Settings and verified fund-profile editing.

The dashboard does not display secrets. It must explain WATCH, unknown data, revision semantics, and the difference between research return and transaction return.

## 20. Failure and freshness behavior

Each provider or optional module can fail independently. Market, quantitative, portfolio, and risk stages should continue when news or notification services fail. No failure path may invent data.

Every run records stage health. The final status is:

- `SUCCESS` when required stages complete and configured optional stages succeed.
- `PARTIAL` when useful output exists but a provider or optional configured stage is missing or failed.
- `FAILED` when the run cannot produce a valid stored result.

## 21. Outcome tracking

For each final daily BUY or REDUCE revision, use the first available NAV after the recommendation date as the research reference point. Update returns after 1, 5, 20, and 60 subsequent NAV observations.

Track:

- Asset return.
- Optional same-date benchmark excess return.
- Directional hit for BUY and REDUCE.
- Worst drawdown.
- Counts of matured and missing observations.
- Confidence buckets after enough samples accumulate.

Only the final revision for a fund and day enters aggregate evaluation. Earlier same-day revisions remain auditable but are not combined.

This evaluation excludes actual fees, order confirmation NAV, settlement timing, and execution constraints.

## 22. Backtesting

V1 backtests only price-based baseline signals using next-observation execution and explicit fee assumptions. It does not reconstruct historical LLM news decisions because doing so invites look-ahead and source-availability bias.

Live LLM research is evaluated prospectively from the date the software begins storing runs.

## 23. Cost controls

- Aggregate research topics into a small number of queries.
- Default to at most five research queries and twelve LLM calls per daily run.
- Limit each research response to two Web Search tool calls.
- Use the stronger optional review model only for elevated risk or conflicting signals.
- Record calls and token usage.
- Estimate cost only when the user supplies explicit per-unit prices.

## 24. Security and privacy

- Keep `.env`, screenshots, private portfolio files, databases, and generated reports out of version control.
- Never commit API keys.
- Never store OpenAI credentials in the database.
- Redact secrets from settings snapshots and logs.
- Protect API write operations with `API_TOKEN` when the separate API is exposed.
- Bind local services to loopback by default.
- Treat all external text as untrusted content.

## 25. Testing

Automated tests cover:

- Decimal money handling and database migration.
- Portfolio validation, replacement, and snapshots.
- NAV parsing, total-return construction, freshness, cache, and retries.
- Quantitative metrics and aligned portfolio risk.
- Signal coverage and ranking.
- Research schema, source filtering, date filtering, and fake-client behavior.
- Allocation and risk vetoes.
- Restricted analyst-field ownership.
- Daily degradation, persistence, replay, reporting, and API authorization.
- Dashboard rendering.
- Outcome alignment and look-ahead-safe baseline backtesting.

Tests must never consume a real paid API token.

## 26. Acceptance criteria

V1 is acceptable when a user can manually start the local dashboard, update a verified portfolio, run a daily briefing, inspect sources and risk reasons, review recommendation history, and evaluate matured outcomes.

The system succeeds by being traceable, repeatable, and measurable. Initial evaluation should focus on data completeness, run reliability, source quality, calibration, and forward outcome quality over at least 60–90 days. Adding a larger LLM is not a substitute for fixing data, signals, or portfolio construction.

# Architecture Decisions

## Scope

- V1 supports one CNY account containing mainland Chinese public-fund share classes.
- The application provides research and recommendations only. It has no broker integration and never places orders.
- Holdings and approved candidates define the research universe. The LLM cannot add securities.
- A and C share classes remain separate instruments because fees and identifiers differ.
- Unknown cash remains unknown. Screenshot amounts are never used to infer units, cost basis, or available cash.
- A recommendation amount is produced only after the user confirms holdings, cash, timestamps, and applicable trading rules.
- Fund categories are manual, coarse risk labels. They are not real-time look-through holdings.

## Application shape

V1 is a modular Python monolith with a Streamlit dashboard, optional FastAPI interface, SQLAlchemy persistence, and provider abstractions. A single-user local tool does not need microservices or a portfolio optimizer.

The main flow is:

```text
portfolio + market data + macro data + researched evidence
    -> deterministic metrics and scores
    -> Python allocation proposal
    -> deterministic risk gate
    -> restricted LLM explanation
    -> report, audit record, and later outcome tracking
```

The research layer never controls the portfolio engine directly. Python owns numeric calculations, action fields, position sizes, confidence, and final risk decisions.

## Storage

- SQLite is the default local database. Monetary values use exact decimal text instead of SQLite `REAL`.
- PostgreSQL uses `NUMERIC(24,8)` and timezone-aware timestamps for a persistent installation.
- Alembic manages schema changes.
- The current account cash balance is stored on the account, while complete historical state is frozen in portfolio snapshots and daily-run inputs.
- Each run stores relevant inputs, settings, metrics, evidence, recommendations, telemetry, and provider health.
- Recommendation actions, amounts, results, and source records also have dedicated tables for querying and evaluation.

## Providers and trust boundaries

- The initial market adapter reads the public Eastmoney source also used by AKShare. It parses JSON data without executing remote JavaScript.
- HTTP access has shared timeout, retry, size, validation, and cache behavior.
- Provider protocols allow replacement without changing the signal engine.
- Web pages and LLM output are untrusted input.
- Research output must pass a strict schema, source-URL membership checks, publication-time checks, recency checks, and approved-symbol checks.
- Missing news, macro data, market data, or model configuration is shown explicitly as partial or insufficient data.
- Secrets remain in environment variables and are excluded from settings snapshots, logs, reports, and the database.

## LLM boundary

The research model classifies recent evidence. It cannot issue trading instructions or invent facts, sources, holdings, prices, or metrics. The analyst model explains recommendations after the deterministic risk gate. It cannot change actions, amounts, scores, confidence, or evidence identifiers.

LLM failure degrades the run. It does not erase valid quantitative results or cause fabricated neutral evidence.

## Fund-specific constraints

- Unit NAV and reconstructed total-return series are distinct values.
- The total-return index chains the source's daily growth percentages to account for distributions represented by that field.
- NAV freshness uses valuation-day approximations, with a larger allowance for QDII funds.
- Recommendations must check subscription status, daily purchase limits, acquisition date, minimum holding period, redemption fee, and settlement notes when relevant.
- Transaction NAV is unknown at recommendation time, so suggested amounts are planning values rather than executable orders.

## Sources used for interface design

- [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [OpenAI Web Search](https://developers.openai.com/api/docs/guides/tools-web-search)
- [AKShare public-fund adapter source](https://github.com/akfamily/akshare/blob/main/akshare/fund/fund_em.py)

These sources informed interface implementation. They do not constitute a current investment judgment.

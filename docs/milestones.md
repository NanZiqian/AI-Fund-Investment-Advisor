# Milestone Verification Record

Implementation followed the staged plan in `spec.md`. Automated tests use fixed fixtures, mocked HTTP, or fake LLM clients and do not consume paid API tokens.

| Stage | Scope | Recorded status |
|---|---|---|
| 1 | Project structure, configuration, database, migrations, health endpoint | Completed |
| 2 | Portfolio, cash, CSV import, and snapshots | Completed |
| 3 | Market data, fund profiles, cache, and retries | Completed |
| 4 | Returns, volatility, drawdown, and portfolio risk | Completed |
| 5 | Tactical and strategic scores, coverage, and ranking | Completed |
| 6 | News research, macro data, and source persistence | Completed with fake external clients |
| 7 | Proposed amounts and deterministic risk vetoes | Completed |
| 8 | Restricted LLM explanations | Completed with a fake LLM client |
| 9 | Daily pipeline, report, and notifications | Completed with fake notification clients |
| 10 | Streamlit dashboard | Completed |
| 11 | Manual execution workflow | Completed |
| 12 | 1/5/20/60-observation outcome evaluation | Completed |

The last full local verification recorded 52 passing tests and one skipped PostgreSQL test. Ruff lint and formatting checks passed at that time. The Eastmoney adapter was exercised once online for the seven funds from the original screenshot. The OpenAI, FRED, and Telegram paths have not been validated against real credentials.

The portfolio imported from the screenshot intentionally remains unconfirmed when cash, date, units, or share class cannot be verified. The system does not fabricate missing values or produce transaction amounts from an undated screenshot.

No Python environment is committed. Current users create and manage the documented Conda environment themselves.

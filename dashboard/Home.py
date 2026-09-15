import csv
import io
import json
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import streamlit as st
from sqlalchemy import select

from app.config import Settings
from app.db import session_factory
from app.db.models import DailyRun, Instrument, Recommendation
from app.jobs.daily import run_daily
from app.portfolio import import_portfolio, parse_csv, portfolio_view
from app.report import number, pct
from app.schemas import ProfileUpdate

st.set_page_config(page_title="FundScope · Fund Research Assistant", page_icon="◈", layout="wide")
st.markdown(
    """<style>
.stApp { background:#f4f6f9; color:#14263d; }
[data-testid="stSidebar"] { background:#14263d; }
[data-testid="stSidebar"] * { color:#e1e8f2; }
h1,h2,h3 { letter-spacing:-.025em; }
[data-testid="stMetric"] { background:white; border:1px solid #e0e6ef; border-radius:12px;
 padding:18px 22px; box-shadow:0 3px 12px #14263d04; }
[data-testid="stMetricLabel"] { color:#6c7d91; }
[data-testid="stMetricValue"] { color:#14263d !important; }
[data-testid="stAlert"] p { color:#5c4f25 !important; }
.eyebrow { color:#718298; font-size:12px; letter-spacing:.18em; font-weight:600; }
.card { background:white; border:1px solid #e0e6ef; border-radius:12px; padding:20px 24px; }
div.stButton > button[kind="primary"] { background:#256c62; border-color:#256c62; }
</style>""",
    unsafe_allow_html=True,
)

settings = Settings()
with st.sidebar:
    st.markdown("## ◈ FundScope")
    st.caption("PUBLIC FUND RESEARCH")
    st.divider()
    page = st.radio(
        "Workspace",
        [
            "Overview",
            "Portfolio",
            "Daily Briefing",
            "Recommendation History",
            "Evaluation",
            "Data Health",
            "Settings",
        ],
        label_visibility="collapsed",
    )
    st.divider()
    st.caption("CNY · Asia/Shanghai")
    st.caption("You review every recommendation. The system never executes trades.")

try:
    with session_factory(settings.database_url)() as session:
        portfolio = portfolio_view(session)
        runs = list(
            session.scalars(select(DailyRun).order_by(DailyRun.started_at.desc()).limit(100))
        )
        latest = next((r for r in runs if r.status in ("SUCCESS", "PARTIAL")), None)
        recs = (
            list(
                session.scalars(
                    select(Recommendation).where(Recommendation.daily_run_id == latest.id)
                )
            )
            if latest
            else []
        )
        instruments = list(session.scalars(select(Instrument).order_by(Instrument.symbol)))
except Exception:
    st.error("The database is not ready. Run python -m app.cli init-db, then import a portfolio.")
    st.stop()

st.markdown(
    '<div class="eyebrow">PERSONAL INVESTMENT RESEARCH</div>',
    unsafe_allow_html=True,
)
st.title(page)


def recommendation_table(items):
    return pd.DataFrame(
        [
            {
                "Fund code": r["symbol"],
                "Fund name": r["name"],
                "Action": r["action"],
                "Proposed amount / CNY": number(r["proposed_amount"]),
                "Strategic score": r["strategic"]["score"],
                "Tactical score": r["tactical"]["score"],
                "Data coverage": pct(r["data_coverage"]),
                "Confidence": pct(r["confidence"]),
            }
            for r in items
        ]
    )


if page == "Overview":
    st.caption("Start with holdings and evidence so every investment judgment remains auditable.")
    display = (
        latest.inputs.get("portfolio", portfolio)
        if latest and latest.inputs.get("portfolio_import") == portfolio
        else portfolio
    )
    if latest and latest.inputs.get("portfolio_import") != portfolio:
        st.info(
            "This page shows the current imported portfolio. The latest report used an earlier "
            "snapshot; generate a new briefing to refresh the research."
        )
    if portfolio["warnings"]:
        st.warning(" · ".join(portfolio["warnings"]))
    cols = st.columns(4)
    cols[0].metric("Invested", f"¥ {number(display['invested'])}")
    cols[1].metric("Available cash", number(display["cash"]))
    cols[2].metric("Total assets", number(display["total"]))
    risk = latest.inputs.get("portfolio_risk", {}) if latest else {}
    cols[3].metric("Annualized volatility", pct(risk.get("volatility")))
    st.caption(
        "Amounts use imported records or known units × published NAV. Undated screenshot "
        "amounts are for verification only."
    )
    left, right = st.columns([1.3, 1])
    with left:
        st.subheader("Portfolio Allocation")
        if display["positions"]:
            chart = pd.DataFrame(
                {
                    "Fund": [p["name"] for p in display["positions"]],
                    "Amount": [float(p["market_value"]) for p in display["positions"]],
                }
            )
            st.bar_chart(chart.set_index("Fund"), horizontal=True, color="#347f74", height=320)
        else:
            st.info("Import a CSV in Portfolio first.")
    with right:
        st.subheader("Latest Research")
        if latest:
            st.caption(f"{latest.started_at:%Y-%m-%d %H:%M %Z} · {latest.status}")
            counts = {
                a: sum(r.action == a for r in recs) for a in ("BUY", "HOLD", "REDUCE", "WATCH")
            }
            counters = st.columns(2)
            for idx, (action, count) in enumerate(counts.items()):
                counters[idx % 2].metric(action, count)
            st.caption(
                "WATCH means monitoring or insufficient data. Confidence is an uncalibrated "
                "rule-based score."
            )
        else:
            st.info("No research report is available yet.")
    st.subheader("Portfolio Research List")
    st.dataframe(recommendation_table([r.payload for r in recs]), hide_index=True, width="stretch")
    with st.expander("Run Daily Analysis"):
        offline = st.checkbox("Use local data only (offline)", value=True)
        st.caption(
            "Online mode refreshes fund NAV data. The research module calls an LLM only when "
            "enabled in the local .env file."
        )
        if st.button("Generate New Research Briefing", type="primary"):
            try:
                with st.spinner("Updating data and applying risk controls…"):
                    run_daily(settings, offline=offline, refresh=True)
                st.rerun()
            except Exception as exc:
                st.error(f"Run failed: {type(exc).__name__}. See Data Health.")

elif page == "Portfolio":
    st.caption("Record A and C share classes separately. Enter amounts and units as decimal text.")
    rows = portfolio["positions"]
    if rows:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Code": p["symbol"],
                        "Name": p["name"],
                        "Amount": p["market_value"],
                        "Holding return": p["holding_profit"],
                        "Units": p["quantity"],
                        "As of": p["as_of"],
                        "Confirmed": p["confirmed"],
                        "Source": p["source"],
                    }
                    for p in rows
                ]
            ),
            hide_index=True,
            width="stretch",
        )
    st.subheader("Import / Manual Edit")
    keys = [
        "symbol",
        "name",
        "market_value",
        "holding_profit",
        "quantity",
        "average_cost",
        "as_of",
        "acquired_on",
        "category",
        "share_class",
        "qdii",
        "confirmed",
        "source",
    ]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=keys)
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row.get(k) for k in keys})
    st.download_button(
        "Export Current Portfolio CSV", buffer.getvalue(), "portfolio.csv", "text/csv"
    )
    upload = st.file_uploader(
        "Upload CSV (replace current portfolio; retain historical snapshots)", type=["csv"]
    )
    content = upload.getvalue().decode("utf-8-sig") if upload else buffer.getvalue()
    edited = st.text_area("CSV content (editable)", value=content, height=230)
    col1, col2 = st.columns(2)
    cash = col1.text_input(
        "Investable cash / CNY (blank means unknown)", value=portfolio["cash"] or ""
    )
    as_of = col2.text_input(
        "Cash / portfolio verification time (include timezone)",
        value=portfolio["as_of"] or "",
        placeholder="2026-09-15T20:00:00+08:00",
    )
    confirm_all = st.checkbox(
        "I verified all fund codes, share classes, and amounts, and want to timestamp this "
        "portfolio update"
    )
    if st.button("Save Portfolio", type="primary"):
        try:
            payload = parse_csv(edited, cash or None, as_of or None)
            if confirm_all:
                if not as_of:
                    raise ValueError("A confirmed portfolio requires a verification time")
                for p in payload.positions:
                    p.as_of = datetime.fromisoformat(as_of)
                    p.confirmed = True
                    p.source = "user:manual_verified"
                payload = type(payload).model_validate(payload.model_dump())
            with session_factory(settings.database_url)() as session:
                import_portfolio(session, payload)
                session.commit()
            st.success("Saved. The next briefing will use this portfolio.")
        except Exception as exc:
            st.error(f"Import was not saved: {exc}")
    st.caption(
        "acquired_on is used for redemption-fee and holding-period checks. For multiple lots, "
        "use the conservative most recent purchase date. "
        "Leave it blank when uncertain; the system will block reduction amounts."
    )

elif page == "Daily Briefing":
    reports = [r for r in runs if r.report]
    if not reports:
        st.info("No daily briefing is available. Run the analysis from Overview.")
    else:
        chosen = st.selectbox(
            "Select report",
            reports,
            format_func=lambda r: f"{r.started_at:%Y-%m-%d %H:%M} · {r.status} · {r.id[:8]}",
        )
        st.download_button(
            "Download Markdown Briefing", chosen.report, f"brief-{chosen.id}.md", "text/markdown"
        )
        st.markdown(chosen.report)

elif page == "Recommendation History":
    a, b, c = st.columns(3)
    action = a.selectbox("Action", ["All", "BUY", "HOLD", "REDUCE", "WATCH"])
    symbol = b.selectbox("Fund", ["All"] + [i.symbol for i in instruments])
    start_date = c.date_input("Start date", value=date.today().replace(day=1))
    kind = st.selectbox("Horizon", ["All", "STRATEGIC", "TACTICAL"])
    with session_factory(settings.database_url)() as session:
        items = list(
            session.scalars(select(Recommendation).order_by(Recommendation.created_at.desc()))
        )
    filtered = [
        r
        for r in items
        if (action == "All" or r.action == action)
        and (symbol == "All" or r.payload["symbol"] == symbol)
        and r.created_at.date() >= start_date
        and (kind == "All" or r.recommendation_type == kind)
    ]
    st.dataframe(
        recommendation_table([r.payload for r in filtered]), hide_index=True, width="stretch"
    )
    st.caption(
        "Same-day refreshes retain earlier revisions. Revisions are alternatives and must not "
        "be combined into one trading plan."
    )
    for rec in filtered[:30]:
        with st.expander(f"{rec.created_at:%m-%d %H:%M} · {rec.payload['name']} · {rec.action}"):
            st.write(rec.payload["thesis"])
            st.write("Risk controls:", rec.payload["rules_triggered"])
            st.write("Invalidation conditions:", rec.payload["invalidation_conditions"])
            st.json(rec.payload)

elif page == "Evaluation":
    st.caption(
        "Uses the first available NAV after publication as the reference point and tracks "
        "NAV-observation horizons. This is neither transaction return nor a complete strategy "
        "backtest."
    )
    try:
        from app.outcomes import evaluate, update_outcomes

        with session_factory(settings.database_url)() as session:
            if st.button("Update Outcomes from Available NAV Data"):
                update_outcomes(session)
                session.commit()
            result = evaluate(session)
        st.metric("Deduplicated Daily Recommendations", result["recommendation_count"])
        horizon = st.selectbox("Observation horizon", ["5d", "20d", "60d", "1d"])
        comparison = []
        for action in ("BUY", "REDUCE"):
            values = result[action][horizon]
            comparison.append(
                {
                    "Direction": action,
                    "Recommendations": result[action]["count"],
                    "Matured": values["matured_count"],
                    "Hit rate": pct(values["hit_rate"]),
                    "Average asset return": pct(values["average_asset_return"]),
                    "Median asset return": pct(values["median_asset_return"]),
                    "Average excess vs benchmark": pct(values["average_excess_asset_return"]),
                    "Worst drawdown": pct(values["worst_drawdown"]),
                }
            )
        st.dataframe(pd.DataFrame(comparison), hide_index=True, width="stretch")
        st.caption(
            "A BUY hit means the asset later rose; a REDUCE hit means it later fell. Return "
            "columns always retain the asset's original direction. Only the final same-day "
            "revision per fund is counted. Immature observations and missing benchmarks show "
            "as unknown."
        )
        st.subheader("Confidence Calibration · 20 Observations")
        if result["confidence_calibration_20d"]:
            st.dataframe(pd.DataFrame(result["confidence_calibration_20d"]), hide_index=True)
        else:
            st.info(
                "No matured BUY or REDUCE samples are available. The system accumulates outcomes "
                "daily; immature data cannot measure accuracy."
            )
    except ImportError:
        st.info("The outcome tracking module is not ready.")

elif page == "Data Health":
    if not runs:
        st.info("No run records are available.")
    else:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Time": r.started_at,
                        "Status": r.status,
                        "Run ID": r.id,
                        "Error": r.error_message,
                    }
                    for r in runs
                ]
            ),
            hide_index=True,
            width="stretch",
        )
        st.subheader("Latest Module Status")
        st.json(runs[0].health)
        st.subheader("Runtime and Cost")
        st.json(runs[0].telemetry)
        st.caption(
            "Cost is null until model prices are configured; null does not mean free. "
            "The calendar approximates valuation days with weekdays, so holidays may "
            "conservatively mark data as stale."
        )

elif page == "Settings":
    st.caption(
        "Configure models, secrets, notifications, and risk thresholds in the local .env file. "
        "This page never displays secrets."
    )
    st.json(settings.public())
    st.subheader("Fund Profile and Trading Rules")
    st.caption(
        "Enter verified information from the fund manager or sales platform. Do not invent "
        "scores to increase coverage. Recheck rules older than seven days. daily_limit=null "
        "means you verified that no limit was stated."
    )
    if instruments:
        item = st.selectbox("Fund", instruments, format_func=lambda i: f"{i.symbol} {i.name}")
        profile = st.text_area(
            "Profile JSON", value=json.dumps(item.profile, ensure_ascii=False, indent=2), height=260
        )
        if st.button("Save Verified Profile"):
            try:
                validated = ProfileUpdate.model_validate_json(profile)
                with session_factory(settings.database_url)() as session:
                    session.get(Instrument, item.id).profile = validated.model_dump(mode="json")
                    session.commit()
                st.success("Saved. Generate a new daily briefing.")
            except Exception as exc:
                st.error(f"Not saved: {exc}")
    st.code("python -m app.cli import-universe config/fund_universe.csv", language="bash")
    st.caption(
        "You maintain and approve the candidate universe. No new funds are added by default."
    )

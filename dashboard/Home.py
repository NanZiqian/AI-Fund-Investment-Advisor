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

st.set_page_config(page_title="知基 · 基金研究助手", page_icon="◈", layout="wide")
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
    st.markdown("## ◈ 知基")
    st.caption("PUBLIC FUND RESEARCH")
    st.divider()
    page = st.radio(
        "工作台",
        ["组合总览", "持仓管理", "每日简报", "历史建议", "表现评估", "数据健康", "设置"],
        label_visibility="collapsed",
    )
    st.divider()
    st.caption("人民币 · Asia/Shanghai")
    st.caption("研究建议由你审核，系统不执行交易。")

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
    st.error("数据库尚未准备好。请先运行 python -m app.cli init-db，再导入持仓。")
    st.stop()

st.markdown(
    '<div class="eyebrow">PERSONAL INVESTMENT RESEARCH / 个人研究工作台</div>',
    unsafe_allow_html=True,
)
st.title(page)


def recommendation_table(items):
    return pd.DataFrame(
        [
            {
                "基金代码": r["symbol"],
                "基金名称": r["name"],
                "动作": r["action"],
                "建议金额 / 元": number(r["proposed_amount"]),
                "长期评分": r["strategic"]["score"],
                "短期评分": r["tactical"]["score"],
                "数据覆盖": pct(r["data_coverage"]),
                "置信度": pct(r["confidence"]),
            }
            for r in items
        ]
    )


if page == "组合总览":
    st.caption("从持仓和证据出发，让每一个投资判断都能回看。")
    display = (
        latest.inputs.get("portfolio", portfolio)
        if latest and latest.inputs.get("portfolio_import") == portfolio
        else portfolio
    )
    if latest and latest.inputs.get("portfolio_import") != portfolio:
        st.info("本页显示当前导入的持仓；最近报告使用的是此前记录，请重新生成简报以更新研究结果。")
    if portfolio["warnings"]:
        st.warning(" · ".join(portfolio["warnings"]))
    cols = st.columns(4)
    cols[0].metric("持仓金额", f"¥ {number(display['invested'])}")
    cols[1].metric("可用现金", number(display["cash"]))
    cols[2].metric("总资产", number(display["total"]))
    risk = latest.inputs.get("portfolio_risk", {}) if latest else {}
    cols[3].metric("组合年化波动", pct(risk.get("volatility")))
    st.caption("金额以已导入记录或已知份额 × 已披露净值计算；日期不明的截图金额只供核对。")
    left, right = st.columns([1.3, 1])
    with left:
        st.subheader("持仓分布")
        if display["positions"]:
            chart = pd.DataFrame(
                {
                    "基金": [p["name"] for p in display["positions"]],
                    "金额": [float(p["market_value"]) for p in display["positions"]],
                }
            )
            st.bar_chart(chart.set_index("基金"), horizontal=True, color="#347f74", height=320)
        else:
            st.info("先在持仓管理中导入 CSV。")
    with right:
        st.subheader("本次研究")
        if latest:
            st.caption(f"{latest.started_at:%Y-%m-%d %H:%M %Z} · {latest.status}")
            counts = {
                a: sum(r.action == a for r in recs) for a in ("BUY", "HOLD", "REDUCE", "WATCH")
            }
            counters = st.columns(2)
            for idx, (action, count) in enumerate(counts.items()):
                counters[idx % 2].metric(action, count)
            st.caption("WATCH 表示观察或数据不足；置信度是未校准的规则评分。")
        else:
            st.info("尚无研究报告。")
    st.subheader("持仓研究清单")
    st.dataframe(recommendation_table([r.payload for r in recs]), hide_index=True, width="stretch")
    with st.expander("运行每日分析"):
        offline = st.checkbox("只使用本地数据（不联网）", value=True)
        st.caption("联网模式更新基金净值；研究模块仅在本地 .env 启用后调用模型。")
        if st.button("生成新的研究简报", type="primary"):
            try:
                with st.spinner("正在更新数据并运行风控…"):
                    run_daily(settings, offline=offline, refresh=True)
                st.rerun()
            except Exception as exc:
                st.error(f"运行失败：{type(exc).__name__}。请查看数据健康页。")

elif page == "持仓管理":
    st.caption("同一只基金的 A / C 份额分别记录；金额和份额用十进制文本填写。")
    rows = portfolio["positions"]
    if rows:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "代码": p["symbol"],
                        "名称": p["name"],
                        "金额": p["market_value"],
                        "持有收益": p["holding_profit"],
                        "份额": p["quantity"],
                        "记录日期": p["as_of"],
                        "已确认": p["confirmed"],
                        "来源": p["source"],
                    }
                    for p in rows
                ]
            ),
            hide_index=True,
            width="stretch",
        )
    st.subheader("导入 / 手动编辑")
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
    st.download_button("导出当前持仓 CSV", buffer.getvalue(), "portfolio.csv", "text/csv")
    upload = st.file_uploader("上传 CSV（替换当前持仓，历史快照保留）", type=["csv"])
    content = upload.getvalue().decode("utf-8-sig") if upload else buffer.getvalue()
    edited = st.text_area("CSV 内容（可直接修改）", value=content, height=230)
    col1, col2 = st.columns(2)
    cash = col1.text_input("可投资现金 / 元（留空表示未知）", value=portfolio["cash"] or "")
    as_of = col2.text_input(
        "现金 / 持仓核对时间（含时区）",
        value=portfolio["as_of"] or "",
        placeholder="2026-09-15T20:00:00+08:00",
    )
    confirm_all = st.checkbox("我已核对本次所有基金代码、份额类别与金额，并以填写时间更新持仓记录")
    if st.button("保存持仓", type="primary"):
        try:
            payload = parse_csv(edited, cash or None, as_of or None)
            if confirm_all:
                if not as_of:
                    raise ValueError("确认持仓需要填写核对时间")
                for p in payload.positions:
                    p.as_of = datetime.fromisoformat(as_of)
                    p.confirmed = True
                    p.source = "user:manual_verified"
                payload = type(payload).model_validate(payload.model_dump())
            with session_factory(settings.database_url)() as session:
                import_portfolio(session, payload)
                session.commit()
            st.success("已保存。生成新简报后将使用本次持仓。")
        except Exception as exc:
            st.error(f"导入未保存：{exc}")
    st.caption(
        "购买日期 acquired_on 用于赎回费 / 持有期检查；多笔持仓需填写保守的最近购买日期。"
        "不确定时留空，系统会停止生成减仓金额。"
    )

elif page == "每日简报":
    reports = [r for r in runs if r.report]
    if not reports:
        st.info("暂无日报，请从组合总览运行分析。")
    else:
        chosen = st.selectbox(
            "选择报告",
            reports,
            format_func=lambda r: f"{r.started_at:%Y-%m-%d %H:%M} · {r.status} · {r.id[:8]}",
        )
        st.download_button(
            "下载 Markdown 日报", chosen.report, f"brief-{chosen.id}.md", "text/markdown"
        )
        st.markdown(chosen.report)

elif page == "历史建议":
    a, b, c = st.columns(3)
    action = a.selectbox("动作", ["全部", "BUY", "HOLD", "REDUCE", "WATCH"])
    symbol = b.selectbox("基金", ["全部"] + [i.symbol for i in instruments])
    start_date = c.date_input("开始日期", value=date.today().replace(day=1))
    kind = st.selectbox("时间周期", ["全部", "STRATEGIC", "TACTICAL"])
    with session_factory(settings.database_url)() as session:
        items = list(
            session.scalars(select(Recommendation).order_by(Recommendation.created_at.desc()))
        )
    filtered = [
        r
        for r in items
        if (action == "全部" or r.action == action)
        and (symbol == "全部" or r.payload["symbol"] == symbol)
        and r.created_at.date() >= start_date
        and (kind == "全部" or r.recommendation_type == kind)
    ]
    st.dataframe(
        recommendation_table([r.payload for r in filtered]), hide_index=True, width="stretch"
    )
    st.caption("同日刷新会保留旧版本；不同版本是替代方案，不可累加成交易计划。")
    for rec in filtered[:30]:
        with st.expander(f"{rec.created_at:%m-%d %H:%M} · {rec.payload['name']} · {rec.action}"):
            st.write(rec.payload["thesis"])
            st.write("风控：", rec.payload["rules_triggered"])
            st.write("失效条件：", rec.payload["invalidation_conditions"])
            st.json(rec.payload)

elif page == "表现评估":
    st.caption(
        "使用建议发布后第一个可获得净值作为参考起点，按净值观测期跟踪。不是成交收益或完整策略回测。"
    )
    try:
        from app.outcomes import evaluate, update_outcomes

        with session_factory(settings.database_url)() as session:
            if st.button("更新已有净值的跟踪结果"):
                update_outcomes(session)
                session.commit()
            result = evaluate(session)
        st.metric("去重后的每日建议数", result["recommendation_count"])
        horizon = st.selectbox("观测周期", ["5d", "20d", "60d", "1d"])
        comparison = []
        for action in ("BUY", "REDUCE"):
            values = result[action][horizon]
            comparison.append(
                {
                    "方向": action,
                    "建议数": result[action]["count"],
                    "已到期": values["matured_count"],
                    "命中率": pct(values["hit_rate"]),
                    "资产平均收益": pct(values["average_asset_return"]),
                    "资产中位收益": pct(values["median_asset_return"]),
                    "相对基准超额": pct(values["average_excess_asset_return"]),
                    "最差回撤": pct(values["worst_drawdown"]),
                }
            )
        st.dataframe(pd.DataFrame(comparison), hide_index=True, width="stretch")
        st.caption(
            "BUY 命中 = 后续资产上涨；REDUCE 命中 = 后续资产下跌。收益列始终保留资产原始方向。"
            "同基金同日仅统计最终版本；未到期和缺基准均显示未知。"
        )
        st.subheader("置信度校准 · 20 期")
        if result["confidence_calibration_20d"]:
            st.dataframe(pd.DataFrame(result["confidence_calibration_20d"]), hide_index=True)
        else:
            st.info(
                "尚无到期的 BUY / REDUCE 样本。系统会每天积累结果，不能用未到期数据评价准确率。"
            )
    except ImportError:
        st.info("结果跟踪模块尚未就绪。")

elif page == "数据健康":
    if not runs:
        st.info("暂无运行记录。")
    else:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "时间": r.started_at,
                        "状态": r.status,
                        "运行 ID": r.id,
                        "错误": r.error_message,
                    }
                    for r in runs
                ]
            ),
            hide_index=True,
            width="stretch",
        )
        st.subheader("最近运行的模块状态")
        st.json(runs[0].health)
        st.subheader("耗时与成本")
        st.json(runs[0].telemetry)
        st.caption(
            "未配置各模型计费价格时，费用显示 null，不能当作免费。"
            "日历默认使用工作日近似，节假日可能使数据被保守地标记过期。"
        )

elif page == "设置":
    st.caption("模型、密钥、通知和风控阈值在本地 .env 中配置；此页面不显示密钥。")
    st.json(settings.public())
    st.subheader("基金资料与申赎规则")
    st.caption(
        "填写来自基金公司或销售平台的已核实资料，不能用主观分数补齐覆盖率。"
        "规则超过 7 天后须复核。daily_limit=null 表示已核实没有列明限额。"
    )
    if instruments:
        item = st.selectbox("基金", instruments, format_func=lambda i: f"{i.symbol} {i.name}")
        profile = st.text_area(
            "资料 JSON", value=json.dumps(item.profile, ensure_ascii=False, indent=2), height=260
        )
        if st.button("保存已核实资料"):
            try:
                validated = ProfileUpdate.model_validate_json(profile)
                with session_factory(settings.database_url)() as session:
                    session.get(Instrument, item.id).profile = validated.model_dump(mode="json")
                    session.commit()
                st.success("已保存。请重新生成日报。")
            except Exception as exc:
                st.error(f"未保存：{exc}")
    st.code("python -m app.cli import-universe config/fund_universe.csv", language="bash")
    st.caption("候选池由你维护和批准，默认不添加新基金。")

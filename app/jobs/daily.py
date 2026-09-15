import argparse
import hashlib
import json
import logging
import time
from dataclasses import asdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.analyst import explain
from app.config import Settings
from app.db import session_factory, utcnow
from app.db.models import DailyRun, Instrument, MacroObservation, News, Recommendation, Snapshot
from app.logging import configure_logging
from app.macro import equity_macro_score, fetch_fred, load_macro_csv, regime, save_macro
from app.notifications import notify_telegram
from app.portfolio import money, portfolio_view
from app.providers.base import is_fresh, validate_history
from app.providers.eastmoney import EastmoneyProvider, load_prices, save_prices
from app.quant import metrics, portfolio_risk
from app.recommendations import recommend
from app.report import daily_report
from app.research import ResearchClient, build_queries, evidence_summary, store_articles
from app.risk import RiskContext, RiskGate
from app.signals import calculate_signals, portfolio_fit

logger = logging.getLogger(__name__)

LLM_REQUEST_ERRORS = {
    "APIConnectionError",
    "APIStatusError",
    "APITimeoutError",
    "AuthenticationError",
    "BadRequestError",
    "InternalServerError",
    "NotFoundError",
    "OpenAIError",
    "PermissionDeniedError",
    "RateLimitError",
    "TypeError",
    "ValueError",
}


def valued_portfolio(session, histories):
    view = portfolio_view(session)
    for p in view["positions"]:
        data = histories.get(p["symbol"])
        if data and p["quantity"] is not None:
            p["market_value"] = str(money(Decimal(p["quantity"]) * data[-1].nav))
            p["valuation_source"] = data[-1].source
            p["nav_date"] = data[-1].date.isoformat()
    invested = sum((Decimal(p["market_value"]) for p in view["positions"]), Decimal(0))
    total = invested + Decimal(view["cash"]) if view["cash"] is not None else None
    view["invested"], view["total"] = (
        str(money(invested)),
        str(money(total)) if total is not None else None,
    )
    view["cash_ratio"] = str(Decimal(view["cash"]) / total) if total else None
    for p in view["positions"]:
        p["weight"] = str(Decimal(p["market_value"]) / total) if total else None
        p["invested_weight"] = str(Decimal(p["market_value"]) / invested) if invested else "0"
    return view


def portfolio_confirmed(view, now, max_age):
    def valid(value):
        if value is None:
            return False
        parsed = datetime.fromisoformat(value)
        return parsed.tzinfo is not None and now - timedelta(days=max_age) <= parsed <= now

    return (
        view["cash"] is not None
        and valid(view["as_of"])
        and all(p["confirmed"] and valid(p["as_of"]) for p in view["positions"])
    )


def run_daily(
    settings=None,
    *,
    offline=False,
    now=None,
    provider=None,
    researcher=None,
    session=None,
    refresh=False,
):
    settings = settings or Settings()
    now = now or utcnow()
    if now.tzinfo is None:
        raise ValueError("Timezone required")
    own_session = session is None
    session = session or session_factory(settings.database_url)()
    start = time.monotonic()
    run = None
    market = None
    timings = {}
    stage_start = start

    def stage(name, state):
        nonlocal stage_start
        elapsed = time.monotonic() - stage_start
        timings[name] = round(elapsed, 3)
        stage_start = time.monotonic()
        logger.info("run_id=%s stage=%s duration=%.3f status=%s", run.id, name, elapsed, state)

    try:
        initial = portfolio_view(session)
        instruments = list(session.scalars(select(Instrument).order_by(Instrument.symbol)))
        held_symbols = {p["symbol"] for p in initial["positions"]}
        universe = [i for i in instruments if i.symbol in held_symbols or i.approved]
        benchmark_symbols = {i.benchmark_symbol for i in universe if i.benchmark_symbol}
        market_universe = [i for i in instruments if i in universe or i.symbol in benchmark_symbols]
        digest = hashlib.sha256(
            json.dumps(
                {
                    "portfolio": initial,
                    "settings": settings.public(),
                    "universe": [(i.symbol, i.profile) for i in universe],
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()[:16]
        day = now.astimezone(ZoneInfo(settings.app_timezone)).date()
        base_key = f"{day}:{'offline' if offline else 'live'}:{digest}"
        previous = session.scalar(select(DailyRun).where(DailyRun.run_key == base_key))
        if previous and not refresh:
            if previous.status in ("SUCCESS", "PARTIAL", "RUNNING"):
                return previous
        key = base_key if previous is None else f"{base_key}:{now.isoformat()}"
        run = DailyRun(run_key=key, started_at=now, status="RUNNING")
        session.add(run)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            return session.scalar(select(DailyRun).where(DailyRun.run_key == key))
        if not initial["positions"]:
            raise ValueError("No portfolio imported")
        health, histories, metric_map, sources = {}, {}, {}, {}
        market_errors = {}
        holiday_path = Path("config/holidays.json")
        holidays = (
            frozenset(date.fromisoformat(d) for d in json.loads(holiday_path.read_text()))
            if holiday_path.exists()
            else frozenset()
        )
        health["calendar"] = "CUSTOM" if holidays else "WEEKDAY_APPROXIMATION"
        if not offline:
            market = provider or EastmoneyProvider(session=session, now=now)
        for instrument in market_universe:
            try:
                if offline:
                    bars = load_prices(session, instrument.id, day)
                    validate_history(bars, day)
                else:
                    bars = market.get_history(instrument.symbol, day - timedelta(days=650), day)
                    validate_history(bars, day)
                    profile = market.get_fund_profile(instrument.symbol)
                    # Provider identity is retained separately from manually confirmed fund rules.
                    sources[instrument.symbol] = profile.model_dump(mode="json")
                    save_prices(session, instrument.id, bars)
                histories[instrument.symbol] = bars
                metric_map[instrument.symbol] = metrics(bars, settings.risk_free_rate)
                if not is_fresh(bars[-1].date, now, instrument.qdii, holidays):
                    market_errors[instrument.symbol] = "STALE"
            except Exception as exc:
                market_errors[instrument.symbol] = type(exc).__name__
                logger.warning(
                    "run_id=%s stage=market symbol=%s error=%s",
                    run.id,
                    instrument.symbol,
                    type(exc).__name__,
                )
        health["market"] = "OK" if not market_errors else market_errors
        if offline:
            health["mode"] = "OFFLINE"
        stage("market", "PARTIAL" if market_errors else "OK")
        view = valued_portfolio(session, histories)
        portfolio_valid = portfolio_confirmed(view, now, settings.portfolio_max_age_days)
        health["portfolio"] = "OK" if portfolio_valid else "UNCONFIRMED_OR_STALE"
        if not portfolio_valid:
            view["warnings"].append(
                "Holdings or cash are unconfirmed or stale; update them in Portfolio"
            )
        if any(s in market_errors for s in held_symbols):
            portfolio_valid = False
        snap = Snapshot(
            account_id="personal",
            created_at=now,
            payload=view,
            invested_value=Decimal(view["invested"]),
            cash_value=Decimal(view["cash"]) if view["cash"] is not None else None,
            total_value=Decimal(view["total"]) if view["total"] is not None else None,
        )
        session.add(snap)
        session.flush()
        run.snapshot_id = snap.id
        weights = {
            p["symbol"]: Decimal(p["weight"]) for p in view["positions"] if p["weight"] is not None
        }
        risk = portfolio_risk(histories, weights)
        health["quant"] = risk["status"]
        health["risk_free"] = "CONFIG_FALLBACK"
        stage("quant", risk["status"])
        macro_rows, macro_errors = ([], ["OFFLINE"]) if offline else fetch_fred(settings, now)
        try:
            macro_rows += load_macro_csv(Path("config/macro_observations.csv"))
            with session.begin_nested():
                save_macro(session, macro_rows, now)
                session.flush()
        except Exception as exc:
            macro_errors.append(type(exc).__name__)
        observations = [m.payload for m in session.scalars(select(MacroObservation))]
        macro = {region: regime(observations, now, region) for region in ("CN", "US")}
        health["macro"] = macro_errors or ("OK" if macro["CN"]["sources"] else "MISSING")
        stage("macro", "PARTIAL" if macro_errors else "OK")
        research_errors = []
        if not offline and settings.research_enabled:
            try:
                researcher = researcher or ResearchClient(settings)
                for query in build_queries(universe, settings.max_research_queries):
                    try:
                        articles = researcher.research(query, [i.symbol for i in universe], now)
                        with session.begin_nested():
                            store_articles(session, articles, now)
                    except Exception as exc:
                        error_name = type(exc).__name__
                        research_errors.append(error_name)
                        if error_name in LLM_REQUEST_ERRORS:
                            break
            except Exception as exc:
                research_errors.append(type(exc).__name__)
            health["research"] = research_errors or "OK"
        else:
            health["research"] = "DISABLED"
        stage("research", str(health["research"]))
        gate, recommendations = RiskGate(settings), []
        positions = {p["symbol"]: p for p in view["positions"]}
        total = Decimal(view["total"]) if view["total"] is not None else None
        cash = Decimal(view["cash"]) if view["cash"] is not None else None
        sector_values = {}
        for p in view["positions"]:
            sector_values[p["category"]] = sector_values.get(p["category"], Decimal(0)) + Decimal(
                p["market_value"]
            )
        prepared = []
        for i in universe:
            p = positions.get(i.symbol)
            current_value = Decimal(p["market_value"]) if p else Decimal(0)
            sector_value = sector_values.get(i.category, Decimal(0))
            candidate_risk = (
                portfolio_risk(histories, weights | {i.symbol: Decimal(0)})
                if i.symbol not in weights and weights
                else risk
            )
            correlations = [
                pair["correlation"]
                for pair in candidate_risk.get("correlations", [])
                if i.symbol in (pair["a"], pair["b"])
            ]
            correlation = max(correlations) if correlations else None
            fit = portfolio_fit(
                current_value / total if total else None,
                sector_value / total if total else None,
                correlation,
            )
            ev = evidence_summary(session, i.symbol, now, settings.news_lookback_hours)
            profile = i.profile or {}
            # Scoring profiles also expire; source alone is not freshness.
            try:
                profile_date = datetime.fromisoformat(profile["as_of"])
                if not (now - timedelta(days=100) <= profile_date <= now):
                    profile = {}
            except (KeyError, ValueError, TypeError):
                profile = {}
            t, st = calculate_signals(
                metric_map.get(i.symbol, {}),
                fit,
                news_score=ev["score"],
                macro_score=equity_macro_score(
                    macro[
                        "US" if i.category.casefold() in {"us broad market", "us equity"} else "CN"
                    ]
                ),
                profile=profile,
                benchmark_return=metric_map.get(i.benchmark_symbol, {}).get("return_60d"),
            )
            data = histories.get(i.symbol, [])
            context = RiskContext(
                total,
                cash,
                current_value,
                sector_value,
                portfolio_valid and i.confirmed,
                data[-1].nav if data else None,
                bool(data and i.symbol not in market_errors),
                0,
                0,
                0,
                i.category,
                correlation=correlation,
                portfolio_volatility=risk.get("volatility"),
                acquired_on=date.fromisoformat(p["acquired_on"])
                if p and p["acquired_on"]
                else None,
                rules=(i.profile or {}).get("rules") or {},
                now=now,
            )
            prepared.append((i, t, st, context, ev, p is not None))
        # Deterministic ranking allocates shared cash to higher strategic scores first.
        prepared.sort(key=lambda x: (-(x[2].score if x[2].score is not None else -1), x[0].symbol))
        decision_inputs = []
        for i, t, st, context, ev, held in prepared:
            decision_inputs.append(
                {
                    "symbol": i.symbol,
                    "name": i.name,
                    "tactical": t.to_dict(),
                    "strategic": st.to_dict(),
                    "context": json.loads(json.dumps(asdict(context), default=str)),
                    "evidence": ev,
                    "held": held,
                }
            )
            rec = recommend(i.symbol, i.name, t, st, context, ev, gate, held=held)
            bars = histories.get(i.symbol, [])
            rec["market_source"] = bars[-1].source if bars else None
            rec["nav_date"] = bars[-1].date.isoformat() if bars else None
            rec["benchmark_symbol"] = i.benchmark_symbol
            recommendations.append(rec)
        stage("risk_gate", "OK")
        evidence = [
            {
                "id": n.id,
                "source_url": n.source_url,
                "published_at": n.published_at.isoformat(),
                "retrieved_at": n.retrieved_at.isoformat(),
                "payload": n.payload,
            }
            for n in session.scalars(
                select(News).where(
                    News.id.in_({e for r in recommendations for e in r["evidence_ids"]})
                )
            )
        ]
        request_failed = any(error in LLM_REQUEST_ERRORS for error in research_errors)
        health["llm"] = "SKIPPED_RESEARCH_ERROR" if request_failed else "DISABLED"
        if researcher and settings.research_enabled and not offline and not request_failed:
            try:
                recommendations = explain(researcher, recommendations, macro, evidence)
                health["llm"] = "OK"
                if settings.llm_review_model and (
                    risk.get("volatility", 0) > settings.max_portfolio_volatility
                    or any("CONFLICTING_SIGNALS" in r["rules_triggered"] for r in recommendations)
                ):
                    recommendations = explain(
                        researcher, recommendations, macro, evidence, review=True
                    )
            except Exception as exc:
                health["llm"] = type(exc).__name__
        stage("llm", health["llm"])
        lookup = {i.symbol: i.id for i in universe}
        for rec in recommendations:
            row = Recommendation(
                daily_run_id=run.id,
                instrument_id=lookup[rec["symbol"]],
                created_at=now,
                action=rec["action"],
                recommendation_type=rec["recommendation_type"],
                proposed_amount=Decimal(rec["proposed_amount"]),
                current_price=Decimal(rec["current_price"])
                if rec["current_price"] is not None
                else None,
                payload=rec,
            )
            session.add(row)
        run.inputs = {
            "portfolio_import": initial,
            "decision_inputs": decision_inputs,
            "portfolio": view,
            "metrics": metric_map,
            "portfolio_risk": risk,
            "macro": macro,
            "macro_observations": observations,
            "evidence": evidence,
            "settings": settings.public(),
            "profiles": {i.symbol: i.profile for i in universe},
            "provider_profiles": sources,
            "histories": {
                s: [bar.model_dump(mode="json") for bar in bars] for s, bars in histories.items()
            },
            "signals": {
                r["symbol"]: {"tactical": r["tactical"], "strategic": r["strategic"]}
                for r in recommendations
            },
            "llm_traces": researcher.traces if researcher else [],
            "holidays": sorted(map(str, holidays)),
        }
        health["notification"] = (
            "DISABLED" if offline or not settings.telegram_enabled else "PENDING"
        )
        run.health = dict(health)
        run.report = daily_report(
            now.astimezone(ZoneInfo(settings.app_timezone)),
            view,
            risk,
            macro,
            recommendations,
            evidence,
            health,
        )
        # Persist before side effects; recommendation rows and their inputs commit atomically.
        session.commit()
        from app.outcomes import update_outcomes

        try:
            with session.begin_nested():
                update_outcomes(session, now)
            health["outcomes"] = "OK"
        except Exception as exc:
            health["outcomes"] = type(exc).__name__
        report_path = settings.report_dir / f"{day}-{run.id}.md"
        try:
            settings.report_dir.mkdir(parents=True, exist_ok=True)
            report_path.write_text(run.report, encoding="utf-8")
            health["report_export"] = "OK"
        except OSError as exc:
            health["report_export"] = type(exc).__name__
        if not offline and settings.telegram_enabled:
            try:
                health["notification"] = notify_telegram(settings, day, recommendations)
            except Exception as exc:
                health["notification"] = type(exc).__name__
        stage("report", "OK")
        run.health = dict(health)
        run.status = (
            "SUCCESS"
            if all(
                health.get(k) == "OK"
                for k in (
                    "market",
                    "portfolio",
                    "quant",
                    "macro",
                    "research",
                    "llm",
                    "outcomes",
                    "report_export",
                )
            )
            and health["notification"] in ("OK", "DISABLED")
            else "PARTIAL"
        )
        run.report = daily_report(
            now.astimezone(ZoneInfo(settings.app_timezone)),
            view,
            risk,
            macro,
            recommendations,
            evidence,
            health,
        )
        if health["report_export"] == "OK":
            try:
                report_path.write_text(run.report, encoding="utf-8")
            except OSError as exc:
                health["report_export"] = type(exc).__name__
                run.health, run.status = dict(health), "PARTIAL"
        usage = {
            "market_requests": getattr(market, "requests", 0),
            "llm_calls": researcher.calls if researcher else 0,
            "web_searches": researcher.searches if researcher else 0,
            "input_tokens": researcher.input_tokens if researcher else 0,
            "output_tokens": researcher.output_tokens if researcher else 0,
            "estimated_llm_cost_usd": None,
            "timings": timings,
            "duration_seconds": round(time.monotonic() - start, 3),
        }
        if all(
            rate is not None
            for rate in (
                settings.llm_input_usd_per_million,
                settings.llm_output_usd_per_million,
                settings.web_search_usd_per_call,
            )
        ):
            usage["estimated_llm_cost_usd"] = str(
                (
                    Decimal(usage["input_tokens"]) * settings.llm_input_usd_per_million
                    + Decimal(usage["output_tokens"]) * settings.llm_output_usd_per_million
                )
                / 1000000
                + Decimal(usage["web_searches"]) * settings.web_search_usd_per_call
            )
        run.telemetry, run.finished_at = usage, utcnow()
        session.commit()
        return run
    except Exception as exc:
        session.rollback()
        if run is not None:
            run = session.get(DailyRun, run.id)
            run.status, run.finished_at = "FAILED", utcnow()
            run.error_message = type(exc).__name__
            session.commit()
        logger.error(
            "run_id=%s stage=daily status=FAILED error=%s",
            run.id if run else "none",
            type(exc).__name__,
        )
        raise
    finally:
        if market is not None and provider is None:
            market.close()
        if own_session:
            session.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--offline", action="store_true", help="Use local data only; make no network requests"
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Create a new research revision and retain the old one",
    )
    args = parser.parse_args()
    configure_logging()
    run = run_daily(offline=args.offline, refresh=args.refresh)
    print(f"{run.id} {run.status}")
    if run.status == "FAILED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

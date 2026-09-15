from collections import defaultdict
from statistics import mean, median
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.db import utcnow
from app.db.models import Instrument, Outcome, Recommendation
from app.providers.eastmoney import load_prices
from app.quant import drawdown

HORIZONS = (1, 5, 20, 60)


def forward_outcome(bars, created_at, benchmark=None, *, now=None):
    now = now or utcnow()
    decision_date = created_at.astimezone(ZoneInfo("Asia/Shanghai")).date()
    today = now.astimezone(ZoneInfo("Asia/Shanghai")).date()
    future = [b for b in bars if decision_date < b.date <= today]
    result = {
        "method": "next_NAV_gross_total_return",
        "entry_date": None,
        "note": (
            "The first published NAV after the recommendation date is the reference point; "
            "horizons count NAV observations and exclude subscription and redemption fees"
        ),
    }
    for n in HORIZONS:
        result.update(
            {
                f"return_{n}d": None,
                f"benchmark_return_{n}d": None,
                f"excess_return_{n}d": None,
                f"max_drawdown_{n}d": None,
                f"end_date_{n}d": None,
            }
        )
    if not future or future[0].total_return is None:
        return result
    result["entry_date"] = future[0].date.isoformat()
    result["entry_source"] = future[0].source
    lookup = {bar.date: bar.total_return for bar in (benchmark or [])}
    for n in HORIZONS:
        if len(future) <= n or any(b.total_return is None for b in future[: n + 1]):
            continue
        change = future[n].total_return / future[0].total_return - 1
        result[f"return_{n}d"] = float(change)
        result[f"end_date_{n}d"] = future[n].date.isoformat()
        result[f"max_drawdown_{n}d"] = drawdown([b.total_return for b in future[: n + 1]])
        start_b, end_b = lookup.get(future[0].date), lookup.get(future[n].date)
        if start_b is not None and end_b is not None:
            baseline = end_b / start_b - 1
            result[f"benchmark_return_{n}d"] = float(baseline)
            result[f"excess_return_{n}d"] = float(change - baseline)
    return result


def update_outcomes(session, now=None):
    now = now or utcnow()
    count = 0
    for rec in session.scalars(select(Recommendation)):
        bars = load_prices(session, rec.instrument_id, now.date())
        # Benchmark assignment is frozen at recommendation time.
        benchmark_symbol = rec.payload.get("benchmark_symbol")
        benchmark = (
            session.scalar(select(Instrument).where(Instrument.symbol == benchmark_symbol))
            if benchmark_symbol
            else None
        )
        baseline = load_prices(session, benchmark.id, now.date()) if benchmark else []
        values = forward_outcome(bars, rec.created_at, baseline, now=now)
        row = session.get(Outcome, rec.id)
        if row is None:
            row = Outcome(recommendation_id=rec.id)
            session.add(row)
        row.updated_at, row.payload = now, values
        count += 1
    session.flush()
    return count


def evaluate(session):
    # Use latest daily revision for each fund, including WATCH replacing an earlier BUY.
    latest = {}
    for r in session.scalars(select(Recommendation).order_by(Recommendation.created_at)):
        key = (r.instrument_id, r.created_at.astimezone(ZoneInfo("Asia/Shanghai")).date())
        latest[key] = r
    result = {
        "recommendation_count": len(latest),
        "method": "Final daily revision per fund; gross NAV return",
        "BUY": {},
        "REDUCE": {},
        "confidence_calibration_20d": [],
    }
    buckets = defaultdict(list)
    for action in ("BUY", "REDUCE"):
        selected = [r for r in latest.values() if r.action == action]
        result[action]["count"] = len(selected)
        for horizon in HORIZONS:
            observations, excess, downs = [], [], []
            for rec in selected:
                outcome = session.get(Outcome, rec.id)
                if outcome is None or outcome.payload.get(f"return_{horizon}d") is None:
                    continue
                ret = outcome.payload[f"return_{horizon}d"]
                observations.append(ret)
                ex = outcome.payload.get(f"excess_return_{horizon}d")
                if ex is not None:
                    excess.append(ex)
                downs.append(outcome.payload[f"max_drawdown_{horizon}d"])
                if horizon == 20:
                    bucket = min(9, int(rec.payload["confidence"] * 10))
                    buckets[(action, bucket)].append(ret > 0 if action == "BUY" else ret < 0)
            hits = [r > 0 if action == "BUY" else r < 0 for r in observations]
            result[action][f"{horizon}d"] = {
                "matured_count": len(observations),
                "hit_rate": mean(hits) if hits else None,
                "average_asset_return": mean(observations) if observations else None,
                "median_asset_return": median(observations) if observations else None,
                "average_excess_asset_return": mean(excess) if excess else None,
                "benchmark_count": len(excess),
                "worst_drawdown": min(downs) if downs else None,
            }
    for (action, bucket), outcomes in sorted(buckets.items()):
        result["confidence_calibration_20d"].append(
            {
                "action": action,
                "confidence_range": f"{bucket * 10}–{(bucket + 1) * 10}%",
                "count": len(outcomes),
                "observed_hit_rate": mean(outcomes),
            }
        )
    return result

"""Explicit score components; missing inputs reduce coverage, never become a neutral 50."""

from dataclasses import asdict, dataclass


def clamp(value):
    return max(0.0, min(100.0, float(value)))


@dataclass
class Signal:
    kind: str
    score: float | None
    coverage: float
    components: dict

    def to_dict(self):
        return asdict(self)


def weighted(kind, components, weights):
    coverage = sum(weight for key, weight in weights.items() if components.get(key) is not None)
    score = (
        (
            sum(
                clamp(components[key]) * weight
                for key, weight in weights.items()
                if components.get(key) is not None
            )
            / coverage
        )
        if coverage
        else None
    )
    return Signal(
        kind, round(score, 2) if score is not None else None, round(coverage, 4), components
    )


def portfolio_fit(weight, sector_weight, correlation=None):
    if weight is None or sector_weight is None:
        return None
    penalty = max(0, (correlation or 0) - 0.7) * 100
    return clamp(100 - float(weight) * 150 - float(sector_weight) * 100 - penalty)


def calculate_signals(
    m, fit, *, news_score=None, macro_score=None, benchmark_return=None, profile=None
):
    p = profile or {}
    # Manually curated profile inputs are accepted only with a traceable source.
    if not p.get("source"):
        p = {}
    r20, r60 = m.get("return_20d"), m.get("return_60d")
    distance = m.get("distance_ma_50")
    vol, dd = m.get("volatility_60d"), m.get("max_drawdown_252d")
    trend = clamp(50 + distance * 500) if distance is not None else None
    momentum = clamp(50 + r20 * 300 + r60 * 100) if r20 is not None and r60 is not None else None
    risk = clamp(100 - vol * 150 + dd * 100) if vol is not None and dd is not None else None
    tactical = weighted(
        "TACTICAL",
        {
            "trend": trend,
            "momentum": momentum,
            "relative_strength": clamp(50 + (r60 - benchmark_return) * 300)
            if r60 is not None and benchmark_return is not None
            else None,
            "risk": risk,
            "macro": macro_score,
            "news": news_score,
            "fit": fit,
            "liquidity": p.get("liquidity_score"),
        },
        {
            "trend": 0.2,
            "momentum": 0.2,
            "relative_strength": 0.1,
            "risk": 0.15,
            "macro": 0.1,
            "news": 0.1,
            "fit": 0.1,
            "liquidity": 0.05,
        },
    )
    long_trend = m.get("distance_ma_200")
    strategic = weighted(
        "STRATEGIC",
        {
            "diversification": p.get("diversification_score"),
            "fit": fit,
            "risk": risk,
            "long_trend": clamp(50 + long_trend * 250) if long_trend is not None else None,
            "cost": clamp(100 - float(p["expense_ratio"]) * 4000)
            if p.get("expense_ratio") is not None
            else None,
            "liquidity": p.get("liquidity_score"),
            "valuation": p.get("valuation_score"),
            "tracking": p.get("tracking_score"),
        },
        {
            "diversification": 0.2,
            "fit": 0.2,
            "risk": 0.15,
            "long_trend": 0.1,
            "cost": 0.1,
            "liquidity": 0.1,
            "valuation": 0.1,
            "tracking": 0.05,
        },
    )
    return tactical, strategic


def confidence(tactical, strategic, *, fresh, evidence_quality, model_confidence):
    coverage = min(tactical.coverage, strategic.coverage)
    consistency = (
        1 - abs(tactical.score - strategic.score) / 100
        if tactical.score is not None and strategic.score is not None
        else 0
    )
    return round(
        min(
            1,
            max(
                0,
                coverage * int(fresh) * 0.35
                + consistency * 0.30
                + evidence_quality * 0.20
                + model_confidence * 0.15,
            ),
        ),
        4,
    )


def rank(items):
    return sorted(
        items, key=lambda item: (-(item[1].score if item[1].score is not None else -1), item[0])
    )

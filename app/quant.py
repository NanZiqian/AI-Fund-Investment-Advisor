"""Pure numerical functions. All outputs are dimensionless statistics, never money."""

import math

import numpy as np
import pandas as pd


def clean_series(values):
    array = np.asarray(values, dtype=float)
    if len(array) == 0 or not np.isfinite(array).all() or (array <= 0).any():
        raise ValueError("Prices must be finite and positive")
    return array


def period_return(values, days):
    a = clean_series(values)
    if days <= 0:
        raise ValueError("Positive horizon required")
    return float(a[-1] / a[-days - 1] - 1) if len(a) > days else None


def moving_average(values, window):
    a = clean_series(values)
    return float(a[-window:].mean()) if len(a) >= window else None


def volatility(values, window):
    a = clean_series(values)
    if len(a) <= window or window < 2:
        return None
    returns = a[-window:] / a[-window - 1 : -1] - 1
    return float(returns.std(ddof=1) * math.sqrt(252))


def drawdown(values):
    a = clean_series(values)
    return float(np.min(a / np.maximum.accumulate(a) - 1))


def ratios(values, annual_risk_free=0.02):
    a = clean_series(values)
    if len(a) < 253:
        return None, None
    a = a[-253:]
    r = a[1:] / a[:-1] - 1
    excess = r - annual_risk_free / 252
    std = r.std(ddof=1)
    downside = np.sqrt(np.mean(np.minimum(excess, 0) ** 2))
    sharpe = float(excess.mean() / std * math.sqrt(252)) if std > 1e-12 else None
    sortino = float(excess.mean() / downside * math.sqrt(252)) if downside > 1e-12 else None
    return sharpe, sortino


def metrics(bars, risk_free=0.02, risk_free_source="config:fallback"):
    valid = [b for b in bars if b.total_return is not None]
    if not valid:
        return {"observations": 0, "data_quality": "MISSING"}
    # Do not splice separated valid islands around missing return observations.
    if len(valid) != len(bars):
        return {"observations": len(valid), "data_quality": "MISSING_ADJUSTMENT"}
    a = clean_series([b.total_return for b in valid])
    result = {
        "observations": len(a),
        "as_of": bars[-1].date.isoformat(),
        "source": bars[-1].source,
        "data_quality": "DEGRADED" if risk_free_source == "config:fallback" else "OK",
        "risk_free_source": risk_free_source,
    }
    for days in (1, 5, 20, 60, 126, 252):
        result[f"return_{days}d"] = period_return(a, days)
    for days in (20, 50, 200):
        ma = moving_average(a, days)
        result[f"ma_{days}"] = ma
        result[f"distance_ma_{days}"] = float(a[-1] / ma - 1) if ma else None
    for days in (20, 60):
        result[f"volatility_{days}d"] = volatility(a, days)
    for days in (60, 252):
        result[f"max_drawdown_{days}d"] = drawdown(a[-days - 1 :]) if len(a) > days else None
    result["sharpe_252d"], result["sortino_252d"] = ratios(a, risk_free)
    return result


def portfolio_risk(histories, weights):
    """Aligned observations; static current weights proxy, NOT realized portfolio P&L."""
    if not weights or any(s not in histories for s in weights):
        return {
            "status": "INSUFFICIENT_DATA",
            "reason": "Missing holding prices or portfolio weights",
        }
    series = {}
    for symbol in weights:
        bars = histories[symbol]
        if any(b.total_return is None for b in bars):
            return {"status": "INSUFFICIENT_DATA", "reason": "Missing total-return data"}
        series[symbol] = pd.Series({b.date: float(b.total_return) for b in bars}, dtype=float)
    aligned = pd.DataFrame(series).sort_index()
    # Calculate returns before intersection to avoid treating multi-day moves as daily returns.
    returns = aligned.pct_change(fill_method=None).dropna().tail(252)
    if len(returns) < 60:
        return {"status": "INSUFFICIENT_DATA", "reason": "Fewer than 60 aligned NAV observations"}
    w = np.array([float(weights[s]) for s in returns.columns])
    covariance = returns.cov().to_numpy() * 252
    variance = float(w @ covariance @ w)
    vol = math.sqrt(max(0, variance))
    pr = returns.to_numpy() @ w
    curve = np.concatenate(([1.0], np.cumprod(1 + pr)))
    contributions = w * (covariance @ w) / variance if variance > 1e-12 else np.zeros(len(w))
    correlations = returns.corr()
    pairs = [
        {"a": a, "b": b, "correlation": float(correlations.loc[a, b])}
        for n, a in enumerate(correlations.columns)
        for b in correlations.columns[n + 1 :]
        if np.isfinite(correlations.loc[a, b])
    ]
    return {
        "status": "OK",
        "method": "Constant-current-weight rebalancing proxy; cash return assumed to be zero",
        "observations": len(returns),
        "volatility": vol,
        "max_drawdown": drawdown(curve),
        "risk_contributions": dict(zip(returns.columns, map(float, contributions))),
        "correlations": pairs,
    }

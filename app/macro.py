import csv
from datetime import date, timedelta
from decimal import Decimal

import httpx

from app.db.models import MacroObservation
from app.providers.http import request

SERIES = {
    "CN_CPI": ("CPALTT01CNM659N", "CN", "inflation", 100, "percent_yoy"),
    "CN_RATE": ("IRSTCI01CNM156N", "CN", "rates", 100, "percent"),
    "US_RATE": ("DGS10", "US", "rates", 7, "percent"),
    "US_VIX": ("VIXCLS", "US", "risk", 7, "index"),
}


def fetch_fred(settings, now, client=None):
    if not settings.fred_api_key.get_secret_value():
        return [], ["FRED_UNCONFIGURED"]
    own = client is None
    client = client or httpx.Client()
    values, errors = [], []
    try:
        for name, (code, region, kind, max_age, unit) in SERIES.items():
            try:
                data = request(
                    client,
                    "GET",
                    "https://api.stlouisfed.org/fred/series/observations",
                    provider="fred",
                    operation="observations",
                    symbol=code,
                    params={
                        "series_id": code,
                        "api_key": settings.fred_api_key.get_secret_value(),
                        "file_type": "json",
                        "sort_order": "desc",
                        "limit": 15,
                        "observation_end": now.date().isoformat(),
                    },
                ).json()
                for row in data["observations"]:
                    if row["value"] == ".":
                        continue
                    values.append(
                        {
                            "series": name,
                            "date": row["date"],
                            "value": row["value"],
                            "region": region,
                            "kind": kind,
                            "max_age_days": max_age,
                            "unit": unit,
                            "source": f"https://fred.stlouisfed.org/series/{code}",
                        }
                    )
            except Exception as exc:
                errors.append(f"{name}:{type(exc).__name__}")
    finally:
        if own:
            client.close()
    return values, errors


def load_macro_csv(path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def save_macro(session, rows, now):
    validated = []
    for data in rows:
        row = dict(data)
        day = date.fromisoformat(row["date"])
        value = Decimal(row["value"])
        if day > now.date() or not value.is_finite() or not row["source"].startswith("https://"):
            raise ValueError("Invalid macro observation")
        row["max_age_days"] = int(row["max_age_days"])
        if row["max_age_days"] <= 0 or row["max_age_days"] > 400:
            raise ValueError("Invalid macro frequency")
        record = session.get(MacroObservation, (row["series"], day))
        if record is None:
            record = MacroObservation(series=row["series"], date=day)
            session.add(record)
        record.value, record.source = value, row["source"]
        record.retrieved_at, record.payload = now, row
        validated.append(row)
    return validated


def regime(rows, now, region="CN"):
    result = {
        "risk_regime": "UNCERTAIN",
        "inflation_regime": "UNCERTAIN",
        "rate_regime": "UNCERTAIN",
        "region": region,
        "sources": [],
    }
    groups = {}
    for row in rows:
        if row["region"] != region or not row.get("source"):
            continue
        groups.setdefault(row["series"], {})[row["date"]] = row
    for observations in groups.values():
        series = sorted(observations.values(), key=lambda r: r["date"])
        last = series[-1]
        if not (
            now.date() - timedelta(days=int(last["max_age_days"]))
            <= date.fromisoformat(last["date"])
            <= now.date()
        ):
            continue
        result["sources"].append(last["source"])
        if last["kind"] == "risk" and last["unit"] == "index":
            value = Decimal(last["value"])
            result["risk_regime"] = (
                "RISK_OFF" if value > 25 else "RISK_ON" if value < 20 else "UNCERTAIN"
            )
        elif len(series) >= 2:
            change = Decimal(last["value"]) - Decimal(series[-2]["value"])
            if last["kind"] == "inflation" and last["unit"] == "percent_yoy":
                result["inflation_regime"] = (
                    "INFLATIONARY"
                    if change > 0
                    else "DISINFLATIONARY"
                    if change < 0
                    else "UNCERTAIN"
                )
            elif last["kind"] == "rates" and last["unit"] == "percent":
                result["rate_regime"] = (
                    "RATE_RISING" if change > 0 else "RATE_FALLING" if change < 0 else "UNCERTAIN"
                )
    return result


def equity_macro_score(state):
    """Transparent equity regime fit; absent regimes add no component."""
    scores = []
    mapping = {"RISK_ON": 75, "RISK_OFF": 20, "RATE_FALLING": 65, "RATE_RISING": 35}
    for key in ("risk_regime", "rate_regime"):
        if state.get(key) in mapping:
            scores.append(mapping[state[key]])
    return sum(scores) / len(scores) if scores else None

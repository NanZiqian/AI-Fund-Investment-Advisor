"""Reproduce deterministic decisions using only the stored inputs of one run."""

import argparse
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select

from app.config import Settings
from app.db import session_factory
from app.db.models import DailyRun, Recommendation
from app.recommendations import recommend
from app.risk import RiskContext, RiskGate
from app.signals import Signal

FIELDS = (
    "action",
    "proposed_amount",
    "score",
    "confidence",
    "risk_gate_status",
    "current_weight",
    "target_weight",
    "data_coverage",
    "rules_triggered",
)


def replay(session, run_id):
    run = session.get(DailyRun, run_id)
    if run is None or "decision_inputs" not in run.inputs:
        raise ValueError("This run has no replayable decision inputs")
    settings = Settings(_env_file=None, **run.inputs["settings"])
    gate = RiskGate(settings)
    stored = {
        r.payload["symbol"]: r.payload
        for r in session.scalars(
            select(Recommendation).where(Recommendation.daily_run_id == run_id)
        )
    }
    mismatches = []
    for item in run.inputs["decision_inputs"]:
        context = dict(item["context"])
        for key in ("total", "cash", "current_value", "sector_value", "price"):
            context[key] = Decimal(context[key]) if context[key] is not None else None
        context["acquired_on"] = (
            date.fromisoformat(context["acquired_on"]) if context["acquired_on"] else None
        )
        context["now"] = datetime.fromisoformat(context["now"])
        actual = recommend(
            item["symbol"],
            item["name"],
            Signal(**item["tactical"]),
            Signal(**item["strategic"]),
            RiskContext(**context),
            item["evidence"],
            gate,
            held=item["held"],
        )
        for key in FIELDS:
            if actual[key] != stored[item["symbol"]][key]:
                mismatches.append({"symbol": item["symbol"], "field": key})
    return {
        "run_id": run_id,
        "verified": not mismatches,
        "mismatches": mismatches,
        "count": len(run.inputs["decision_inputs"]),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_id")
    args = parser.parse_args()
    with session_factory(Settings().database_url)() as session:
        result = replay(session, args.run_id)
    print(result)
    if not result["verified"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

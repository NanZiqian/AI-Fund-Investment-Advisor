from datetime import datetime
from decimal import Decimal

from app.risk import RiskContext, RiskGate
from app.signals import Signal, confidence


def recommend(
    symbol,
    name,
    tactical: Signal,
    strategic: Signal,
    context: RiskContext,
    evidence,
    gate: RiskGate,
    *,
    held,
):
    s = gate.settings
    # OTC fund tactical signals are observation-only; strategic plan owns sizing.
    score = strategic.score
    action = "HOLD" if held else "WATCH"
    proposed = Decimal(0)
    total = context.total
    if total and held and context.current_value / total > s.max_position:
        action = "REDUCE"
        proposed = context.current_value - total * s.max_position
    elif total and score is not None and tactical.score is not None:
        if held and score < 40 and tactical.score < 40:
            action, proposed = "REDUCE", context.current_value * Decimal(".25")
        elif score >= s.min_buy_score:
            action, proposed = "BUY", total * s.max_new_position
    context.coverage = min(tactical.coverage, strategic.coverage)
    context.confidence = confidence(
        tactical,
        strategic,
        fresh=context.fresh,
        evidence_quality=evidence["quality"],
        model_confidence=evidence["model_confidence"],
    )
    context.independent_sources = evidence["independent_sources"]
    context.conflicting = (
        tactical.score is not None
        and strategic.score is not None
        and abs(tactical.score - strategic.score) > 35
    )
    result = gate.validate(action, proposed, context)
    current_weight = context.current_value / total if total else None
    delta = result.amount / total if total else None
    if result.action == "REDUCE" and delta is not None:
        delta = -delta
    target = current_weight + delta if current_weight is not None and delta is not None else None
    return {
        "symbol": symbol,
        "name": name,
        "held": held,
        "action": result.action,
        "recommendation_type": "STRATEGIC",
        "original_action": action,
        "original_amount": str(proposed),
        "proposed_amount": str(result.amount),
        "current_price": str(context.price) if context.price is not None else None,
        "current_weight": str(current_weight) if current_weight is not None else None,
        "target_weight": str(target) if target is not None else None,
        "proposed_weight_change": str(delta) if delta is not None else None,
        "score": score,
        "confidence": context.confidence,
        "data_coverage": context.coverage,
        "tactical": tactical.to_dict(),
        "strategic": strategic.to_dict(),
        "time_horizon_days_min": 180,
        "time_horizon_days_max": 1095,
        "tactical_horizon": "5–20 NAV observations; monitoring only",
        "evidence_ids": evidence["ids"],
        "risk_gate_status": result.status,
        "rules_triggered": result.rules,
        "thesis": (
            "Generated from structured data, quantitative scores, and risk controls; "
            "review manually."
        ),
        "risks": [
            "Published NAV is a valuation reference; the transaction NAV is unknown",
            "Active-fund exposure may differ from its assigned theme",
        ],
        "invalidation_conditions": [
            "Data or fund trading rules become stale",
            "Trend reversal or macro regime change",
            "Cash balance or portfolio structure changes",
        ],
        "generated_at": context.now.isoformat() if isinstance(context.now, datetime) else None,
    }

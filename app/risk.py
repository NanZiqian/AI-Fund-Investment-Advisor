from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import ROUND_DOWN, Decimal
from math import isfinite

from app.config import Settings

D = Decimal


@dataclass
class RiskContext:
    total: Decimal | None
    cash: Decimal | None
    current_value: Decimal
    sector_value: Decimal | None
    portfolio_confirmed: bool
    price: Decimal | None
    fresh: bool
    coverage: float
    confidence: float
    independent_sources: int
    category: str
    correlation: float | None = None
    portfolio_volatility: float | None = None
    conflicting: bool = False
    acquired_on: date | None = None
    rules: dict = field(default_factory=dict)
    now: datetime | None = None


@dataclass
class GateResult:
    action: str
    amount: Decimal
    status: str
    rules: list[str]


class RiskGate:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.spent = D(0)
        self.sector_buys = {}

    def validate(self, action, amount: Decimal, context: RiskContext):
        c, s = context, self.settings
        blocked = []
        if c.price is None or not c.price.is_finite() or c.price <= 0:
            blocked.append("MISSING_PRICE")
        if not c.fresh:
            blocked.append("DATA_STALE")
        if not c.portfolio_confirmed or c.total is None or c.total <= 0:
            blocked.append("PORTFOLIO_UNCONFIRMED")
        if not isfinite(c.coverage) or c.coverage < s.min_coverage:
            blocked.append("INSUFFICIENT_DATA")
        if not isfinite(c.confidence) or c.confidence < s.min_confidence:
            blocked.append("LOW_CONFIDENCE")
        if c.independent_sources < 2:
            blocked.append("INSUFFICIENT_EVIDENCE")
        if c.conflicting:
            blocked.append("CONFLICTING_SIGNALS")
        if action not in ("BUY", "REDUCE"):
            return GateResult(
                "WATCH" if blocked else action, D(0), "BLOCKED" if blocked else "NO_ACTION", blocked
            )
        if not isinstance(amount, Decimal) or not amount.is_finite() or amount <= 0:
            blocked.append("INVALID_AMOUNT")
        rules = c.rules or {}
        try:
            checked = datetime.fromisoformat(rules["as_of"])
            rules_ok = bool(
                rules["source"].startswith("https://")
                and checked.tzinfo
                and c.now - timedelta(days=s.rules_max_age_days) <= checked <= c.now
            )
        except (KeyError, TypeError, ValueError):
            rules_ok = False
        if not rules_ok:
            blocked.append("FUND_RULES_UNCONFIRMED")
        if action == "BUY":
            if c.cash is None:
                blocked.append("CASH_UNKNOWN")
            if c.category == "unknown" or c.sector_value is None:
                blocked.append("SECTOR_UNKNOWN")
            if c.portfolio_volatility is None or not isfinite(c.portfolio_volatility):
                blocked.append("PORTFOLIO_RISK_UNKNOWN")
            elif c.portfolio_volatility > s.max_portfolio_volatility:
                blocked.append("PORTFOLIO_RISK_TOO_HIGH")
            if c.correlation is not None and c.correlation >= s.max_correlation:
                blocked.append("EXCESS_CORRELATION")
            if rules.get("subscription_status") != "OPEN":
                blocked.append("SUBSCRIPTION_NOT_OPEN")
            if "daily_limit" not in rules:  # null explicitly means no stated upper limit
                blocked.append("SUBSCRIPTION_LIMIT_UNKNOWN")
        else:
            if rules.get("redemption_status") != "OPEN":
                blocked.append("REDEMPTION_NOT_OPEN")
            if c.acquired_on is None:
                blocked.append("HOLDING_PERIOD_UNKNOWN")
            elif c.now is None or c.acquired_on > c.now.date():
                blocked.append("HOLDING_PERIOD_INVALID")
            elif rules.get("minimum_holding_days") is None:
                blocked.append("HOLDING_RULE_UNKNOWN")
            elif (c.now.date() - c.acquired_on).days < int(rules["minimum_holding_days"]):
                blocked.append("HOLDING_PERIOD_LOCKED")
            if rules.get("redemption_fee_rate") is None:
                blocked.append("REDEMPTION_FEE_UNKNOWN")
            elif D(str(rules["redemption_fee_rate"])) > D("0.005"):
                blocked.append("HIGH_REDEMPTION_FEE")
        if blocked:
            return GateResult("WATCH", D(0), "BLOCKED", blocked)
        triggered = []
        if action == "BUY":
            caps = {
                "MIN_CASH_BREACH": c.cash - self.spent - c.total * s.min_cash_ratio,
                "MAX_POSITION_BREACH": c.total * s.max_position - c.current_value,
                "MAX_SECTOR_BREACH": c.total * s.max_sector
                - c.sector_value
                - self.sector_buys.get(c.category, D(0)),
                "MAX_DAILY_BUY_BREACH": c.total * s.max_daily_buy - self.spent,
            }
            if c.current_value == 0:
                caps["MAX_NEW_POSITION"] = c.total * s.max_new_position
            if rules["daily_limit"] is not None:
                caps["FUND_DAILY_LIMIT"] = D(str(rules["daily_limit"]))
            approved = amount
            for rule, cap in caps.items():
                if cap < amount:
                    triggered.append(rule)
                approved = min(approved, cap)
            minimum = max(s.min_trade_amount, D(str(rules.get("minimum_subscription", "0"))))
        else:
            approved = min(amount, c.current_value)
            minimum = s.min_trade_amount
        approved = max(D(0), approved).quantize(D("0.01"), rounding=ROUND_DOWN)
        if approved < minimum:
            return GateResult("WATCH", D(0), "BLOCKED", triggered + ["BELOW_MINIMUM_AMOUNT"])
        if action == "BUY":
            self.spent += approved
            self.sector_buys[c.category] = self.sector_buys.get(c.category, D(0)) + approved
        return GateResult(
            action, approved, "RESIZED" if approved < amount else "APPROVED", triggered
        )

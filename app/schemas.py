from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, HttpUrl, model_validator

Nonnegative = Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class PositionInput(StrictModel):
    symbol: str = Field(pattern=r"^(\d{6}|UNRESOLVED-[A-Za-z0-9]+)$")
    name: str = Field(min_length=1, max_length=200)
    market_value: Nonnegative
    quantity: Nonnegative | None = None
    holding_profit: Decimal | None = None
    average_cost: Nonnegative | None = None
    as_of: AwareDatetime | None = None
    acquired_on: date | None = None
    category: str = "unknown"
    share_class: str = "unknown"
    qdii: bool = False
    confirmed: bool = False
    source: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_confirmed(self):
        if self.confirmed and (self.as_of is None or self.symbol.startswith("UNRESOLVED")):
            raise ValueError("确认持仓必须有基金代码和带时区的日期")
        if self.acquired_on and self.as_of and self.acquired_on > self.as_of.date():
            raise ValueError("购买日期不能晚于持仓日期")
        return self


class PortfolioImport(StrictModel):
    positions: list[PositionInput] = Field(max_length=200)
    cash: Nonnegative | None = None
    as_of: AwareDatetime | None = None
    source: str = Field(min_length=1)
    mode: Literal["replace", "merge"] = "replace"

    @model_validator(mode="after")
    def consistent(self):
        symbols = [p.symbol for p in self.positions]
        if len(symbols) != len(set(symbols)):
            raise ValueError("重复基金代码；请先合并同一份额的记录")
        if self.cash is not None and self.as_of is None:
            raise ValueError("现金余额必须注明日期")
        return self


class FundRules(StrictModel):
    source: HttpUrl
    as_of: AwareDatetime
    subscription_status: Literal["OPEN", "CLOSED", "UNKNOWN"]
    daily_limit: Nonnegative | None
    minimum_subscription: Nonnegative = Decimal("0")
    redemption_status: Literal["OPEN", "CLOSED", "UNKNOWN"]
    minimum_holding_days: int | None = Field(default=None, ge=0, le=10000)
    redemption_fee_rate: Decimal | None = Field(default=None, ge=0, le=1)
    settlement_note: str = "到账时间以平台确认为准"


class ProfileUpdate(StrictModel):
    source: HttpUrl
    as_of: AwareDatetime
    expense_ratio: Decimal | None = Field(default=None, ge=0, le=1)
    diversification_score: float | None = Field(default=None, ge=0, le=100)
    liquidity_score: float | None = Field(default=None, ge=0, le=100)
    valuation_score: float | None = Field(default=None, ge=0, le=100)
    tracking_score: float | None = Field(default=None, ge=0, le=100)
    scoring_notes: str = ""
    rules: FundRules | None = None

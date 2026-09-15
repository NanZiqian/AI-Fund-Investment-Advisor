from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///data/advisor.db"
    app_timezone: str = "Asia/Shanghai"
    api_token: SecretStr = SecretStr("")
    openai_api_key: SecretStr = SecretStr("")
    openai_base_url: str = ""
    llm_fast_model: str = ""
    llm_reasoning_model: str = ""
    llm_review_model: str = ""
    research_enabled: bool = False
    telegram_enabled: bool = False
    telegram_bot_token: SecretStr = SecretStr("")
    telegram_chat_id: str = ""
    fred_api_key: SecretStr = SecretStr("")
    min_cash_ratio: Decimal = Field(Decimal("0.10"), ge=0, le=1)
    max_position: Decimal = Field(Decimal("0.20"), gt=0, le=1)
    max_sector: Decimal = Field(Decimal("0.35"), gt=0, le=1)
    max_new_position: Decimal = Field(Decimal("0.05"), gt=0, le=1)
    max_daily_buy: Decimal = Field(Decimal("0.10"), gt=0, le=1)
    min_trade_amount: Decimal = Field(Decimal("100"), gt=0)
    min_buy_score: float = Field(70, ge=0, le=100)
    min_confidence: float = Field(0.65, ge=0, le=1)
    min_coverage: float = Field(0.80, ge=0, le=1)
    max_portfolio_volatility: float = Field(0.35, gt=0)
    max_correlation: float = Field(0.95, ge=0, le=1)
    risk_free_rate: float = 0.02
    news_lookback_hours: int = Field(72, ge=24, le=72)
    max_research_queries: int = Field(5, ge=1, le=15)
    max_llm_calls: int = Field(12, ge=1, le=30)
    llm_input_usd_per_million: Decimal | None = None
    llm_output_usd_per_million: Decimal | None = None
    web_search_usd_per_call: Decimal | None = None
    rules_max_age_days: int = 7
    portfolio_max_age_days: int = 7
    report_dir: Path = Path("reports")

    @field_validator("app_timezone")
    @classmethod
    def valid_timezone(cls, value):
        ZoneInfo(value)
        return value

    def public(self):
        return self.model_dump(
            mode="json",
            exclude={
                "database_url",
                "api_token",
                "openai_api_key",
                "openai_base_url",
                "telegram_bot_token",
                "telegram_chat_id",
                "fred_api_key",
            },
        )

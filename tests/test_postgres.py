import os
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.db import make_engine, utcnow
from app.db.models import Account


@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="PostgreSQL service required (CI)")
def test_postgres_numeric_and_timezone():
    engine = make_engine(os.environ["TEST_DATABASE_URL"])
    with Session(engine) as session:
        account = Account(
            id="pg-test", cash=Decimal("12345678.12345678"), as_of=utcnow(), source="fixture"
        )
        session.add(account)
        session.flush()
        session.expire_all()
        result = session.get(Account, "pg-test")
        assert result.cash == Decimal("12345678.12345678")
        assert result.as_of.tzinfo is not None
        session.rollback()
    engine.dispose()

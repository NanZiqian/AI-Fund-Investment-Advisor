import pytest
from sqlalchemy.orm import Session

from app.db import (
    Base,
    make_engine,
    models,  # noqa: F401
)


@pytest.fixture
def session(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        yield db
    engine.dispose()

from pathlib import Path

from streamlit.testing.v1 import AppTest

from app.config import Settings
from app.db import Base, make_engine


def test_dashboard_empty_state(monkeypatch, tmp_path):
    url = f"sqlite:///{tmp_path}/ui.db"
    monkeypatch.setenv("DATABASE_URL", url)
    Base.metadata.create_all(make_engine(url))
    assert Settings().database_url == url
    app = AppTest.from_file(Path("dashboard/Home.py").resolve()).run(timeout=30)
    assert not app.exception
    assert app.title[0].value == "组合总览"
    app.sidebar.radio[0].set_value("持仓管理").run()
    assert not app.exception

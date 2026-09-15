from pathlib import Path

from streamlit.testing.v1 import AppTest

from app.config import Settings
from app.db import Base, make_engine


def test_dashboard_empty_state(monkeypatch, tmp_path):
    url = f"sqlite:///{tmp_path}/ui.db"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("LLM_FAST_MODEL", "")
    monkeypatch.setenv("LLM_REASONING_MODEL", "")
    monkeypatch.setenv("RESEARCH_ENABLED", "false")
    Base.metadata.create_all(make_engine(url))
    assert Settings().database_url == url
    app = AppTest.from_file(Path("dashboard/Home.py").resolve()).run(timeout=30)
    assert not app.exception
    assert app.title[0].value == "Overview"
    assert any(item.label == "API key" for item in app.text_input)
    assert any(item.label == "Save LLM Configuration" for item in app.button)

    offline = next(item for item in app.checkbox if item.label == "Use local data only (offline)")
    research = next(
        item for item in app.checkbox if item.label == "Enable LLM news research and explanations"
    )
    offline.set_value(False)
    research.set_value(True)
    app.run()
    generate = next(item for item in app.button if item.label == "Generate New Research Briefing")
    generate.click().run()
    assert any("settings are missing" in item.value for item in app.error)

    app.sidebar.radio[0].set_value("Portfolio").run()
    assert not app.exception

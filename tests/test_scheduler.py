from pathlib import Path

import pytest
import yaml

from app.config import Settings
from scripts.check_scheduled_config import check


def test_scheduler_persistence_and_manual_trigger():
    with pytest.raises(ValueError):
        check(Settings(database_url="sqlite:///data/advisor.db"))
    check(Settings(database_url="postgresql+psycopg://configured"))
    workflow = yaml.load(Path(".github/workflows/daily.yml").read_text(), Loader=yaml.BaseLoader)
    assert "schedule" in workflow["on"] and "workflow_dispatch" in workflow["on"]
    assert workflow["concurrency"]["cancel-in-progress"] == "false"

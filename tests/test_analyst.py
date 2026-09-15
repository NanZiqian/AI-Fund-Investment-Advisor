from types import SimpleNamespace

import pytest

from app.analyst import AnalysisBatch, Explanation, explain
from app.config import Settings
from app.research import ResearchClient


class FakeLLMClient:
    """No HTTP and no token consumption."""

    def __init__(self, output):
        self.output = output
        self.responses = self

    def parse(self, **kwargs):
        class Response:
            usage = SimpleNamespace(input_tokens=10, output_tokens=20)
            output_parsed = self.output

            def model_dump(self):
                return {"output": []}

        return Response()


def test_analyst_cannot_change_allocation():
    item = Explanation(
        symbol="012885",
        thesis="Limited evidence",
        risks=["Risk"],
        invalidation_conditions=["Stale data"],
        evidence_ids=["e1"],
    )
    client = ResearchClient(
        Settings(llm_reasoning_model="fake"), FakeLLMClient(AnalysisBatch(explanations=[item]))
    )
    original = [
        {
            "symbol": "012885",
            "action": "WATCH",
            "proposed_amount": "0.00",
            "score": 70,
            "evidence_ids": ["e1"],
        }
    ]
    output = explain(client, original, {}, [])
    assert output[0]["proposed_amount"] == "0.00" and output[0]["action"] == "WATCH"
    assert "thesis" not in original[0]
    assert client.input_tokens == 10
    with pytest.raises(ValueError):
        Explanation(**(item.model_dump() | {"proposed_amount": 1000}))


def test_unknown_evidence_rejected():
    item = Explanation(
        symbol="012885",
        thesis="bad",
        risks=[],
        invalidation_conditions=[],
        evidence_ids=["invented"],
    )
    client = ResearchClient(
        Settings(llm_reasoning_model="fake"), FakeLLMClient(AnalysisBatch(explanations=[item]))
    )
    with pytest.raises(ValueError):
        explain(client, [{"symbol": "012885", "evidence_ids": []}], {}, [])

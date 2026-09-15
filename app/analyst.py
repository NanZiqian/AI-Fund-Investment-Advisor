import json

from app.schemas import StrictModel


class Explanation(StrictModel):
    symbol: str
    thesis: str
    risks: list[str]
    invalidation_conditions: list[str]
    evidence_ids: list[str]


class AnalysisBatch(StrictModel):
    explanations: list[Explanation]


def explain(research_client, recommendations, macro, evidence, *, review=False):
    allowed = {r["symbol"]: r for r in recommendations}
    prompt = json.dumps(
        {
            "task": "解释已通过确定性风控的研究结果。不可修改动作、数字、金额、评分或置信度。"
            "不得添加输入外事实，不写新数字，只写解释文字。引用只能使用给定 evidence_ids。"
            "缺少证据时明确说明不足，不补造理由。",
            "recommendations": recommendations,
            "macro": macro,
            "evidence": evidence,
        },
        ensure_ascii=False,
    )
    model = (
        research_client.settings.llm_review_model
        if review
        else research_client.settings.llm_reasoning_model
    )
    batch, _ = research_client.parse(model, AnalysisBatch, prompt)
    seen = set()
    for item in batch.explanations:
        if item.symbol not in allowed or item.symbol in seen:
            raise ValueError("Analyst returned unknown or duplicate symbol")
        seen.add(item.symbol)
        if not set(item.evidence_ids).issubset(allowed[item.symbol]["evidence_ids"]):
            raise ValueError("Analyst returned unrecognized evidence")
    result = [dict(r) for r in recommendations]
    mapped = {r["symbol"]: r for r in result}
    for item in batch.explanations:
        # Explicit assignment: LLM cannot touch deterministic fields, even via merge.
        target = mapped[item.symbol]
        target["thesis"] = item.thesis
        target["risks"] = item.risks
        target["invalidation_conditions"] = item.invalidation_conditions
        target["explanation_source"] = "LLM interpretation of supplied inputs"
    return result

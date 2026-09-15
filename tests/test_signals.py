from app.signals import calculate_signals, confidence, portfolio_fit, rank, weighted


def test_missing_components_reduce_coverage():
    signal = weighted("STRATEGIC", {"a": 100, "b": None}, {"a": 0.3, "b": 0.7})
    assert signal.coverage == 0.3 and signal.score == 100
    assert weighted("TACTICAL", {}, {"x": 1}).score is None


def test_ranking_ties_and_portfolio_fit():
    signal = weighted("TACTICAL", {"x": 80}, {"x": 1})
    assert [r[0] for r in rank([("002", signal), ("001", signal)])] == ["001", "002"]
    assert portfolio_fit(0.2, 0.35, 0.99) < portfolio_fit(0.05, 0.1, 0.2)
    assert portfolio_fit(None, None) is None


def test_missing_profile_not_fabricated_and_confidence_is_deterministic():
    t, s = calculate_signals({}, None, profile={"liquidity_score": 100})
    assert t.coverage == 0 and s.coverage == 0
    assert confidence(t, s, fresh=False, evidence_quality=0, model_confidence=0) == 0

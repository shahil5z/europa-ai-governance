import pytest
from pydantic import ValidationError

from europa.schemas import (
    DISCLAIMER,
    AgentFinding,
    AssessmentRequest,
    ConfidenceAdjustment,
    CriticAssessment,
    ExecutiveSummary,
    GovernanceAssessment,
    Level,
    OrchestratorOutput,
    RiskAssessment,
    RouteDecision,
    Severity,
    SpecialistName,
    clean_text,
)
from tests.fakes import finding, make_governance, make_orchestrator, make_risk

VALID = "A hiring tool that ranks candidates from their CVs for recruiters to review."


def test_request_valid_and_trimmed():
    r = AssessmentRequest(description="  " + VALID + "  ", scenario_id="credit-scoring")
    assert r.description == VALID
    assert r.scenario_id == "credit-scoring"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"description": ""},
        {"description": "too short"},
        {"description": "x" * 6001},
        {"description": 123},
        {"description": VALID, "extra": 1},
        {"description": VALID, "scenario_id": "Bad Id!"},
    ],
)
def test_request_invalid(payload):
    with pytest.raises(ValidationError):
        AssessmentRequest.model_validate(payload)


def test_request_strips_control_characters_before_length_check():
    noisy = "\x00\x07\u202e" + VALID + "\x1b[31m\u200b"
    r = AssessmentRequest(description=noisy)
    assert "\x00" not in r.description and "\u202e" not in r.description
    assert "\x1b" not in r.description and "\u200b" not in r.description
    # control characters cannot be used to pad past the minimum length
    with pytest.raises(ValidationError):
        AssessmentRequest(description="\x00" * 40 + "short text")


def test_clean_text_keeps_newlines_and_tabs():
    assert clean_text("a\r\nb\tc\n\n\n\n\n\nd") == "a\nb\tc\n\n\nd"


def test_finding_bounds():
    ok = finding("Valid title")
    assert ok.severity is Severity.MEDIUM
    with pytest.raises(ValidationError):
        AgentFinding(**{**ok.model_dump(), "confidence": 1.2})
    with pytest.raises(ValidationError):
        AgentFinding(**{**ok.model_dump(), "severity": "SEVERE"})
    with pytest.raises(ValidationError):
        AgentFinding(**{k: v for k, v in ok.model_dump().items() if k != "recommendation"})


def test_bad_enum_and_missing_fields_in_specialist():
    data = make_risk().model_dump()
    with pytest.raises(ValidationError):
        RiskAssessment.model_validate({**data, "level": "EXTREME"})
    with pytest.raises(ValidationError):
        RiskAssessment.model_validate({k: v for k, v in data.items() if k != "impact"})
    with pytest.raises(ValidationError):
        RiskAssessment.model_validate({**data, "findings": []})
    with pytest.raises(ValidationError):
        RiskAssessment.model_validate({**data, "unknown_field": True})


def test_malformed_nested_finding_rejected():
    data = make_risk().model_dump()
    data["findings"][0]["severity"] = "nope"
    with pytest.raises(ValidationError):
        RiskAssessment.model_validate(data)
    data = make_risk().model_dump()
    data["findings"] = [{"title": "x"}]
    with pytest.raises(ValidationError):
        RiskAssessment.model_validate(data)


def test_governance_always_requires_legal_review():
    data = make_governance().model_dump()
    data["requires_legal_review"] = False
    assert GovernanceAssessment.model_validate(data).requires_legal_review is True


@pytest.mark.parametrize(
    "phrase",
    [
        "The system is non-compliant with the AI Act.",
        "This use violates the GDPR.",
        "The tool is classified as high-risk.",
        "This design guarantees compliance.",
        "The deployment is illegal.",
    ],
)
def test_assertive_legal_wording_is_rejected(phrase):
    data = make_governance().model_dump()
    data["summary"] = phrase + " It was reviewed against the description."
    with pytest.raises(ValidationError, match="assertive legal phrase"):
        GovernanceAssessment.model_validate(data)
    with pytest.raises(ValidationError):
        ExecutiveSummary(text=phrase + " Further text that makes it long enough.", key_points=["x"])


def test_hedged_wording_is_accepted():
    data = make_governance().model_dump()
    data["summary"] = (
        "Based on the provided description this appears relevant to high-risk concepts and "
        "may be potentially applicable; legal review is required."
    )
    assert GovernanceAssessment.model_validate(data)


def test_orchestrator_needs_exactly_one_route_per_specialist():
    out = make_orchestrator().model_dump()
    out["routing"] = [*out["routing"][:4], out["routing"][0]]
    with pytest.raises(ValidationError):
        OrchestratorOutput.model_validate(out)
    out = make_orchestrator().model_dump()
    out["routing"][0]["agent"] = "ORCHESTRATOR"
    with pytest.raises(ValidationError):
        OrchestratorOutput.model_validate(out)


def test_critic_cannot_target_orchestrator_or_boost_confidence():
    with pytest.raises(ValidationError):
        ConfidenceAdjustment(agent=SpecialistName.RISK, delta=0.2, reason="boost")
    with pytest.raises(ValidationError):
        ConfidenceAdjustment(agent="CRITIC", delta=-0.1, reason="self")
    with pytest.raises(ValidationError):
        CriticAssessment.model_validate({"summary": "short"})


def test_route_decision_requires_justification():
    with pytest.raises(ValidationError):
        RouteDecision(agent=SpecialistName.RISK, run=False, focus="a focus", justification="x")


def test_level_ordering_and_disclaimer_text():
    assert Level.LOW.rank < Level.CRITICAL.rank
    assert Level.from_rank(9) is Level.CRITICAL and Level.from_rank(-3) is Level.LOW
    assert "does not constitute legal advice" in DISCLAIMER
    assert "\u2014" not in DISCLAIMER

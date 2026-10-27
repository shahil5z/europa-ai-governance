"""Pure-code components: guardrails, disagreement detection, consensus, rate limit."""

from __future__ import annotations

import pytest

from europa.consensus import apply_critic_adjustments, build_recommendations, compute_consensus
from europa.disagreement import (
    detect,
    detect_level_disagreements,
    finalize_open,
    merge,
    plan_reassessments,
)
from europa.guardrails import apply_guardrails, detect_signals, fallback_plan
from europa.ratelimit import SlidingWindowLimiter
from europa.schemas import (
    AgentName,
    AgentResult,
    AgentRunStatus,
    AgentStatus,
    ConfidenceAdjustment,
    CriticIssue,
    DisagreementKind,
    DisagreementStatus,
    IssueKind,
    Level,
    Severity,
    SpecialistName,
)
from tests.fakes import (
    make_critic,
    make_data,
    make_governance,
    make_orchestrator,
    make_oversight,
    make_risk,
    make_security,
)


def res(agent: AgentName, assessment) -> AgentResult:
    return AgentResult(
        agent=agent,
        assessment=assessment,
        revision=0,
        level_history=[assessment.level],
        adjusted_confidence=assessment.confidence,
    )


def results(
    risk=Level.MEDIUM,
    sec=Level.MEDIUM,
    data=Level.MEDIUM,
    ov=Level.MEDIUM,
    gov=Level.MEDIUM,
    conf=0.8,
):
    return {
        AgentName.RISK: res(AgentName.RISK, make_risk(risk, conf)),
        AgentName.SECURITY: res(AgentName.SECURITY, make_security(sec, conf)),
        AgentName.DATA_GOVERNANCE: res(AgentName.DATA_GOVERNANCE, make_data(data, conf)),
        AgentName.HUMAN_OVERSIGHT: res(AgentName.HUMAN_OVERSIGHT, make_oversight(ov, conf)),
        AgentName.GOVERNANCE: res(AgentName.GOVERNANCE, make_governance(gov, conf)),
    }


# guardrails
def test_signals_detect_high_impact_domains_and_respect_negation():
    keys = {s.key for s in detect_signals("We screen job applicants with facial recognition")}
    assert {"employment", "biometric"} <= keys
    assert "personal_data" not in {s.key for s in detect_signals("No personal data is processed.")}
    assert "personal_data" in {s.key for s in detect_signals("It stores personal data of users.")}


def test_guardrails_raise_impact_and_force_required_agents():
    out = make_orchestrator(
        skip=(SpecialistName.HUMAN_OVERSIGHT, SpecialistName.GOVERNANCE),
        impact=Level.LOW,
    )
    profile, plan = apply_guardrails(out, "Automated credit scoring for loan applicants.")
    assert profile.decision_impact is Level.HIGH
    assert set(plan.selected()) >= {AgentName.HUMAN_OVERSIGHT, AgentName.GOVERNANCE}
    assert {o.agent for o in plan.overrides} == {
        SpecialistName.HUMAN_OVERSIGHT,
        SpecialistName.GOVERNANCE,
    }
    assert plan.source == "LLM_WITH_GUARDRAILS"


def test_guardrails_never_skip_risk_and_security():
    out = make_orchestrator(skip=(SpecialistName.RISK, SpecialistName.SECURITY), impact=Level.LOW)
    _, plan = apply_guardrails(out, "Sensor model for predictive maintenance of machines.")
    assert AgentName.RISK in plan.selected() and AgentName.SECURITY in plan.selected()


def test_fallback_plan_runs_everything():
    profile, plan = fallback_plan("anything about recruitment of candidates")
    assert len(plan.selected()) == 5 and plan.source == "DETERMINISTIC_FALLBACK"
    assert profile.decision_impact is Level.HIGH


# disagreements
def test_no_disagreement_when_levels_are_close():
    assert detect_level_disagreements(results(risk=Level.LOW, sec=Level.MEDIUM), 0) == []


def test_level_spread_of_two_is_detected_with_extremes_only():
    found = detect_level_disagreements(results(risk=Level.LOW, sec=Level.MEDIUM, gov=Level.HIGH), 0)
    assert [d.kind for d in found] == [DisagreementKind.LEVEL_SPREAD]
    assert set(found[0].agents) == {AgentName.RISK, AgentName.GOVERNANCE}


def test_security_outlier_critical_while_others_low():
    r = results(risk=Level.LOW, sec=Level.CRITICAL, data=Level.LOW, ov=Level.LOW, gov=Level.LOW)
    found = detect_level_disagreements(r, 0)
    assert [d.kind for d in found] == [DisagreementKind.SECURITY_OUTLIER]  # not double counted


def test_security_blind_spot_when_security_low_and_others_high():
    r = results(risk=Level.HIGH, sec=Level.LOW, data=Level.HIGH, ov=Level.CRITICAL, gov=Level.HIGH)
    assert detect_level_disagreements(r, 0)[0].kind is DisagreementKind.SECURITY_OUTLIER


def test_critic_issues_become_disagreements_only_when_material():
    r = results()
    critic = make_critic(
        issues=(
            CriticIssue(
                kind=IssueKind.CONTRADICTION,
                description="Risk and oversight conflict.",
                agents=[SpecialistName.RISK, SpecialistName.HUMAN_OVERSIGHT],
                severity=Severity.HIGH,
            ),
            CriticIssue(
                kind=IssueKind.CONTRADICTION,
                description="Minor wording conflict only.",
                agents=[SpecialistName.RISK, SpecialistName.SECURITY],
                severity=Severity.LOW,
            ),
            CriticIssue(
                kind=IssueKind.DUPLICATE,
                description="Duplicate findings found.",
                agents=[SpecialistName.RISK],
                severity=Severity.HIGH,
            ),
            CriticIssue(
                kind=IssueKind.INCONSISTENT_LEVEL,
                description="Level does not fit.",
                agents=[SpecialistName.GOVERNANCE],
                severity=Severity.MEDIUM,
            ),
        )
    )
    found = detect(r, critic, 1)
    assert {d.kind for d in found} == {
        DisagreementKind.CRITIC_CONTRADICTION,
        DisagreementKind.CRITIC_INCONSISTENT_LEVEL,
    }
    assert all(d.round_detected == 1 for d in found)


def test_merge_lifecycle_resolved_open_and_unresolved():
    r1 = results(risk=Level.LOW, sec=Level.HIGH)
    first = detect(r1, None, 0)
    merged0 = merge([], first, 0, reassessed=False)
    assert merged0[0].status is DisagreementStatus.OPEN
    # after reassessment the gap closed -> resolved but preserved
    r2 = results(risk=Level.MEDIUM, sec=Level.HIGH)
    merged1 = merge(merged0, detect(r2, None, 1), 1, reassessed=True)
    assert len(merged1) == 1 and merged1[0].status is DisagreementStatus.RESOLVED
    assert merged1[0].resolution_note
    # still present and no budget: becomes unresolved, never dropped
    still = merge(merged0, detect(r1, None, 1), 1, reassessed=True)
    assert still[0].status is DisagreementStatus.OPEN
    assert finalize_open(still)[0].status is DisagreementStatus.UNRESOLVED


def test_critic_disagreement_not_resolved_when_critic_missing():
    critic = make_critic(
        issues=(
            CriticIssue(
                kind=IssueKind.CONTRADICTION,
                description="Conflict between views.",
                agents=[SpecialistName.RISK, SpecialistName.SECURITY],
                severity=Severity.HIGH,
            ),
        )
    )
    r = results()
    merged0 = merge([], detect(r, critic, 0), 0, False)
    merged1 = merge(merged0, detect(r, None, 1), 1, True, critic_available=False)
    assert merged1[0].status is DisagreementStatus.OPEN


def test_reassessment_plan_is_capped_and_targets_extremes():
    r = results(risk=Level.LOW, sec=Level.CRITICAL, data=Level.LOW, ov=Level.LOW, gov=Level.LOW)
    open_ = detect(r, None, 0)
    plan = plan_reassessments(open_, r, None)
    assert 1 <= len(plan) <= 3
    assert AgentName.SECURITY not in plan  # the outlier is the evidence, others re-examine
    assert all("SECURITY rated CRITICAL" in fb for fb in plan.values())


def test_critic_requests_come_first_in_plan():
    from europa.schemas import ReassessmentRequest

    r = results(risk=Level.LOW, sec=Level.HIGH)
    critic = make_critic(
        requests=(
            ReassessmentRequest(
                agent=SpecialistName.GOVERNANCE, feedback="Substantiate the tier claim."
            ),
        )
    )
    plan = plan_reassessments(detect(r, critic, 0), r, critic)
    assert next(iter(plan)) is AgentName.GOVERNANCE


# consensus
def statuses(**failed):
    return {
        AgentName(k): AgentRunStatus(agent=AgentName(k), status=AgentStatus.FAILED) for k in failed
    }


def test_consensus_is_deterministic_and_explainable():
    r = results(risk=Level.HIGH, sec=Level.MEDIUM, data=Level.MEDIUM, ov=Level.HIGH, gov=Level.HIGH)
    a = compute_consensus(r, [], {}, None)
    b = compute_consensus(r, [], {}, None)
    assert a == b
    assert a.overall_level is Level.HIGH
    assert len(a.entries) == 5 and a.rules_applied
    assert sum(e.base_weight for e in a.entries) == pytest.approx(1.0)


def test_consensus_precautionary_floor_for_confident_critical():
    r = results(
        risk=Level.LOW, sec=Level.CRITICAL, data=Level.LOW, ov=Level.LOW, gov=Level.LOW, conf=0.9
    )
    c = compute_consensus(r, [], {}, None)
    assert c.overall_level is Level.HIGH
    assert any("Precautionary floor" in x for x in c.rules_applied)


def test_low_confidence_critical_does_not_trigger_floor():
    r = results(risk=Level.LOW, sec=Level.CRITICAL, data=Level.LOW, ov=Level.LOW, gov=Level.LOW)
    r[AgentName.SECURITY] = res(AgentName.SECURITY, make_security(Level.CRITICAL, 0.4))
    c = compute_consensus(r, [], {}, None)
    assert c.overall_level is not Level.HIGH
    assert not any("Precautionary" in x for x in c.rules_applied)


def test_profile_floor_applies():
    r = results(risk=Level.LOW, sec=Level.LOW, data=Level.LOW, ov=Level.LOW, gov=Level.LOW)
    from tests.fakes import make_profile

    c = compute_consensus(r, [], {}, make_profile(Level.CRITICAL))
    assert c.overall_level is Level.HIGH


def test_critic_adjustment_reduces_weight_and_confidence_penalties_apply():
    r = results(conf=0.8)
    critic = make_critic(
        adjustments=(
            ConfidenceAdjustment(agent=SpecialistName.RISK, delta=-0.3, reason="overconfident"),
        )
    )
    adj = apply_critic_adjustments(r, critic)
    assert adj[AgentName.RISK].adjusted_confidence == pytest.approx(0.5)
    clean = compute_consensus(r, [], {}, None)
    penalised = compute_consensus(
        adj,
        [],
        statuses(DATA_GOVERNANCE=1),
        None,
    )
    assert penalised.overall_confidence < clean.overall_confidence


def test_consensus_none_without_results():
    assert compute_consensus({}, [], {}, None) is None


def test_recommendations_sorted_and_deduped():
    r = results(risk=Level.CRITICAL, sec=Level.LOW)
    recs, priority = build_recommendations(r)
    assert recs[0].severity is Severity.CRITICAL
    assert [x.priority_rank for x in recs] == list(range(1, len(recs) + 1))
    assert priority and all(p in recs for p in priority)


# rate limiter
def test_rate_limiter_per_key_and_global():
    lim = SlidingWindowLimiter(per_key=2, global_limit=3, window_s=60)
    assert lim.check("a", now=0) is None
    assert lim.check("a", now=1) is None
    assert lim.check("a", now=2) == 58
    assert lim.check("b", now=3) is None
    assert lim.check("c", now=4) is not None  # global cap hit
    assert lim.check("a", now=61) is None  # window slid

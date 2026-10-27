"""Deterministic, explainable consensus over structured agent results.

No model call is involved. Inputs: validated specialist results, critic confidence
adjustments, disagreements, failures and the orchestrator's profile. Every rule that
changes the outcome is appended to `rules_applied` so the table in the report can
explain the result.
"""

from __future__ import annotations

import re

from .schemas import (
    SPECIALISTS,
    AgentConsensusEntry,
    AgentName,
    AgentResult,
    AgentRunStatus,
    AgentStatus,
    ConsensusAssessment,
    CriticAssessment,
    Disagreement,
    DisagreementStatus,
    Level,
    Recommendation,
    Severity,
    SystemProfile,
    specialist_to_agent,
)

BASE_WEIGHTS: dict[AgentName, float] = {
    AgentName.RISK: 0.28,
    AgentName.SECURITY: 0.22,
    AgentName.GOVERNANCE: 0.18,
    AgentName.DATA_GOVERNANCE: 0.16,
    AgentName.HUMAN_OVERSIGHT: 0.16,
}

METHOD = (
    "Weighted mean of agent levels (LOW=1 to CRITICAL=4). Weight = base domain weight x "
    "confidence after critic adjustment. Precautionary floors apply. Overall confidence is the "
    "base-weighted mean of adjusted confidences, reduced for unresolved disagreements and "
    "failed agents."
)

PRECAUTION_CONFIDENCE = 0.6
MIN_CONFIDENCE = 0.05
MAX_CONFIDENCE = 0.95


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def apply_critic_adjustments(
    results: dict[AgentName, AgentResult], critic: CriticAssessment | None
) -> dict[AgentName, AgentResult]:
    """Set adjusted_confidence = confidence + sum(critic deltas), floored at 0.05."""
    delta: dict[AgentName, float] = {}
    if critic is not None:
        for adj in critic.confidence_adjustments:
            agent = specialist_to_agent(adj.agent)
            delta[agent] = delta.get(agent, 0.0) + adj.delta
    out: dict[AgentName, AgentResult] = {}
    for agent, res in results.items():
        adjusted = _clamp(res.assessment.confidence + delta.get(agent, 0.0), MIN_CONFIDENCE)
        out[agent] = res.model_copy(update={"adjusted_confidence": round(adjusted, 3)})
    return out


def _level_from_score(score: float) -> Level:
    if score < 1.75:
        return Level.LOW
    if score < 2.5:
        return Level.MEDIUM
    if score < 3.25:
        return Level.HIGH
    return Level.CRITICAL


def compute_consensus(
    results: dict[AgentName, AgentResult],
    disagreements: list[Disagreement],
    statuses: dict[AgentName, AgentRunStatus],
    profile: SystemProfile | None,
) -> ConsensusAssessment | None:
    if not results:
        return None

    entries: list[AgentConsensusEntry] = []
    for agent in SPECIALISTS:
        res = results.get(agent)
        if res is None:
            continue
        base = BASE_WEIGHTS[agent]
        eff = base * res.adjusted_confidence
        note = None
        if res.adjusted_confidence < res.assessment.confidence - 1e-9:
            note = (
                f"confidence reduced by critic "
                f"({res.assessment.confidence:.2f} to {res.adjusted_confidence:.2f})"
            )
        if res.revision > 0:
            hist = " to ".join(level.value for level in res.level_history)
            note = (note + "; " if note else "") + f"reassessed ({hist})"
        entries.append(
            AgentConsensusEntry(
                agent=agent,
                level=res.assessment.level,
                confidence=round(res.assessment.confidence, 3),
                adjusted_confidence=res.adjusted_confidence,
                base_weight=base,
                effective_weight=eff,
                note=note,
            )
        )

    total = sum(e.effective_weight for e in entries)
    score = sum(e.level.rank * e.effective_weight for e in entries) / total
    level = _level_from_score(score)
    rules = [f"Weighted score {score:.2f} maps to {level.value}."]

    strong = [e for e in entries if e.adjusted_confidence >= PRECAUTION_CONFIDENCE]
    if strong:
        top = max(strong, key=lambda e: e.level.rank)
        floor = Level.from_rank(top.level.rank - 1)
        if top.level.rank >= Level.HIGH.rank and level.rank < floor.rank:
            level = floor
            rules.append(
                f"Precautionary floor: {top.agent.value} rated {top.level.value} with adjusted "
                f"confidence {top.adjusted_confidence:.2f}; overall not below {floor.value}."
            )
    if profile is not None:
        impact_floor = {Level.CRITICAL: Level.HIGH, Level.HIGH: Level.MEDIUM}.get(
            profile.decision_impact
        )
        if impact_floor is not None and level.rank < impact_floor.rank:
            level = impact_floor
            rules.append(
                f"Profile floor: decision impact {profile.decision_impact.value} implies at "
                f"least {impact_floor.value}."
            )

    unresolved = sum(1 for d in disagreements if d.status is DisagreementStatus.UNRESOLVED)
    failed = sum(
        1 for a, s in statuses.items() if a in SPECIALISTS and s.status is AgentStatus.FAILED
    )
    base_total = sum(e.base_weight for e in entries)
    mean_conf = sum(e.adjusted_confidence * e.base_weight for e in entries) / base_total
    penalty = min(0.2, 0.04 * unresolved) + min(0.24, 0.08 * failed)
    confidence = round(_clamp(mean_conf - penalty, MIN_CONFIDENCE, MAX_CONFIDENCE), 3)
    if unresolved:
        rules.append(f"Confidence reduced for {unresolved} unresolved disagreement(s).")
    if failed:
        rules.append(f"Confidence reduced for {failed} failed specialist(s).")

    return ConsensusAssessment(
        overall_level=level,
        overall_confidence=confidence,
        weighted_score=round(score, 3),
        entries=entries,
        rules_applied=rules,
        unresolved_disagreements=unresolved,
        method=METHOD,
    )


_WORD = re.compile(r"[a-z]{4,}")


def _tokens(text: str) -> set[str]:
    return set(_WORD.findall(text.lower()))


def _similar(a: str, b: str, threshold: float = 0.6) -> bool:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return False
    return len(ta & tb) / len(ta | tb) >= threshold


def build_recommendations(
    results: dict[AgentName, AgentResult],
) -> tuple[list[Recommendation], list[Recommendation]]:
    """Rank findings by severity then confidence, de-duplicate similar recommendations."""
    candidates = []
    for agent in SPECIALISTS:
        res = results.get(agent)
        if res is None:
            continue
        for f in res.assessment.findings:
            candidates.append((agent, f))
    candidates.sort(key=lambda t: (-t[1].severity.rank, -t[1].confidence, t[0].value))

    recs: list[Recommendation] = []
    for agent, f in candidates:
        if any(_similar(f.recommendation, r.text) or _similar(f.title, r.title) for r in recs):
            continue
        recs.append(
            Recommendation(
                agent=agent,
                title=f.title,
                text=f.recommendation,
                severity=f.severity,
                confidence=round(f.confidence, 3),
                priority_rank=len(recs) + 1,
            )
        )
    priority = [r for r in recs if r.severity.rank >= Severity.HIGH.rank][:5]
    if len(priority) < 3:
        priority = recs[:3]
    return recs, priority

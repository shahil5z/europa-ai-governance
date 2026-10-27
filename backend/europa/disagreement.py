"""Disagreement detection and reassessment planning.

Level disagreements are found in code. The critic's issues are added as a second
source. Each disagreement has a stable id so it can be followed across rounds.
"""

from __future__ import annotations

from .schemas import (
    SPECIALISTS,
    AgentName,
    AgentResult,
    CriticAssessment,
    Disagreement,
    DisagreementKind,
    DisagreementSource,
    DisagreementStatus,
    IssueKind,
    Level,
    Severity,
    specialist_to_agent,
)

SPREAD_THRESHOLD = 2
MAX_REASSESSMENT_TARGETS = 3


def _levels(results: dict[AgentName, AgentResult]) -> dict[str, str]:
    return {a.value: r.assessment.level.value for a, r in results.items()}


def detect_level_disagreements(
    results: dict[AgentName, AgentResult], round_: int
) -> list[Disagreement]:
    """Rules over structured levels only."""
    if len(results) < 2:
        return []
    out: list[Disagreement] = []
    ranks = {a: r.assessment.level.rank for a, r in results.items()}
    hi, lo = max(ranks.values()), min(ranks.values())
    levels = _levels(results)

    sec = results.get(AgentName.SECURITY)
    outlier_fired = False
    if sec is not None:
        others = [rank for a, rank in ranks.items() if a is not AgentName.SECURITY]
        sec_rank = ranks[AgentName.SECURITY]
        if others and sec_rank >= Level.HIGH.rank and max(others) <= Level.LOW.rank:
            outlier_fired = True
            out.append(
                Disagreement(
                    id="security-outlier",
                    kind=DisagreementKind.SECURITY_OUTLIER,
                    source=DisagreementSource.DETERMINISTIC,
                    agents=list(results),
                    description=(
                        f"Security rates the system {sec.assessment.level.value} while every "
                        "other agent rates it LOW. Either security found something the others "
                        "missed or it is overstated."
                    ),
                    levels=levels,
                    round_detected=round_,
                )
            )
        elif others and sec_rank <= Level.LOW.rank and min(others) >= Level.HIGH.rank:
            outlier_fired = True
            out.append(
                Disagreement(
                    id="security-outlier",
                    kind=DisagreementKind.SECURITY_OUTLIER,
                    source=DisagreementSource.DETERMINISTIC,
                    agents=list(results),
                    description=(
                        "Security rates the system LOW while every other agent rates it HIGH or "
                        "CRITICAL. Possible security blind spot or over-rating elsewhere."
                    ),
                    levels=levels,
                    round_detected=round_,
                )
            )
    if not outlier_fired and hi - lo >= SPREAD_THRESHOLD:
        involved = [a for a, rank in ranks.items() if rank in (hi, lo)]
        out.append(
            Disagreement(
                id="level-spread",
                kind=DisagreementKind.LEVEL_SPREAD,
                source=DisagreementSource.DETERMINISTIC,
                agents=involved,
                description=(
                    f"Agent levels differ by {hi - lo} steps "
                    f"({Level.from_rank(lo).value} to {Level.from_rank(hi).value})."
                ),
                levels=levels,
                round_detected=round_,
            )
        )
    return out


def disagreements_from_critic(
    critic: CriticAssessment | None,
    results: dict[AgentName, AgentResult],
    round_: int,
) -> list[Disagreement]:
    if critic is None:
        return []
    out: list[Disagreement] = []
    levels = _levels(results)
    for issue in critic.issues:
        if issue.severity.rank < Severity.MEDIUM.rank:
            continue
        agents = sorted(
            {specialist_to_agent(a) for a in issue.agents if specialist_to_agent(a) in results},
            key=lambda a: a.value,
        )
        if issue.kind is IssueKind.CONTRADICTION and len(agents) >= 2:
            kind = DisagreementKind.CRITIC_CONTRADICTION
        elif issue.kind is IssueKind.INCONSISTENT_LEVEL and agents:
            kind = DisagreementKind.CRITIC_INCONSISTENT_LEVEL
        else:
            continue
        out.append(
            Disagreement(
                id=f"{kind.value.lower()}:{'+'.join(a.value for a in agents)}",
                kind=kind,
                source=DisagreementSource.CRITIC,
                agents=agents,
                description=issue.description,
                levels={a.value: levels[a.value] for a in agents},
                round_detected=round_,
            )
        )
    return out


def detect(
    results: dict[AgentName, AgentResult], critic: CriticAssessment | None, round_: int
) -> list[Disagreement]:
    found = detect_level_disagreements(results, round_) + disagreements_from_critic(
        critic, results, round_
    )
    seen: set[str] = set()
    unique = []
    for d in found:
        if d.id not in seen:
            seen.add(d.id)
            unique.append(d)
    return unique


def merge(
    previous: list[Disagreement],
    current: list[Disagreement],
    round_: int,
    reassessed: bool,
    critic_available: bool = True,
) -> list[Disagreement]:
    """Carry disagreements across passes. Nothing is dropped from the record.

    - new in `current` -> OPEN
    - previously OPEN and still present -> stays OPEN (UNRESOLVED once no budget remains,
      see `finalize_open`)
    - previously OPEN and gone after a reassessment -> RESOLVED (kept, with a note);
      critic-sourced items are not resolved when the critic did not run this pass
    """
    cur = {d.id: d for d in current}
    merged: list[Disagreement] = []
    seen: set[str] = set()
    for prev in previous:
        seen.add(prev.id)
        if prev.status is DisagreementStatus.RESOLVED:
            merged.append(prev)
        elif prev.id in cur:
            still = cur[prev.id]
            merged.append(
                prev.model_copy(
                    update={
                        "levels": still.levels,
                        "resolution_note": (
                            "Still present after reassessment."
                            if reassessed
                            else prev.resolution_note
                        ),
                    }
                )
            )
        elif reassessed and (critic_available or prev.source is not DisagreementSource.CRITIC):
            merged.append(
                prev.model_copy(
                    update={
                        "status": DisagreementStatus.RESOLVED,
                        "resolution_note": "No longer detected after targeted reassessment.",
                    }
                )
            )
        else:
            merged.append(prev)
    merged.extend(d for d in current if d.id not in seen)
    return merged


def open_ids(disagreements: list[Disagreement]) -> list[Disagreement]:
    return [d for d in disagreements if d.status is DisagreementStatus.OPEN]


def finalize_open(disagreements: list[Disagreement]) -> list[Disagreement]:
    """No rounds left: anything still OPEN becomes UNRESOLVED (accepted, disclosed)."""
    return [
        d.model_copy(
            update={
                "status": DisagreementStatus.UNRESOLVED,
                "resolution_note": d.resolution_note
                or "No reassessment budget remained; disclosed as unresolved.",
            }
        )
        if d.status is DisagreementStatus.OPEN
        else d
        for d in disagreements
    ]


def _brief(result: AgentResult) -> str:
    a = result.assessment
    top = "; ".join(f.title for f in a.findings[:3])
    return f"{result.agent.value} rated {a.level.value} (confidence {a.confidence:.2f}): {top}"


def plan_reassessments(
    open_disagreements: list[Disagreement],
    results: dict[AgentName, AgentResult],
    critic: CriticAssessment | None,
) -> dict[AgentName, str]:
    """Pick at most MAX_REASSESSMENT_TARGETS agents and build targeted feedback.

    Critic requests come first (explicit, specific), then deterministic targets.
    """
    feedback: dict[AgentName, list[str]] = {}

    def add(agent: AgentName, text: str) -> None:
        if agent in results and agent in SPECIALISTS:
            feedback.setdefault(agent, []).append(text)

    if critic is not None:
        for req in critic.reassessment_requests:
            add(specialist_to_agent(req.agent), f"Critic feedback: {req.feedback}")

    for d in open_disagreements:
        involved = [a for a in d.agents if a in results]
        if d.kind is DisagreementKind.LEVEL_SPREAD:
            ranks = {a: results[a].assessment.level.rank for a in involved}
            hi, _lo = max(ranks.values()), min(ranks.values())
            for a in involved:
                other = [results[b] for b in involved if ranks[b] != ranks[a]]
                if other:
                    side = "higher" if ranks[a] == hi else "lower"
                    add(
                        a,
                        f"Disagreement ({d.description}). You are on the {side} side "
                        f"of the range. Contrasting views: "
                        + " | ".join(_brief(r) for r in other[:2]),
                    )
        elif d.kind is DisagreementKind.SECURITY_OUTLIER:
            sec = results.get(AgentName.SECURITY)
            if sec and sec.assessment.level.rank >= Level.HIGH.rank:
                for a in results:
                    if a is not AgentName.SECURITY:
                        add(
                            a,
                            f"{d.description} Security view: {_brief(sec)}. Consider whether "
                            "you missed a related consequence in your domain.",
                        )
            else:
                others = [results[a] for a in results if a is not AgentName.SECURITY]
                add(
                    AgentName.SECURITY,
                    f"{d.description} Others: " + " | ".join(_brief(r) for r in others[:3]),
                )
        else:
            for a in involved:
                add(a, f"Disagreement ({d.description}). Re-examine your level and findings.")

    ordered = list(feedback)[:MAX_REASSESSMENT_TARGETS]
    return {a: "\n".join(feedback[a])[:1500] for a in ordered}

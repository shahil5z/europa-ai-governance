"""Guardrails around the orchestrator's routing proposal.

The model proposes a profile and which specialists to run. Code then looks for
high-signal keywords, raises the decision-impact floor when they justify it, forces
specialists on when needed and always keeps RISK and SECURITY. Overrides are
recorded and shown in the report.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .schemas import (
    AutonomyLevel,
    DataType,
    GuardrailOverride,
    Level,
    OrchestratorOutput,
    RouteDecision,
    RoutingPlan,
    SpecialistName,
    SystemProfile,
)


@dataclass(frozen=True)
class Signal:
    key: str
    pattern: re.Pattern[str]
    impact_floor: Level | None
    forces: tuple[SpecialistName, ...]
    label: str


_ALL = tuple(SpecialistName)
S = SpecialistName


def _sig(
    key: str, pattern: str, floor: Level | None, forces: tuple[SpecialistName, ...], label: str
) -> Signal:
    return Signal(key, re.compile(pattern, re.IGNORECASE), floor, forces, label)


SIGNALS: tuple[Signal, ...] = (
    _sig(
        "biometric",
        r"\b(biometric|facial recognition|face recognition|fingerprint|emotion "
        r"(?:recognition|detection|analysis))",
        Level.HIGH,
        _ALL,
        "biometric processing",
    ),
    _sig(
        "employment",
        r"\b(recruit\w*|hiring|job (?:applicant|application)s?|candidates?|"
        r"cv|resumes?|employee monitoring|performance review|worker management)\b",
        Level.HIGH,
        _ALL,
        "employment or worker management",
    ),
    _sig(
        "credit",
        r"\b(credit scor\w*|loan|lender|creditworth\w*|mortgage|insurance (?:pricing|"
        r"underwriting)|welfare|benefits? eligibility)\b",
        Level.HIGH,
        _ALL,
        "access to essential services or credit",
    ),
    _sig(
        "health",
        r"\b(medical|diagnos\w*|patients?|clinical|hospital|physicians?|radiolog\w*|"
        r"health records?)\b",
        Level.HIGH,
        _ALL,
        "health or medical context",
    ),
    _sig(
        "law_enforcement",
        r"\b(police|law enforcement|surveillance|border control|migration|"
        r"watchlist|predictive policing|asylum)\b",
        Level.HIGH,
        _ALL,
        "law enforcement, surveillance or migration",
    ),
    _sig(
        "education",
        r"\b(students?|pupils?|exam(?:s|ination)?s?|grading|admissions?|"
        r"university|school)\b",
        Level.MEDIUM,
        (S.DATA_GOVERNANCE, S.HUMAN_OVERSIGHT, S.GOVERNANCE),
        "education or assessment of students",
    ),
    _sig(
        "children",
        r"\b(children|minors?|child|kids|under 18|under-18)\b",
        Level.MEDIUM,
        (S.DATA_GOVERNANCE, S.HUMAN_OVERSIGHT, S.GOVERNANCE),
        "children or minors",
    ),
    _sig(
        "personal_data",
        r"\b(personal data|customers?'? (?:email|data|address)|email address|"
        r"home address|date of birth|user data|account balance|conversation logs?|"
        r"logged for)\b",
        None,
        (S.DATA_GOVERNANCE,),
        "personal data processing",
    ),
    _sig(
        "automation",
        r"\b(fully automated|automatically (?:reject|approve|decline|open|issue)\w*"
        r"|without human review|no human review|autonomous(?:ly)?|auto-?approve\w*)\b",
        None,
        (S.HUMAN_OVERSIGHT, S.SECURITY),
        "automated decisions or actions",
    ),
    _sig(
        "tools",
        r"\b(tool calls?|function calling|plugins?|internal api|api access|can issue|"
        r"can draft|agentic|mcp)\b",
        None,
        (S.SECURITY,),
        "tool use or action-taking",
    ),
)


_NEGATED = re.compile(r"\b(?:no|without|not|zero|never)\s+(?:\w+\s+){0,2}$", re.IGNORECASE)


def _signal_present(sig: Signal, text: str) -> bool:
    for match in sig.pattern.finditer(text):
        if not _NEGATED.search(text[max(0, match.start() - 24) : match.start()]):
            return True
    return False


def detect_signals(text: str) -> list[Signal]:
    return [s for s in SIGNALS if _signal_present(s, text)]


_PERSONAL_TYPES = {
    DataType.PERSONAL,
    DataType.SPECIAL_CATEGORY,
    DataType.BIOMETRIC,
    DataType.HEALTH,
    DataType.FINANCIAL,
    DataType.CHILDREN,
    DataType.LOCATION,
}


def required_specialists(
    profile: SystemProfile, signals: list[Signal]
) -> dict[SpecialistName, str]:
    """Specialists that must run, with the reason (deterministic)."""
    req: dict[SpecialistName, str] = {
        S.RISK: "risk assessment always runs",
        S.SECURITY: "security assessment always runs for AI systems",
    }
    if profile.decision_impact in (Level.HIGH, Level.CRITICAL):
        for name in _ALL:
            req.setdefault(name, f"decision impact is {profile.decision_impact.value}")
    if profile.autonomy_level is AutonomyLevel.AUTONOMOUS_ACTIONS:
        req.setdefault(S.HUMAN_OVERSIGHT, "system appears to act autonomously")
        req.setdefault(S.GOVERNANCE, "autonomous actions need governance review")
    if _PERSONAL_TYPES & set(profile.data_types):
        req.setdefault(S.DATA_GOVERNANCE, "personal or sensitive data types in profile")
    for sig in signals:
        for name in sig.forces:
            req.setdefault(name, f"signal detected: {sig.label}")
    return req


def _impact_floor(signals: list[Signal]) -> Level | None:
    floors = [s.impact_floor for s in signals if s.impact_floor]
    return max(floors, key=lambda lv: lv.rank) if floors else None


def apply_guardrails(output: OrchestratorOutput, text: str) -> tuple[SystemProfile, RoutingPlan]:
    signals = detect_signals(text)
    profile = output.profile
    notes = [f"signal: {s.label}" for s in signals]
    floor = _impact_floor(signals)
    if floor and profile.decision_impact.rank < floor.rank:
        notes.append(
            f"decision impact raised from {profile.decision_impact.value} to {floor.value} "
            "by deterministic signals"
        )
        profile = profile.model_copy(update={"decision_impact": floor})

    required = required_specialists(profile, signals)
    decisions: list[RouteDecision] = []
    overrides: list[GuardrailOverride] = []
    for d in output.routing:
        if not d.run and d.agent in required:
            overrides.append(
                GuardrailOverride(
                    agent=d.agent,
                    reason=f"forced to run: {required[d.agent]} (orchestrator proposed skip)",
                )
            )
            d = d.model_copy(
                update={
                    "run": True,
                    "justification": f"Guardrail: {required[d.agent]}."[:300],
                }
            )
        decisions.append(d)
    return profile, RoutingPlan(
        decisions=decisions, overrides=overrides, signals=notes, source="LLM_WITH_GUARDRAILS"
    )


def fallback_plan(text: str) -> tuple[SystemProfile, RoutingPlan]:
    """Used when the orchestrator LLM fails: run every specialist, profile from signals."""
    signals = detect_signals(text)
    floor = _impact_floor(signals) or Level.MEDIUM
    data_types = (
        [DataType.PERSONAL]
        if any(s.key == "personal_data" for s in signals)
        else [DataType.NONE_APPARENT]
    )
    profile = SystemProfile(
        domain="unclassified",
        purpose_summary="Profile unavailable: orchestrator model call failed. Deterministic "
        "fallback used.",
        decision_impact=floor,
        data_types=data_types,
        autonomy_level=AutonomyLevel.UNCLEAR,
        affected_people=["unspecified"],
        uses_external_tools=any(s.key == "tools" for s in signals),
        user_facing=True,
        missing_information=["Structured profile could not be produced"],
    )
    decisions = [
        RouteDecision(
            agent=name,
            run=True,
            focus="Assess this domain from the description as given.",
            justification="Fallback routing: all specialists run because the orchestrator failed.",
        )
        for name in _ALL
    ]
    return profile, RoutingPlan(
        decisions=decisions,
        overrides=[],
        signals=[f"signal: {s.label}" for s in signals],
        source="DETERMINISTIC_FALLBACK",
    )

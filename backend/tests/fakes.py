"""Test doubles and builders. No test or dev server in this repo calls OpenAI."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from europa.llm import LLMTimeoutError, OutputValidationError
from europa.schemas import (
    AgentFinding,
    AgentName,
    AIActTier,
    AutonomyLevel,
    ConfidenceAdjustment,
    CriticAssessment,
    CriticIssue,
    DataGovernanceAssessment,
    DataType,
    ExecutiveSummary,
    FrameworkReference,
    GovernanceAssessment,
    HumanOversightAssessment,
    Level,
    OrchestratorOutput,
    OversightModel,
    ReassessmentRequest,
    Relevance,
    RiskAssessment,
    RouteDecision,
    SecurityAssessment,
    Severity,
    SpecialistName,
    SystemProfile,
    ThreatCategory,
)

Response = BaseModel | Exception | Callable[[dict[str, Any]], BaseModel]

SEV = {
    Level.LOW: Severity.LOW,
    Level.MEDIUM: Severity.MEDIUM,
    Level.HIGH: Severity.HIGH,
    Level.CRITICAL: Severity.CRITICAL,
}


def finding(title: str, severity: Severity = Severity.MEDIUM, confidence: float = 0.8):
    return AgentFinding(
        title=title,
        severity=severity,
        confidence=confidence,
        explanation=f"{title}: explanation grounded in the provided description.",
        evidence="Derived from the described data flow and decision process.",
        recommendation=f"Mitigate: {title.lower()} through documented controls.",
    )


def _base(level: Level, confidence: float, title: str) -> dict[str, Any]:
    return {
        "summary": f"Overall {level.value} from this domain perspective: {title}.",
        "level": level,
        "confidence": confidence,
        "findings": [finding(title, SEV[level], confidence)],
        "assumptions_and_gaps": ["Deployment details were not described."],
    }


def make_risk(level: Level = Level.MEDIUM, confidence: float = 0.8, title: str = "Biased outcomes"):
    return RiskAssessment(
        **_base(level, confidence, title),
        likelihood=level,
        impact=level,
        potential_harms=["Unfair treatment of affected people"],
    )


def make_data(level=Level.MEDIUM, confidence=0.8, title="Excessive data retention"):
    return DataGovernanceAssessment(
        **_base(level, confidence, title),
        data_categories=["Personal data"],
        special_category_data_likely=False,
        lawful_basis_considerations=["Purpose limitation requires review"],
        minimisation_and_retention="Retention period is not specified and should be limited.",
    )


def make_security(level=Level.MEDIUM, confidence=0.8, title="Prompt injection exposure"):
    return SecurityAssessment(
        **_base(level, confidence, title),
        threat_categories=[ThreatCategory.PROMPT_INJECTION],
        attack_surface_notes="Untrusted text reaches the model without isolation.",
    )


def make_oversight(level=Level.MEDIUM, confidence=0.8, title="Weak override path"):
    return HumanOversightAssessment(
        **_base(level, confidence, title),
        oversight_model=OversightModel.HUMAN_ON_THE_LOOP,
        oversight_gaps=["No documented override procedure"],
        contestability_described=False,
        accountability_owner_described=False,
    )


def make_governance(level=Level.MEDIUM, confidence=0.8, title="Potential high-risk use area"):
    return GovernanceAssessment(
        **_base(level, confidence, title),
        potential_ai_act_tier=AIActTier.POTENTIAL_HIGH_RISK,
        tier_rationale="Based on the provided description, this appears relevant to a listed area.",
        frameworks=[
            FrameworkReference(
                name="EU AI Act (high-risk concepts)",
                relevance=Relevance.POTENTIALLY_APPLICABLE,
                note="Requires legal review to confirm applicability.",
            )
        ],
        requires_legal_review=True,
    )


MAKERS = {
    AgentName.RISK: make_risk,
    AgentName.DATA_GOVERNANCE: make_data,
    AgentName.SECURITY: make_security,
    AgentName.HUMAN_OVERSIGHT: make_oversight,
    AgentName.GOVERNANCE: make_governance,
}


def make_profile(impact: Level = Level.HIGH, data=(DataType.PERSONAL,)) -> SystemProfile:
    return SystemProfile(
        domain="employment",
        purpose_summary="Screens job applications and ranks candidates automatically.",
        decision_impact=impact,
        data_types=list(data),
        autonomy_level=AutonomyLevel.HUMAN_APPROVES_ACTIONS,
        affected_people=["Job applicants"],
        uses_external_tools=False,
        user_facing=True,
        missing_information=[],
    )


def make_orchestrator(
    skip: tuple[SpecialistName, ...] = (), impact: Level = Level.HIGH, data=(DataType.PERSONAL,)
) -> OrchestratorOutput:
    return OrchestratorOutput(
        profile=make_profile(impact, data),
        routing=[
            RouteDecision(
                agent=name,
                run=name not in skip,
                focus=f"Focus on {name.value.lower()} aspects of this system.",
                justification="Relevant to the described use case."
                if name not in skip
                else "Clearly not needed for this low impact case.",
            )
            for name in SpecialistName
        ],
    )


def make_critic(
    issues: tuple[CriticIssue, ...] = (),
    requests: tuple[ReassessmentRequest, ...] = (),
    adjustments: tuple[ConfidenceAdjustment, ...] = (),
) -> CriticAssessment:
    return CriticAssessment(
        summary="Reviewed the specialist outputs for consistency and support.",
        confidence=0.8,
        issues=list(issues),
        missing_risks=[],
        confidence_adjustments=list(adjustments),
        reassessment_requests=list(requests),
    )


def make_summary() -> ExecutiveSummary:
    return ExecutiveSummary(
        text="Based on the provided description, the system appears to carry elevated risk "
        "that requires legal review and human oversight improvements.",
        key_points=["Review oversight design", "Limit data retention"],
    )


class ScriptedLLM:
    """Returns scripted responses per agent. The last response repeats.

    A response is a model instance, an Exception, or a callable taking the prompt
    variables. Every call also renders the real ChatPromptTemplate so template
    errors surface in tests.
    """

    def __init__(self, script: dict[AgentName, list[Response]] | None = None, delay: float = 0):
        self.script = script or {}
        self.calls: list[tuple[AgentName, type, dict[str, Any], list[Any]]] = []
        self.delay = delay

    def count(self, agent: AgentName) -> int:
        return sum(1 for c in self.calls if c[0] is agent)

    async def ainvoke(self, *, agent, schema, prompt, variables, timeout_s):
        messages = prompt.format_messages(**variables)
        self.calls.append((agent, schema, variables, messages))
        if self.delay:
            await asyncio.sleep(self.delay)
        key = agent
        if schema is ExecutiveSummary:
            key = "SUMMARY"  # type: ignore[assignment]
        seq = self.script.get(key)
        if not seq:
            raise LLMTimeoutError("no scripted response")
        n = sum(1 for c in self.calls if c[0] is agent and c[1] is schema) - 1
        item = seq[min(n, len(seq) - 1)]
        if isinstance(item, Exception):
            raise item
        if callable(item) and not isinstance(item, BaseModel):
            return item(variables)
        return item


def happy_script() -> dict:
    script: dict = {
        AgentName.ORCHESTRATOR: [make_orchestrator()],
        AgentName.CRITIC: [make_critic()],
        "SUMMARY": [make_summary()],
    }
    for agent, maker in MAKERS.items():
        script[agent] = [maker()]
    return script


def invalid_output(detail: str = "findings: List should have at least 1 item"):
    return OutputValidationError(detail)

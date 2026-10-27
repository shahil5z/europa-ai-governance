"""Pydantic v2 domain contracts for EUROPA AI GOVERNANCE.

Every agent output, every API payload and the final report are defined here.
Model output is never trusted: it is parsed into these types and anything that
fails validation is rejected before it can reach the report.

Models used as LLM structured-output targets avoid default values and open
dicts so that they are compatible with strict JSON-schema output modes.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DISCLAIMER = (
    "This tool provides AI-assisted governance analysis for informational purposes "
    "and does not constitute legal advice, regulatory certification, or a formal "
    "compliance determination."
)

MIN_DESCRIPTION_CHARS = 30
MAX_DESCRIPTION_CHARS = 6000

Confidence = Annotated[float, Field(ge=0.0, le=1.0)]


# enums
class Level(StrEnum):
    """Overall level assigned by an agent or by consensus."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    @property
    def rank(self) -> int:
        return _LEVEL_RANK[self]

    @classmethod
    def from_rank(cls, rank: int) -> Level:
        return _RANK_LEVEL[max(1, min(4, rank))]


_LEVEL_RANK = {Level.LOW: 1, Level.MEDIUM: 2, Level.HIGH: 3, Level.CRITICAL: 4}
_RANK_LEVEL = {v: k for k, v in _LEVEL_RANK.items()}


class Severity(StrEnum):
    """Severity of an individual finding."""

    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    @property
    def rank(self) -> int:
        return ("INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL").index(self.value)


class SpecialistName(StrEnum):
    RISK = "RISK"
    DATA_GOVERNANCE = "DATA_GOVERNANCE"
    SECURITY = "SECURITY"
    HUMAN_OVERSIGHT = "HUMAN_OVERSIGHT"
    GOVERNANCE = "GOVERNANCE"


class AgentName(StrEnum):
    ORCHESTRATOR = "ORCHESTRATOR"
    RISK = "RISK"
    DATA_GOVERNANCE = "DATA_GOVERNANCE"
    SECURITY = "SECURITY"
    HUMAN_OVERSIGHT = "HUMAN_OVERSIGHT"
    GOVERNANCE = "GOVERNANCE"
    CRITIC = "CRITIC"


SPECIALISTS: tuple[AgentName, ...] = (
    AgentName.RISK,
    AgentName.DATA_GOVERNANCE,
    AgentName.SECURITY,
    AgentName.HUMAN_OVERSIGHT,
    AgentName.GOVERNANCE,
)


def specialist_to_agent(name: SpecialistName) -> AgentName:
    return AgentName(name.value)


class AgentStatus(StrEnum):
    WAITING = "WAITING"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    REASSESSING = "REASSESSING"
    SKIPPED = "SKIPPED"


class ReportStatus(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class DataType(StrEnum):
    PERSONAL = "PERSONAL"
    SPECIAL_CATEGORY = "SPECIAL_CATEGORY"
    BIOMETRIC = "BIOMETRIC"
    HEALTH = "HEALTH"
    FINANCIAL = "FINANCIAL"
    CHILDREN = "CHILDREN"
    LOCATION = "LOCATION"
    CONFIDENTIAL_BUSINESS = "CONFIDENTIAL_BUSINESS"
    OPERATIONAL_SENSOR = "OPERATIONAL_SENSOR"
    PUBLIC = "PUBLIC"
    NONE_APPARENT = "NONE_APPARENT"


class AutonomyLevel(StrEnum):
    INFORMATIONAL = "INFORMATIONAL"
    ADVISORY_HUMAN_DECIDES = "ADVISORY_HUMAN_DECIDES"
    HUMAN_APPROVES_ACTIONS = "HUMAN_APPROVES_ACTIONS"
    AUTONOMOUS_ACTIONS = "AUTONOMOUS_ACTIONS"
    UNCLEAR = "UNCLEAR"


class ThreatCategory(StrEnum):
    PROMPT_INJECTION = "PROMPT_INJECTION"
    DATA_LEAKAGE = "DATA_LEAKAGE"
    UNAUTHORIZED_ACCESS = "UNAUTHORIZED_ACCESS"
    INSECURE_TOOLS = "INSECURE_TOOLS"
    MODEL_ABUSE = "MODEL_ABUSE"
    ADVERSARIAL_INPUT = "ADVERSARIAL_INPUT"
    SECRETS_EXPOSURE = "SECRETS_EXPOSURE"
    OPERATIONAL_SECURITY = "OPERATIONAL_SECURITY"


class OversightModel(StrEnum):
    HUMAN_IN_THE_LOOP = "HUMAN_IN_THE_LOOP"
    HUMAN_ON_THE_LOOP = "HUMAN_ON_THE_LOOP"
    HUMAN_IN_COMMAND = "HUMAN_IN_COMMAND"
    NONE_DESCRIBED = "NONE_DESCRIBED"


class AIActTier(StrEnum):
    """Potential AI Act risk tier. Always a hypothesis, never a determination."""

    POTENTIAL_PROHIBITED_PRACTICE = "POTENTIAL_PROHIBITED_PRACTICE"
    POTENTIAL_HIGH_RISK = "POTENTIAL_HIGH_RISK"
    POTENTIAL_TRANSPARENCY_OBLIGATIONS = "POTENTIAL_TRANSPARENCY_OBLIGATIONS"
    POTENTIAL_MINIMAL_RISK = "POTENTIAL_MINIMAL_RISK"
    UNCLEAR_NEEDS_MORE_INFORMATION = "UNCLEAR_NEEDS_MORE_INFORMATION"


class Relevance(StrEnum):
    APPEARS_RELEVANT = "APPEARS_RELEVANT"
    POTENTIALLY_APPLICABLE = "POTENTIALLY_APPLICABLE"
    UNLIKELY_BUT_CHECK = "UNLIKELY_BUT_CHECK"


class IssueKind(StrEnum):
    CONTRADICTION = "CONTRADICTION"
    UNSUPPORTED_CONCLUSION = "UNSUPPORTED_CONCLUSION"
    OVERCONFIDENCE = "OVERCONFIDENCE"
    MISSING_RISK = "MISSING_RISK"
    INCONSISTENT_LEVEL = "INCONSISTENT_LEVEL"
    DUPLICATE = "DUPLICATE"


class DisagreementKind(StrEnum):
    LEVEL_SPREAD = "LEVEL_SPREAD"
    SECURITY_OUTLIER = "SECURITY_OUTLIER"
    CRITIC_CONTRADICTION = "CRITIC_CONTRADICTION"
    CRITIC_INCONSISTENT_LEVEL = "CRITIC_INCONSISTENT_LEVEL"


class DisagreementStatus(StrEnum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    UNRESOLVED = "UNRESOLVED"


class DisagreementSource(StrEnum):
    DETERMINISTIC = "DETERMINISTIC"
    CRITIC = "CRITIC"


class AuditEventType(StrEnum):
    ASSESSMENT_STARTED = "ASSESSMENT_STARTED"
    ORCHESTRATION_COMPLETED = "ORCHESTRATION_COMPLETED"
    ROUTING_DECIDED = "ROUTING_DECIDED"
    AGENT_STARTED = "AGENT_STARTED"
    AGENT_RETRY = "AGENT_RETRY"
    AGENT_COMPLETED = "AGENT_COMPLETED"
    AGENT_FAILED = "AGENT_FAILED"
    CRITIC_TRIGGERED = "CRITIC_TRIGGERED"
    DISAGREEMENT_DETECTED = "DISAGREEMENT_DETECTED"
    DISAGREEMENT_RESOLVED = "DISAGREEMENT_RESOLVED"
    REASSESSMENT_TRIGGERED = "REASSESSMENT_TRIGGERED"
    CONSENSUS_COMPUTED = "CONSENSUS_COMPUTED"
    SUMMARY_WRITTEN = "SUMMARY_WRITTEN"
    REPORT_GENERATED = "REPORT_GENERATED"


# request
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def clean_text(value: str) -> str:
    """Normalise untrusted text: NFC, unify newlines, drop control and format chars."""
    text = unicodedata.normalize("NFC", value).replace("\r\n", "\n").replace("\r", "\n")
    text = _CONTROL_RE.sub("", text)
    text = "".join(
        ch for ch in text if ch in "\n\t" or unicodedata.category(ch) not in {"Cc", "Cf"}
    )
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip()


class AssessmentRequest(BaseModel):
    """Input to POST /api/assess."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    description: str = Field(min_length=MIN_DESCRIPTION_CHARS, max_length=MAX_DESCRIPTION_CHARS)
    scenario_id: str | None = Field(default=None, pattern=r"^[a-z0-9-]{1,40}$")

    @field_validator("description", mode="before")
    @classmethod
    def _clean_description(cls, value: object) -> object:
        return clean_text(value) if isinstance(value, str) else value


# orchestrator
class SystemProfile(BaseModel):
    """Structured profile of the described AI system (orchestrator output)."""

    model_config = ConfigDict(extra="forbid")

    domain: str = Field(min_length=2, max_length=80)
    purpose_summary: str = Field(min_length=10, max_length=500)
    decision_impact: Level
    data_types: list[DataType] = Field(min_length=1, max_length=8)
    autonomy_level: AutonomyLevel
    affected_people: list[str] = Field(min_length=1, max_length=6)
    uses_external_tools: bool
    user_facing: bool
    missing_information: list[str] = Field(max_length=6)


class RouteDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent: SpecialistName
    run: bool
    focus: str = Field(min_length=5, max_length=300)
    justification: str = Field(min_length=10, max_length=300)


class OrchestratorOutput(BaseModel):
    """What the orchestrator LLM must return: a profile plus routing proposal."""

    model_config = ConfigDict(extra="forbid")

    profile: SystemProfile
    routing: list[RouteDecision] = Field(min_length=5, max_length=5)

    @model_validator(mode="after")
    def _one_decision_per_specialist(self) -> OrchestratorOutput:
        names = {r.agent for r in self.routing}
        if names != set(SpecialistName):
            raise ValueError("routing must contain exactly one decision per specialist")
        return self


class GuardrailOverride(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent: SpecialistName
    reason: str = Field(max_length=300)


class RoutingPlan(BaseModel):
    """Final routing: LLM proposal after deterministic guardrails were applied."""

    model_config = ConfigDict(extra="forbid")

    decisions: list[RouteDecision]
    overrides: list[GuardrailOverride]
    signals: list[str]
    source: Literal["LLM_WITH_GUARDRAILS", "DETERMINISTIC_FALLBACK"]

    def selected(self) -> list[AgentName]:
        return [specialist_to_agent(d.agent) for d in self.decisions if d.run]

    def skipped(self) -> list[AgentName]:
        return [specialist_to_agent(d.agent) for d in self.decisions if not d.run]

    def focus_for(self, agent: AgentName) -> str:
        for d in self.decisions:
            if d.agent.value == agent.value:
                return d.focus
        return ""


# specialists
class AgentFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=140)
    severity: Severity
    confidence: Confidence
    explanation: str = Field(min_length=10, max_length=1000)
    evidence: str = Field(min_length=5, max_length=600, description="Reasoning summary.")
    recommendation: str = Field(min_length=5, max_length=600)


class SpecialistAssessment(BaseModel):
    """Fields shared by every specialist assessment."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=20, max_length=700)
    level: Level
    confidence: Confidence
    findings: list[AgentFinding] = Field(min_length=1, max_length=7)
    assumptions_and_gaps: list[str] = Field(max_length=5)

    @model_validator(mode="after")
    def _careful_wording(self) -> SpecialistAssessment:
        _guard_model(self)
        return self


class RiskAssessment(SpecialistAssessment):
    likelihood: Level
    impact: Level
    potential_harms: list[str] = Field(min_length=1, max_length=5)


class DataGovernanceAssessment(SpecialistAssessment):
    data_categories: list[str] = Field(min_length=1, max_length=8)
    special_category_data_likely: bool
    lawful_basis_considerations: list[str] = Field(max_length=4)
    minimisation_and_retention: str = Field(min_length=10, max_length=500)


class SecurityAssessment(SpecialistAssessment):
    threat_categories: list[ThreatCategory] = Field(min_length=1, max_length=8)
    attack_surface_notes: str = Field(min_length=10, max_length=500)


class HumanOversightAssessment(SpecialistAssessment):
    oversight_model: OversightModel
    oversight_gaps: list[str] = Field(max_length=5)
    contestability_described: bool
    accountability_owner_described: bool


class FrameworkReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=3, max_length=120)
    relevance: Relevance
    note: str = Field(min_length=10, max_length=400)


class GovernanceAssessment(SpecialistAssessment):
    potential_ai_act_tier: AIActTier
    tier_rationale: str = Field(min_length=10, max_length=600)
    frameworks: list[FrameworkReference] = Field(min_length=1, max_length=6)
    requires_legal_review: bool

    @model_validator(mode="after")
    def _legal_review_always_required(self) -> GovernanceAssessment:
        # Governance output is never a legal determination; force the flag.
        self.requires_legal_review = True
        return self


SPECIALIST_SCHEMAS: dict[AgentName, type[SpecialistAssessment]] = {
    AgentName.RISK: RiskAssessment,
    AgentName.DATA_GOVERNANCE: DataGovernanceAssessment,
    AgentName.SECURITY: SecurityAssessment,
    AgentName.HUMAN_OVERSIGHT: HumanOversightAssessment,
    AgentName.GOVERNANCE: GovernanceAssessment,
}


# critic
class CriticIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: IssueKind
    description: str = Field(min_length=10, max_length=500)
    agents: list[SpecialistName] = Field(min_length=1, max_length=5)
    severity: Severity


class ReassessmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent: SpecialistName
    feedback: str = Field(min_length=10, max_length=600)


class ConfidenceAdjustment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent: SpecialistName
    delta: float = Field(ge=-0.3, le=0.0)
    reason: str = Field(min_length=5, max_length=300)


class CriticAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=20, max_length=700)
    confidence: Confidence
    issues: list[CriticIssue] = Field(max_length=10)
    missing_risks: list[str] = Field(max_length=5)
    confidence_adjustments: list[ConfidenceAdjustment] = Field(max_length=5)
    reassessment_requests: list[ReassessmentRequest] = Field(max_length=3)


# disagreements
class Disagreement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: DisagreementKind
    source: DisagreementSource
    agents: list[AgentName]
    description: str
    levels: dict[str, str]
    status: DisagreementStatus = DisagreementStatus.OPEN
    round_detected: int = 0
    resolution_note: str | None = None


# audit + status
class AuditEvent(BaseModel):
    """One structured, user-text-free entry in the audit trail."""

    model_config = ConfigDict(extra="forbid")

    seq: int
    ts: datetime
    type: AuditEventType
    message: str
    agent: AgentName | None = None
    status: AgentStatus | None = None
    round: int = 0
    data: dict[str, str | int | float | bool | list[str]] = Field(default_factory=dict)


class AgentRunStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent: AgentName
    status: AgentStatus
    attempts: int = 0
    revisions: int = 0
    duration_ms: int | None = None
    level: Level | None = None
    confidence: float | None = None
    error_code: str | None = None
    note: str | None = None


class AgentResult(BaseModel):
    """A specialist's validated assessment plus run metadata (set by code)."""

    model_config = ConfigDict(extra="forbid")

    agent: AgentName
    assessment: (
        RiskAssessment
        | DataGovernanceAssessment
        | SecurityAssessment
        | HumanOversightAssessment
        | GovernanceAssessment
    )
    revision: int = 0
    level_history: list[Level]
    adjusted_confidence: Confidence


# consensus
class AgentConsensusEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent: AgentName
    level: Level
    confidence: float
    adjusted_confidence: float
    base_weight: float
    effective_weight: float
    note: str | None = None


class ConsensusAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overall_level: Level
    overall_confidence: Confidence
    weighted_score: float
    entries: list[AgentConsensusEntry]
    rules_applied: list[str]
    unresolved_disagreements: int
    method: str


class Recommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent: AgentName
    title: str
    text: str
    severity: Severity
    confidence: float
    priority_rank: int


class ExecutiveSummary(BaseModel):
    """Output of the bounded summary step. Written from structured data only."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=40, max_length=1400)
    key_points: list[str] = Field(min_length=1, max_length=5)

    @model_validator(mode="after")
    def _careful_wording(self) -> ExecutiveSummary:
        _guard_model(self)
        return self


# report
class ReportMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str
    critic_model: str
    max_reassessment_rounds: int
    reassessment_rounds_used: int
    duration_ms: int
    description_chars: int
    scenario_id: str | None = None
    summary_mode: Literal["LLM", "DETERMINISTIC", "NONE"]


class GovernanceReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_id: str = Field(default_factory=lambda: uuid4().hex)
    status: ReportStatus
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    profile: SystemProfile | None
    routing: RoutingPlan | None
    results: list[AgentResult]
    critic: CriticAssessment | None
    disagreements: list[Disagreement]
    consensus: ConsensusAssessment | None
    executive_summary: ExecutiveSummary | None
    recommendations: list[Recommendation]
    priority_actions: list[Recommendation]
    agent_statuses: list[AgentRunStatus]
    audit_trail: list[AuditEvent]
    limitations: list[str]
    disclaimer: str = DISCLAIMER
    meta: ReportMeta


class Scenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    category: str
    description: str


class ErrorBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    retry_after_seconds: int | None = None


# wording guard
_ASSERTIVE_LEGAL = re.compile(
    r"\b(?:"
    r"(?:is|are|was|were)\s+(?:definitely\s+|clearly\s+|certainly\s+|legally\s+)?"
    r"(?:prohibited|illegal|unlawful|non-?compliant|compliant)"
    r"|(?:violates?|breach(?:es)?|infring(?:es|ing))\s+(?:the\s+)?(?:EU\s+)?"
    r"(?:AI\s+Act|GDPR|law|regulation)"
    r"|(?:is|are)\s+(?:classified|categori[sz]ed)\s+as\s+(?:a\s+)?(?:high-risk|prohibited)"
    r"|guarantee[sd]?\s+compliance|fully\s+compliant|legally\s+certified"
    r")\b",
    re.IGNORECASE,
)


def assert_careful_wording(text: str) -> None:
    """Reject text that asserts a legal conclusion instead of a hypothesis."""
    match = _ASSERTIVE_LEGAL.search(text)
    if match:
        raise ValueError(
            f"assertive legal phrase '{match.group(0)}'; use hedged wording such as "
            "'potentially applicable' or 'requires legal review'"
        )


def _guard_model(model: BaseModel) -> None:
    assert_careful_wording(model.model_dump_json())

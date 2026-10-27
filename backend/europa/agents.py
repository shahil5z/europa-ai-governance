"""Agent runners: orchestrator, specialists, critic and the bounded summary step.

Each runner builds its prompt variables, calls the model through `StructuredLLM`,
validates the result against its Pydantic schema, retries once on malformed output
and reports every transition to the audit log.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel

from . import prompts
from .audit import AuditLog
from .config import Settings
from .guardrails import apply_guardrails, fallback_plan
from .llm import (
    DeadlineExceededError,
    LLMError,
    OutputValidationError,
    StructuredLLM,
)
from .schemas import (
    SPECIALIST_SCHEMAS,
    AgentName,
    AgentResult,
    AgentRunStatus,
    AgentStatus,
    AuditEventType,
    ConsensusAssessment,
    CriticAssessment,
    Disagreement,
    ExecutiveSummary,
    OrchestratorOutput,
    Recommendation,
    RoutingPlan,
    SpecialistAssessment,
    SystemProfile,
)

LABELS: dict[AgentName, str] = {
    AgentName.ORCHESTRATOR: "Orchestrator",
    AgentName.RISK: "Risk Assessment",
    AgentName.DATA_GOVERNANCE: "Data Governance",
    AgentName.SECURITY: "Security",
    AgentName.HUMAN_OVERSIGHT: "Human Oversight",
    AgentName.GOVERNANCE: "Governance",
    AgentName.CRITIC: "Critic",
}

MIN_CALL_BUDGET_S = 4.0
MAX_ATTEMPTS = 2


@dataclass
class RunContext:
    """Per-run services shared by all graph nodes (kept out of graph state)."""

    settings: Settings
    llm: StructuredLLM
    audit: AuditLog
    deadline: float
    started: float = field(default_factory=time.perf_counter)
    deadline_hit: bool = False

    def remaining(self) -> float:
        return self.deadline - time.monotonic()


@dataclass
class Outcome[T: BaseModel]:
    value: T | None
    attempts: int
    duration_ms: int
    error_code: str | None = None


async def run_structured[T: BaseModel](
    ctx: RunContext,
    *,
    agent: AgentName,
    schema: type[T],
    prompt: ChatPromptTemplate,
    variables: dict[str, Any],
    round_: int = 0,
    reassessing: bool = False,
    announce: bool = True,
) -> Outcome[T]:
    """One agent call: bounded timeout, one retry on malformed output, audited."""
    label = LABELS[agent]
    began = time.perf_counter()
    if announce:
        ctx.audit.emit(
            AuditEventType.AGENT_STARTED,
            f"{label} agent {'reassessing' if reassessing else 'started'}",
            agent=agent,
            status=AgentStatus.REASSESSING if reassessing else AgentStatus.RUNNING,
            round_=round_,
        )
    attempts = 0
    hint: str | None = None
    code = "upstream_error"
    for _ in range(MAX_ATTEMPTS):
        attempts += 1
        budget = min(ctx.settings.call_timeout_s, ctx.remaining())
        if budget < MIN_CALL_BUDGET_S:
            ctx.deadline_hit = True
            code = DeadlineExceededError.code
            break
        call_vars = {**variables, "retry_feedback": prompts.retry_hint(hint)}
        try:
            value = await ctx.llm.ainvoke(
                agent=agent, schema=schema, prompt=prompt, variables=call_vars, timeout_s=budget
            )
            return Outcome(value, attempts, int((time.perf_counter() - began) * 1000))
        except OutputValidationError as exc:
            code = exc.code
            hint = exc.detail
            if attempts < MAX_ATTEMPTS and announce:
                ctx.audit.emit(
                    AuditEventType.AGENT_RETRY,
                    f"{label} output failed validation; retrying once with feedback",
                    agent=agent,
                    status=AgentStatus.REASSESSING if reassessing else AgentStatus.RUNNING,
                    round_=round_,
                )
            continue
        except LLMError as exc:
            code = exc.code
            break
    duration = int((time.perf_counter() - began) * 1000)
    if announce:
        ctx.audit.emit(
            AuditEventType.AGENT_FAILED,
            f"{label} agent failed ({code})",
            agent=agent,
            status=AgentStatus.FAILED,
            round_=round_,
            error_code=code,
            attempts=attempts,
        )
    return Outcome(None, attempts, duration, code)


# ----------------------------------------------------------------- orchestrator


async def run_orchestrator(
    ctx: RunContext, description: str
) -> tuple[SystemProfile, RoutingPlan, AgentRunStatus]:
    outcome = await run_structured(
        ctx,
        agent=AgentName.ORCHESTRATOR,
        schema=OrchestratorOutput,
        prompt=prompts.prompt_for(AgentName.ORCHESTRATOR),
        variables=prompts.variables(
            description,
            None,
            prompts.task_block(
                "Produce the system profile and the routing decision for all five specialists."
            ),
        ),
    )
    if outcome.value is None:
        profile, plan = fallback_plan(description)
        status = AgentRunStatus(
            agent=AgentName.ORCHESTRATOR,
            status=AgentStatus.FAILED,
            attempts=outcome.attempts,
            duration_ms=outcome.duration_ms,
            error_code=outcome.error_code,
            note="Deterministic fallback profile and full routing used",
        )
    else:
        profile, plan = apply_guardrails(outcome.value, description)
        status = AgentRunStatus(
            agent=AgentName.ORCHESTRATOR,
            status=AgentStatus.COMPLETE,
            attempts=outcome.attempts,
            duration_ms=outcome.duration_ms,
            level=profile.decision_impact,
        )
        ctx.audit.emit(
            AuditEventType.ORCHESTRATION_COMPLETED,
            "Orchestrator produced the system profile",
            agent=AgentName.ORCHESTRATOR,
            status=AgentStatus.COMPLETE,
            domain=profile.domain,
            decision_impact=profile.decision_impact.value,
        )
    ctx.audit.emit(
        AuditEventType.ROUTING_DECIDED,
        f"Routing decided: {len(plan.selected())} specialist(s) selected"
        + (f", {len(plan.skipped())} skipped" if plan.skipped() else ""),
        agent=AgentName.ORCHESTRATOR,
        selected=[a.value for a in plan.selected()],
        skipped=[a.value for a in plan.skipped()],
        guardrail_overrides=len(plan.overrides),
        source=plan.source,
    )
    return profile, plan, status


# ------------------------------------------------------------------ specialists


def _result_brief(result: AgentResult) -> dict[str, Any]:
    a = result.assessment
    return {
        "agent": result.agent.value,
        "level": a.level.value,
        "confidence": round(a.confidence, 2),
        "summary": a.summary,
        "revision": result.revision,
        "level_history": [lv.value for lv in result.level_history],
        "findings": [
            {
                "title": f.title,
                "severity": f.severity.value,
                "confidence": round(f.confidence, 2),
                "explanation": f.explanation[:300],
            }
            for f in a.findings
        ],
    }


async def run_specialist(
    ctx: RunContext,
    *,
    agent: AgentName,
    description: str,
    profile: SystemProfile,
    focus: str,
    round_: int,
    previous: AgentResult | None,
    previous_status: AgentRunStatus | None,
    feedback: str | None,
) -> tuple[AgentResult | None, AgentRunStatus]:
    """Run (or re-run) one specialist. On a failed reassessment keep the earlier result."""
    reassessing = previous is not None and feedback is not None
    schema = SPECIALIST_SCHEMAS[agent]
    reassess = ""
    if reassessing and previous is not None and feedback is not None:
        reassess = prompts.reassessment_block(
            json.dumps(_result_brief(previous), ensure_ascii=False), feedback
        )
    outcome = await run_structured(
        ctx,
        agent=agent,
        schema=schema,
        prompt=prompts.prompt_for(agent),
        variables=prompts.variables(
            description, profile, prompts.task_block(focus), reassess=reassess
        ),
        round_=round_,
        reassessing=reassessing,
    )
    prior_attempts = previous_status.attempts if previous_status else 0
    prior_ms = (previous_status.duration_ms or 0) if previous_status else 0
    if outcome.value is None:
        if previous is not None and previous_status is not None:
            kept = previous_status.model_copy(
                update={
                    "status": AgentStatus.COMPLETE,
                    "attempts": prior_attempts + outcome.attempts,
                    "duration_ms": prior_ms + outcome.duration_ms,
                    "error_code": outcome.error_code,
                    "note": "Reassessment failed; earlier assessment retained",
                }
            )
            return previous, kept
        return None, AgentRunStatus(
            agent=agent,
            status=AgentStatus.FAILED,
            attempts=outcome.attempts,
            duration_ms=outcome.duration_ms,
            error_code=outcome.error_code,
        )
    assessment: SpecialistAssessment = outcome.value
    history = [*(previous.level_history if previous else []), assessment.level]
    result = AgentResult(
        agent=agent,
        assessment=assessment,
        revision=(previous.revision + 1) if previous else 0,
        level_history=history,
        adjusted_confidence=assessment.confidence,
    )
    status = AgentRunStatus(
        agent=agent,
        status=AgentStatus.COMPLETE,
        attempts=prior_attempts + outcome.attempts,
        revisions=result.revision,
        duration_ms=prior_ms + outcome.duration_ms,
        level=assessment.level,
        confidence=assessment.confidence,
    )
    ctx.audit.emit(
        AuditEventType.AGENT_COMPLETED,
        f"{LABELS[agent]} agent completed: {assessment.level.value}",
        agent=agent,
        status=AgentStatus.COMPLETE,
        round_=round_,
        level=assessment.level.value,
        confidence=round(assessment.confidence, 2),
        findings=len(assessment.findings),
        revision=result.revision,
    )
    return result, status


# ----------------------------------------------------------------------- critic


async def run_critic(
    ctx: RunContext,
    *,
    description: str,
    profile: SystemProfile,
    results: dict[AgentName, AgentResult],
    deterministic: list[Disagreement],
    pass_number: int,
    round_: int,
) -> tuple[CriticAssessment | None, AgentRunStatus]:
    results_json = json.dumps([_result_brief(r) for r in results.values()], ensure_ascii=False)
    outcome = await run_structured(
        ctx,
        agent=AgentName.CRITIC,
        schema=CriticAssessment,
        prompt=prompts.prompt_for(AgentName.CRITIC),
        variables=prompts.variables(
            description,
            profile,
            prompts.critic_task_block(results_json, deterministic, pass_number),
        ),
        round_=round_,
        reassessing=pass_number > 1,
    )
    if outcome.value is None:
        return None, AgentRunStatus(
            agent=AgentName.CRITIC,
            status=AgentStatus.FAILED,
            attempts=outcome.attempts,
            duration_ms=outcome.duration_ms,
            error_code=outcome.error_code,
        )
    critic = outcome.value
    ctx.audit.emit(
        AuditEventType.AGENT_COMPLETED,
        f"Critic review {pass_number} completed: {len(critic.issues)} issue(s)",
        agent=AgentName.CRITIC,
        status=AgentStatus.COMPLETE,
        round_=round_,
        issues=len(critic.issues),
        reassessment_requests=len(critic.reassessment_requests),
        pass_number=pass_number,
    )
    return critic, AgentRunStatus(
        agent=AgentName.CRITIC,
        status=AgentStatus.COMPLETE,
        attempts=outcome.attempts,
        revisions=pass_number - 1,
        duration_ms=outcome.duration_ms,
        confidence=critic.confidence,
    )


# --------------------------------------------------------------------- summary


async def run_summary(
    ctx: RunContext,
    *,
    profile: SystemProfile | None,
    consensus: ConsensusAssessment,
    recommendations: list[Recommendation],
    disagreements: list[Disagreement],
    report_status: str,
) -> ExecutiveSummary | None:
    structured = {
        "report_status": report_status,
        "profile": (
            {
                "domain": profile.domain,
                "purpose": profile.purpose_summary,
                "decision_impact": profile.decision_impact.value,
                "autonomy": profile.autonomy_level.value,
            }
            if profile
            else None
        ),
        "overall_level": consensus.overall_level.value,
        "overall_confidence": consensus.overall_confidence,
        "agents": [{"agent": e.agent.value, "level": e.level.value} for e in consensus.entries],
        "top_recommendations": [
            {"title": r.title, "severity": r.severity.value} for r in recommendations[:6]
        ],
        "disagreements": [
            {"description": d.description, "status": d.status.value} for d in disagreements
        ],
    }
    outcome = await run_structured(
        ctx,
        agent=AgentName.ORCHESTRATOR,
        schema=ExecutiveSummary,
        prompt=prompts.SUMMARY_PROMPT,
        variables=prompts.summary_variables(structured, consensus.overall_level.value),
        announce=False,
    )
    return outcome.value

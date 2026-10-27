"""LangGraph workflow for one assessment run.

    START -> orchestrate -> specialist (parallel) -> review
    review -> specialist (reassess only the agents in disagreement, bounded) -> review
    review -> consensus -> summarize -> finalize -> END

`results` and `statuses` use a dict-merge reducer so parallel specialists can write
at the same time. The LLM, audit log and deadline are passed through
`config["configurable"]["ctx"]` instead of living in state.
"""

from __future__ import annotations

import time
from functools import lru_cache
from typing import Annotated, Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from . import consensus as consensus_mod
from . import disagreement as dis
from . import report as report_mod
from .agents import (
    RunContext,
    run_critic,
    run_orchestrator,
    run_specialist,
    run_summary,
)
from .schemas import (
    DISCLAIMER,
    AgentName,
    AgentResult,
    AgentRunStatus,
    AgentStatus,
    AuditEventType,
    ConsensusAssessment,
    CriticAssessment,
    Disagreement,
    DisagreementStatus,
    ExecutiveSummary,
    GovernanceReport,
    Recommendation,
    ReportMeta,
    RoutingPlan,
    SystemProfile,
)


def _merge(left: dict | None, right: dict | None) -> dict:
    return {**(left or {}), **(right or {})}


class GraphState(TypedDict, total=False):
    description: str
    scenario_id: str | None
    profile: SystemProfile | None
    routing: RoutingPlan | None
    results: Annotated[dict[AgentName, AgentResult], _merge]
    statuses: Annotated[dict[AgentName, AgentRunStatus], _merge]
    critic: CriticAssessment | None
    critic_failed: bool
    critic_passes: int
    disagreements: list[Disagreement]
    pending: dict[AgentName, str]
    round: int
    consensus: ConsensusAssessment | None
    recommendations: list[Recommendation]
    priority_actions: list[Recommendation]
    summary: ExecutiveSummary | None
    summary_mode: str
    report: GovernanceReport | None


class SpecialistTask(TypedDict):
    """Payload of one `Send` to the specialist node."""

    agent: AgentName
    description: str
    profile: SystemProfile
    focus: str
    round: int
    previous: AgentResult | None
    previous_status: AgentRunStatus | None
    feedback: str | None


def _ctx(config: RunnableConfig) -> RunContext:
    return config["configurable"]["ctx"]


# nodes
async def orchestrate_node(state: GraphState, config: RunnableConfig) -> dict[str, Any]:
    ctx = _ctx(config)
    profile, plan, status = await run_orchestrator(ctx, state["description"])
    statuses: dict[AgentName, AgentRunStatus] = {AgentName.ORCHESTRATOR: status}
    for d in plan.decisions:
        if not d.run:
            agent = AgentName(d.agent.value)
            statuses[agent] = AgentRunStatus(
                agent=agent, status=AgentStatus.SKIPPED, note=d.justification
            )
    return {
        "profile": profile,
        "routing": plan,
        "statuses": statuses,
        "round": 0,
        "disagreements": [],
        "pending": {},
    }


def dispatch_specialists(state: GraphState) -> list[Send]:
    plan = state["routing"]
    assert plan is not None
    return [
        Send(
            "specialist",
            SpecialistTask(
                agent=agent,
                description=state["description"],
                profile=state["profile"],
                focus=plan.focus_for(agent),
                round=0,
                previous=None,
                previous_status=None,
                feedback=None,
            ),
        )
        for agent in plan.selected()
    ]


async def specialist_node(task: SpecialistTask, config: RunnableConfig) -> dict[str, Any]:
    ctx = _ctx(config)
    result, status = await run_specialist(
        ctx,
        agent=task["agent"],
        description=task["description"],
        profile=task["profile"],
        focus=task["focus"],
        round_=task["round"],
        previous=task["previous"],
        previous_status=task["previous_status"],
        feedback=task["feedback"],
    )
    update: dict[str, Any] = {"statuses": {task["agent"]: status}}
    if result is not None:
        update["results"] = {task["agent"]: result}
    return update


async def review_node(state: GraphState, config: RunnableConfig) -> dict[str, Any]:
    """Critic + deterministic disagreement detection + reassessment planning."""
    ctx = _ctx(config)
    results = state.get("results") or {}
    round_ = state.get("round", 0)
    if not results:
        return {"pending": {}}

    pass_number = state.get("critic_passes", 0) + 1
    previous = state.get("disagreements", [])
    deterministic = dis.detect_level_disagreements(results, round_)
    ctx.audit.emit(
        AuditEventType.CRITIC_TRIGGERED,
        f"Critic review {pass_number} triggered over {len(results)} specialist result(s)",
        agent=AgentName.CRITIC,
        status=AgentStatus.RUNNING,
        round_=round_,
        pass_number=pass_number,
    )
    critic, critic_status = await run_critic(
        ctx,
        description=state["description"],
        profile=state["profile"],
        results=results,
        deterministic=deterministic,
        pass_number=pass_number,
        round_=round_,
    )
    critic_failed = state.get("critic_failed", False) or critic is None
    kept_critic = critic if critic is not None else state.get("critic")
    if critic is not None:
        critic = _sanitize_critic(critic, results)
        kept_critic = critic
    elif state.get("critic") is not None:
        critic_status = critic_status.model_copy(
            update={"note": "Re-review failed; first-pass review retained"}
        )

    detected = dis.detect(results, critic, round_)
    reassessed = round_ > 0
    merged = dis.merge(previous, detected, round_, reassessed, critic is not None)
    known = {d.id for d in previous}
    for d in merged:
        if d.id not in known:
            ctx.audit.emit(
                AuditEventType.DISAGREEMENT_DETECTED,
                f"Disagreement detected: {d.kind.value}",
                round_=round_,
                disagreement_id=d.id,
                kind=d.kind.value,
                source=d.source.value,
                agents=[a.value for a in d.agents],
            )
    for old in previous:
        now = next(d for d in merged if d.id == old.id)
        if old.status is not DisagreementStatus.RESOLVED and now.status is (
            DisagreementStatus.RESOLVED
        ):
            ctx.audit.emit(
                AuditEventType.DISAGREEMENT_RESOLVED,
                f"Disagreement resolved after reassessment: {now.kind.value}",
                round_=round_,
                disagreement_id=now.id,
            )

    pending: dict[AgentName, str] = {}
    if round_ < ctx.settings.max_reassessment_rounds and ctx.remaining() > 30:
        pending = dis.plan_reassessments(dis.open_ids(merged), results, critic)
    if pending:
        ctx.audit.emit(
            AuditEventType.REASSESSMENT_TRIGGERED,
            f"Reassessment round {round_ + 1} triggered for {len(pending)} agent(s)",
            round_=round_ + 1,
            agents=[a.value for a in pending],
        )
    else:
        merged = dis.finalize_open(merged)

    update: dict[str, Any] = {
        "critic": kept_critic,
        "critic_failed": critic_failed,
        "critic_passes": pass_number,
        "disagreements": merged,
        "pending": pending,
        "statuses": {AgentName.CRITIC: critic_status},
    }
    if pending:
        update["round"] = round_ + 1
    return update


def _sanitize_critic(
    critic: CriticAssessment, results: dict[AgentName, AgentResult]
) -> CriticAssessment:
    """Drop critic references to agents that did not produce a result."""
    present = {a.value for a in results}
    return critic.model_copy(
        update={
            "confidence_adjustments": [
                a for a in critic.confidence_adjustments if a.agent.value in present
            ],
            "reassessment_requests": [
                r for r in critic.reassessment_requests if r.agent.value in present
            ],
        }
    )


def route_after_review(state: GraphState) -> list[Send] | str:
    pending = state.get("pending") or {}
    if not pending:
        return "consensus"
    results = state["results"]
    statuses = state["statuses"]
    plan = state["routing"]
    assert plan is not None
    return [
        Send(
            "specialist",
            SpecialistTask(
                agent=agent,
                description=state["description"],
                profile=state["profile"],
                focus=plan.focus_for(agent),
                round=state["round"],
                previous=results[agent],
                previous_status=statuses.get(agent),
                feedback=feedback,
            ),
        )
        for agent, feedback in pending.items()
    ]


def consensus_node(state: GraphState, config: RunnableConfig) -> dict[str, Any]:
    ctx = _ctx(config)
    results = consensus_mod.apply_critic_adjustments(
        state.get("results") or {}, state.get("critic")
    )
    disagreements = dis.finalize_open(state.get("disagreements", []))
    consensus = consensus_mod.compute_consensus(
        results, disagreements, state.get("statuses") or {}, state.get("profile")
    )
    recs, priority = consensus_mod.build_recommendations(results)
    if consensus is not None:
        ctx.audit.emit(
            AuditEventType.CONSENSUS_COMPUTED,
            f"Consensus computed: {consensus.overall_level.value}",
            level=consensus.overall_level.value,
            confidence=consensus.overall_confidence,
            unresolved=consensus.unresolved_disagreements,
        )
    return {
        "results": results,
        "disagreements": disagreements,
        "consensus": consensus,
        "recommendations": recs,
        "priority_actions": priority,
    }


async def summarize_node(state: GraphState, config: RunnableConfig) -> dict[str, Any]:
    ctx = _ctx(config)
    consensus = state.get("consensus")
    if consensus is None:
        return {"summary": None, "summary_mode": "NONE"}
    status = _status(state, critic_failed=state.get("critic_failed", False))
    summary = await run_summary(
        ctx,
        profile=state.get("profile"),
        consensus=consensus,
        recommendations=state.get("recommendations", []),
        disagreements=state.get("disagreements", []),
        report_status=status.value,
    )
    mode = "LLM"
    if summary is None:
        mode = "DETERMINISTIC"
        summary = report_mod.deterministic_summary(
            consensus, state.get("recommendations", []), state.get("disagreements", []), status
        )
    ctx.audit.emit(
        AuditEventType.SUMMARY_WRITTEN,
        "Executive summary written from structured results"
        if mode == "LLM"
        else "Executive summary composed by code (summary model step failed)",
        mode=mode,
    )
    return {"summary": summary, "summary_mode": mode}


def _status(state: GraphState, *, critic_failed: bool):
    return report_mod.report_status(
        state.get("statuses") or {},
        state.get("routing"),
        critic_failed,
        bool(state.get("results")),
    )


def finalize_node(state: GraphState, config: RunnableConfig) -> dict[str, Any]:
    ctx = _ctx(config)
    statuses = dict(state.get("statuses") or {})
    results = state.get("results") or {}
    critic_failed = state.get("critic_failed", False)
    status = _status(state, critic_failed=critic_failed)
    disagreements = state.get("disagreements", [])
    summary_mode = state.get("summary_mode", "NONE")
    limitations = report_mod.build_limitations(
        statuses,
        state.get("routing"),
        disagreements,
        critic_failed,
        summary_mode,
        ctx.deadline_hit,
    )
    ctx.audit.emit(
        AuditEventType.REPORT_GENERATED,
        f"Report generated with status {status.value}",
        report_status=status.value,
    )
    order = list(AgentName)
    report = GovernanceReport(
        status=status,
        profile=state.get("profile"),
        routing=state.get("routing"),
        results=[results[a] for a in order if a in results],
        critic=state.get("critic"),
        disagreements=disagreements,
        consensus=state.get("consensus"),
        executive_summary=state.get("summary"),
        recommendations=state.get("recommendations", []),
        priority_actions=state.get("priority_actions", []),
        agent_statuses=[statuses[a] for a in order if a in statuses],
        audit_trail=list(ctx.audit.events),
        limitations=limitations,
        disclaimer=DISCLAIMER,
        meta=ReportMeta(
            model=ctx.settings.model,
            critic_model=ctx.settings.critic_model,
            max_reassessment_rounds=ctx.settings.max_reassessment_rounds,
            reassessment_rounds_used=state.get("round", 0),
            duration_ms=int((time.perf_counter() - ctx.started) * 1000),
            description_chars=len(state["description"]),
            scenario_id=state.get("scenario_id"),
            summary_mode=summary_mode,  # type: ignore[arg-type]
        ),
    )
    return {"report": report}


# graph
@lru_cache(maxsize=1)
def build_graph():
    g = StateGraph(GraphState)
    g.add_node("orchestrate", orchestrate_node)
    g.add_node("specialist", specialist_node, input_schema=SpecialistTask)
    g.add_node("review", review_node)
    g.add_node("consensus", consensus_node)
    g.add_node("summarize", summarize_node)
    g.add_node("finalize", finalize_node)

    g.add_edge(START, "orchestrate")
    g.add_conditional_edges("orchestrate", dispatch_specialists, ["specialist"])
    g.add_edge("specialist", "review")
    g.add_conditional_edges("review", route_after_review, ["specialist", "consensus"])
    g.add_edge("consensus", "summarize")
    g.add_edge("summarize", "finalize")
    g.add_edge("finalize", END)
    return g.compile()

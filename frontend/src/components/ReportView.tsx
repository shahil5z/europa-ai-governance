import { forwardRef } from "react";
import { humanize, pct, seconds } from "@/lib/format";
import {
  AGENT_LABEL,
  AGENT_ORDER,
  type AgentName,
  type AgentResult,
  type Disagreement,
  type GovernanceReport,
  type Recommendation,
} from "@/lib/types";
import { LevelBadge, StatusTag } from "./Badges";

const SPECIALIST_ORDER: AgentName[] = AGENT_ORDER.filter((a) => a !== "ORCHESTRATOR" && a !== "CRITIC");

function H2({ id, children }: { id: string; children: React.ReactNode }) {
  return (
    <h2 id={id} className="section-title">
      {children}
    </h2>
  );
}

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section aria-labelledby={id} className="rule-top mt-10 pt-8">
      <H2 id={id}>{title}</H2>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function List({ items }: { items: string[] }) {
  if (items.length === 0) return null;
  return (
    <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-muted marker:text-eu">
      {items.map((t, i) => (
        <li key={i}>{t}</li>
      ))}
    </ul>
  );
}

function Extras({ r }: { r: AgentResult }) {
  const a = r.assessment;
  const rows: [string, React.ReactNode][] = [];
  if (a.likelihood && a.impact) rows.push(["Likelihood / impact", `${a.likelihood} / ${a.impact}`]);
  if (a.potential_harms?.length) rows.push(["Potential harms", a.potential_harms.join("; ")]);
  if (a.data_categories?.length) rows.push(["Data categories", a.data_categories.join("; ")]);
  if (a.special_category_data_likely !== undefined)
    rows.push(["Special category data likely", a.special_category_data_likely ? "Yes, based on the description" : "Not indicated"]);
  if (a.lawful_basis_considerations?.length) rows.push(["Lawful basis considerations", a.lawful_basis_considerations.join("; ")]);
  if (a.minimisation_and_retention) rows.push(["Minimisation and retention", a.minimisation_and_retention]);
  if (a.threat_categories?.length) rows.push(["Threat categories", a.threat_categories.map(humanize).join(", ")]);
  if (a.attack_surface_notes) rows.push(["Attack surface", a.attack_surface_notes]);
  if (a.oversight_model) rows.push(["Oversight model", humanize(a.oversight_model)]);
  if (a.oversight_gaps?.length) rows.push(["Oversight gaps", a.oversight_gaps.join("; ")]);
  if (a.contestability_described !== undefined)
    rows.push(["Contestability described", a.contestability_described ? "Yes" : "No"]);
  if (a.accountability_owner_described !== undefined)
    rows.push(["Accountable owner described", a.accountability_owner_described ? "Yes" : "No"]);
  if (a.potential_ai_act_tier) rows.push(["Potential AI Act tier", humanize(a.potential_ai_act_tier)]);
  if (a.tier_rationale) rows.push(["Tier rationale", a.tier_rationale]);
  if (a.frameworks?.length)
    rows.push([
      "Frameworks",
      <ul key="f" className="space-y-1">
        {a.frameworks.map((f, i) => (
          <li key={i}>
            <span className="text-paper">{f.name}</span> <span className="font-mono text-[0.7rem] uppercase text-eu-soft">{humanize(f.relevance)}</span>
            <br />
            {f.note}
          </li>
        ))}
      </ul>,
    ]);
  if (a.requires_legal_review) rows.push(["Legal review", "Requires legal review by a qualified professional"]);
  if (rows.length === 0) return null;
  return (
    <dl className="mt-4 grid grid-cols-1 gap-x-6 gap-y-2 border-t border-rule pt-3 text-sm sm:grid-cols-[12rem_1fr]">
      {rows.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="font-mono text-[0.7rem] uppercase tracking-[0.1em] text-faint">{k}</dt>
          <dd className="min-w-0 break-words text-muted">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

function DomainCard({ r }: { r: AgentResult }) {
  const a = r.assessment;
  return (
    <article aria-labelledby={`dom-${r.agent}`} className="panel p-4 sm:p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 id={`dom-${r.agent}`} className="font-display text-base uppercase tracking-[0.12em]">
          {AGENT_LABEL[r.agent]}
        </h3>
        <div className="flex flex-wrap items-center gap-3 font-mono text-xs text-muted">
          <LevelBadge level={a.level} />
          <span>confidence {pct(r.adjusted_confidence)}</span>
          {r.revision > 0 ? <span>reassessed: {r.level_history.join(" > ")}</span> : null}
        </div>
      </div>
      <p className="mt-3 text-sm leading-relaxed text-paper">{a.summary}</p>
      <ol className="mt-4 list-none space-y-4">
        {a.findings.map((f, i) => (
          <li key={i} className="border-l-2 border-rule-strong pl-4">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <h4 className="text-sm font-semibold text-white">{f.title}</h4>
              <LevelBadge level={f.severity} />
              <span className="font-mono text-[0.7rem] text-faint">conf {pct(f.confidence)}</span>
            </div>
            <p className="mt-1 text-sm text-muted">{f.explanation}</p>
            <p className="mt-1 text-sm text-muted">
              <span className="font-mono text-[0.68rem] uppercase tracking-[0.1em] text-faint">Evidence </span>
              {f.evidence}
            </p>
            <p className="mt-1 text-sm text-muted">
              <span className="font-mono text-[0.68rem] uppercase tracking-[0.1em] text-eu-soft">Recommendation </span>
              {f.recommendation}
            </p>
          </li>
        ))}
      </ol>
      <Extras r={r} />
      {a.assumptions_and_gaps.length ? (
        <div className="mt-3">
          <p className="font-mono text-[0.7rem] uppercase tracking-[0.1em] text-faint">Assumptions and gaps</p>
          <List items={a.assumptions_and_gaps} />
        </div>
      ) : null}
    </article>
  );
}

function DisagreementCard({ d }: { d: Disagreement }) {
  const tone = d.status === "RESOLVED" ? "border-level-low" : d.status === "UNRESOLVED" ? "border-level-high" : "border-level-medium";
  return (
    <li className={`border-l-2 bg-surface p-4 ${tone}`}>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <h3 className="text-sm font-semibold text-white">{humanize(d.kind)}</h3>
        <span className="font-mono text-[0.7rem] uppercase tracking-[0.1em] text-muted">
          {humanize(d.status)} / detected round {d.round_detected} / {humanize(d.source)}
        </span>
      </div>
      <p className="mt-1 text-sm text-muted">{d.description}</p>
      {Object.keys(d.levels).length > 0 ? (
        <p className="mt-2 flex flex-wrap gap-x-3 gap-y-1 font-mono text-[0.72rem] text-muted">
          {(Object.entries(d.levels) as [AgentName, string][]).map(([agent, lvl]) => (
            <span key={agent}>
              {AGENT_LABEL[agent]}: <span className="text-paper">{lvl}</span>
            </span>
          ))}
        </p>
      ) : null}
      {d.resolution_note ? <p className="mt-2 text-xs text-faint">{d.resolution_note}</p> : null}
    </li>
  );
}

function RecItem({ r }: { r: Recommendation }) {
  return (
    <li className="flex gap-4 border-b border-rule py-3 last:border-b-0">
      <span className="w-6 shrink-0 font-mono text-sm text-eu-soft">{r.priority_rank}</span>
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <h4 className="text-sm font-semibold text-white">{r.title}</h4>
          <LevelBadge level={r.severity} />
          <span className="font-mono text-[0.7rem] text-faint">{AGENT_LABEL[r.agent]}</span>
        </div>
        <p className="mt-1 text-sm text-muted">{r.text}</p>
      </div>
    </li>
  );
}

export const ReportView = forwardRef<HTMLElement, { report: GovernanceReport }>(function ReportView({ report }, ref) {
  const c = report.consensus;
  const failed = report.agent_statuses.filter((s) => s.status === "FAILED");
  const byAgent = new Map(report.results.map((r) => [r.agent, r]));
  const rest = report.recommendations.filter((r) => !report.priority_actions.some((p) => p.priority_rank === r.priority_rank));

  return (
    <article ref={ref} tabIndex={-1} aria-labelledby="report-title" className="mt-16 scroll-mt-6 outline-none">
      <header className="border-y border-rule-strong py-8">
        <p className="eyebrow">Governance report / {report.report_id.slice(0, 8)}</p>
        <h2 id="report-title" className="mt-2 font-display text-2xl uppercase tracking-[0.14em] sm:text-3xl">
          Assessment report
        </h2>
        {report.status !== "COMPLETE" ? (
          <div role="status" className="mt-4 border border-level-medium p-3 text-sm text-muted">
            <strong className="font-semibold text-level-medium">
              {report.status === "PARTIAL" ? "Partial report." : "Assessment failed."}
            </strong>{" "}
            {failed.length > 0
              ? `These agents did not produce a result: ${failed.map((f) => AGENT_LABEL[f.agent]).join(", ")}. `
              : ""}
            Treat conclusions below as incomplete.
          </div>
        ) : null}
        {c ? (
          <dl className="mt-6 grid grid-cols-2 gap-px border border-rule bg-rule sm:grid-cols-4">
            <div className="bg-ink p-4">
              <dt className="font-mono text-[0.68rem] uppercase tracking-[0.12em] text-faint">Overall risk</dt>
              <dd className="mt-2">
                <LevelBadge level={c.overall_level} />
              </dd>
            </div>
            <div className="bg-ink p-4">
              <dt className="font-mono text-[0.68rem] uppercase tracking-[0.12em] text-faint">Confidence</dt>
              <dd className="mt-1 font-display text-2xl">{pct(c.overall_confidence)}</dd>
            </div>
            <div className="bg-ink p-4">
              <dt className="font-mono text-[0.68rem] uppercase tracking-[0.12em] text-faint">Report status</dt>
              <dd className="mt-2 font-mono text-sm uppercase">{report.status}</dd>
            </div>
            <div className="bg-ink p-4">
              <dt className="font-mono text-[0.68rem] uppercase tracking-[0.12em] text-faint">Run time</dt>
              <dd className="mt-2 font-mono text-sm">{seconds(report.meta.duration_ms)}</dd>
            </div>
          </dl>
        ) : null}
      </header>

      {report.executive_summary ? (
        <Section id="sec-summary" title="Executive summary">
          <p className="max-w-3xl leading-relaxed text-paper">{report.executive_summary.text}</p>
          <List items={report.executive_summary.key_points} />
          {report.meta.summary_mode !== "LLM" ? (
            <p className="mt-2 text-xs text-faint">This summary was composed by code because the summary step failed.</p>
          ) : null}
        </Section>
      ) : null}

      {c ? (
        <Section id="sec-consensus" title="Agent consensus">
          <div className="overflow-x-auto border border-rule" role="region" aria-label="Agent consensus table, scrollable" tabIndex={0}>
            <table className="w-full min-w-[34rem] border-collapse text-left text-sm">
              <caption className="sr-only">Level, confidence and weight contributed by each agent to the overall result</caption>
              <thead className="bg-surface-2 font-mono text-[0.68rem] uppercase tracking-[0.1em] text-faint">
                <tr>
                  <th scope="col" className="p-3 font-normal">Agent</th>
                  <th scope="col" className="p-3 font-normal">Level</th>
                  <th scope="col" className="p-3 font-normal">Confidence</th>
                  <th scope="col" className="p-3 font-normal">Weight</th>
                  <th scope="col" className="p-3 font-normal">Note</th>
                </tr>
              </thead>
              <tbody>
                {c.entries.map((e) => (
                  <tr key={e.agent} className="border-t border-rule">
                    <th scope="row" className="p-3 font-normal text-paper">{AGENT_LABEL[e.agent]}</th>
                    <td className="p-3"><LevelBadge level={e.level} /></td>
                    <td className="p-3 font-mono text-xs text-muted">
                      {pct(e.adjusted_confidence)}
                      {e.adjusted_confidence !== e.confidence ? ` (from ${pct(e.confidence)})` : ""}
                    </td>
                    <td className="p-3 font-mono text-xs text-muted">{Math.round(e.effective_weight * 100)}%</td>
                    <td className="p-3 text-xs text-muted">{e.note ?? ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-3 max-w-3xl text-xs leading-relaxed text-faint">{c.method}</p>
          <List items={c.rules_applied} />
        </Section>
      ) : null}

      <Section id="sec-disagreements" title="Disagreements">
        {report.disagreements.length === 0 ? (
          <p className="text-sm text-muted">No material disagreement between agents was detected.</p>
        ) : (
          <>
            <p className="mb-3 max-w-3xl text-sm text-muted">
              Disagreements are kept on the record even when a targeted reassessment resolves them.
            </p>
            <ul className="list-none space-y-3">
              {report.disagreements.map((d) => (
                <DisagreementCard key={d.id} d={d} />
              ))}
            </ul>
          </>
        )}
        {report.meta.reassessment_rounds_used > 0 ? (
          <p className="mt-3 font-mono text-xs text-faint">
            Reassessment rounds used: {report.meta.reassessment_rounds_used} of {report.meta.max_reassessment_rounds}
          </p>
        ) : null}
      </Section>

      {report.priority_actions.length > 0 ? (
        <Section id="sec-priority" title="Priority actions">
          <ol className="list-none border border-rule bg-surface px-4">
            {report.priority_actions.map((r) => (
              <RecItem key={r.priority_rank} r={r} />
            ))}
          </ol>
        </Section>
      ) : null}

      {rest.length > 0 ? (
        <Section id="sec-recs" title="All recommendations">
          <details className="border border-rule bg-surface">
            <summary className="cursor-pointer p-3 font-mono text-xs uppercase tracking-[0.1em] text-eu-soft">
              Show {rest.length} further recommendation(s)
            </summary>
            <ol className="list-none px-4">
              {rest.map((r) => (
                <RecItem key={r.priority_rank} r={r} />
              ))}
            </ol>
          </details>
        </Section>
      ) : null}

      <Section id="sec-domains" title="Findings by domain">
        <div className="space-y-4">
          {SPECIALIST_ORDER.map((agent) => {
            const r = byAgent.get(agent);
            if (r) return <DomainCard key={agent} r={r} />;
            const st = report.agent_statuses.find((s) => s.agent === agent);
            if (!st) return null;
            return (
              <article key={agent} className="panel p-4">
                <h3 className="font-display text-base uppercase tracking-[0.12em]">{AGENT_LABEL[agent]}</h3>
                <div className="mt-2">
                  <StatusTag status={st.status} />
                </div>
                <p className="mt-2 text-sm text-muted">
                  {st.status === "SKIPPED"
                    ? (report.routing?.decisions.find((d) => d.agent === agent)?.justification ?? "Skipped by the orchestrator.")
                    : `No result was produced${st.error_code ? ` (${st.error_code})` : ""}.`}
                </p>
              </article>
            );
          })}
        </div>
      </Section>

      {report.critic ? (
        <Section id="sec-critic" title="Critic review">
          <p className="max-w-3xl text-sm leading-relaxed text-paper">{report.critic.summary}</p>
          {report.critic.issues.length > 0 ? (
            <ul className="mt-3 list-none space-y-2">
              {report.critic.issues.map((i, n) => (
                <li key={n} className="border-l-2 border-rule-strong pl-3 text-sm text-muted">
                  <LevelBadge level={i.severity} /> <span className="ml-2 font-mono text-[0.7rem] uppercase text-faint">{humanize(i.kind)}</span>
                  <br />
                  {i.description}
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-sm text-muted">The critic raised no issues.</p>
          )}
          <List items={report.critic.missing_risks.map((m) => `Possibly missing: ${m}`)} />
        </Section>
      ) : null}

      {report.profile ? (
        <Section id="sec-profile" title="System profile and routing">
          <p className="max-w-3xl text-sm text-muted">{report.profile.purpose_summary}</p>
          <p className="mt-2 font-mono text-xs text-faint">
            domain: {report.profile.domain} / decision impact: {report.profile.decision_impact} / autonomy:{" "}
            {humanize(report.profile.autonomy_level)}
          </p>
          {report.routing ? (
            <ul className="mt-3 list-none space-y-1 text-sm text-muted">
              {report.routing.decisions.map((d) => (
                <li key={d.agent}>
                  <span className="text-paper">{AGENT_LABEL[d.agent]}</span>: {d.run ? "ran" : "skipped"}. {d.justification}
                </li>
              ))}
              {report.routing.overrides.map((o) => (
                <li key={`o-${o.agent}`} className="text-level-medium">
                  Guardrail override for {AGENT_LABEL[o.agent]}: {o.reason}
                </li>
              ))}
            </ul>
          ) : null}
          <List items={report.profile.missing_information.map((m) => `Not stated: ${m}`)} />
        </Section>
      ) : null}

      <Section id="sec-limits" title="Limitations">
        <List items={report.limitations} />
        <p className="mt-4 max-w-3xl border border-rule bg-surface p-4 text-sm leading-relaxed text-muted">{report.disclaimer}</p>
        <p className="mt-3 font-mono text-xs text-faint">
          model {report.meta.model} / generated {new Date(report.created_at).toLocaleString("en-GB")}
        </p>
      </Section>
    </article>
  );
});

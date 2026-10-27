"use client";

import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from "react";
import { AgentNetwork } from "./AgentNetwork";
import { AuditTimeline } from "./AuditTimeline";
import { LevelBadge } from "./Badges";
import { Console, CUSTOM } from "./Console";
import { ErrorPanel } from "./ErrorPanel";
import { ReportView } from "./ReportView";
import { initialRunState, runReducer } from "@/lib/state";
import { ApiError, fetchScenarios, runAssessment } from "@/lib/stream";
import { AGENT_LABEL, type AuditEvent, type Scenario } from "@/lib/types";
import { checkDescription, cleanDescription } from "@/lib/validation";
import { humanize } from "@/lib/format";

const ANNOUNCE: Partial<Record<AuditEvent["type"], true>> = {
  AGENT_COMPLETED: true,
  AGENT_FAILED: true,
  DISAGREEMENT_DETECTED: true,
  DISAGREEMENT_RESOLVED: true,
  REASSESSMENT_TRIGGERED: true,
  CONSENSUS_COMPUTED: true,
  REPORT_GENERATED: true,
};

function Elapsed({ running }: { running: boolean }) {
  const [start] = useState(() => Date.now());
  const [now, setNow] = useState(start);
  useEffect(() => {
    if (!running) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [running]);
  return <span className="font-mono text-xs text-muted">{Math.max(0, Math.round((now - start) / 1000))} s elapsed</span>;
}

export function Assessment() {
  const [scenarios, setScenarios] = useState<Scenario[] | null>(null);
  const [scenariosError, setScenariosError] = useState(false);
  const [selectedId, setSelectedId] = useState<string>(CUSTOM);
  const [description, setDescription] = useState("");
  const [run, dispatch] = useReducer(runReducer, undefined, initialRunState);
  const [error, setError] = useState<ApiError | null>(null);
  const [announcement, setAnnouncement] = useState("");
  const [runId, setRunId] = useState(0);
  const abortRef = useRef<AbortController | null>(null);
  const networkRef = useRef<HTMLDivElement>(null);
  const reportRef = useRef<HTMLElement>(null);

  const loadScenarios = useCallback(() => {
    fetchScenarios()
      .then((list) => {
        setScenarios(list);
        setScenariosError(false);
      })
      .catch(() => setScenariosError(true));
  }, []);
  useEffect(() => {
    loadScenarios();
  }, [loadScenarios]);

  const selected = useMemo(() => scenarios?.find((s) => s.id === selectedId) ?? null, [scenarios, selectedId]);
  const edited = selected !== null && cleanDescription(description) !== cleanDescription(selected.description);

  const onSelect = (id: string) => {
    setSelectedId(id);
    const s = scenarios?.find((x) => x.id === id);
    setDescription(s ? s.description : "");
  };

  const start = useCallback(async () => {
    const text = cleanDescription(description);
    if (!checkDescription(text).ok) return;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setError(null);
    setAnnouncement("Assessment started.");
    dispatch({ type: "start" });
    setRunId((n) => n + 1);
    if (typeof window !== "undefined" && window.innerWidth < 1024) {
      networkRef.current?.scrollIntoView({ block: "start" });
    }
    try {
      const report = await runAssessment(
        text,
        selected && !edited ? selected.id : null,
        {
          onAudit: (event) => {
            dispatch({ type: "event", event });
            if (ANNOUNCE[event.type]) setAnnouncement(event.message);
          },
        },
        { signal: controller.signal },
      );
      dispatch({ type: "report", report });
      setAnnouncement(`Report ready. Status ${report.status}.`);
    } catch (e) {
      const err = e instanceof ApiError ? e : new ApiError("server", "Something went wrong. Please try again.");
      dispatch({ type: "fail" });
      if (err.kind !== "cancelled") setError(err);
      setAnnouncement(err.kind === "cancelled" ? "Assessment cancelled." : `Assessment failed: ${err.message}`);
    } finally {
      if (abortRef.current === controller) abortRef.current = null;
    }
  }, [description, selected, edited]);

  useEffect(() => () => abortRef.current?.abort(), []);

  useEffect(() => {
    if (run.report) reportRef.current?.focus({ preventScroll: false });
  }, [run.report]);

  const running = run.phase === "running";

  return (
    <section id="console" aria-labelledby="console-title" className="mx-auto max-w-6xl scroll-mt-4 px-5 pt-16 sm:px-8">
      <p className="eyebrow">Governance console</p>
      <h2 id="console-title" className="mt-2 font-display text-2xl uppercase tracking-[0.14em] sm:text-3xl">
        Run an assessment
      </h2>
      <p className="mt-3 max-w-2xl text-sm text-muted">
        Each run uses live model calls and takes roughly half a minute to a few minutes. Use fictional or anonymised descriptions only.
      </p>

      <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
        <div className="min-w-0 space-y-4 sticky-console">
          <Console
            scenarios={scenarios}
            scenariosError={scenariosError}
            onRetryScenarios={loadScenarios}
            selectedId={selectedId}
            onSelect={onSelect}
            description={description}
            onDescription={setDescription}
            running={running}
            onRun={start}
            onCancel={() => abortRef.current?.abort()}
            edited={edited}
          />
          {error ? <ErrorPanel error={error} onRetry={error.kind === "rate_limited" ? undefined : start} /> : null}
        </div>

        <div ref={networkRef} className="min-w-0 scroll-mt-4 space-y-4">
          <div className="flex items-center justify-between gap-3">
            <p className="font-mono text-xs uppercase tracking-[0.14em] text-faint">Live view</p>
            {running ? <Elapsed key={runId} running={running} /> : null}
          </div>
          <AgentNetwork run={run} />
          {run.disagreements.length > 0 ? (
            <section aria-labelledby="live-dis" className="panel border-level-medium p-4 sm:p-5">
              <h3 id="live-dis" className="section-title">
                Disagreements
              </h3>
              <ul className="mt-3 list-none space-y-2">
                {run.disagreements.map((d) => (
                  <li key={d.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
                    <LevelBadge level={d.resolved ? "LOW" : "HIGH"} prefix={d.resolved ? "resolved" : "open"} />
                    <span className="text-paper">{humanize(d.kind)}</span>
                    <span className="text-muted">{d.agents.map((a) => AGENT_LABEL[a]).join(" vs ")}</span>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
          <AuditTimeline events={run.events} />
        </div>
      </div>

      <div aria-live="polite" role="status" className="sr-only-live">
        {announcement}
      </div>

      {run.report ? <ReportView ref={reportRef} report={run.report} /> : null}
    </section>
  );
}

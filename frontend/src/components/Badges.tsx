import { STATUS_LABEL } from "@/lib/state";
import type { AgentStatus, Level } from "@/lib/types";

const LEVEL_STYLE: Record<Level, string> = {
  LOW: "border-level-low text-level-low",
  MEDIUM: "border-level-medium text-level-medium",
  HIGH: "border-level-high text-level-high",
  CRITICAL: "border-level-critical text-level-critical",
};

export function LevelBadge({ level, prefix }: { level: Level; prefix?: string }) {
  return (
    <span
      className={`inline-flex items-center border px-2 py-0.5 font-mono text-[0.7rem] uppercase tracking-[0.12em] ${LEVEL_STYLE[level]}`}
    >
      {prefix ? `${prefix} ` : ""}
      {level}
    </span>
  );
}

const STATUS_STYLE: Record<AgentStatus, { dot: string; text: string }> = {
  WAITING: { dot: "bg-faint", text: "text-faint" },
  RUNNING: { dot: "bg-eu pulse", text: "text-eu-soft" },
  REASSESSING: { dot: "bg-level-medium pulse", text: "text-level-medium" },
  COMPLETE: { dot: "bg-level-low", text: "text-level-low" },
  FAILED: { dot: "bg-level-critical", text: "text-level-critical" },
  SKIPPED: { dot: "bg-rule-strong", text: "text-muted" },
};

export function StatusTag({ status }: { status: AgentStatus }) {
  const s = STATUS_STYLE[status];
  return (
    <span className={`inline-flex items-center gap-2 font-mono text-[0.72rem] uppercase tracking-[0.12em] ${s.text}`}>
      <span aria-hidden="true" className={`inline-block h-2 w-2 rounded-full ${s.dot}`} />
      {STATUS_LABEL[status]}
    </span>
  );
}

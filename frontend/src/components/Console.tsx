"use client";

import { useId } from "react";
import { cleanDescription, checkDescription, MAX_CHARS, MIN_CHARS } from "@/lib/validation";
import type { Scenario } from "@/lib/types";

export const CUSTOM = "custom";

interface Props {
  scenarios: Scenario[] | null;
  scenariosError: boolean;
  onRetryScenarios: () => void;
  selectedId: string;
  onSelect: (id: string) => void;
  description: string;
  onDescription: (text: string) => void;
  running: boolean;
  onRun: () => void;
  onCancel: () => void;
  edited: boolean;
}

export function Console({
  scenarios,
  scenariosError,
  onRetryScenarios,
  selectedId,
  onSelect,
  description,
  onDescription,
  running,
  onRun,
  onCancel,
  edited,
}: Props) {
  const uid = useId();
  const textId = `${uid}-text`;
  const helpId = `${uid}-help`;
  const count = cleanDescription(description).length;
  const check = checkDescription(description);
  const showProblem = !check.ok && description.length > 0;
  const options: { id: string; title: string; category: string }[] = [
    ...(scenarios ?? []).map((s) => ({ id: s.id, title: s.title, category: s.category })),
    { id: CUSTOM, title: "Custom input", category: "Your own system" },
  ];

  return (
    <form
      className="panel p-4 sm:p-5"
      onSubmit={(e) => {
        e.preventDefault();
        if (check.ok && !running) onRun();
      }}
      aria-label="Assessment console"
    >
      <fieldset disabled={running} className="min-w-0">
        <legend className="section-title">Scenario</legend>
        <p className="mt-1 text-xs text-faint">Pick a demo scenario or write your own. You can edit any text before running.</p>
        {scenariosError ? (
          <div role="status" className="mt-3 border border-level-medium p-3 text-sm text-muted">
            Demo scenarios could not be loaded. You can still type a custom description.{" "}
            <button type="button" className="underline decoration-eu underline-offset-4 hover:text-white" onClick={onRetryScenarios}>
              Retry
            </button>
          </div>
        ) : null}
        {!scenarios && !scenariosError ? <p className="mt-3 text-sm text-muted">Loading scenarios...</p> : null}
        <div role="radiogroup" aria-label="Scenario" className="mt-3 grid grid-cols-1 gap-px border border-rule bg-rule sm:grid-cols-2">
          {options.map((o) => {
            const checked = selectedId === o.id;
            return (
              <label
                key={o.id}
                className={`flex cursor-pointer items-start gap-3 bg-surface p-3 transition-colors has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:-outline-offset-2 has-[:focus-visible]:outline-eu-soft ${
                  checked ? "bg-surface-2" : "hover:bg-surface-2"
                }`}
              >
                <input
                  type="radio"
                  name={`${uid}-scenario`}
                  value={o.id}
                  checked={checked}
                  onChange={() => onSelect(o.id)}
                  className="mt-1 h-4 w-4 shrink-0 accent-eu"
                />
                <span className="min-w-0">
                  <span className={`block text-sm ${checked ? "text-white" : "text-paper"}`}>{o.title}</span>
                  <span className="block font-mono text-[0.68rem] uppercase tracking-[0.1em] text-faint">{o.category}</span>
                </span>
              </label>
            );
          })}
        </div>

        <div className="mt-5 flex items-baseline justify-between gap-3">
          <label htmlFor={textId} className="section-title">
            System description
          </label>
          {edited ? <span className="font-mono text-[0.7rem] uppercase tracking-[0.1em] text-level-medium">Edited</span> : null}
        </div>
        <textarea
          id={textId}
          value={description}
          onChange={(e) => onDescription(e.target.value)}
          rows={9}
          maxLength={MAX_CHARS + 500}
          aria-describedby={helpId}
          aria-invalid={showProblem}
          spellCheck
          placeholder="Describe what the AI system does, who it affects, what data it uses, and how people are involved in decisions."
          className="mt-2 block w-full resize-y border border-rule-strong bg-ink p-3 text-sm leading-relaxed text-paper placeholder:text-faint focus:border-eu"
        />
        <div id={helpId} className="mt-2 flex flex-wrap items-start justify-between gap-x-4 gap-y-1">
          <p className={`text-xs ${showProblem ? "text-level-critical" : "text-faint"}`} role={showProblem ? "alert" : undefined}>
            {showProblem && !check.ok
              ? check.message
              : `Between ${MIN_CHARS} and ${MAX_CHARS} characters. Do not include personal data or secrets.`}
          </p>
          <p className={`font-mono text-xs ${count > MAX_CHARS ? "text-level-critical" : "text-muted"}`} aria-label={`${count} of ${MAX_CHARS} characters`}>
            {count} / {MAX_CHARS}
          </p>
        </div>
      </fieldset>

      <div className="mt-5 flex flex-wrap items-center gap-3">
        <button type="submit" className="btn-primary" disabled={running || !check.ok}>
          {running ? "Assessment running" : "Run assessment"}
        </button>
        {running ? (
          <button type="button" className="btn-ghost" onClick={onCancel}>
            Cancel
          </button>
        ) : null}
      </div>
    </form>
  );
}

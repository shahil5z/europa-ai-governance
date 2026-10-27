import type { Level } from "./types";

export const pct = (v: number | null | undefined): string => (v == null ? "n/a" : `${Math.round(v * 100)}%`);

export function seconds(ms: number | null | undefined): string {
  if (ms == null) return "";
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`;
}

export function clockTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString("en-GB", { hour12: false });
}

export const LEVELS: Level[] = ["LOW", "MEDIUM", "HIGH", "CRITICAL"];

export const humanize = (s: string): string =>
  s
    .toLowerCase()
    .split("_")
    .map((w, i) => (i === 0 ? w.charAt(0).toUpperCase() + w.slice(1) : w))
    .join(" ");

export const LEVEL_TEXT: Record<Level, string> = {
  LOW: "text-level-low",
  MEDIUM: "text-level-medium",
  HIGH: "text-level-high",
  CRITICAL: "text-level-critical",
};

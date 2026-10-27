import { ApiError, type ApiErrorKind } from "@/lib/stream";

const TITLES: Record<ApiErrorKind, string> = {
  validation: "The description needs attention",
  rate_limited: "Rate limit reached",
  busy: "The service is busy",
  not_configured: "Service not configured",
  too_large: "Request too large",
  timeout: "The assessment timed out",
  stalled: "The connection stopped responding",
  network: "Network problem",
  server: "The service reported an error",
  interrupted: "The connection was interrupted",
  report_lost: "The report did not arrive",
  cancelled: "Assessment cancelled",
};

const RETRYABLE: ApiErrorKind[] = ["timeout", "stalled", "network", "server", "interrupted", "report_lost", "busy"];

export function ErrorPanel({ error, onRetry }: { error: ApiError; onRetry?: () => void }) {
  return (
    <div role="alert" className="border border-level-critical bg-surface p-4 sm:p-5">
      <p className="eyebrow !text-level-critical">Error</p>
      <h3 className="mt-1 font-display text-lg uppercase tracking-[0.1em]">{TITLES[error.kind]}</h3>
      <p className="mt-2 text-sm text-muted">{error.message}</p>
      {error.kind === "rate_limited" && error.retryAfter ? (
        <p className="mt-2 font-mono text-xs text-level-medium">
          Try again in about {Math.max(1, Math.ceil(error.retryAfter / 60))} minute(s).
        </p>
      ) : null}
      {onRetry && RETRYABLE.includes(error.kind) ? (
        <button type="button" onClick={onRetry} className="btn-ghost mt-4">
          Try again
        </button>
      ) : null}
    </div>
  );
}

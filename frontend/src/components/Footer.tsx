import { DISCLAIMER } from "@/lib/types";

export function Footer() {
  return (
    <footer className="rule-top mt-24 bg-ink">
      <div className="mx-auto flex max-w-6xl flex-col gap-4 px-5 py-10 sm:px-8">
        <p className="max-w-3xl text-sm leading-relaxed text-muted">{DISCLAIMER}</p>
        <div className="flex items-center justify-between gap-4 border-t border-rule pt-4 font-mono text-xs tracking-wider text-faint">
          <p className="min-w-0">
            <span className="font-display tracking-[0.18em] text-paper">EUROPA AI GOVERNANCE</span>
            <span className="mx-2" aria-hidden="true">
              /
            </span>
            Portfolio project by Shahil
          </p>
          <a
            href="https://github.com/shahil5z/europa-ai-governance"
            target="_blank"
            rel="noopener noreferrer"
            aria-label="View source on GitHub"
            className="-mr-2 inline-flex h-11 w-11 shrink-0 items-center justify-center text-muted transition-colors hover:text-paper focus-visible:text-paper active:text-eu-soft"
          >
            <svg viewBox="0 0 16 16" width="22" height="22" fill="currentColor" aria-hidden="true" focusable="false">
              <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82A7.6 7.6 0 0 1 8 4.58c.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8Z" />
            </svg>
          </a>
        </div>
      </div>
    </footer>
  );
}

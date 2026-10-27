import { DISCLAIMER } from "@/lib/types";

export function Footer() {
  return (
    <footer className="rule-top mt-24 bg-ink">
      <div className="mx-auto flex max-w-6xl flex-col gap-4 px-5 py-10 sm:px-8">
        <p className="max-w-3xl text-sm leading-relaxed text-muted">{DISCLAIMER}</p>
        <div className="flex flex-col gap-2 border-t border-rule pt-4 font-mono text-xs tracking-wider text-faint sm:flex-row sm:items-center sm:justify-between">
          <p>
            <span className="font-display tracking-[0.18em] text-paper">EUROPA AI GOVERNANCE</span>
            <span className="mx-2" aria-hidden="true">
              /
            </span>
            Portfolio project by Shahil
          </p>
          <p>Demonstration software. Results are AI generated and unverified.</p>
        </div>
      </div>
    </footer>
  );
}

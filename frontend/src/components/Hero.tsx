import Image from "next/image";

export function Hero() {
  return (
    <section aria-labelledby="hero-title" className="relative border-b border-rule">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-eu to-transparent opacity-60"
      />
      <div className="mx-auto flex max-w-4xl flex-col items-center px-5 pb-20 pt-10 text-center sm:px-8 sm:pt-14">
        <Image
          src="/logo.png"
          alt="EUROPA AI Governance logo: a classical column forming the letter E beneath an arc of EU stars"
          width={720}
          height={720}
          priority
          sizes="(max-width: 640px) 70vw, 340px"
          className="h-auto w-[min(70vw,340px)]"
        />
        <h1
          id="hero-title"
          className="mt-2 font-display text-[1.65rem] font-medium uppercase leading-tight tracking-[0.14em] sm:text-4xl sm:tracking-[0.2em]"
        >
          EUROPA AI GOVERNANCE
        </h1>
        <p className="mt-4 font-mono text-[0.72rem] uppercase tracking-[0.16em] text-eu-soft sm:text-xs">
          Multi-Agent AI Governance &amp; Risk Intelligence Platform
        </p>
        <p className="mt-6 max-w-2xl text-base leading-relaxed text-muted sm:text-lg">
          Describe an AI system. Specialist agents assess risk, data, security, oversight and EU
          regulatory concepts in parallel, a critic audits their work, and every disagreement stays on the record.
        </p>
        <a href="#console" className="btn-primary mt-10">
          Start assessment
        </a>
        <dl className="mt-14 grid w-full max-w-2xl grid-cols-1 gap-px border border-rule bg-rule text-left sm:grid-cols-3">
          {[
            ["Parallel specialists", "Five domain agents run at the same time"],
            ["Deterministic consensus", "Weights and floors you can read, not a vote by prompt"],
            ["Auditable", "Every step is logged and streamed as it happens"],
          ].map(([t, d]) => (
            <div key={t} className="bg-ink p-4">
              <dt className="font-mono text-[0.7rem] uppercase tracking-[0.14em] text-paper">{t}</dt>
              <dd className="mt-1 text-sm text-muted">{d}</dd>
            </div>
          ))}
        </dl>
      </div>
    </section>
  );
}

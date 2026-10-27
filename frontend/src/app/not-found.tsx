import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = { title: "Page not found" };

export default function NotFound() {
  return (
    <main id="main" className="mx-auto flex max-w-2xl flex-col items-center px-6 py-32 text-center">
      <p className="eyebrow">Error 404</p>
      <h1 className="mt-4 font-display text-3xl tracking-[0.12em] uppercase">Page not found</h1>
      <p className="mt-4 text-muted">The page you requested does not exist in this console.</p>
      <Link href="/" className="btn-primary mt-8">
        Return to console
      </Link>
    </main>
  );
}

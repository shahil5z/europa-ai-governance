import type { Metadata, Viewport } from "next";
import { Cinzel, IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";
import { Footer } from "@/components/Footer";
import "./globals.css";

const cinzel = Cinzel({ subsets: ["latin"], variable: "--font-cinzel", display: "swap" });
const plexSans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-plex-sans",
  display: "swap",
});
const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-plex-mono",
  display: "swap",
});

const DESCRIPTION =
  "Multi-agent AI governance and risk intelligence. Specialist agents assess an AI system in parallel, a critic audits them, and disagreements are surfaced rather than hidden. Informational only, not legal advice.";

export const metadata: Metadata = {
  title: { default: "EUROPA AI GOVERNANCE", template: "%s | EUROPA AI GOVERNANCE" },
  description: DESCRIPTION,
  applicationName: "EUROPA AI GOVERNANCE",
  authors: [{ name: "Shahil" }],
  openGraph: { type: "website", siteName: "EUROPA AI GOVERNANCE", title: "EUROPA AI GOVERNANCE", description: DESCRIPTION },
  twitter: { card: "summary", title: "EUROPA AI GOVERNANCE", description: DESCRIPTION },
  robots: { index: true, follow: true },
};

export const viewport: Viewport = { themeColor: "#000000", colorScheme: "dark" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${cinzel.variable} ${plexSans.variable} ${plexMono.variable}`}>
      <body className="flex min-h-dvh flex-col">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-50 focus:bg-eu-deep focus:px-4 focus:py-2 focus:text-white"
        >
          Skip to content
        </a>
        <div className="flex-1">{children}</div>
        <Footer />
      </body>
    </html>
  );
}

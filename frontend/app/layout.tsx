import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Agent Commerce Readiness Lab",
  description:
    "Compile messy catalogs into machine-readable commerce, score agent-readiness, simulate an AI buyer, and prove transactability.",
};

const NAV = [
  { href: "/", label: "Dashboard" },
  { href: "/buyer", label: "AI Buyer Lab" },
  { href: "/evaluation", label: "Evaluation Lab" },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="border-b border-slate-200 bg-white">
          <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
            <Link href="/" className="text-lg font-semibold tracking-tight">
              Agent Commerce <span className="text-indigo-600">Readiness Lab</span>
            </Link>
            <nav className="flex gap-1">
              {NAV.map((n) => (
                <Link
                  key={n.href}
                  href={n.href}
                  className="rounded-md px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                >
                  {n.label}
                </Link>
              ))}
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-6 py-8">{children}</main>
        <footer className="mx-auto max-w-6xl px-6 pb-10 pt-4 text-xs text-slate-400">
          LLM never touches transactional facts · prices from the DB only · amounts in subunits
        </footer>
      </body>
    </html>
  );
}

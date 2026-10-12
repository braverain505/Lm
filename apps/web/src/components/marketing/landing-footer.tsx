import { ArrowUpRight } from "lucide-react";
import Image from "next/image";
import Link from "next/link";

import { FlintwireCredit } from "@/components/flintwire-credit";

/**
 * Every link here resolves to a real destination: a section on this page, a
 * route in the app, or the Flintwire site. A marketing footer full of dead
 * links is the fastest way to make a product feel unfinished.
 */
const COLUMNS: { title: string; links: { label: string; href: string }[] }[] = [
  {
    title: "Platform",
    links: [
      { label: "One platform", href: "#platform" },
      { label: "Features", href: "#features" },
      { label: "Results & report cards", href: "#results" },
      { label: "AI tools", href: "#ai" },
      { label: "How it works", href: "#how" },
    ],
  },
  {
    title: "Get started",
    links: [
      { label: "Create a workspace", href: "/register" },
      { label: "Sign in", href: "/login" },
      { label: "Check a result", href: "/check-result" },
      { label: "Reset password", href: "/reset-password" },
    ],
  },
  {
    title: "Questions",
    links: [
      { label: "FAQ", href: "#faq" },
      { label: "Data isolation", href: "#faq" },
      { label: "Access control", href: "#faq" },
      { label: "AI features", href: "#ai" },
    ],
  },
];

export function LandingFooter() {
  return (
    <footer className="border-t border-border/70 bg-muted/25">
      <div className="mx-auto w-full max-w-6xl px-4 py-14 sm:px-6">
        <div className="grid gap-10 lg:grid-cols-[1.4fr_1fr_1fr_1fr]">
          <div>
            <Link href="/" aria-label="Clearis home" className="inline-flex">
              <Image
                src="/clearisbg.png"
                alt="Clearis"
                width={1536}
                height={1024}
                className="h-9 w-auto object-contain"
              />
            </Link>
            <p className="mt-4 max-w-xs text-[13px] leading-relaxed text-muted-foreground">
              Clearis is the school management platform that keeps a term&apos;s
              records in one place — students, staff, results, fees and the AI
              that reads them back to you.
            </p>
            <a
              href="https://flintwire.com"
              target="_blank"
              rel="noreferrer noopener"
              className="mt-4 inline-flex items-center gap-1 text-[12.5px] font-semibold text-foreground transition-colors hover:text-primary"
            >
              Flintwire Technologies
              <ArrowUpRight className="h-3.5 w-3.5" />
            </a>
          </div>

          {COLUMNS.map((column) => (
            <div key={column.title}>
              <p className="text-[11px] font-bold uppercase tracking-[0.14em] text-foreground">
                {column.title}
              </p>
              <ul className="mt-4 space-y-2.5">
                {column.links.map((link) => (
                  <li key={`${column.title}-${link.label}`}>
                    <Link
                      href={link.href}
                      className="text-[13px] text-muted-foreground transition-colors hover:text-foreground"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-12 flex flex-col items-center justify-between gap-4 border-t border-border/70 pt-6 sm:flex-row">
          <p className="text-[12px] text-muted-foreground/85">
            © {new Date().getFullYear()} Clearis. School management, results and
            reporting.
          </p>
          <FlintwireCredit className="text-left sm:text-right" />
        </div>
      </div>
    </footer>
  );
}

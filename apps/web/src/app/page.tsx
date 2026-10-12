import type { Metadata } from "next";

import { LandingBody } from "@/components/marketing/landing-body";
import { LandingFooter } from "@/components/marketing/landing-footer";
import { LandingHeader } from "@/components/marketing/landing-header";
import { LandingHero } from "@/components/marketing/landing-hero";

/**
 * The marketing front door.
 *
 * Everything under this page is served from the same app as the product, so the
 * one thing a visitor arrives to do — sign in, or start a school workspace —
 * happens without a hop to another domain. Both routes are one click from here
 * and from every section's call to action.
 */
export const metadata: Metadata = {
  title: "Clearis — Run your school from one clear platform",
  description:
    "Admissions, results, report cards, fees, attendance, timetables, staff, inventory and an AI copilot grounded in your school's own records — one platform instead of six spreadsheets.",
  alternates: { canonical: "/" },
};

/** Structured data, so search engines read the product the way we describe it. */
const softwareJsonLd = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  name: "Clearis",
  applicationCategory: "BusinessApplication",
  operatingSystem: "Web",
  description:
    "Multi-tenant school management platform for student records, results and report cards, fees and billing, attendance, timetables, payroll and AI tools.",
  url: "https://clearis.site",
  offers: {
    "@type": "Offer",
    category: "SaaS",
  },
};

export default function HomePage() {
  return (
    <div className="min-h-screen bg-background">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-[60] focus:rounded-lg focus:bg-card focus:px-4 focus:py-2 focus:text-[13px] focus:font-semibold focus:text-foreground focus:shadow-pop"
      >
        Skip to content
      </a>

      <LandingHeader />

      <main id="main">
        <LandingHero />
        <LandingBody />
      </main>

      <LandingFooter />

      <script
        type="application/ld+json"
        // eslint-disable-next-line react/no-danger -- static, author-controlled JSON-LD
        dangerouslySetInnerHTML={{ __html: JSON.stringify(softwareJsonLd) }}
      />
    </div>
  );
}

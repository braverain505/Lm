"use client";

import { motion } from "framer-motion";
import { ArrowRight, BadgeCheck, Download, Sparkles } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { APP_DOWNLOAD_NAME, APP_DOWNLOAD_URL } from "@/lib/app-download";

import { AuroraBackdrop, EASE, Reveal } from "./landing-shared";
import { LandingProductSlider } from "./landing-product-slider";

const PROMISES = ["Set up in minutes", "Nothing to install", "Roles from day one"];

export function LandingHero() {
  return (
    <section className="mk-hero-wash relative isolate overflow-hidden pb-20 pt-16 sm:pb-28 sm:pt-24">
      <AuroraBackdrop />

      <div className="relative mx-auto w-full max-w-6xl px-4 sm:px-6">
        <div className="mx-auto max-w-4xl text-center">
          <Reveal>
            <span className="inline-flex items-center gap-2 rounded-full bg-primary/10 px-4 py-2 text-[11.5px] font-bold uppercase tracking-[0.1em] text-primary">
              <Sparkles className="h-3.5 w-3.5" />
              One platform for the whole school
            </span>
          </Reveal>

          <Reveal delay={0.05}>
            <h1 className="mt-7 text-[38px] font-extrabold leading-[1.02] tracking-[-0.035em] text-foreground sm:text-[56px] lg:text-[68px]">
              Run your school from{" "}
              <span className="relative z-0 text-primary mk-swash">one clear platform</span>.
            </h1>
          </Reveal>

          <Reveal delay={0.1}>
            <p className="mx-auto mt-6 max-w-2xl text-[16px] leading-relaxed text-muted-foreground sm:text-[18.5px]">
              Admissions, results, report cards, fees, attendance, timetables,
              staff and your own AI copilot — one system of record instead of six
              spreadsheets and a group chat.
            </p>
          </Reveal>

          <Reveal delay={0.15}>
            <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
              <Button
                asChild
                className="mk-pill h-[52px] w-full px-7 text-[15px] font-bold shadow-lg shadow-primary/25 sm:w-auto"
              >
                <Link href="/register">
                  Get started free
                  <ArrowRight className="ml-1.5 h-4 w-4" />
                </Link>
              </Button>
              <Button
                asChild
                variant="outline"
                className="mk-pill h-[52px] w-full border-border bg-card px-7 text-[15px] font-semibold sm:w-auto"
              >
                <Link href="/login">Sign in</Link>
              </Button>
              <Button
                asChild
                variant="outline"
                className="mk-pill h-[52px] w-full border-transparent bg-[hsl(var(--mk-yellow))]/[0.16] px-7 text-[15px] font-semibold text-[hsl(35_86%_30%)] hover:bg-[hsl(var(--mk-yellow))]/25 hover:text-[hsl(35_86%_24%)] sm:w-auto"
              >
                <a href={APP_DOWNLOAD_URL} download={APP_DOWNLOAD_NAME}>
                  <Download className="mr-1.5 h-4 w-4" />
                  Download the app
                </a>
              </Button>
            </div>
          </Reveal>

          <Reveal delay={0.2}>
            <div className="mt-8 flex flex-wrap items-center justify-center gap-2.5">
              {PROMISES.map((promise) => (
                <span
                  key={promise}
                  className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3.5 py-1.5 text-[12.5px] font-medium text-foreground/80"
                >
                  <BadgeCheck className="h-3.5 w-3.5 text-[hsl(var(--mk-green))]" />
                  {promise}
                </span>
              ))}
            </div>
          </Reveal>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 28 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, ease: EASE, delay: 0.2 }}
          className="mx-auto mt-14 max-w-5xl sm:mt-16"
        >
          <div className="mk-lift-lg rounded-[28px] border border-border/80 bg-card p-2 sm:p-3">
            <div className="overflow-hidden rounded-[22px] border border-border/60 bg-background">
              <LandingProductSlider />
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}

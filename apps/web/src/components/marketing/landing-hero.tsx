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
    <section className="relative isolate overflow-hidden pb-16 pt-14 sm:pb-24 sm:pt-20">
      <AuroraBackdrop />

      <div className="relative mx-auto w-full max-w-6xl px-4 sm:px-6">
        <div className="mx-auto max-w-3xl text-center">
          <Reveal>
            <span className="inline-flex items-center gap-2 rounded-full border border-border/70 bg-card/70 px-3.5 py-1.5 text-[11.5px] font-semibold text-muted-foreground backdrop-blur">
              <Sparkles className="h-3.5 w-3.5 text-primary" />
              One platform for the whole school
            </span>
          </Reveal>

          <Reveal delay={0.05}>
            <h1 className="mt-6 text-[34px] font-bold leading-[1.08] tracking-tight text-foreground sm:text-[48px] lg:text-[58px]">
              Run your school from{" "}
              <span className="bg-gradient-to-br from-primary via-primary to-chart-5 bg-clip-text text-transparent">
                one clear platform
              </span>
              .
            </h1>
          </Reveal>

          <Reveal delay={0.1}>
            <p className="mx-auto mt-5 max-w-2xl text-[15px] leading-relaxed text-muted-foreground sm:text-[17px]">
              Admissions, results, report cards, fees, attendance, timetables,
              staff and your own AI copilot — one system of record instead of six
              spreadsheets and a group chat.
            </p>
          </Reveal>

          <Reveal delay={0.15}>
            <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
              <Button
                asChild
                className="h-12 w-full px-6 text-[14.5px] font-semibold shadow-md shadow-primary/25 sm:w-auto"
              >
                <Link href="/register">
                  Get started free
                  <ArrowRight className="ml-1.5 h-4 w-4" />
                </Link>
              </Button>
              <Button
                asChild
                variant="outline"
                className="h-12 w-full border-border/80 px-6 text-[14.5px] sm:w-auto"
              >
                <Link href="/login">Sign in</Link>
              </Button>
              <Button
                asChild
                variant="outline"
                className="h-12 w-full border-primary/40 bg-primary/[0.07] px-6 text-[14.5px] text-primary hover:bg-primary/12 hover:text-primary sm:w-auto"
              >
                <a href={APP_DOWNLOAD_URL} download={APP_DOWNLOAD_NAME}>
                  <Download className="mr-1.5 h-4 w-4" />
                  Download the app
                </a>
              </Button>
            </div>
          </Reveal>

          <Reveal delay={0.2}>
            <div className="mt-7 flex flex-wrap items-center justify-center gap-x-5 gap-y-2">
              {PROMISES.map((promise) => (
                <span
                  key={promise}
                  className="inline-flex items-center gap-1.5 text-[12.5px] text-muted-foreground/90"
                >
                  <BadgeCheck className="h-3.5 w-3.5 text-success" />
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
          <LandingProductSlider />
        </motion.div>
      </div>
    </section>
  );
}

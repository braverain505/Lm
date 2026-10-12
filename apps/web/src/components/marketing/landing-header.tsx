"use client";

import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, LayoutDashboard, Menu, X } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";

import { ThemeSwitch } from "@/components/theme-switch";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/providers/auth-provider";
import { cn } from "@/lib/utils";

import { EASE } from "./landing-shared";

const LINKS = [
  { href: "#platform", label: "Platform" },
  { href: "#features", label: "Features" },
  { href: "#results", label: "Results" },
  { href: "#ai", label: "AI" },
  { href: "#faq", label: "FAQ" },
];

/**
 * The marketing header.
 *
 * It carries the one decision every visitor arrives with — "am I signing in or
 * starting fresh?" — so the two routes are always visible: Sign in to the app,
 * or Get started into the school registration flow. Someone already holding a
 * session gets the dashboard link instead of being asked to sign in again.
 */
export function LandingHeader() {
  const { user, loading } = useAuth();
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 12);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // Never leave the mobile panel hanging over the page after a resize.
  useEffect(() => {
    const onResize = () => {
      if (window.innerWidth >= 1024) setOpen(false);
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const signedIn = !loading && Boolean(user);

  return (
    <header
      className={cn(
        "sticky top-0 z-50 w-full transition-colors duration-200",
        scrolled
          ? "border-b border-border/70 bg-background/80 backdrop-blur-xl"
          : "border-b border-transparent bg-transparent",
      )}
    >
      <div className="mx-auto flex h-16 w-full max-w-6xl items-center gap-3 px-4 sm:px-6">
        <Link
          href="/"
          className="flex shrink-0 items-center gap-2 rounded-lg py-1"
          aria-label="Clearis home"
        >
          <Image
            src="/clearisbg.png"
            alt="Clearis"
            width={1536}
            height={1024}
            priority
            className="h-9 w-auto object-contain"
          />
        </Link>

        <nav
          aria-label="Sections"
          className="ml-4 hidden items-center gap-0.5 lg:flex"
        >
          {LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="rounded-lg px-3 py-2 text-[13px] font-medium text-muted-foreground transition-colors hover:bg-muted/60 hover:text-foreground"
            >
              {link.label}
            </a>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-2">
          <div className="hidden sm:block">
            <ThemeSwitch />
          </div>

          {signedIn ? (
            <Button asChild size="sm" className="h-9 px-4">
              <Link href="/dashboard">
                <LayoutDashboard className="mr-1.5 h-3.5 w-3.5" />
                Dashboard
              </Link>
            </Button>
          ) : (
            <>
              <Button
                asChild
                variant="ghost"
                size="sm"
                className="hidden h-9 px-3 text-muted-foreground hover:text-foreground sm:inline-flex"
              >
                <Link href="/login">Sign in</Link>
              </Button>
              <Button asChild size="sm" className="h-9 px-4 shadow-sm shadow-primary/20">
                <Link href="/register">
                  Get started
                  <ArrowRight className="ml-1 h-3.5 w-3.5" />
                </Link>
              </Button>
            </>
          )}

          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            aria-label={open ? "Close menu" : "Open menu"}
            className="flex h-9 w-9 items-center justify-center rounded-lg border border-border/70 text-foreground transition-colors hover:bg-muted/60 lg:hidden"
          >
            {open ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
          </button>
        </div>
      </div>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.22, ease: EASE }}
            className="overflow-hidden border-b border-border/70 bg-background/95 backdrop-blur-xl lg:hidden"
          >
            <div className="mx-auto max-w-6xl px-4 pb-5 pt-2 sm:px-6">
              <nav aria-label="Sections" className="grid gap-0.5">
                {LINKS.map((link) => (
                  <a
                    key={link.href}
                    href={link.href}
                    onClick={() => setOpen(false)}
                    className="rounded-lg px-3 py-2.5 text-[14px] font-medium text-muted-foreground transition-colors hover:bg-muted/60 hover:text-foreground"
                  >
                    {link.label}
                  </a>
                ))}
              </nav>

              <div className="mt-4 flex items-center justify-between gap-3 border-t border-border/70 pt-4">
                <ThemeSwitch />
                {!signedIn && (
                  <Link
                    href="/login"
                    className="text-[13px] font-semibold text-primary hover:text-primary/90"
                  >
                    Sign in
                  </Link>
                )}
              </div>

              {!signedIn && (
                <Button asChild className="mt-4 h-11 w-full text-[14px]">
                  <Link href="/register" onClick={() => setOpen(false)}>
                    Get started free
                    <ArrowRight className="ml-1.5 h-4 w-4" />
                  </Link>
                </Button>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}

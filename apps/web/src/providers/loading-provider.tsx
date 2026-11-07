"use client";

import { useIsFetching, useIsMutating } from "@tanstack/react-query";
import { ReactNode, useEffect, useState } from "react";

import { LoadingScreen } from "@/components/loading-screen";

// Wait a beat before covering the screen, so an instant cache hit or a fast
// save does not flash a spinner. Everything that takes longer shows one.
const SHOW_DELAY = 250; // ms
const SAFETY_TIMEOUT = 8000; // never hold someone behind a spinner for longer

/**
 * One spinner for every loading activity in the product.
 *
 * React Query knows about both directions of work: `useIsFetching` covers every
 * read (page data, refetches after a save) and `useIsMutating` covers every
 * write (saving a change, changing a result's status, publishing). Watching
 * both means a save shows the same spinner as a page load — no call site has to
 * remember to opt in.
 */
export function LoadingProvider({ children }: { children: ReactNode }) {
  const fetching = useIsFetching();
  const mutating = useIsMutating();
  const busy = fetching + mutating > 0;
  const [showSpinner, setShowSpinner] = useState(false);

  useEffect(() => {
    if (!busy) {
      setShowSpinner(false);
      return;
    }
    const delay = setTimeout(() => setShowSpinner(true), SHOW_DELAY);
    return () => clearTimeout(delay);
  }, [busy]);

  // Safety valve: if a request hangs, the app must not stay covered forever.
  useEffect(() => {
    if (!showSpinner) return;
    const timeout = setTimeout(() => setShowSpinner(false), SAFETY_TIMEOUT);
    return () => clearTimeout(timeout);
  }, [showSpinner]);

  return (
    <>
      <LoadingScreen isLoading={showSpinner} />
      {children}
    </>
  );
}

// Kept for call sites that manage a local loading flag by hand.
export function useLoading() {
  const [isLoading, setIsLoading] = useState(false);

  const startLoading = () => setIsLoading(true);
  const stopLoading = () => setIsLoading(false);

  return { isLoading, startLoading, stopLoading };
}
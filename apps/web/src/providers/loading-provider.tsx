"use client";

import { useIsFetching } from "@tanstack/react-query";
import { ReactNode, useEffect, useRef, useState } from "react";

import { LoadingScreen } from "@/components/loading-screen";
import { ProcessingBar } from "@/components/processing-indicator";

// Show the branded splash only for the first batch of requests after a page
// load; everything after that is background work and gets the thin top bar.
const SPLASH_DELAY = 300; // ms
const SPLASH_TIMEOUT = 8000; // never hold someone hostage to a slow boot

export function LoadingProvider({ children }: { children: ReactNode }) {
  const isFetching = useIsFetching();
  const booted = useRef(false);
  const [bootFinished, setBootFinished] = useState(false);
  const [showSplash, setShowSplash] = useState(false);

  useEffect(() => {
    if (bootFinished) return;

    if (isFetching > 0) {
      booted.current = true;
      const delay = setTimeout(() => setShowSplash(true), SPLASH_DELAY);
      const safety = setTimeout(() => setShowSplash(false), SPLASH_TIMEOUT);
      return () => {
        clearTimeout(delay);
        clearTimeout(safety);
      };
    }

    // The first burst of requests has settled.
    if (booted.current) {
      setShowSplash(false);
      setBootFinished(true);
    }
  }, [isFetching, bootFinished]);

  return (
    <>
      <ProcessingBar />
      {showSplash && !bootFinished && <LoadingScreen />}
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
"use client";

import { ReactNode, useState, useEffect } from "react";
import { useIsFetching } from "@tanstack/react-query";
import { LoadingScreen } from "@/components/loading-screen";

interface LoadingProviderProps {
  children: ReactNode;
}

// Delay to show loading screen only for meaningful loads (not instantaneous fetches)
const MIN_LOADING_DELAY = 300; // ms
const GLOBAL_LOADING_TIMEOUT = 5000; // Maximum time to show loading screen

export function LoadingProvider({ children }: LoadingProviderProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [showLoadingScreen, setShowLoadingScreen] = useState(false);
  const [loadingTimeoutId, setLoadingTimeoutId] = useState<NodeJS.Timeout | null>(null);

  // Use React Query's global fetching state
  const isFetching = useIsFetching();

  useEffect(() => {
    // Clear any existing timeout
    if (loadingTimeoutId) {
      clearTimeout(loadingTimeoutId);
    }

    if (isFetching > 0) {
      // Start loading
      setIsLoading(true);

      // Show loading screen after a short delay to avoid flash for quick loads
      const timeout = setTimeout(() => {
        setShowLoadingScreen(true);
      }, MIN_LOADING_DELAY);

      setLoadingTimeoutId(timeout);

      // Safety timeout - hide loading screen after max duration
      const safetyTimeout = setTimeout(() => {
        setShowLoadingScreen(false);
        setIsLoading(false);
      }, GLOBAL_LOADING_TIMEOUT);

      setLoadingTimeoutId(prev => {
        if (prev) clearTimeout(prev);
        return safetyTimeout;
      });
    } else {
      // Stop loading
      setIsLoading(false);
      setShowLoadingScreen(false);
      setLoadingTimeoutId(null);
    }

    return () => {
      if (loadingTimeoutId) {
        clearTimeout(loadingTimeoutId);
      }
    };
  }, [isFetching]);

  return (
    <>
      {showLoadingScreen && <LoadingScreen />}
      {children}
    </>
  );
}

// Hook to manually control loading state (for non-query loads)
export function useLoading() {
  const [isLoading, setIsLoading] = useState(false);

  const startLoading = () => {
    setIsLoading(true);
  };

  const stopLoading = () => {
    setIsLoading(false);
  };

  return {
    isLoading,
    startLoading,
    stopLoading,
  };
}
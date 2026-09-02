"use client";

import { ReactNode } from "react";

import { AuthProvider } from "./auth-provider";
import { QueryProvider } from "./query-provider";
import { ThemeProvider } from "./theme-provider";
import { LoadingProvider } from "./loading-provider";
import { ToastProvider } from "@/components/toast";

export function Providers({ children }: { children: ReactNode }) {
  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
      <QueryProvider>
        <AuthProvider>
          <LoadingProvider>
            <ToastProvider>{children}</ToastProvider>
          </LoadingProvider>
        </AuthProvider>
      </QueryProvider>
    </ThemeProvider>
  );
}
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

const CURRENCY_SYMBOLS: Record<string, string> = {
  NGN: "₦",
  USD: "$",
  GBP: "£",
  EUR: "€",
};

/**
 * Format money for the finance/accounting screens.
 *
 * Centralised so a receipt, a cashbook line and a report never disagree about
 * how the same amount looks.
 */
export function formatMoney(
  amount: number | null | undefined,
  currency = "NGN",
  opts: { decimals?: boolean } = {},
): string {
  const symbol = CURRENCY_SYMBOLS[(currency || "NGN").toUpperCase()] ?? "";
  const value = Number(amount ?? 0);
  const decimals = opts.decimals ?? false;
  const formatted = value.toLocaleString(undefined, {
    minimumFractionDigits: decimals ? 2 : 0,
    maximumFractionDigits: decimals ? 2 : 0,
  });
  return `${symbol}${formatted}`;
}

/** ISO date (YYYY-MM-DD) for today, in the browser's own timezone. */
export function todayIso(): string {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60000;
  return new Date(now.getTime() - offset).toISOString().slice(0, 10);
}
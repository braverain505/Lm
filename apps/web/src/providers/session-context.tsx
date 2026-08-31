"use client";

import type { AcademicSession, Term } from "@schoolos/shared";
import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { useAuth } from "@/providers/auth-provider";
import { useSessions, useTerms } from "@/hooks/use-api";

interface SessionTermState {
  sessions: AcademicSession[];
  terms: Term[];
  session: AcademicSession | null;
  term: Term | null;
  loadingTerms: boolean;
  setSession: (session: AcademicSession) => void;
  setTerm: (term: Term) => void;
  /** True when the active term is closed (no mutations allowed). */
  isTermClosed: boolean;
  /** Confirm before switching away from an open term. Returns true if user confirmed. */
  confirmTermSwitch: (nextTerm: Term) => boolean;
}

const SessionTermContext = createContext<SessionTermState | null>(null);

const STORAGE_KEY = "schoolos.active-term";

export function SessionTermProvider({ children }: { children: ReactNode }) {
  const { activeSchool } = useAuth();
  const schoolId = activeSchool?.school_id;
  const { data: sessions = [] } = useSessions();
  const [sessionId, setSessionId] = useState<string | null>(null);

  // Resolve the active session: explicit selection, else the school's current
  // session, else the most recent one.
  const session = useMemo(() => {
    if (!sessions.length) return null;
    const saved = sessionId ? sessions.find((s) => s.id === sessionId) : null;
    return saved ?? sessions.find((s) => s.is_current) ?? sessions[sessions.length - 1] ?? null;
  }, [sessions, sessionId]);

  const { data: terms = [], isLoading: loadingTerms } = useTerms(session?.id ?? null);

  const [termId, setTermId] = useState<string | null>(null);

  // Restore a persisted term selection for this school, else fall back to the
  // session's current term (or its first term).
  useEffect(() => {
    if (!schoolId || !terms.length) return;
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "null") as {
        school: string;
        term_id: string;
      } | null;
      if (saved && saved.school === schoolId && terms.some((t) => t.id === saved.term_id)) {
        setTermId(saved.term_id);
        return;
      }
    } catch {
      /* ignore */
    }
    setTermId(terms.find((t) => t.is_current)?.id ?? terms[0]?.id ?? null);
  }, [schoolId, session?.id, terms.length]); // eslint-disable-line react-hooks/exhaustive-deps

  const term = useMemo(() => terms.find((t) => t.id === termId) ?? null, [terms, termId]);

  const isTermClosed = useMemo(
    () => term?.status === "closed",
    [term?.status],
  );

  /** Warn the user when switching from an open term with unsaved work. */
  const confirmTermSwitch = useCallback(
    (nextTerm: Term): boolean => {
      if (!term) return true;
      // If the current term is closed, always allow switching (read-only).
      if (term.status === "closed") return true;
      // If switching to the same term, no-op.
      if (nextTerm.id === term.id) return true;
      // If switching to a closed term, allow (viewing historical data).
      if (nextTerm.status === "closed") return true;
      // Switching between open terms — warn about potential unsaved changes.
      return window.confirm(
        `You are about to switch from ${term.name} to ${nextTerm.name}. ` +
        `Any unsaved score entries will be lost. Continue?`,
      );
    },
    [term],
  );

  const value = useMemo<SessionTermState>(() => {
    const setSession = (next: AcademicSession) => {
      setSessionId(next.id);
      setTermId(null);
    };
    const setTerm = (next: Term) => {
      setTermId(next.id);
      if (schoolId) {
        try {
          localStorage.setItem(STORAGE_KEY, JSON.stringify({ school: schoolId, term_id: next.id }));
        } catch {
          /* ignore */
        }
      }
    };
    return { sessions, terms, session, term, loadingTerms, setSession, setTerm, isTermClosed, confirmTermSwitch };
  }, [sessions, terms, session, term, loadingTerms, schoolId, isTermClosed, confirmTermSwitch]);

  return <SessionTermContext.Provider value={value}>{children}</SessionTermContext.Provider>;
}

export function useSessionTerm(): SessionTermState {
  const ctx = useContext(SessionTermContext);
  if (!ctx) throw new Error("useSessionTerm must be used within SessionTermProvider");
  return ctx;
}

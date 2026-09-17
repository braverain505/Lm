"use client";

import type { MembershipOut, MeResponse, UserSummary } from "@clearis/shared";

import { api } from "@clearis/shared";
import { useQueryClient } from "@tanstack/react-query";
import {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

interface AuthState {
  user: UserSummary | null;
  memberships: MembershipOut[];
  activeSchool: MembershipOut | null;
  loading: boolean;
  refreshMe: () => Promise<void>;
  setActiveSchool: (membership: MembershipOut) => void;
  clear: () => void;
  /** Revoke the session, drop every cached byte and return to the login screen. */
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState<UserSummary | null>(null);
  const [memberships, setMemberships] = useState<MembershipOut[]>([]);
  const [loading, setLoading] = useState(true);
  // Which school the user is currently operating in (persisted per tab).
  const [activeSchool, setActiveSchool] = useState<MembershipOut | null>(null);

  // The identity the data currently sitting in the query cache belongs to.
  // React Query keys are scoped by school, not by person, so two users of the
  // same school (or the same person with a changed role) would otherwise read
  // each other's responses. Every identity change — sign-in as somebody else,
  // sign-out, impersonation — must drop the whole cache before anything reads
  // it again. Without this the next user sees the previous user's dashboard.
  const identityRef = useRef<string | null>(null);

  const adoptIdentity = useCallback(
    (nextUserId: string | null) => {
      if (identityRef.current === nextUserId) return;
      identityRef.current = nextUserId;
      queryClient.clear();
    },
    [queryClient],
  );

  const refreshMe = useCallback(async () => {
    try {
      const me: MeResponse = await api.me();
      adoptIdentity(me.user.id);
      setUser(me.user);
      setMemberships(me.memberships);
      setActiveSchool((prev) => {
        if (prev && me.memberships.some((m) => m.school_id === prev.school_id)) return prev;
        return me.memberships[0] ?? null;
      });
    } catch (error) {
      // 401/404 when unauthenticated is expected — user not logged in
      adoptIdentity(null);
      setUser(null);
      setMemberships([]);
      setActiveSchool(null);
    } finally {
      setLoading(false);
    }
  }, [adoptIdentity]);

  useEffect(() => {
    void refreshMe();
  }, [refreshMe]);

  const clear = useCallback(() => {
    adoptIdentity(null);
    setUser(null);
    setMemberships([]);
    setActiveSchool(null);
  }, [adoptIdentity]);

  const signOut = useCallback(async () => {
    try {
      await api.logout();
    } catch {
      // Revoking the refresh token failed (offline, already expired). Still tear
      // everything down locally — never leave the tab holding the old session.
    }
    clear();
    // A hard navigation, not router.replace(): only a fresh document is
    // guaranteed to drop the query cache, Next's client router cache and every
    // component's state, so no trace of the previous user can reach the login
    // screen or whoever signs in next on this machine.
    if (typeof window !== "undefined") {
      window.location.replace("/login");
    }
  }, [clear]);

  const value = useMemo(
    () => ({ user, memberships, activeSchool, loading, refreshMe, setActiveSchool, clear, signOut }),
    [user, memberships, activeSchool, loading, refreshMe, clear, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

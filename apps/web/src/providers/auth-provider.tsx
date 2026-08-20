"use client";

import type { MembershipOut, MeResponse, UserSummary } from "@schoolos/shared";

import { api } from "@schoolos/shared";
import {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
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
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserSummary | null>(null);
  const [memberships, setMemberships] = useState<MembershipOut[]>([]);
  const [loading, setLoading] = useState(true);
  // Which school the user is currently operating in (persisted per tab).
  const [activeSchool, setActiveSchool] = useState<MembershipOut | null>(null);

  const refreshMe = useCallback(async () => {
    try {
      const me: MeResponse = await api.me();
      setUser(me.user);
      setMemberships(me.memberships);
      setActiveSchool((prev) => {
        if (prev && me.memberships.some((m) => m.school_id === prev.school_id)) return prev;
        return me.memberships[0] ?? null;
      });
    } catch {
      setUser(null);
      setMemberships([]);
      setActiveSchool(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshMe();
  }, [refreshMe]);

  const clear = useCallback(() => {
    setUser(null);
    setMemberships([]);
    setActiveSchool(null);
  }, []);

  const value = useMemo(
    () => ({ user, memberships, activeSchool, loading, refreshMe, setActiveSchool, clear }),
    [user, memberships, activeSchool, loading, refreshMe, clear],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type {
  SaAnnouncementCreate,
  SaAnnouncement,
  SaOverview,
  SaSchoolCreate,
  SaSchoolDetail,
  SaSchoolList,
  SaSubscriptionUpdate,
  SaTicketCreate,
  SaTicketUpdate,
} from "@schoolos/shared";

import { api } from "@schoolos/shared";
import { useAuth } from "@/providers/auth-provider";

function usePlatformEnabled() {
  const { user } = useAuth();
  return !!user?.is_superadmin;
}

// --- Overview ---------------------------------------------------------------
export function useSaOverview() {
  const enabled = usePlatformEnabled();
  return useQuery({
    queryKey: ["sa", "overview"],
    enabled,
    queryFn: async () => api.superAdminOverview(),
  });
}

// --- Analytics ----------------------------------------------------------------
export function useSaGrowth(range: string) {
  const enabled = usePlatformEnabled();
  return useQuery({
    queryKey: ["sa", "growth", range],
    enabled,
    queryFn: async () => api.superAdminGrowth(range),
  });
}

export function useSaRevenue(params: { range?: string; plan?: string; source?: string }) {
  const enabled = usePlatformEnabled();
  return useQuery({
    queryKey: ["sa", "revenue", params],
    enabled,
    queryFn: async () => api.superAdminRevenue(params),
  });
}

export function useSaSubscriptions() {
  const enabled = usePlatformEnabled();
  return useQuery({
    queryKey: ["sa", "subscriptions"],
    enabled,
    queryFn: async () => api.superAdminSubscriptions(),
  });
}

export function useSaAi(params: { range?: string; feature?: string; plan?: string }) {
  const enabled = usePlatformEnabled();
  return useQuery({
    queryKey: ["sa", "ai", params],
    enabled,
    queryFn: async () => api.superAdminAi(params),
  });
}

export function useSaUsers(range: string) {
  const enabled = usePlatformEnabled();
  return useQuery({
    queryKey: ["sa", "users", range],
    enabled,
    queryFn: async () => api.superAdminUsers(range),
  });
}

export function useSaEngagement() {
  const enabled = usePlatformEnabled();
  return useQuery({
    queryKey: ["sa", "engagement"],
    enabled,
    queryFn: async () => api.superAdminEngagement(),
  });
}

export function useSaGeo() {
  const enabled = usePlatformEnabled();
  return useQuery({
    queryKey: ["sa", "geo"],
    enabled,
    queryFn: async () => api.superAdminGeo(),
  });
}

export function useSaActivity(params: { limit?: number; category?: string } = {}) {
  const enabled = usePlatformEnabled();
  return useQuery({
    queryKey: ["sa", "activity", params],
    enabled,
    queryFn: async () => api.superAdminActivity(params),
  });
}

export function useSaHealth() {
  const enabled = usePlatformEnabled();
  return useQuery({
    queryKey: ["sa", "health"],
    enabled,
    queryFn: async () => api.superAdminHealth(),
  });
}

// --- Schools ------------------------------------------------------------------
export function useSaSchools(params: {
  q?: string; status?: string; plan?: string; state?: string; sort?: string; page?: number; per_page?: number;
}) {
  const enabled = usePlatformEnabled();
  return useQuery({
    queryKey: ["sa", "schools", params],
    enabled,
    placeholderData: (prev: SaSchoolList | undefined) => prev,
    queryFn: async () => api.superAdminSchools(params),
  });
}

export function useSaSchool(schoolId: string | null) {
  const enabled = usePlatformEnabled();
  return useQuery({
    queryKey: ["sa", "school", schoolId],
    enabled: enabled && !!schoolId,
    queryFn: async () => api.superAdminSchool(schoolId!),
  });
}

export function useSaAddSchool() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: SaSchoolCreate) => api.superAdminAddSchool(body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["sa", "schools"] });
      void queryClient.invalidateQueries({ queryKey: ["sa", "overview"] });
    },
  });
}

export function useSaUpdateSubscription(schoolId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: SaSubscriptionUpdate) => {
      if (!schoolId) throw new Error("No school selected");
      return api.superAdminUpdateSubscription(schoolId, body);
    },
    onSuccess: (detail: SaSchoolDetail) => {
      void queryClient.invalidateQueries({ queryKey: ["sa", "school", detail.profile.id] });
      void queryClient.invalidateQueries({ queryKey: ["sa", "schools"] });
      void queryClient.invalidateQueries({ queryKey: ["sa", "subscriptions"] });
      void queryClient.invalidateQueries({ queryKey: ["sa", "overview"] });
    },
  });
}

export function useSaResetAdmin() {
  return useMutation({
    mutationFn: (schoolId: string) => api.superAdminResetAdmin(schoolId),
  });
}

export function useSaImpersonate() {
  return useMutation({
    mutationFn: (schoolId: string) => api.superAdminImpersonate(schoolId),
  });
}

export function useSaDeleteSchool() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (schoolId: string) => api.superAdminDeleteSchool(schoolId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["sa", "schools"] });
      void queryClient.invalidateQueries({ queryKey: ["sa", "overview"] });
    },
  });
}

export function useImpersonateEnter() {
  const { refreshMe } = useAuth();
  return useMutation({
    mutationFn: (token: string) => api.impersonateEnter(token),
    onSuccess: () => void refreshMe(),
  });
}

export function useImpersonateExit() {
  const { refreshMe } = useAuth();
  return useMutation({
    mutationFn: () => api.impersonateExit(),
    onSuccess: () => void refreshMe(),
  });
}

// --- Support ------------------------------------------------------------------
export function useSaIssues(params: { severity?: string; status?: string } = {}) {
  const enabled = usePlatformEnabled();
  return useQuery({
    queryKey: ["sa", "issues", params],
    enabled,
    queryFn: async () => api.superAdminIssues(params),
  });
}

export function useSaTickets() {
  const enabled = usePlatformEnabled();
  return useQuery({
    queryKey: ["sa", "tickets"],
    enabled,
    queryFn: async () => api.superAdminTickets(),
  });
}

export function useSaCreateTicket() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: SaTicketCreate) => api.superAdminCreateTicket(body),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["sa", "tickets"] }),
  });
}

export function useSaUpdateTicket() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ ticketId, body }: { ticketId: string; body: SaTicketUpdate }) =>
      api.superAdminUpdateTicket(ticketId, body),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["sa", "tickets"] }),
  });
}

// --- Notifications -------------------------------------------------------------
export function useSaNotifications() {
  const enabled = usePlatformEnabled();
  return useQuery({
    queryKey: ["sa", "notifications"],
    enabled,
    queryFn: async () => api.superAdminNotifications(),
  });
}

export function useSaMarkNotificationsRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (ids: string[]) => api.superAdminMarkNotificationsRead(ids),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["sa", "notifications"] }),
  });
}

// --- Audit ---------------------------------------------------------------------
export function useSaAudit(params: { q?: string; action?: string; entity?: string; page?: number; per_page?: number }) {
  const enabled = usePlatformEnabled();
  return useQuery({
    queryKey: ["sa", "audit", params],
    enabled,
    queryFn: async () => api.superAdminAudit(params),
  });
}

// --- Settings / announcements --------------------------------------------------
export function useSaSettings() {
  const enabled = usePlatformEnabled();
  return useQuery({
    queryKey: ["sa", "settings"],
    enabled,
    queryFn: async () => api.superAdminSettings(),
  });
}

export function useSaUpdateSettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (updates: Record<string, unknown>) => api.superAdminUpdateSettings(updates),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["sa", "settings"] }),
  });
}

export function useSaAnnouncements() {
  const enabled = usePlatformEnabled();
  return useQuery({
    queryKey: ["sa", "announcements"],
    enabled,
    queryFn: async () => api.superAdminAnnouncements(),
  });
}

export function useSaCreateAnnouncement() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: SaAnnouncementCreate) => api.superAdminCreateAnnouncement(body),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["sa", "announcements"] }),
  });
}

export type { SaAnnouncement, SaOverview, SaSchoolDetail, SaSchoolList };
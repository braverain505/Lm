// SchoolOS — typed fetch client for the browser. Reads tokens from httpOnly
// cookies (set by the API), sends X-School-Id for tenant resolution.
import {
  AskResponse,
  AskResponseSchema,
  ApiError,
  ApiErrorSchema,
  Assignment,
  AssignmentCreate,
  AssignmentCreateSchema,
  AssignmentSchema,
  AttendanceRecord,
  AttendanceRecordSchema,
  AttendanceSummary,
  AttendanceSummarySchema,
  Book,
  BookIn,
  BookInSchema,
  BookSchema,
  Borrowing,
  BorrowingIn,
  BorrowingInSchema,
  BorrowingSchema,
  CompileResult,
  CompileResultSchema,
  CopilotAsk,
  CopilotConversation,
  CopilotConversationDetail,
  CopilotConversationDetailSchema,
  CopilotConversationSchema,
  CopilotIntent,
  CopilotIntentSchema,
  CopilotMessage,
  CopilotMessageSchema,
  EnrollmentHistoryRow,
  EnrollmentHistoryRowSchema,
  FeeStructure,
  FeeStructureIn,
  FeeStructureSchema,
  InventoryCategory,
  InventoryCategoryIn,
  InventoryCategoryInSchema,
  InventoryCategorySchema,
  InventoryItem,
  InventoryItemIn,
  InventoryItemInSchema,
  InventoryItemSchema,
  Invoice,
  InvoiceIn,
  InvoiceSchema,
  MeResponse,
  MeResponseSchema,
  MyAssignment,
  MyAssignmentSchema,
  Payment,
  PaymentIn,
  PaymentSchema,
  PinCheckOut,
  PinCheckOutSchema,
  PinSetOut,
  PinSetOutSchema,
  PlatformSchool,
  PlatformSchoolSchema,
  SchoolAdminCreate,
  SchoolAdminCreated,
  SchoolAdminCreatedSchema,
  SchoolAiUpdate,
  SchoolAiUpdateSchema,
  SchoolSuspendedUpdate,
  SchoolSuspendedUpdateSchema,
  TeacherOut,
  TeacherOutSchema,
  ReportCard,
  ReportCardSchema,
  ReportIndexRow,
  ReportIndexRowSchema,
  ResultCell,
  ResultComment,
  ResultCommentSchema,
  CommentBankEntry,
  CommentBankEntrySchema,
  BestInSubjectRow,
  BestInSubjectRowSchema,
  GradeBandRow,
  GradeBandRowSchema,
  PsychomotorRow,
  PsychomotorRowSchema,
  RoleDetail,
  RoleDetailSchema,
  Staff,
  StaffAccountCreate,
  StaffAccountCreateSchema,
  StaffAccountOut,
  StaffAccountOutSchema,
  StaffAccountUpdate,
  StaffCreate,
  StaffCreateSchema,
  StaffSchema,
  LessonPlan,
  LessonPlanInput,
  LessonPlanSchema,
  QuestionBank,
  QuestionBankInput,
  QuestionBankSchema,
  ScheduleEntry,
  ScheduleEntrySchema,
  ScheduleGenerateIn,
  ScheduleGenerateInSchema,
  ScheduleGenerateOut,
  ScheduleGenerateOutSchema,
  ScheduleValidateIn,
  ScheduleValidateInSchema,
  ScheduleValidateOut,
  ScheduleValidateOutSchema,
  SchoolBrief,
  SchoolBriefSchema,
  ScoreCard,
  ScoreCardSchema,
  StaffAttendanceIn,
  StaffAttendanceInSchema,
  StaffAttendanceSummary,
  StaffAttendanceSummarySchema,
  StockMovement,
  StockMovementIn,
  StockMovementInSchema,
  StockMovementSchema,
  StudentAttendanceIn,
  StudentAttendanceInSchema,
  StudentFeeBalance,
  StudentFeeBalanceSchema,
  Receipt,
  ReceiptSchema,
  PaymentStatus,
  PaymentStatusSchema,
  PayRun,
  PayRunCreate,
  PayRunCreateSchema,
  PayRunDetail,
  PayRunDetailSchema,
  PayRunSchema,
  Payslip,
  PayslipSchema,
  PromotionRequest,
  PromotionRequestSchema,
  PromotionResult,
  PromotionResultSchema,
  SalaryStructure,
  SalaryStructureIn,
  SalaryStructureInSchema,
  SalaryStructureSchema,
  StaffSalaryIn,
  StaffSalaryInSchema,
  StaffSalaryOut,
  StaffSalaryOutSchema,
  TimeSlot,
  TimeSlotSchema,
  TokenResponse,
  TokenResponseSchema,
  TransitionResult,
  TransitionResultSchema,
  WeekScheduleOut,
  WeekScheduleOutSchema,
  WorkbenchRow,
  WorkbenchRowSchema,
  DashboardSummary,
  DashboardSummarySchema,
  SaOverview,
  SaOverviewSchema,
  SaSchoolList,
  SaSchoolListSchema,
  SaSchoolDetail,
  SaSchoolDetailSchema,
  SaSchoolCreate,
  SaSubscriptionUpdate,
  SaTickets,
  SaTicketsSchema,
  SaTicketCreate,
  SaTicketUpdate,
  SaAnnouncementCreate,
  SaHealth,
  SaHealthSchema,
  SaAuditRow,
  SaAnnouncement,
  SaAnnouncementSchema,
  SaGrowth,
  SaGrowthSchema,
  SaRevenue,
  SaRevenueSchema,
  SaSubscriptions,
  SaSubscriptionsSchema,
  SaAi,
  SaAiSchema,
  SaUsers,
  SaUsersSchema,
  SaEngagement,
  SaEngagementSchema,
  SaGeo,
  SaGeoSchema,
  SaActivityRow,
  SaActivityRowSchema,
  SaIssues,
  SaIssuesSchema,
  SaAudit,
  SaAuditSchema,
  SaNotification,
  SaNotificationSchema,
} from "./contracts";
import { z } from "zod";

export type {
  AskResponse,
  AskResponseSchema,
  CopilotAsk,
  CopilotConversation,
  CopilotConversationDetail,
  CopilotConversationDetailSchema,
  CopilotConversationSchema,
  CopilotIntent,
  CopilotIntentSchema,
  CopilotMessage,
  CopilotMessageSchema,
};

const BASE = (
  process.env.NEXT_PUBLIC_API_URL ??
  "/api/proxy"
).replace(/\/$/, "");

export class ApiClientError extends Error {
  code: string;
  status: number;
  details?: unknown;

  constructor(status: number, err: ApiError) {
    super(err.error.message);
    this.status = status;
    this.code = err.error.code;
    this.details = err.error.details;
  }
}

async function request<T>(
  path: string,
  options: RequestInit & { zod?: (data: unknown) => T } = {},
): Promise<T> {
  const doFetch = () =>
    fetch(`${BASE}${path}`, {
      ...options,
      headers: {
        ...(options.body instanceof FormData
          ? {}
          : { "Content-Type": "application/json" }),
        ...(options.headers ?? {}),
      },
      credentials: "include",
    });

  let res = await doFetch();

  // The access cookie lives for a short time (15 min). If it has expired, the
  // API answers 401 — silently rotate it via the refresh cookie and retry once.
  if (res.status === 401 && shouldAutoRefresh(path)) {
    const refreshed = await attemptRefresh();
    if (refreshed) res = await doFetch();
  }

  const text = await res.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      throw new ApiClientError(res.status, {
        error: {
          code: "ERR_INVALID_RESPONSE",
          message: `API returned a non-JSON response (${res.status})`,
        },
      });
    }
  }

  if (!res.ok) {
    const parsed = ApiErrorSchema.safeParse(data);
    throw new ApiClientError(
      res.status,
      parsed.success ? parsed.data : { error: { code: "ERR_INTERNAL", message: text } },
    );
  }
  return (options.zod ? options.zod(data) : data) as T;
}

// Paths where a 401 is a genuine authentication failure (bad credentials,
// logout, token rotation) — never auto-refresh these.
function shouldAutoRefresh(path: string): boolean {
  return ![
    "/auth/login",
    "/auth/register-school",
    "/auth/refresh",
    "/auth/logout",
    "/auth/passwords/reset",
  ].some((p) => path.startsWith(p));
}

// Concurrent 401s share a single refresh so the rotating refresh cookie is
// never consumed twice in a race.
let refreshInFlight: Promise<boolean> | null = null;

async function attemptRefresh(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = fetch(`${BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
    })
      .then((res) => res.ok)
      .catch(() => false)
      .finally(() => {
        refreshInFlight = null;
      });
  }
  return refreshInFlight;
}

// fetch() variant for non-JSON bodies (uploads) with the same silent
// refresh-on-401 + single retry behaviour.
async function fetchWithRefresh(path: string, init: RequestInit): Promise<Response> {
  const res = await fetch(`${BASE}${path}`, { ...init, credentials: "include" });
  if (res.status === 401 && shouldAutoRefresh(path)) {
    const refreshed = await attemptRefresh();
    if (refreshed) return fetch(`${BASE}${path}`, { ...init, credentials: "include" });
  }
  return res;
}

// --- Auth ---------------------------------------------------------------------
export async function registerSchool(body: {
  school_name: string;
  school_type: string;
  established_year?: number;
  website?: string;
  school_email?: string;
  phone?: string;
  address?: string;
  state?: string;
  country?: string;
  admin_email: string;
  admin_full_name: string;
  password: string;
}): Promise<TokenResponse> {
  return request("/auth/register-school", {
    method: "POST",
    body: JSON.stringify(body),
    zod: TokenResponseSchema.parse,
  });
}

export type SchoolProfile = {
  id: string;
  name: string;
  short_name: string | null;
  slug: string;
  school_type: string;
  currency: string;
  timezone: string;
  email: string | null;
  phone: string | null;
  logo_url: string | null;
  established_year: number | null;
  website: string | null;
  address: string | null;
  state: string | null;
  country: string;
};

export async function fetchSchoolMe(schoolId: string): Promise<SchoolProfile> {
  return schoolFetch<SchoolProfile>(schoolId, "/schools/me");
}

export async function updateSchool(schoolId: string, body: Record<string, unknown>): Promise<SchoolProfile> {
  return schoolFetch<SchoolProfile>(schoolId, "/schools/me", { method: "PATCH", body: JSON.stringify(body) });
}

export async function login(body: { email: string; password: string }): Promise<TokenResponse> {
  return request("/auth/login", { method: "POST", body: JSON.stringify(body), zod: TokenResponseSchema.parse });
}

export async function logout(): Promise<void> {
  return request("/auth/logout", { method: "POST" });
}

export async function me(): Promise<MeResponse> {
  return request("/auth/me", { zod: MeResponseSchema.parse });
}

// --- Platform (Lumo admin dashboard) -------------------------------------------
export async function fetchPlatformSchools(): Promise<PlatformSchool[]> {
  return request("/platform/schools", {
    zod: PlatformSchoolSchema.array().parse,
  });
}

export async function setSchoolAi(
  schoolId: string,
  enabled: boolean,
): Promise<PlatformSchool> {
  return request(`/platform/schools/${schoolId}/ai`, {
    method: "PATCH",
    body: JSON.stringify({ enabled }),
    zod: PlatformSchoolSchema.parse,
  });
}

export async function setSchoolSuspended(
  schoolId: string,
  suspended: boolean,
): Promise<PlatformSchool> {
  return request(`/platform/schools/${schoolId}/status`, {
    method: "PATCH",
    body: JSON.stringify({ suspended }),
    zod: PlatformSchoolSchema.parse,
  });
}

export async function createSchoolAdmin(
  schoolId: string,
  body: SchoolAdminCreate,
): Promise<SchoolAdminCreated> {
  return request(`/platform/schools/${schoolId}/admins`, {
    method: "POST",
    body: JSON.stringify(body),
    zod: SchoolAdminCreatedSchema.parse,
  });
}

export async function fetchPlatformTeachers(): Promise<TeacherOut[]> {
  return request("/platform/teachers", {
    zod: TeacherOutSchema.array().parse,
  });
}

// --- Super Admin (platform command center) --------------------------------------
export async function superAdminOverview(): Promise<SaOverview> {
  return request("/superadmin/overview", { zod: SaOverviewSchema.parse });
}

export async function superAdminGrowth(range: string = "12m"): Promise<SaGrowth> {
  return request(`/superadmin/growth?range=${range}`, { zod: SaGrowthSchema.parse });
}

export async function superAdminRevenue(params: { range?: string; plan?: string; source?: string } = {}): Promise<SaRevenue> {
  const q = new URLSearchParams();
  if (params.range) q.set("range", params.range);
  if (params.plan) q.set("plan", params.plan);
  if (params.source) q.set("source", params.source);
  return request(`/superadmin/revenue?${q.toString()}`, { zod: SaRevenueSchema.parse });
}

export async function superAdminSubscriptions(): Promise<SaSubscriptions> {
  return request("/superadmin/subscriptions", { zod: SaSubscriptionsSchema.parse });
}

export async function superAdminAi(params: { range?: string; feature?: string; plan?: string } = {}): Promise<SaAi> {
  const q = new URLSearchParams();
  if (params.range) q.set("range", params.range);
  if (params.feature) q.set("feature", params.feature);
  if (params.plan) q.set("plan", params.plan);
  return request(`/superadmin/ai?${q.toString()}`, { zod: SaAiSchema.parse });
}

export async function superAdminUsers(range: string = "12m"): Promise<SaUsers> {
  return request(`/superadmin/users?range=${range}`, { zod: SaUsersSchema.parse });
}

export async function superAdminEngagement(): Promise<SaEngagement> {
  return request("/superadmin/engagement", { zod: SaEngagementSchema.parse });
}

export async function superAdminGeo(): Promise<SaGeo> {
  return request("/superadmin/geo", { zod: SaGeoSchema.parse });
}

export async function superAdminActivity(params: { limit?: number; category?: string } = {}): Promise<SaActivityRow[]> {
  const q = new URLSearchParams();
  if (params.limit) q.set("limit", String(params.limit));
  if (params.category) q.set("category", params.category);
  return request(`/superadmin/activity?${q.toString()}`, { zod: SaActivityRowSchema.array().parse });
}

export async function superAdminHealth(): Promise<SaHealth> {
  return request("/superadmin/health", { zod: SaHealthSchema.parse });
}

export async function superAdminSchools(params: {
  q?: string; status?: string; plan?: string; state?: string; sort?: string; page?: number; per_page?: number;
} = {}): Promise<SaSchoolList> {
  const q = new URLSearchParams();
  if (params.q) q.set("q", params.q);
  if (params.status) q.set("status", params.status);
  if (params.plan) q.set("plan", params.plan);
  if (params.state) q.set("state", params.state);
  if (params.sort) q.set("sort", params.sort);
  if (params.page) q.set("page", String(params.page));
  if (params.per_page) q.set("per_page", String(params.per_page));
  return request(`/superadmin/schools?${q.toString()}`, { zod: SaSchoolListSchema.parse });
}

export async function superAdminSchool(schoolId: string): Promise<SaSchoolDetail> {
  return request(`/superadmin/schools/${schoolId}`, { zod: SaSchoolDetailSchema.parse });
}

export async function superAdminAddSchool(body: SaSchoolCreate): Promise<{ id: string; name: string; admin_email: string; temp_password: string }> {
  return request("/superadmin/schools", { method: "POST", body: JSON.stringify(body) });
}

export async function superAdminUpdateSubscription(schoolId: string, body: SaSubscriptionUpdate): Promise<SaSchoolDetail> {
  return request(`/superadmin/schools/${schoolId}/subscription`, {
    method: "PATCH", body: JSON.stringify(body), zod: SaSchoolDetailSchema.parse,
  });
}

export async function superAdminResetAdmin(schoolId: string): Promise<{ email: string; temp_password: string }> {
  return request(`/superadmin/schools/${schoolId}/reset-admin`, { method: "POST" });
}

export async function superAdminImpersonate(schoolId: string): Promise<{ token: string; school_id: string; school_name: string; expires_in_minutes: number }> {
  return request(`/superadmin/schools/${schoolId}/impersonate`, { method: "POST", body: JSON.stringify({}) });
}

export async function superAdminDeleteSchool(schoolId: string): Promise<{ id: string; name: string; deleted: boolean }> {
  return request(`/superadmin/schools/${schoolId}`, { method: "DELETE" });
}

export async function impersonateEnter(token: string): Promise<{ token: string; user_id: string; full_name: string; email: string; school_id: string; school_name: string }> {
  return request("/auth/impersonate/enter", { method: "POST", body: JSON.stringify({ token }) });
}

export async function impersonateExit(): Promise<{ ok: boolean }> {
  return request("/auth/impersonate/exit", { method: "POST" });
}

export async function superAdminIssues(params: { severity?: string; status?: string } = {}): Promise<SaIssues> {
  const q = new URLSearchParams();
  if (params.severity) q.set("severity", params.severity);
  if (params.status) q.set("status", params.status);
  return request(`/superadmin/issues?${q.toString()}`, { zod: SaIssuesSchema.parse });
}

export async function superAdminTickets(): Promise<SaTickets> {
  return request("/superadmin/tickets", { zod: SaTicketsSchema.parse });
}

export async function superAdminCreateTicket(body: SaTicketCreate): Promise<{ id: string; subject: string; status: string }> {
  return request("/superadmin/tickets", { method: "POST", body: JSON.stringify(body) });
}

export async function superAdminUpdateTicket(ticketId: string, body: SaTicketUpdate): Promise<{ id: string; subject: string; status: string }> {
  return request(`/superadmin/tickets/${ticketId}`, { method: "PATCH", body: JSON.stringify(body) });
}

export async function superAdminNotifications(): Promise<SaNotification[]> {
  return request("/superadmin/notifications", { zod: SaNotificationSchema.array().parse });
}

export async function superAdminMarkNotificationsRead(ids: string[]): Promise<{ ok: boolean }> {
  return request("/superadmin/notifications/read", { method: "POST", body: JSON.stringify(ids) });
}

export async function superAdminAudit(params: { q?: string; action?: string; entity?: string; page?: number; per_page?: number } = {}): Promise<SaAudit> {
  const q = new URLSearchParams();
  if (params.q) q.set("q", params.q);
  if (params.action) q.set("action", params.action);
  if (params.entity) q.set("entity", params.entity);
  if (params.page) q.set("page", String(params.page));
  if (params.per_page) q.set("per_page", String(params.per_page));
  return request(`/superadmin/audit?${q.toString()}`, { zod: SaAuditSchema.parse });
}

export async function superAdminSettings(): Promise<Record<string, unknown>> {
  return request("/superadmin/settings");
}

export async function superAdminUpdateSettings(updates: Record<string, unknown>): Promise<Record<string, unknown>> {
  return request("/superadmin/settings", { method: "PATCH", body: JSON.stringify({ updates }) });
}

export async function superAdminAnnouncements(): Promise<SaAnnouncement[]> {
  return request("/superadmin/announcements", { zod: SaAnnouncementSchema.array().parse });
}

export async function superAdminCreateAnnouncement(body: SaAnnouncementCreate): Promise<SaAnnouncement> {
  return request("/superadmin/announcements", { method: "POST", body: JSON.stringify(body), zod: SaAnnouncementSchema.parse });
}

export async function refresh(): Promise<TokenResponse> {
  return request("/auth/refresh", { method: "POST", zod: TokenResponseSchema.parse });
}

export async function requestPasswordReset(email: string): Promise<{
  message: string;
  reset_token: string | null;
}> {
  return request("/auth/passwords/reset", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export async function confirmPasswordReset(
  token: string,
  new_password: string,
): Promise<{ message: string }> {
  return request("/auth/passwords/reset/confirm", {
    method: "POST",
    body: JSON.stringify({ token, new_password }),
  });
}

export const changePassword = (body: {
  current_password: string;
  new_password: string;
}) =>
  request<{ message: string }>("/auth/change-password", {
    method: "POST",
    body: JSON.stringify(body),
  });

export const changeEmail = (body: {
  current_password: string;
  new_email: string;
}) =>
  request<{ message: string; email: string }>("/auth/change-email", {
    method: "POST",
    body: JSON.stringify(body),
  });

// --- Public result portal (no auth, no school header) ----------------------------
export async function publicSchools(): Promise<SchoolBrief[]> {
  return request("/public/schools", { zod: SchoolBriefSchema.array().parse });
}

export async function pinCheck(body: {
  school_slug: string;
  admission_no: string;
  pin: string;
}): Promise<PinCheckOut> {
  return request("/public/pin-check", {
    method: "POST",
    body: JSON.stringify(body),
    zod: PinCheckOutSchema.parse,
  });
}

export const publicReportCard = (token: string, termId?: string) => {
  const q = termId ? `&term_id=${termId}` : "";
  return request<ReportCard>(`/public/report-card?token=${encodeURIComponent(token)}${q}`, {
    zod: ReportCardSchema.parse,
  });
};

// --- School-scoped ---------------------------------------------------------------
export function schoolFetch<T>(
  schoolId: string,
  path: string,
  init: RequestInit = {},
  zod?: (d: unknown) => T,
): Promise<T> {
  return request(path, { ...init, headers: { "X-School-Id": schoolId, ...(init.headers ?? {}) }, zod });
}

export const fetchScoreCard = (schoolId: string, armId: string, subjectId: string, termId: string) =>
  schoolFetch<ScoreCard>(
    schoolId,
    `/results/scorecard?arm_id=${armId}&subject_id=${subjectId}&term_id=${termId}`,
    {},
    ScoreCardSchema.parse,
  );

// --- Results approval workflow --------------------------------------------------
export const fetchWorkbench = (schoolId: string, termId: string) =>
  schoolFetch<WorkbenchRow[]>(
    schoolId,
    `/results/workbench?term_id=${termId}`,
    {},
    WorkbenchRowSchema.array().parse,
  );

// --- Report cards --------------------------------------------------------------
export const fetchReportIndex = (schoolId: string, armId: string, termId: string) =>
  schoolFetch<ReportIndexRow[]>(
    schoolId,
    `/results/report-index?arm_id=${armId}&term_id=${termId}`,
    {},
    ReportIndexRowSchema.array().parse,
  );

export const fetchReportCard = (schoolId: string, studentId: string, termId: string) =>
  schoolFetch<ReportCard>(
    schoolId,
    `/results/report-card?student_id=${studentId}&term_id=${termId}`,
    {},
    ReportCardSchema.parse,
  );

export const fetchReportCards = (schoolId: string, armId: string, termId: string) =>
  schoolFetch<ReportCard[]>(
    schoolId,
    `/results/report-cards?arm_id=${armId}&term_id=${termId}`,
    {},
    ReportCardSchema.array().parse,
  );

const reportCommentPath = (studentId: string, termId: string) =>
  `/results/${studentId}/comment?term_id=${termId}`;

export const fetchResultComment = (schoolId: string, studentId: string, termId: string) =>
  schoolFetch<ResultComment>(
    schoolId,
    reportCommentPath(studentId, termId),
    {},
    ResultCommentSchema.parse,
  );

export const generateResultComment = (schoolId: string, studentId: string, termId: string) =>
  schoolFetch<ResultComment>(
    schoolId,
    reportCommentPath(studentId, termId),
    { method: "POST" },
    ResultCommentSchema.parse,
  );

/** AI generation with role/focus/tone — persisted (revision bump, metered). */
export const generateRoleComment = (
  schoolId: string,
  studentId: string,
  body: { term_id: string; role: string; focus?: string | null; tone?: string },
) =>
  schoolFetch<ResultComment>(
    schoolId,
    `/results/${studentId}/comment`,
    { method: "POST", body: JSON.stringify(body) },
    ResultCommentSchema.parse,
  );

/** Non-persisted AI draft for review in the comment modal. */
export const previewRoleComment = (
  schoolId: string,
  studentId: string,
  body: { term_id: string; role: string; focus?: string | null; tone?: string },
) =>
  schoolFetch<{ body: string }>(
    schoolId,
    `/results/${studentId}/comment/preview`,
    { method: "POST", body: JSON.stringify(body) },
    z.object({ body: z.string() }).parse,
  );

/** Persist a manually written/edited comment for one role (provider=manual). */
export const saveRoleComment = (
  schoolId: string,
  studentId: string,
  body: { term_id: string; role: string; body: string },
) =>
  schoolFetch<ResultComment>(
    schoolId,
    `/results/${studentId}/comment`,
    { method: "PUT", body: JSON.stringify(body) },
    ResultCommentSchema.parse,
  );

export const fetchCommentBank = (
  schoolId: string,
  params: { category?: string; sentiment?: string; search?: string } = {},
) => {
  const q = new URLSearchParams();
  if (params.category) q.set("category", params.category);
  if (params.sentiment) q.set("sentiment", params.sentiment);
  if (params.search) q.set("search", params.search);
  const qs = q.toString();
  return schoolFetch<CommentBankEntry[]>(
    schoolId,
    `/results/comment-bank${qs ? `?${qs}` : ""}`,
    {},
    z.array(CommentBankEntrySchema).parse,
  );
};

export const createCommentBankEntry = (
  schoolId: string,
  body: { comment_text: string; category: string; sentiment: string; applicable_domain?: string | null },
) =>
  schoolFetch<CommentBankEntry>(
    schoolId,
    "/results/comment-bank",
    { method: "POST", body: JSON.stringify(body) },
    CommentBankEntrySchema.parse,
  );

export const updateCommentBankEntry = (
  schoolId: string,
  entryId: string,
  body: {
    comment_text?: string;
    category?: string;
    sentiment?: string;
    applicable_domain?: string | null;
    is_active?: boolean;
  },
) =>
  schoolFetch<CommentBankEntry>(
    schoolId,
    `/results/comment-bank/${entryId}`,
    { method: "PATCH", body: JSON.stringify(body) },
    CommentBankEntrySchema.parse,
  );

export const deactivateCommentBankEntry = (schoolId: string, entryId: string) =>
  schoolFetch<CommentBankEntry>(
    schoolId,
    `/results/comment-bank/${entryId}`,
    { method: "DELETE" },
    CommentBankEntrySchema.parse,
  );

export const fetchBestInSubjects = (schoolId: string, armId: string, termId: string) =>
  schoolFetch<BestInSubjectRow[]>(
    schoolId,
    `/results/best-in-subjects?arm_id=${armId}&term_id=${termId}`,
    {},
    z.array(BestInSubjectRowSchema).parse,
  );

export const fetchGradeBands = (schoolId: string, termId: string) =>
  schoolFetch<GradeBandRow[]>(
    schoolId,
    `/results/grade-bands?term_id=${termId}`,
    {},
    z.array(GradeBandRowSchema).parse,
  );

export const fetchPsychomotor = (schoolId: string, studentId: string, termId: string) =>
  schoolFetch<PsychomotorRow[]>(
    schoolId,
    `/results/psychomotor?student_id=${studentId}&term_id=${termId}`,
    {},
    z.array(PsychomotorRowSchema).parse,
  );

export const savePsychomotor = (
  schoolId: string,
  body: { student_id: string; term_id: string; rows: { learning_area: string; achievement_level: string }[] },
) =>
  schoolFetch<PsychomotorRow[]>(
    schoolId,
    "/results/psychomotor",
    { method: "PUT", body: JSON.stringify(body) },
    z.array(PsychomotorRowSchema).parse,
  );

const lessonPlanPath = (
  subjectId: string,
  classArmId: string,
  termId: string,
  topic: string,
) =>
  `/lesson-plans?term_id=${termId}&subject_id=${subjectId}&class_arm_id=${classArmId}&topic=${encodeURIComponent(topic)}`;

export const fetchLessonPlan = (
  schoolId: string,
  subjectId: string,
  classArmId: string,
  termId: string,
  topic: string,
) =>
  schoolFetch<LessonPlan>(
    schoolId,
    lessonPlanPath(subjectId, classArmId, termId, topic),
    {},
    LessonPlanSchema.parse,
  );

export const generateLessonPlan = (schoolId: string, input: LessonPlanInput) =>
  schoolFetch<LessonPlan>(
    schoolId,
    "/lesson-plans",
    { method: "POST", body: JSON.stringify(input) },
    LessonPlanSchema.parse,
  );

const questionBankPath = (
  subjectId: string,
  classArmId: string,
  termId: string,
  topic: string,
) =>
  `/question-banks?term_id=${termId}&subject_id=${subjectId}&class_arm_id=${classArmId}&topic=${encodeURIComponent(topic)}`;

export const fetchQuestionBank = (
  schoolId: string,
  subjectId: string,
  classArmId: string,
  termId: string,
  topic: string,
) =>
  schoolFetch<QuestionBank>(
    schoolId,
    questionBankPath(subjectId, classArmId, termId, topic),
    {},
    QuestionBankSchema.parse,
  );

export const generateQuestionBank = (schoolId: string, input: QuestionBankInput) =>
  schoolFetch<QuestionBank>(
    schoolId,
    "/question-banks",
    { method: "POST", body: JSON.stringify(input) },
    QuestionBankSchema.parse,
  );

// --- Timetable / class scheduling -------------------------------------------------
export const fetchTimeSlots = (schoolId: string) =>
  schoolFetch<TimeSlot[]>(
    schoolId,
    "/timetable/time-slots",
    {},
    TimeSlotSchema.array().parse,
  );

export const generateSchedule = (schoolId: string, input: ScheduleGenerateIn) =>
  schoolFetch<ScheduleGenerateOut>(
    schoolId,
    "/timetable/generate",
    { method: "POST", body: JSON.stringify(input) },
    ScheduleGenerateOutSchema.parse,
  );

export const fetchWeeklySchedule = (
  schoolId: string,
  classArmId: string,
  academicSessionId?: string,
) => {
  const q = academicSessionId ? `?academic_session_id=${academicSessionId}` : "";
  return schoolFetch<WeekScheduleOut>(
    schoolId,
    `/timetable/week/${classArmId}${q}`,
    {},
    WeekScheduleOutSchema.parse,
  );
};

export const validateSchedule = (schoolId: string, input: ScheduleValidateIn) =>
  schoolFetch<ScheduleValidateOut>(
    schoolId,
    "/timetable/validate",
    { method: "POST", body: JSON.stringify(input) },
    ScheduleValidateOutSchema.parse,
  );

// --- Staff / teachers ------------------------------------------------------------------
export const createStaff = (schoolId: string, input: StaffCreate) =>
  schoolFetch<Staff>(
    schoolId,
    "/staff",
    { method: "POST", body: JSON.stringify(input) },
    StaffSchema.parse,
  );

export const createStaffAccount = (schoolId: string, staffId: string, input: StaffAccountCreate) =>
  schoolFetch<StaffAccountOut>(
    schoolId,
    `/staff/${staffId}/account`,
    { method: "POST", body: JSON.stringify(input) },
    StaffAccountOutSchema.parse,
  );

export const updateStaffAccount = (schoolId: string, staffId: string, input: StaffAccountUpdate) =>
  schoolFetch<StaffAccountOut>(
    schoolId,
    `/staff/${staffId}/account`,
    { method: "PATCH", body: JSON.stringify(input) },
    StaffAccountOutSchema.parse,
  );

export const deleteStaff = (schoolId: string, staffId: string) =>
  schoolFetch<void>(schoolId, `/staff/${staffId}`, { method: "DELETE" });

// --- Roles (for staff account creation) ---------------------------------------------------
export const fetchRoles = (schoolId: string) =>
  schoolFetch<RoleDetail[]>(
    schoolId,
    "/roles",
    {},
    RoleDetailSchema.array().parse,
  );

// --- Subject assignments (admin assigns classes/subjects to teachers) ----------------------
export const createAssignment = (schoolId: string, input: AssignmentCreate) =>
  schoolFetch<Assignment>(
    schoolId,
    "/academics/assignments",
    { method: "POST", body: JSON.stringify(input) },
    AssignmentSchema.parse,
  );

export const deleteAssignment = (schoolId: string, assignmentId: string) =>
  schoolFetch<void>(schoolId, `/academics/assignments/${assignmentId}`, { method: "DELETE" });

export const activateSession = (schoolId: string, sessionId: string) =>
  schoolFetch<unknown>(schoolId, `/academics/sessions/${sessionId}/activate`, { method: "POST" });

export const activateTerm = (schoolId: string, termId: string) =>
  schoolFetch<unknown>(schoolId, `/academics/terms/${termId}/activate`, { method: "POST" });

export const closeTerm = (schoolId: string, termId: string) =>
  schoolFetch<unknown>(schoolId, `/academics/terms/${termId}/close`, { method: "POST" });

export const fetchMyAssignments = (schoolId: string) =>
  schoolFetch<MyAssignment[]>(
    schoolId,
    "/academics/my-assignments",
    {},
    MyAssignmentSchema.array().parse,
  );

export const fetchStaffAssignments = (schoolId: string, staffId: string) =>
  schoolFetch<MyAssignment[]>(
    schoolId,
    `/staff/${staffId}/assignments`,
    {},
    MyAssignmentSchema.array().parse,
  );

export const enrollStudent = (schoolId: string, input: {
  student_id: string;
  arm_id: string;
  session_id: string;
}) =>
  schoolFetch<unknown>(schoolId, "/students/enrollments", {
    method: "POST",
    body: JSON.stringify(input),
  });

export const promoteStudents = (schoolId: string, input: PromotionRequest) =>
  schoolFetch<PromotionResult>(
    schoolId,
    "/students/promote",
    { method: "POST", body: JSON.stringify(input) },
    PromotionResultSchema.parse,
  );

export const changeStudentClass = (
  schoolId: string,
  studentId: string,
  input: { session_id: string; target_arm_id: string },
) =>
  schoolFetch<{ arm_id: string; arm_name: string }>(
    schoolId,
    `/students/${studentId}/class-change`,
    { method: "POST", body: JSON.stringify(input) },
    (d) => d as { arm_id: string; arm_name: string },
  );

export const deleteStudent = (schoolId: string, studentId: string) =>
  schoolFetch<void>(schoolId, `/students/${studentId}`, { method: "DELETE" });

export const uploadStudentPhoto = async (schoolId: string, file: File) => {
  const prepared = await prepareImageForUpload(file);
  const body = new FormData();
  body.append("file", prepared);
  const res = await fetchWithRefresh("/uploads/student-photo", {
    method: "POST",
    body,
    headers: { "X-School-Id": schoolId },
  });
  const data = res.ok ? await res.json() : await res.text();
  if (!res.ok) {
    const parsed = ApiErrorSchema.safeParse(typeof data === "string" ? null : data);
    throw new ApiClientError(
      res.status,
      parsed.success ? parsed.data : { error: { code: "ERR_INTERNAL", message: String(data) } },
    );
  }
  return (data as { photo_url: string }).photo_url;
};

// Keep the byte limit in sync with the API (storage_service.MAX_IMAGE_BYTES).
const MAX_IMAGE_BYTES = 5 * 1024 * 1024;
// Logos and student photos render small (sidebar, avatars, report cards);
// 640px covers retina/print while keeping the stored base64 a few KB.
const MAX_IMAGE_DIMENSION = 640;
const ALLOWED_IMAGE_TYPES = /^image\/(jpeg|png|webp)$/;

/**
 * Downscale + re-encode an image in the browser before upload so the base64
 * stored in the DB stays a few KB instead of the raw file size. Throws a
 * user-facing Error for disallowed types and files over the 5 MB limit.
 * Shared by logo and student-photo uploads (both are stored as data URLs).
 */
async function prepareImageForUpload(file: File): Promise<Blob> {
  if (!ALLOWED_IMAGE_TYPES.test(file.type)) {
    throw new Error("Only JPEG, PNG and WebP images are allowed");
  }
  if (file.size > MAX_IMAGE_BYTES) {
    throw new Error("Image is too large (max 5 MB)");
  }

  const bitmap = await createImageBitmap(file);
  try {
    const scale = Math.min(1, MAX_IMAGE_DIMENSION / Math.max(bitmap.width, bitmap.height));
    const width = Math.max(1, Math.round(bitmap.width * scale));
    const height = Math.max(1, Math.round(bitmap.height * scale));

    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    if (!ctx) return file; // defensive: canvas unavailable, send the original
    ctx.drawImage(bitmap, 0, 0, width, height);

    // WebP keeps alpha (PNG logos) and is small; fall back to JPEG for old browsers.
    const webp = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, "image/webp", 0.85)
    );
    if (webp) return webp;

    ctx.fillStyle = "#ffffff"; // white background so transparency isn't black in JPEG
    ctx.fillRect(0, 0, width, height);
    ctx.drawImage(bitmap, 0, 0, width, height);
    const jpeg = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, "image/jpeg", 0.9)
    );
    return jpeg ?? file;
  } finally {
    bitmap.close();
  }
}

export const uploadSchoolLogo = async (schoolId: string, file: File) => {
  const prepared = await prepareImageForUpload(file);
  const body = new FormData();
  body.append("file", prepared);
  const res = await fetchWithRefresh("/uploads/school-logo", {
    method: "POST",
    body,
    headers: { "X-School-Id": schoolId },
  });
  const data = res.ok ? await res.json() : await res.text();
  if (!res.ok) {
    const parsed = ApiErrorSchema.safeParse(typeof data === "string" ? null : data);
    throw new ApiClientError(
      res.status,
      parsed.success ? parsed.data : { error: { code: "ERR_INTERNAL", message: String(data) } },
    );
  }
  return (data as { photo_url: string }).photo_url;
};

export const fetchEnrollmentHistory = (schoolId: string, studentId: string) =>
  schoolFetch<EnrollmentHistoryRow[]>(
    schoolId,
    `/students/${studentId}/enrollments`,
    {},
    EnrollmentHistoryRowSchema.array().parse,
  );

// --- Fees / billing ------------------------------------------------------------------
export const fetchFeeStructures = (schoolId: string, activeOnly = true) =>
  schoolFetch<FeeStructure[]>(
    schoolId,
    `/fees/structures?active_only=${activeOnly}`,
    {},
    FeeStructureSchema.array().parse,
  );

export const createFeeStructure = (schoolId: string, input: FeeStructureIn) =>
  schoolFetch<FeeStructure>(
    schoolId,
    "/fees/structures",
    { method: "POST", body: JSON.stringify(input) },
    FeeStructureSchema.parse,
  );

export const toggleFeeStructure = (schoolId: string, structureId: string) =>
  schoolFetch<{ id: string; is_active: boolean; name: string }>(
    schoolId,
    `/fees/structures/${structureId}/toggle-status`,
    { method: "POST" },
    (d) => d as { id: string; is_active: boolean; name: string },
  );

export const fetchInvoices = (schoolId: string, studentId?: string) => {
  const q = studentId ? `?student_id=${studentId}` : "";
  return schoolFetch<Invoice[]>(
    schoolId,
    `/fees/invoices${q}`,
    {},
    InvoiceSchema.array().parse,
  );
};

export const createInvoice = (schoolId: string, input: InvoiceIn) =>
  schoolFetch<Invoice>(
    schoolId,
    "/fees/invoices",
    { method: "POST", body: JSON.stringify(input) },
    InvoiceSchema.parse,
  );

export const recordPayment = (schoolId: string, input: PaymentIn) =>
  schoolFetch<Payment>(
    schoolId,
    "/fees/payments",
    { method: "POST", body: JSON.stringify(input) },
    PaymentSchema.parse,
  );

export const fetchStudentFeeBalance = (schoolId: string, studentId: string) =>
  schoolFetch<StudentFeeBalance>(
    schoolId,
    `/fees/balances/${studentId}`,
    {},
    StudentFeeBalanceSchema.parse,
  );

export const fetchPayments = (schoolId: string, studentId?: string) => {
  const q = studentId ? `?student_id=${studentId}` : "";
  return schoolFetch<Payment[]>(
    schoolId,
    `/fees/payments${q}`,
    {},
    PaymentSchema.array().parse,
  );
};

export const fetchReceipt = (schoolId: string, paymentId: string) =>
  schoolFetch<Receipt>(
    schoolId,
    `/fees/payments/${paymentId}/receipt`,
    {},
    ReceiptSchema.parse,
  );

export const fetchFeeStatus = (
  schoolId: string,
  opts?: { termId?: string; armId?: string },
) => {
  const params = new URLSearchParams();
  if (opts?.termId) params.set("term_id", opts.termId);
  if (opts?.armId) params.set("arm_id", opts.armId);
  const q = params.toString() ? `?${params.toString()}` : "";
  return schoolFetch<PaymentStatus>(
    schoolId,
    `/fees/status${q}`,
    {},
    PaymentStatusSchema.parse,
  );
};

// --- Attendance ----------------------------------------------------------------------
export const markStudentAttendance = (schoolId: string, input: StudentAttendanceIn) =>
  schoolFetch<AttendanceRecord>(
    schoolId,
    "/attendance/mark/student",
    { method: "POST", body: JSON.stringify(input) },
    AttendanceRecordSchema.parse,
  );

export const markStaffAttendance = (schoolId: string, input: StaffAttendanceIn) =>
  schoolFetch<AttendanceRecord>(
    schoolId,
    "/attendance/mark/staff",
    { method: "POST", body: JSON.stringify(input) },
    AttendanceRecordSchema.parse,
  );

export const fetchStudentAttendance = (
  schoolId: string,
  studentId: string,
  startDate?: string,
  endDate?: string,
) => {
  const params = new URLSearchParams();
  if (startDate) params.set("start_date", startDate);
  if (endDate) params.set("end_date", endDate);
  const qs = params.toString() ? `?${params.toString()}` : "";
  return schoolFetch<AttendanceRecord[]>(
    schoolId,
    `/attendance/student/${studentId}${qs}`,
    {},
    AttendanceRecordSchema.array().parse,
  );
};

export const fetchStaffAttendance = (schoolId: string, staffId: string) =>
  schoolFetch<AttendanceRecord[]>(
    schoolId,
    `/attendance/staff/${staffId}`,
    {},
    AttendanceRecordSchema.array().parse,
  );

export const fetchStudentAttendanceSummary = (schoolId: string, studentId: string) =>
  schoolFetch<AttendanceSummary>(
    schoolId,
    `/attendance/summary/${studentId}`,
    {},
    AttendanceSummarySchema.parse,
  );

export const fetchStaffAttendanceSummary = (schoolId: string, staffId: string) =>
  schoolFetch<StaffAttendanceSummary>(
    schoolId,
    `/attendance/staff/summary/${staffId}`,
    {},
    StaffAttendanceSummarySchema.parse,
  );

// --- Result portal ------------------------------------------------------------------
export const setStudentPin = (schoolId: string, studentId: string, pin: string) =>
  schoolFetch<PinSetOut>(
    schoolId,
    `/students/${studentId}/pin`,
    { method: "PUT", body: JSON.stringify({ pin }) },
    PinSetOutSchema.parse,
  );

function postTransition(
  schoolId: string,
  cell: ResultCell,
  action: string,
  reason?: string,
): Promise<TransitionResult> {
  const body = reason !== undefined ? { ...cell, reason } : cell;
  return schoolFetch<TransitionResult>(
    schoolId,
    `/results/${action}`,
    { method: "POST", body: JSON.stringify(body) },
    TransitionResultSchema.parse,
  );
}

export type ResultAction = "verify" | "approve" | "publish" | "reject";

export function reviewResults(
  schoolId: string,
  action: ResultAction,
  cell: ResultCell,
  reason?: string,
): Promise<TransitionResult> {
  return postTransition(schoolId, cell, action, reason);
}

/** One-click compile: submit → verify → approve → publish. */
export function compileResults(
  schoolId: string,
  cell: ResultCell,
): Promise<CompileResult> {
  return schoolFetch<CompileResult>(
    schoolId,
    "/results/compile",
    { method: "POST", body: JSON.stringify(cell) },
    CompileResultSchema.parse,
  );
}

// --- School copilot -----------------------------------------------------------
export const fetchCopilotIntents = (schoolId: string) =>
  schoolFetch<CopilotIntent[]>(
    schoolId,
    "/copilot/intents",
    {},
    CopilotIntentSchema.array().parse,
  );

export const askCopilot = (schoolId: string, input: CopilotAsk) =>
  schoolFetch<AskResponse>(
    schoolId,
    "/copilot/ask",
    { method: "POST", body: JSON.stringify(input) },
    AskResponseSchema.parse,
  );

export const fetchConversations = (schoolId: string) =>
  schoolFetch<CopilotConversation[]>(
    schoolId,
    "/copilot/conversations",
    {},
    CopilotConversationSchema.array().parse,
  );

export const fetchConversation = (schoolId: string, conversationId: string) =>
  schoolFetch<CopilotConversationDetail>(
    schoolId,
    `/copilot/conversations/${conversationId}`,
    {},
    CopilotConversationDetailSchema.parse,
  );

// --- Payroll --------------------------------------------------------------------
export const fetchSalaryStructures = (schoolId: string, activeOnly = true) =>
  schoolFetch<SalaryStructure[]>(
    schoolId,
    `/payroll/structures?active_only=${activeOnly}`,
    {},
    SalaryStructureSchema.array().parse,
  );

export const createSalaryStructure = (schoolId: string, input: SalaryStructureIn) =>
  schoolFetch<SalaryStructure>(
    schoolId,
    "/payroll/structures",
    { method: "POST", body: JSON.stringify(input) },
    SalaryStructureSchema.parse,
  );

export const updateSalaryStructure = (
  schoolId: string,
  structureId: string,
  input: SalaryStructureIn,
) =>
  schoolFetch<SalaryStructure>(
    schoolId,
    `/payroll/structures/${structureId}`,
    { method: "PUT", body: JSON.stringify(input) },
    SalaryStructureSchema.parse,
  );

export const toggleSalaryStructure = (schoolId: string, structureId: string) =>
  schoolFetch<{ id: string; name: string; is_active: boolean }>(
    schoolId,
    `/payroll/structures/${structureId}/toggle-status`,
    { method: "POST" },
    (d) => d as { id: string; name: string; is_active: boolean },
  );

export const fetchStaffSalaries = (schoolId: string) =>
  schoolFetch<StaffSalaryOut[]>(
    schoolId,
    "/payroll/assignments",
    {},
    StaffSalaryOutSchema.array().parse,
  );

export const assignStaffSalary = (schoolId: string, input: StaffSalaryIn) =>
  schoolFetch<StaffSalaryOut>(
    schoolId,
    "/payroll/assignments",
    { method: "POST", body: JSON.stringify(input) },
    StaffSalaryOutSchema.parse,
  );

export const fetchPayRuns = (schoolId: string) =>
  schoolFetch<PayRun[]>(
    schoolId,
    "/payroll/runs",
    {},
    PayRunSchema.array().parse,
  );

export const createPayRun = (schoolId: string, input: PayRunCreate) =>
  schoolFetch<PayRunDetail>(
    schoolId,
    "/payroll/runs",
    { method: "POST", body: JSON.stringify(input) },
    PayRunDetailSchema.parse,
  );

export const fetchPayRun = (schoolId: string, payRunId: string) =>
  schoolFetch<PayRunDetail>(
    schoolId,
    `/payroll/runs/${payRunId}`,
    {},
    PayRunDetailSchema.parse,
  );

export const markPayRunPaid = (schoolId: string, payRunId: string) =>
  schoolFetch<PayRunDetail>(
    schoolId,
    `/payroll/runs/${payRunId}/mark-paid`,
    { method: "POST" },
    PayRunDetailSchema.parse,
  );

// --- Inventory --------------------------------------------------------------------
export const fetchInventoryCategories = (schoolId: string) =>
  schoolFetch<InventoryCategory[]>(
    schoolId,
    "/inventory/categories",
    {},
    InventoryCategorySchema.array().parse,
  );

export const createInventoryCategory = (schoolId: string, input: InventoryCategoryIn) =>
  schoolFetch<InventoryCategory>(
    schoolId,
    "/inventory/categories",
    { method: "POST", body: JSON.stringify(input) },
    InventoryCategorySchema.parse,
  );

export const updateInventoryCategory = (
  schoolId: string,
  categoryId: string,
  input: InventoryCategoryIn,
) =>
  schoolFetch<InventoryCategory>(
    schoolId,
    `/inventory/categories/${categoryId}`,
    { method: "PUT", body: JSON.stringify(input) },
    InventoryCategorySchema.parse,
  );

export const fetchInventoryItems = (schoolId: string, lowStockOnly = false) =>
  schoolFetch<InventoryItem[]>(
    schoolId,
    `/inventory/items?low_stock_only=${lowStockOnly}`,
    {},
    InventoryItemSchema.array().parse,
  );

export const createInventoryItem = (schoolId: string, input: InventoryItemIn) =>
  schoolFetch<InventoryItem>(
    schoolId,
    "/inventory/items",
    { method: "POST", body: JSON.stringify(input) },
    InventoryItemSchema.parse,
  );

export const updateInventoryItem = (schoolId: string, itemId: string, input: InventoryItemIn) =>
  schoolFetch<InventoryItem>(
    schoolId,
    `/inventory/items/${itemId}`,
    { method: "PUT", body: JSON.stringify(input) },
    InventoryItemSchema.parse,
  );

export const recordStockMovement = (schoolId: string, input: StockMovementIn) =>
  schoolFetch<StockMovement>(
    schoolId,
    "/inventory/movements",
    { method: "POST", body: JSON.stringify(input) },
    StockMovementSchema.parse,
  );

export const fetchStockMovements = (schoolId: string, itemId?: string) => {
  const q = itemId ? `?item_id=${itemId}` : "";
  return schoolFetch<StockMovement[]>(
    schoolId,
    `/inventory/movements${q}`,
    {},
    StockMovementSchema.array().parse,
  );
};

// --- Library ----------------------------------------------------------------------
export const fetchBooks = (schoolId: string, availableOnly = false) =>
  schoolFetch<Book[]>(
    schoolId,
    `/library/books?available_only=${availableOnly}`,
    {},
    BookSchema.array().parse,
  );

export const createBook = (schoolId: string, input: BookIn) =>
  schoolFetch<Book>(
    schoolId,
    "/library/books",
    { method: "POST", body: JSON.stringify(input) },
    BookSchema.parse,
  );

export const updateBook = (schoolId: string, bookId: string, input: BookIn) =>
  schoolFetch<Book>(
    schoolId,
    `/library/books/${bookId}`,
    { method: "PUT", body: JSON.stringify(input) },
    BookSchema.parse,
  );

export const fetchBorrowings = (schoolId: string, opts: { status?: string; overdue?: boolean } = {}) => {
  const params = new URLSearchParams();
  if (opts.status) params.set("status", opts.status);
  if (opts.overdue) params.set("overdue", "true");
  const q = params.toString();
  return schoolFetch<Borrowing[]>(
    schoolId,
    `/library/borrowings${q ? `?${q}` : ""}`,
    {},
    BorrowingSchema.array().parse,
  );
};

export const checkOutBook = (schoolId: string, input: BorrowingIn) =>
  schoolFetch<Borrowing>(
    schoolId,
    "/library/borrowings",
    { method: "POST", body: JSON.stringify(input) },
    BorrowingSchema.parse,
  );

export const returnBook = (schoolId: string, borrowingId: string) =>
  schoolFetch<Borrowing>(
    schoolId,
    `/library/borrowings/${borrowingId}/return`,
    { method: "POST", body: JSON.stringify({}) },
    BorrowingSchema.parse,
  );

export const fetchDashboardSummary = (schoolId: string, termId?: string) => {
  const q = termId ? `?term_id=${termId}` : "";
  return schoolFetch<DashboardSummary>(
    schoolId,
    `/dashboard/summary${q}`,
    {},
    DashboardSummarySchema.parse,
  );
};

export const api = {
  registerSchool,
  login,
  logout,
  me,
  refresh,
  requestPasswordReset,
  confirmPasswordReset,
  changePassword,
  changeEmail,
  fetchSchoolMe,
  updateSchool,
  fetchPlatformSchools,
  setSchoolAi,
  setSchoolSuspended,
  createSchoolAdmin,
  fetchPlatformTeachers,
  superAdminOverview,
  superAdminGrowth,
  superAdminRevenue,
  superAdminSubscriptions,
  superAdminAi,
  superAdminUsers,
  superAdminEngagement,
  superAdminGeo,
  superAdminActivity,
  superAdminHealth,
  superAdminSchools,
  superAdminSchool,
  superAdminAddSchool,
  superAdminUpdateSubscription,
  superAdminResetAdmin,
  superAdminImpersonate,
  superAdminDeleteSchool,
  impersonateEnter,
  impersonateExit,
  superAdminIssues,
  superAdminTickets,
  superAdminCreateTicket,
  superAdminUpdateTicket,
  superAdminNotifications,
  superAdminMarkNotificationsRead,
  superAdminAudit,
  superAdminSettings,
  superAdminUpdateSettings,
  superAdminAnnouncements,
  superAdminCreateAnnouncement,
  schoolFetch,
  fetchScoreCard,
  fetchWorkbench,
  fetchReportIndex,
  fetchReportCard,
  fetchReportCards,
  fetchResultComment,
  generateResultComment,
  generateRoleComment,
  previewRoleComment,
  saveRoleComment,
  fetchCommentBank,
  createCommentBankEntry,
  updateCommentBankEntry,
  deactivateCommentBankEntry,
  fetchBestInSubjects,
  fetchGradeBands,
  fetchPsychomotor,
  savePsychomotor,
  fetchLessonPlan,
  generateLessonPlan,
  fetchQuestionBank,
  generateQuestionBank,
  setStudentPin,
  publicSchools,
  pinCheck,
  publicReportCard,
  reviewResults,
  compileResults,
  fetchCopilotIntents,
  askCopilot,
  fetchConversations,
  fetchConversation,
  fetchTimeSlots,
  generateSchedule,
  fetchWeeklySchedule,
  validateSchedule,
  fetchFeeStructures,
  createFeeStructure,
  toggleFeeStructure,
  fetchInvoices,
  createInvoice,
  recordPayment,
  fetchStudentFeeBalance,
  fetchPayments,
  fetchReceipt,
  fetchFeeStatus,
  markStudentAttendance,
  markStaffAttendance,
  fetchStudentAttendance,
  fetchStaffAttendance,
  fetchStudentAttendanceSummary,
  fetchStaffAttendanceSummary,
  fetchSalaryStructures,
  createSalaryStructure,
  updateSalaryStructure,
  toggleSalaryStructure,
  fetchStaffSalaries,
  assignStaffSalary,
  fetchPayRuns,
  createPayRun,
  fetchPayRun,
  markPayRunPaid,
  fetchInventoryCategories,
  createInventoryCategory,
  updateInventoryCategory,
  fetchInventoryItems,
  createInventoryItem,
  updateInventoryItem,
  recordStockMovement,
  fetchStockMovements,
  fetchBooks,
  createBook,
  updateBook,
  fetchBorrowings,
  checkOutBook,
  returnBook,
  createStaff,
  createStaffAccount,
  updateStaffAccount,
  deleteStaff,
  fetchRoles,
  createAssignment,
  deleteAssignment,
  fetchMyAssignments,
  fetchStaffAssignments,
  enrollStudent,
  promoteStudents,
  changeStudentClass,
  deleteStudent,
  uploadStudentPhoto,
  uploadSchoolLogo,
  activateSession,
  activateTerm,
  closeTerm,
  fetchEnrollmentHistory,
  fetchDashboardSummary,
};
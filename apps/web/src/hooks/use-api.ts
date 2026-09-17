"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type {
  AcademicSession,
  Arm,
  AskResponse,
  AssessmentComponent,
  Assignment,
  AssignmentCreate,
  AttendanceRecord,
  AttendanceSummary,
  Book,
  BookIn,
  Borrowing,
  BorrowingIn,
  CompileResult,
  CopilotAsk,
  CopilotConversation,
  CopilotConversationDetail,
  CopilotIntent,
  CopilotMessage,
  FeeStructure,
  FeeStructureIn,
  InventoryCategory,
  InventoryCategoryIn,
  InventoryItem,
  InventoryItemIn,
  Invoice,
  InvoiceIn,
  MyAssignment,
  Offering,
  Overview,
  Payment,
  PaymentIn,
  PaymentStatus,
  Receipt,
  PayRun,
  PayRunCreate,
  PayRunDetail,
  PromotionRequest,
  ReadyRow,
  ReportCard,
  ReportIndexRow,
  ResultCell,
  ResultComment,
  CommentBankEntry,
  BestInSubjectRow,
  GradeBandRow,
  PsychomotorRow,
  LessonPlanInput,
  QuestionBankInput,
  RoleDetail,
  ScheduleGenerateIn,
  School,
  ScoreCard,
  SalaryStructure,
  SalaryStructureIn,
  Staff,
  StaffAccountCreate,
  StaffAccountUpdate,
  StaffCreate,
  StaffAttendanceIn,
  StaffAttendanceSummary,
  StaffSalaryIn,
  StaffSalaryOut,
  StockMovementIn,
  Student,
  StudentAttendanceIn,
  StudentFeeBalance,
  Subject,
  Term,
  TimeSlot,
  WeekScheduleOut,
  WorkbenchRow,
  SchoolAdminCreate,
  AccountingSummary,
  Accountant,
  AccountantIn,
  CashAccount,
  CashAccountIn,
  Cashbook,
  CashPosition,
  CollectionReport,
  CreditNote,
  CreditNoteIn,
  Debtors,
  Discount,
  DiscountIn,
  Expense,
  ExpenseCategory,
  ExpenseIn,
  ExpenseList,
  IncomeExpenditure,
  ReceiptEmailResult,
  Refund,
  RefundIn,
} from "@clearis/shared";

import { api, reviewResults, compileResults, type ResultAction } from "@clearis/shared";
import { useAuth } from "@/providers/auth-provider";

export function useCanComment(): boolean {
  const { activeSchool } = useAuth();
  return activeSchool?.permissions?.includes("results.comment") ?? false;
}

export function useCanCopilot(): boolean {
  const { activeSchool } = useAuth();
  return activeSchool?.permissions?.includes("ai.copilot") ?? false;
}

export function useActiveSchoolId(): string | null {
  const { activeSchool } = useAuth();
  return activeSchool?.school_id ?? null;
}

export interface UseApiOptions {
  enabled?: boolean;
}

export function useSchoolMe() {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["school", schoolId],
    enabled: !!schoolId,
    queryFn: async () => api.schoolFetch<School>(schoolId!, "/schools/me"),
  });
}

export function usePromoteStudents() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: PromotionRequest) => {
      if (!schoolId) throw new Error("No active school");
      return api.promoteStudents(schoolId, input);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["students", schoolId] });
      queryClient.invalidateQueries({ queryKey: ["enrollment-history", schoolId] });
    },
  });
}

export function useEnrollStudent() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { student_id: string; arm_id: string; session_id: string }) => {
      if (!schoolId) throw new Error("No active school");
      return api.enrollStudent(schoolId, input);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["students", schoolId] });
      queryClient.invalidateQueries({ queryKey: ["enrollment-history", schoolId] });
    },
  });
}

export function useEnrollmentHistory(studentId: string | null) {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["enrollment-history", schoolId, studentId],
    enabled: !!schoolId && !!studentId,
    queryFn: async () => api.fetchEnrollmentHistory(schoolId!, studentId!),
  });
}

export function useOverview() {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["overview", schoolId],
    enabled: !!schoolId,
    queryFn: async () => api.schoolFetch<Overview>(schoolId!, "/schools/me/overview"),
  });
}

export function useSessions() {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["sessions", schoolId],
    enabled: !!schoolId,
    queryFn: async () =>
      api.schoolFetch<AcademicSession[]>(schoolId!, "/academics/sessions"),
  });
}

export function useTerms(sessionId: string | null) {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["terms", schoolId, sessionId],
    enabled: !!schoolId && !!sessionId,
    queryFn: async () =>
      api.schoolFetch<Term[]>(schoolId!, `/academics/sessions/${sessionId}/terms`),
  });
}

export function useCloseTerm() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (termId: string) => {
      if (!schoolId) throw new Error("No active school");
      return api.closeTerm(schoolId, termId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["terms", schoolId] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary", schoolId] });
    },
  });
}

export function useOfferings(armId: string | null) {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["offerings", schoolId, armId],
    enabled: !!schoolId && !!armId,
    queryFn: async () =>
      api.schoolFetch<Offering[]>(schoolId!, `/academics/arms/${armId}/offerings`),
  });
}

export function useSubjects() {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["subjects", schoolId],
    enabled: !!schoolId,
    queryFn: async () =>
      api.schoolFetch<Subject[]>(schoolId!, "/academics/subjects"),
  });
}

export function useArms(sessionId: string | null) {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["arms", schoolId, sessionId],
    enabled: !!schoolId && !!sessionId,
    queryFn: async () =>
      api.schoolFetch<Arm[]>(schoolId!, `/academics/sessions/${sessionId}/arms`),
  });
}

export function useAssignments(armId: string | null) {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["assignments", schoolId, armId],
    enabled: !!schoolId && !!armId,
    queryFn: async () =>
      api.schoolFetch<Assignment[]>(schoolId!, `/academics/arms/${armId}/assignments`),
  });
}

export function useComponents(termId: string | null, armId: string | null) {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["components", schoolId, termId, armId],
    enabled: !!schoolId && !!termId,
    queryFn: async () => {
      const q = armId ? `&arm_id=${armId}` : "";
      return api.schoolFetch<AssessmentComponent[]>(
        schoolId!,
        `/results/components?term_id=${termId}${q}`,
      );
    },
  });
}

export function useStudents(options: UseApiOptions = {}) {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["students", schoolId],
    enabled: !!schoolId && options.enabled !== false,
    queryFn: async () => api.schoolFetch<Student[]>(schoolId!, "/students"),
  });
}

export function useRoster(armId: string | null) {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["roster", schoolId, armId],
    enabled: !!schoolId && !!armId,
    queryFn: async () => api.schoolFetch<Student[]>(schoolId!, `/students?arm_id=${armId}`),
  });
}

export function useChangeStudentClass() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      studentId,
      sessionId,
      targetArmId,
    }: {
      studentId: string;
      sessionId: string;
      targetArmId: string;
    }) => {
      if (!schoolId) throw new Error("No active school");
      return api.changeStudentClass(schoolId, studentId, {
        session_id: sessionId,
        target_arm_id: targetArmId,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["roster", schoolId] });
      queryClient.invalidateQueries({ queryKey: ["students", schoolId] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary", schoolId] });
    },
  });
}

export function useUpdateStudent() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ studentId, data }: { studentId: string; data: Record<string, unknown> }) => {
      if (!schoolId) throw new Error("No active school");
      return api.schoolFetch(schoolId, `/students/${studentId}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      });
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["students"] });
    },
  });
}

export function useDeleteStudent() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (studentId: string) => {
      if (!schoolId) throw new Error("No active school");
      return api.deleteStudent(schoolId, studentId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["roster", schoolId] });
      queryClient.invalidateQueries({ queryKey: ["students", schoolId] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary", schoolId] });
    },
  });
}

export function useStaff(options: UseApiOptions = {}) {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["staff", schoolId],
    enabled: !!schoolId && options.enabled !== false,
    queryFn: async () => api.schoolFetch<Staff[]>(schoolId!, "/staff"),
  });
}

export function useCreateStaff() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: StaffCreate) => {
      if (!schoolId) throw new Error("No active school");
      return api.createStaff(schoolId, input);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["staff", schoolId] });
    },
  });
}

export function useCreateStaffAccount() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ staffId, input }: { staffId: string; input: StaffAccountCreate }) => {
      if (!schoolId) throw new Error("No active school");
      return api.createStaffAccount(schoolId, staffId, input);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["staff", schoolId] });
    },
  });
}

export function useUpdateStaff() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ staffId, data }: { staffId: string; data: Record<string, unknown> }) => {
      if (!schoolId) throw new Error("No active school");
      return api.schoolFetch(schoolId, `/staff/${staffId}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      });
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["staff", schoolId] });
    },
  });
}

export function useUpdateStaffAccount() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ staffId, input }: { staffId: string; input: StaffAccountUpdate }) => {
      if (!schoolId) throw new Error("No active school");
      return api.updateStaffAccount(schoolId, staffId, input);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["staff", schoolId] });
    },
  });
}

export function useDeleteStaff() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (staffId: string) => {
      if (!schoolId) throw new Error("No active school");
      return api.deleteStaff(schoolId, staffId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["staff", schoolId] });
    },
  });
}

export function useRoles() {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["roles", schoolId],
    enabled: !!schoolId,
    queryFn: async () => api.fetchRoles(schoolId!),
  });
}

export function useMyAssignments(options: UseApiOptions = {}) {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["my-assignments", schoolId],
    enabled: !!schoolId && options.enabled !== false,
    queryFn: async () => api.fetchMyAssignments(schoolId!),
  });
}

export function useStaffAssignments(staffId: string | null, enabled = true) {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["staff-assignments", schoolId, staffId],
    enabled: !!schoolId && !!staffId && enabled,
    queryFn: async () => api.fetchStaffAssignments(schoolId!, staffId!),
  });
}

export function useCreateAssignment() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: AssignmentCreate) => {
      if (!schoolId) throw new Error("No active school");
      return api.createAssignment(schoolId, input);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["assignments", schoolId] });
      queryClient.invalidateQueries({ queryKey: ["my-assignments", schoolId] });
    },
  });
}

export function useDeleteAssignment() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (assignmentId: string) => {
      if (!schoolId) throw new Error("No active school");
      return api.deleteAssignment(schoolId, assignmentId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["assignments", schoolId] });
      queryClient.invalidateQueries({ queryKey: ["my-assignments", schoolId] });
    },
  });
}

export function useReadiness(termId: string | null) {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["readiness", schoolId, termId],
    enabled: !!schoolId && !!termId,
    queryFn: async () =>
      api.schoolFetch<ReadyRow[]>(schoolId!, `/results/readiness?term_id=${termId}`),
  });
}

export function useScoreCard(armId: string | null, subjectId: string | null, termId: string | null) {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["scorecard", schoolId, armId, subjectId, termId],
    enabled: !!schoolId && !!armId && !!subjectId && !!termId,
    queryFn: async () =>
      api.schoolFetch<ScoreCard>(
        schoolId!,
        `/results/scorecard?arm_id=${armId}&subject_id=${subjectId}&term_id=${termId}`,
      ),
  });
}

export function useWorkbench(termId: string | null) {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["workbench", schoolId, termId],
    enabled: !!schoolId && !!termId,
    queryFn: async () => api.fetchWorkbench(schoolId!, termId!),
  });
}

export function useReportIndex(armId: string | null, termId: string | null) {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["report-index", schoolId, armId, termId],
    enabled: !!schoolId && !!armId && !!termId,
    queryFn: async () => api.fetchReportIndex(schoolId!, armId!, termId!),
  });
}

export function useReportCard(studentId: string | null, termId: string | null) {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["report-card", schoolId, studentId, termId],
    enabled: !!schoolId && !!studentId && !!termId,
    queryFn: async () => api.fetchReportCard(schoolId!, studentId!, termId!),
  });
}

export function useReportCards(armId: string | null, termId: string | null) {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["report-cards", schoolId, armId, termId],
    enabled: !!schoolId && !!armId && !!termId,
    queryFn: async () => api.fetchReportCards(schoolId!, armId!, termId!),
  });
}

export function useResultComment(studentId: string | null, termId: string | null) {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["result-comment", schoolId, studentId, termId],
    enabled: !!schoolId && !!studentId && !!termId,
    queryFn: async () => api.fetchResultComment(schoolId!, studentId!, termId!),
    retry: false, // 404 = not generated yet; don't retry a clean absence
  });
}

export function useGenerateResultComment() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ studentId, termId }: { studentId: string; termId: string }) => {
      if (!schoolId) throw new Error("No active school");
      return api.generateResultComment(schoolId, studentId, termId);
    },
    onSuccess: (_, { studentId, termId }) => {
      queryClient.invalidateQueries({ queryKey: ["result-comment", schoolId, studentId, termId] });
    },
  });
}

export type CommentRole = "principal" | "vice_principal" | "homeroom";

export const COMMENT_ROLES: { key: CommentRole; label: string }[] = [
  { key: "principal", label: "Principal" },
  { key: "vice_principal", label: "Vice Principal" },
  { key: "homeroom", label: "Homeroom Teacher" },
];

/** One role's stored comment for a student × term (404 = not saved yet). */
export function useRoleComment(
  studentId: string | null,
  termId: string | null,
  role: CommentRole,
) {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["role-comment", schoolId, studentId, termId, role],
    enabled: !!schoolId && !!studentId && !!termId,
    queryFn: async () =>
      api.schoolFetch<ResultComment>(
        schoolId!,
        `/results/${studentId}/comment?term_id=${termId}&role=${role}`,
        {},
        undefined,
      ),
    retry: false,
  });
}

/** Persist AI generation for one role (revision bump, metered). */
export function useGenerateRoleComment(studentId: string | null, termId: string | null) {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { role: CommentRole; focus?: string | null; tone?: string }) => {
      if (!schoolId || !studentId || !termId) throw new Error("Missing comment context");
      return api.generateRoleComment(schoolId, studentId, {
        term_id: termId,
        role: body.role,
        focus: body.focus,
        tone: body.tone,
      });
    },
    onSuccess: (_, { role }) => {
      queryClient.invalidateQueries({ queryKey: ["role-comment", schoolId, studentId, termId, role] });
      queryClient.invalidateQueries({ queryKey: ["report-card", schoolId, studentId, termId] });
    },
  });
}

/** Non-persisted AI draft for review in the comment modal. */
export function usePreviewRoleComment() {
  const schoolId = useActiveSchoolId();
  return useMutation({
    mutationFn: (body: {
      studentId: string;
      termId: string;
      role: CommentRole;
      focus?: string | null;
      tone?: string;
    }) => {
      if (!schoolId) throw new Error("No active school");
      return api.previewRoleComment(schoolId, body.studentId, {
        term_id: body.termId,
        role: body.role,
        focus: body.focus,
        tone: body.tone,
      });
    },
  });
}

/** Persist a manually written/edited comment for one role. */
export function useSaveRoleComment(studentId: string | null, termId: string | null) {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { role: CommentRole; body: string }) => {
      if (!schoolId || !studentId || !termId) throw new Error("Missing comment context");
      return api.saveRoleComment(schoolId, studentId, {
        term_id: termId,
        role: body.role,
        body: body.body,
      });
    },
    onSuccess: (_, { role }) => {
      queryClient.invalidateQueries({ queryKey: ["role-comment", schoolId, studentId, termId, role] });
      queryClient.invalidateQueries({ queryKey: ["report-card", schoolId, studentId, termId] });
    },
  });
}

/** School comment bank (search + filter). */
export function useCommentBank(filters: {
  category?: string;
  sentiment?: string;
  search?: string;
}) {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["comment-bank", schoolId, filters],
    enabled: !!schoolId,
    queryFn: async () => api.fetchCommentBank(schoolId!, filters),
  });
}

export function useCreateCommentBankEntry() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      comment_text: string;
      category: string;
      sentiment: string;
      applicable_domain?: string | null;
    }) => {
      if (!schoolId) throw new Error("No active school");
      return api.createCommentBankEntry(schoolId, body);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["comment-bank"] }),
  });
}

export function useDeactivateCommentBankEntry() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (entryId: string) => {
      if (!schoolId) throw new Error("No active school");
      return api.deactivateCommentBankEntry(schoolId, entryId);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["comment-bank"] }),
  });
}

/** Core-subject leadership: who is best in each subject this term. */
export function useBestInSubjects(armId: string | null, termId: string | null) {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["best-in-subjects", schoolId, armId, termId],
    enabled: !!schoolId && !!armId && !!termId,
    queryFn: async () => api.fetchBestInSubjects(schoolId!, armId!, termId!),
  });
}

/** Grading key for a term (live grade previews during score entry). */
export function useGradeBands(termId: string | null) {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["grade-bands", schoolId, termId],
    enabled: !!schoolId && !!termId,
    queryFn: async () => api.fetchGradeBands(schoolId!, termId!),
  });
}

/** Psychomotor/affective rows for one student × term. */
export function usePsychomotor(studentId: string | null, termId: string | null) {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["psychomotor", schoolId, studentId, termId],
    enabled: !!schoolId && !!studentId && !!termId,
    queryFn: async () => api.fetchPsychomotor(schoolId!, studentId!, termId!),
  });
}

export function useSavePsychomotor(studentId: string | null, termId: string | null) {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (rows: { learning_area: string; achievement_level: string }[]) => {
      if (!schoolId || !studentId || !termId) throw new Error("Missing psychomotor context");
      return api.savePsychomotor(schoolId, { student_id: studentId, term_id: termId, rows });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["psychomotor", schoolId, studentId, termId] });
      queryClient.invalidateQueries({ queryKey: ["report-card", schoolId, studentId, termId] });
    },
  });
}

/** Result-entry capability (teachers with an assignment). */
export function useCanEnterResults(): boolean {
  const { activeSchool } = useAuth();
  return activeSchool?.permissions?.includes("results.enter") ?? false;
}

export function useLessonPlan(
  subjectId: string | null,
  classArmId: string | null,
  termId: string | null,
  topic: string | null,
) {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["lesson-plan", schoolId, subjectId, classArmId, termId, topic],
    enabled: !!schoolId && !!subjectId && !!classArmId && !!termId && !!topic,
    queryFn: async () =>
      api.fetchLessonPlan(schoolId!, subjectId!, classArmId!, termId!, topic!),
    retry: false, // 404 = not generated yet; don't retry a clean absence
  });
}

export function useGenerateLessonPlan() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: LessonPlanInput) => {
      if (!schoolId) throw new Error("No active school");
      return api.generateLessonPlan(schoolId, input);
    },
    onSuccess: (_, input) => {
      queryClient.invalidateQueries({
        queryKey: [
          "lesson-plan",
          schoolId,
          input.subject_id,
          input.class_arm_id,
          input.term_id,
          input.topic,
        ],
      });
    },
  });
}

export function useQuestionBank(
  subjectId: string | null,
  classArmId: string | null,
  termId: string | null,
  topic: string | null,
) {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["question-bank", schoolId, subjectId, classArmId, termId, topic],
    enabled: !!schoolId && !!subjectId && !!classArmId && !!termId && !!topic,
    queryFn: async () =>
      api.fetchQuestionBank(schoolId!, subjectId!, classArmId!, termId!, topic!),
    retry: false, // 404 = not generated yet; don't retry a clean absence
  });
}

export function useGenerateQuestionBank() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: QuestionBankInput) => {
      if (!schoolId) throw new Error("No active school");
      return api.generateQuestionBank(schoolId, input);
    },
    onSuccess: (_, input) => {
      queryClient.invalidateQueries({
        queryKey: [
          "question-bank",
          schoolId,
          input.subject_id,
          input.class_arm_id,
          input.term_id,
          input.topic,
        ],
      });
    },
  });
}

export function useTimeSlots() {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["time-slots", schoolId],
    enabled: !!schoolId,
    queryFn: async () => api.fetchTimeSlots(schoolId!),
  });
}

export function useWeeklySchedule(armId: string | null, sessionId: string | null) {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["timetable", schoolId, armId, sessionId],
    enabled: !!schoolId && !!armId,
    queryFn: async () => api.fetchWeeklySchedule(schoolId!, armId!, sessionId ?? undefined),
  });
}

export function useGenerateSchedule() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: ScheduleGenerateIn) => {
      if (!schoolId) throw new Error("No active school");
      return api.generateSchedule(schoolId, input);
    },
    onSuccess: (_, input) => {
      queryClient.invalidateQueries({ queryKey: ["timetable", schoolId] });
    },
  });
}

// --- Fees / billing -----------------------------------------------------------
export function useFeeStructures() {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["fee-structures", schoolId],
    enabled: !!schoolId,
    queryFn: async () => api.fetchFeeStructures(schoolId!),
  });
}

export function useCreateFeeStructure() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: FeeStructureIn) => {
      if (!schoolId) throw new Error("No active school");
      return api.createFeeStructure(schoolId, input);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["fee-structures", schoolId] });
    },
  });
}

export function useToggleFeeStructure() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (structureId: string) => {
      if (!schoolId) throw new Error("No active school");
      return api.toggleFeeStructure(schoolId, structureId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["fee-structures", schoolId] });
    },
  });
}

export function useInvoices(studentId: string | null) {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["invoices", schoolId, studentId],
    enabled: !!schoolId,
    queryFn: async () => api.fetchInvoices(schoolId!, studentId ?? undefined),
  });
}

export function useCreateInvoice() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: InvoiceIn) => {
      if (!schoolId) throw new Error("No active school");
      return api.createInvoice(schoolId, input);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["invoices", schoolId] });
      queryClient.invalidateQueries({ queryKey: ["fee-balances", schoolId] });
    },
  });
}

export function useRecordPayment() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: PaymentIn) => {
      if (!schoolId) throw new Error("No active school");
      return api.recordPayment(schoolId, input);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["invoices", schoolId] });
      queryClient.invalidateQueries({ queryKey: ["fee-balances", schoolId] });
    },
  });
}

export function useStudentFeeBalance(studentId: string | null) {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["fee-balances", schoolId, studentId],
    enabled: !!schoolId && !!studentId,
    queryFn: async () => api.fetchStudentFeeBalance(schoolId!, studentId!),
  });
}

export function usePayments(studentId?: string) {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["payments", schoolId, studentId],
    enabled: !!schoolId,
    queryFn: async () => api.fetchPayments(schoolId!, studentId),
  });
}

export function useReceipt(paymentId: string | null) {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["receipt", schoolId, paymentId],
    enabled: !!schoolId && !!paymentId,
    queryFn: async () => api.fetchReceipt(schoolId!, paymentId!),
  });
}

export function useFeeStatus(opts?: { termId?: string; armId?: string }) {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["fee-status", schoolId, opts?.termId ?? null, opts?.armId ?? null],
    enabled: !!schoolId,
    queryFn: async () => api.fetchFeeStatus(schoolId!, opts),
  });
}

// --- Accounting (Accountant's desk) ------------------------------------------------

export function useAccountingSummary(termId?: string) {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["accounting-summary", schoolId, termId ?? null],
    enabled: !!schoolId,
    queryFn: async () => api.fetchAccountingSummary(schoolId!, termId),
  });
}

export function useCashAccounts(activeOnly = false) {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["cash-accounts", schoolId, activeOnly],
    enabled: !!schoolId,
    queryFn: async () => api.fetchCashAccounts(schoolId!, activeOnly),
  });
}

export function useCreateCashAccount() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CashAccountIn) => {
      if (!schoolId) throw new Error("No active school");
      return api.createCashAccount(schoolId, input);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["cash-accounts", schoolId] });
      queryClient.invalidateQueries({ queryKey: ["cash-position", schoolId] });
    },
  });
}

export function useUpdateCashAccount() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ accountId, input }: { accountId: string; input: CashAccountIn }) => {
      if (!schoolId) throw new Error("No active school");
      return api.updateCashAccount(schoolId, accountId, input);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["cash-accounts", schoolId] });
      queryClient.invalidateQueries({ queryKey: ["cash-position", schoolId] });
    },
  });
}

export function useExpenseCategories(activeOnly = false) {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["expense-categories", schoolId, activeOnly],
    enabled: !!schoolId,
    queryFn: async () => api.fetchExpenseCategories(schoolId!, activeOnly),
  });
}

export function useCreateExpenseCategory() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { name: string; description?: string | null }) => {
      if (!schoolId) throw new Error("No active school");
      return api.createExpenseCategory(schoolId, input);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["expense-categories", schoolId] });
    },
  });
}

export function useExpenses(opts?: {
  status?: string;
  categoryId?: string;
  termId?: string;
  dateFrom?: string;
  dateTo?: string;
}) {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["expenses", schoolId, JSON.stringify(opts ?? {})],
    enabled: !!schoolId,
    queryFn: async () => api.fetchExpenses(schoolId!, opts),
  });
}

function useAccountingInvalidate() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return () => {
    for (const key of [
      "expenses",
      "cashbook",
      "accounting-summary",
      "cash-position",
      "income-expenditure",
      "collection-report",
      "debtors",
    ]) {
      queryClient.invalidateQueries({ queryKey: [key, schoolId] });
    }
  };
}

export function useCreateExpense() {
  const schoolId = useActiveSchoolId();
  const invalidate = useAccountingInvalidate();
  return useMutation({
    mutationFn: (input: ExpenseIn) => {
      if (!schoolId) throw new Error("No active school");
      return api.createExpense(schoolId, input);
    },
    onSuccess: invalidate,
  });
}

export function useUpdateExpense() {
  const schoolId = useActiveSchoolId();
  const invalidate = useAccountingInvalidate();
  return useMutation({
    mutationFn: ({ expenseId, input }: { expenseId: string; input: ExpenseIn }) => {
      if (!schoolId) throw new Error("No active school");
      return api.updateExpense(schoolId, expenseId, input);
    },
    onSuccess: invalidate,
  });
}

export function useApproveExpense() {
  const schoolId = useActiveSchoolId();
  const invalidate = useAccountingInvalidate();
  return useMutation({
    mutationFn: (expenseId: string) => {
      if (!schoolId) throw new Error("No active school");
      return api.approveExpense(schoolId, expenseId);
    },
    onSuccess: invalidate,
  });
}

export function useRejectExpense() {
  const schoolId = useActiveSchoolId();
  const invalidate = useAccountingInvalidate();
  return useMutation({
    mutationFn: ({ expenseId, reason }: { expenseId: string; reason?: string }) => {
      if (!schoolId) throw new Error("No active school");
      return api.rejectExpense(schoolId, expenseId, reason);
    },
    onSuccess: invalidate,
  });
}

export function usePayExpense() {
  const schoolId = useActiveSchoolId();
  const invalidate = useAccountingInvalidate();
  return useMutation({
    mutationFn: (expenseId: string) => {
      if (!schoolId) throw new Error("No active school");
      return api.payExpense(schoolId, expenseId);
    },
    onSuccess: invalidate,
  });
}

export function useDeleteExpense() {
  const schoolId = useActiveSchoolId();
  const invalidate = useAccountingInvalidate();
  return useMutation({
    mutationFn: (expenseId: string) => {
      if (!schoolId) throw new Error("No active school");
      return api.deleteExpense(schoolId, expenseId);
    },
    onSuccess: invalidate,
  });
}

export function useCashbook(opts?: {
  cashAccountId?: string;
  dateFrom?: string;
  dateTo?: string;
  onlyUnreconciled?: boolean;
}) {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["cashbook", schoolId, JSON.stringify(opts ?? {})],
    enabled: !!schoolId,
    queryFn: async () => api.fetchCashbook(schoolId!, opts),
  });
}

export function useReconcileCashbookEntry() {
  const schoolId = useActiveSchoolId();
  const invalidate = useAccountingInvalidate();
  return useMutation({
    mutationFn: (input: {
      source_type: "payment" | "expense" | "refund";
      source_id: string;
      reconciled: boolean;
      bank_reference?: string | null;
    }) => {
      if (!schoolId) throw new Error("No active school");
      return api.reconcileCashbookEntry(schoolId, input);
    },
    onSuccess: invalidate,
  });
}

export function useDiscounts(opts?: { studentId?: string; activeOnly?: boolean }) {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["discounts", schoolId, JSON.stringify(opts ?? {})],
    enabled: !!schoolId,
    queryFn: async () => api.fetchDiscounts(schoolId!, opts),
  });
}

export function useCreateDiscount() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: DiscountIn) => {
      if (!schoolId) throw new Error("No active school");
      return api.createDiscount(schoolId, input);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["discounts", schoolId] });
    },
  });
}

export function useUpdateDiscount() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ discountId, input }: { discountId: string; input: DiscountIn }) => {
      if (!schoolId) throw new Error("No active school");
      return api.updateDiscount(schoolId, discountId, input);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["discounts", schoolId] });
    },
  });
}

export function useDeleteDiscount() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (discountId: string) => {
      if (!schoolId) throw new Error("No active school");
      return api.deleteDiscount(schoolId, discountId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["discounts", schoolId] });
    },
  });
}

export function useCreditNotes(opts?: { studentId?: string; status?: string }) {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["credit-notes", schoolId, JSON.stringify(opts ?? {})],
    enabled: !!schoolId,
    queryFn: async () => api.fetchCreditNotes(schoolId!, opts),
  });
}

export function useCreateCreditNote() {
  const schoolId = useActiveSchoolId();
  const invalidate = useAccountingInvalidate();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CreditNoteIn) => {
      if (!schoolId) throw new Error("No active school");
      return api.createCreditNote(schoolId, input);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["credit-notes", schoolId] });
      invalidate();
    },
  });
}

export function useApplyCreditNote() {
  const schoolId = useActiveSchoolId();
  const invalidate = useAccountingInvalidate();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ noteId, invoiceId }: { noteId: string; invoiceId: string }) => {
      if (!schoolId) throw new Error("No active school");
      return api.applyCreditNote(schoolId, noteId, invoiceId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["credit-notes", schoolId] });
      queryClient.invalidateQueries({ queryKey: ["invoices", schoolId] });
      invalidate();
    },
  });
}

export function useVoidCreditNote() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (noteId: string) => {
      if (!schoolId) throw new Error("No active school");
      return api.voidCreditNote(schoolId, noteId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["credit-notes", schoolId] });
    },
  });
}

export function useRefunds(opts?: { studentId?: string; status?: string }) {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["refunds", schoolId, JSON.stringify(opts ?? {})],
    enabled: !!schoolId,
    queryFn: async () => api.fetchRefunds(schoolId!, opts),
  });
}

export function useCreateRefund() {
  const schoolId = useActiveSchoolId();
  const invalidate = useAccountingInvalidate();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: RefundIn) => {
      if (!schoolId) throw new Error("No active school");
      return api.createRefund(schoolId, input);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["refunds", schoolId] });
      invalidate();
    },
  });
}

export function useApproveRefund() {
  const schoolId = useActiveSchoolId();
  const invalidate = useAccountingInvalidate();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (refundId: string) => {
      if (!schoolId) throw new Error("No active school");
      return api.approveRefund(schoolId, refundId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["refunds", schoolId] });
      invalidate();
    },
  });
}

export function useRejectRefund() {
  const schoolId = useActiveSchoolId();
  const invalidate = useAccountingInvalidate();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ refundId, reason }: { refundId: string; reason?: string }) => {
      if (!schoolId) throw new Error("No active school");
      return api.rejectRefund(schoolId, refundId, reason);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["refunds", schoolId] });
      invalidate();
    },
  });
}

export function usePayRefund() {
  const schoolId = useActiveSchoolId();
  const invalidate = useAccountingInvalidate();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ refundId, refundDate }: { refundId: string; refundDate?: string }) => {
      if (!schoolId) throw new Error("No active school");
      return api.payRefund(schoolId, refundId, refundDate);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["refunds", schoolId] });
      invalidate();
    },
  });
}

export function useDebtors(opts?: { termId?: string; armId?: string }) {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["debtors", schoolId, JSON.stringify(opts ?? {})],
    enabled: !!schoolId,
    queryFn: async () => api.fetchDebtors(schoolId!, opts),
  });
}

export function useIncomeExpenditure(opts?: {
  termId?: string;
  sessionId?: string;
  dateFrom?: string;
  dateTo?: string;
}) {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["income-expenditure", schoolId, JSON.stringify(opts ?? {})],
    enabled: !!schoolId,
    queryFn: async () => api.fetchIncomeExpenditure(schoolId!, opts),
  });
}

export function useCollectionReport(opts?: { termId?: string; sessionId?: string }) {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["collection-report", schoolId, JSON.stringify(opts ?? {})],
    enabled: !!schoolId,
    queryFn: async () => api.fetchCollectionReport(schoolId!, opts),
  });
}

export function useCashPosition() {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["cash-position", schoolId],
    enabled: !!schoolId,
    queryFn: async () => api.fetchCashPosition(schoolId!),
  });
}

export function useAccountants() {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["accountants", schoolId],
    enabled: !!schoolId,
    queryFn: async () => api.fetchAccountants(schoolId!),
  });
}

export function useCreateAccountant() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: AccountantIn) => {
      if (!schoolId) throw new Error("No active school");
      return api.createAccountant(schoolId, input);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["accountants", schoolId] });
      queryClient.invalidateQueries({ queryKey: ["staff", schoolId] });
    },
  });
}

export function useEmailReceipt() {
  const schoolId = useActiveSchoolId();
  return useMutation({
    mutationFn: ({ paymentId, to }: { paymentId: string; to?: string | null }) => {
      if (!schoolId) throw new Error("No active school");
      return api.emailReceipt(schoolId, paymentId, { to });
    },
  });
}

// --- Attendance ------------------------------------------------------------------
export function useStudentAttendance(
  studentId: string | null,
  startDate?: string,
  endDate?: string,
) {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["attendance-student", schoolId, studentId, startDate, endDate],
    enabled: !!schoolId && !!studentId,
    queryFn: async () =>
      api.fetchStudentAttendance(schoolId!, studentId!, startDate, endDate),
  });
}

export function useStaffAttendance(staffId: string | null) {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["attendance-staff", schoolId, staffId],
    enabled: !!schoolId && !!staffId,
    queryFn: async () => api.fetchStaffAttendance(schoolId!, staffId!),
  });
}

export function useStudentAttendanceSummary(studentId: string | null) {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["attendance-summary-student", schoolId, studentId],
    enabled: !!schoolId && !!studentId,
    queryFn: async () => api.fetchStudentAttendanceSummary(schoolId!, studentId!),
  });
}

export function useStaffAttendanceSummary(staffId: string | null) {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["attendance-summary-staff", schoolId, staffId],
    enabled: !!schoolId && !!staffId,
    queryFn: async () => api.fetchStaffAttendanceSummary(schoolId!, staffId!),
  });
}

export function useMarkStudentAttendance() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: StudentAttendanceIn) => {
      if (!schoolId) throw new Error("No active school");
      return api.markStudentAttendance(schoolId, input);
    },
    onSuccess: (_, input) => {
      queryClient.invalidateQueries({ queryKey: ["attendance-student", schoolId] });
      queryClient.invalidateQueries({
        queryKey: ["attendance-summary-student", schoolId, input.student_id],
      });
    },
  });
}

export function useMarkStaffAttendance() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: StaffAttendanceIn) => {
      if (!schoolId) throw new Error("No active school");
      return api.markStaffAttendance(schoolId, input);
    },
    onSuccess: (_, input) => {
      queryClient.invalidateQueries({ queryKey: ["attendance-staff", schoolId] });
      queryClient.invalidateQueries({
        queryKey: ["attendance-summary-staff", schoolId, input.staff_id],
      });
    },
  });
}

// --- Payroll ---------------------------------------------------------------------
export function useSalaryStructures() {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["salary-structures", schoolId],
    enabled: !!schoolId,
    queryFn: async () => api.fetchSalaryStructures(schoolId!),
  });
}

export function useCreateSalaryStructure() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: SalaryStructureIn) => {
      if (!schoolId) throw new Error("No active school");
      return api.createSalaryStructure(schoolId, input);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["salary-structures", schoolId] });
    },
  });
}

export function useUpdateSalaryStructure() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ structureId, input }: { structureId: string; input: SalaryStructureIn }) => {
      if (!schoolId) throw new Error("No active school");
      return api.updateSalaryStructure(schoolId, structureId, input);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["salary-structures", schoolId] });
    },
  });
}

export function useToggleSalaryStructure() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (structureId: string) => {
      if (!schoolId) throw new Error("No active school");
      return api.toggleSalaryStructure(schoolId, structureId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["salary-structures", schoolId] });
    },
  });
}

export function useStaffSalaries() {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["staff-salaries", schoolId],
    enabled: !!schoolId,
    queryFn: async () => api.fetchStaffSalaries(schoolId!),
  });
}

export function useAssignStaffSalary() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: StaffSalaryIn) => {
      if (!schoolId) throw new Error("No active school");
      return api.assignStaffSalary(schoolId, input);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["staff-salaries", schoolId] });
    },
  });
}

export function usePayRuns() {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["pay-runs", schoolId],
    enabled: !!schoolId,
    queryFn: async () => api.fetchPayRuns(schoolId!),
  });
}

export function usePayRun(payRunId: string | null) {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["pay-run", schoolId, payRunId],
    enabled: !!schoolId && !!payRunId,
    queryFn: async () => api.fetchPayRun(schoolId!, payRunId!),
  });
}

export function useCreatePayRun() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: PayRunCreate) => {
      if (!schoolId) throw new Error("No active school");
      return api.createPayRun(schoolId, input);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pay-runs", schoolId] });
    },
  });
}

export function useMarkPayRunPaid() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payRunId: string) => {
      if (!schoolId) throw new Error("No active school");
      return api.markPayRunPaid(schoolId, payRunId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pay-runs", schoolId] });
      queryClient.invalidateQueries({ queryKey: ["pay-run", schoolId] });
    },
  });
}

// --- Inventory ---------------------------------------------------------------------
export function useInventoryCategories() {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["inventory-categories", schoolId],
    enabled: !!schoolId,
    queryFn: async () => api.fetchInventoryCategories(schoolId!),
  });
}

export function useCreateInventoryCategory() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: InventoryCategoryIn) => {
      if (!schoolId) throw new Error("No active school");
      return api.createInventoryCategory(schoolId, input);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["inventory-categories", schoolId] });
    },
  });
}

export function useInventoryItems(lowStockOnly = false) {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["inventory-items", schoolId, lowStockOnly],
    enabled: !!schoolId,
    queryFn: async () => api.fetchInventoryItems(schoolId!, lowStockOnly),
  });
}

export function useCreateInventoryItem() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: InventoryItemIn) => {
      if (!schoolId) throw new Error("No active school");
      return api.createInventoryItem(schoolId, input);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["inventory-items", schoolId] });
    },
  });
}

export function useUpdateInventoryItem() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ itemId, input }: { itemId: string; input: InventoryItemIn }) => {
      if (!schoolId) throw new Error("No active school");
      return api.updateInventoryItem(schoolId, itemId, input);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["inventory-items", schoolId] });
      queryClient.invalidateQueries({ queryKey: ["inventory-movements", schoolId] });
    },
  });
}

export function useRecordStockMovement() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: StockMovementIn) => {
      if (!schoolId) throw new Error("No active school");
      return api.recordStockMovement(schoolId, input);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["inventory-items", schoolId] });
      queryClient.invalidateQueries({ queryKey: ["inventory-movements", schoolId] });
    },
  });
}

export function useStockMovements(itemId: string | null) {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["inventory-movements", schoolId, itemId],
    enabled: !!schoolId,
    queryFn: async () => api.fetchStockMovements(schoolId!, itemId ?? undefined),
  });
}

// --- Library ------------------------------------------------------------------------
export function useBooks(availableOnly = false) {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["library-books", schoolId, availableOnly],
    enabled: !!schoolId,
    queryFn: async () => api.fetchBooks(schoolId!, availableOnly),
  });
}

export function useCreateBook() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: BookIn) => {
      if (!schoolId) throw new Error("No active school");
      return api.createBook(schoolId, input);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["library-books", schoolId] });
    },
  });
}

export function useUpdateBook() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ bookId, input }: { bookId: string; input: BookIn }) => {
      if (!schoolId) throw new Error("No active school");
      return api.updateBook(schoolId, bookId, input);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["library-books", schoolId] });
    },
  });
}

export function useBorrowings(opts: { status?: string; overdue?: boolean } = {}) {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["library-borrowings", schoolId, opts.status, opts.overdue],
    enabled: !!schoolId,
    queryFn: async () => api.fetchBorrowings(schoolId!, opts),
  });
}

export function useCheckOutBook() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: BorrowingIn) => {
      if (!schoolId) throw new Error("No active school");
      return api.checkOutBook(schoolId, input);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["library-borrowings", schoolId] });
      queryClient.invalidateQueries({ queryKey: ["library-books", schoolId] });
    },
  });
}

export function useReturnBook() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (borrowingId: string) => {
      if (!schoolId) throw new Error("No active school");
      return api.returnBook(schoolId, borrowingId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["library-borrowings", schoolId] });
      queryClient.invalidateQueries({ queryKey: ["library-books", schoolId] });
    },
  });
}

// --- School copilot -----------------------------------------------------------
export function useCopilotIntents() {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["copilot-intents", schoolId],
    enabled: !!schoolId,
    queryFn: async () => api.fetchCopilotIntents(schoolId!),
  });
}

export function useConversations() {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["copilot-conversations", schoolId],
    enabled: !!schoolId,
    queryFn: async () => api.fetchConversations(schoolId!),
  });
}

export function useConversation(conversationId: string | null) {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["copilot-conversation", schoolId, conversationId],
    enabled: !!schoolId && !!conversationId,
    queryFn: async () => api.fetchConversation(schoolId!, conversationId!),
    retry: false, // 404 = unknown thread; don't retry
  });
}

export function useAskCopilot() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CopilotAsk) => {
      if (!schoolId) throw new Error("No active school");
      return api.askCopilot(schoolId, input);
    },
    onSuccess: (result, input) => {
      // The conversation list changes after every turn (new thread or new
      // message) — refresh it so the rail stays true.
      queryClient.invalidateQueries({ queryKey: ["copilot-conversations", schoolId] });
      // Seed the thread cache with the turn (user question + assistant answer)
      // so the chat renders instantly, then let a background refetch confirm.
      const convId = result.conversation.id;
      const userMessage: CopilotMessage = {
        id: `local-${result.message.id}`,
        conversation_id: convId,
        role: "user",
        content: input.question,
        intent: null,
        answer_payload: null,
        created_at: result.message.created_at,
      };
      queryClient.setQueryData<CopilotConversationDetail>(
        ["copilot-conversation", schoolId, convId],
        (old) => ({
          ...(old ?? { ...result.conversation, messages: [] }),
          messages: [...(old?.messages ?? []), userMessage, result.message],
        }),
      );
      queryClient.invalidateQueries({
        queryKey: ["copilot-conversation", schoolId, convId],
      });
    },
  });
}

// --- Result portal -----------------------------------------------------------
export function useSetStudentPin() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ studentId, pin }: { studentId: string; pin: string }) => {
      if (!schoolId) throw new Error("No active school");
      return api.setStudentPin(schoolId, studentId, pin);
    },
    onSuccess: () => {
      // PIN changes don't touch any list row, but keep a fresh read anyway.
      queryClient.invalidateQueries({ queryKey: ["students"] });
    },
  });
}

// --- School result code (the code parents type instead of per-student PINs) ---
export function useSchoolResultPin() {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["school-result-pin", schoolId],
    queryFn: () => api.fetchSchoolResultPin(schoolId!),
    enabled: !!schoolId,
  });
}

export function useGenerateSchoolResultPin() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => {
      if (!schoolId) throw new Error("No active school");
      return api.generateSchoolResultPin(schoolId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["school-result-pin", schoolId] });
    },
  });
}

export function useRevokeSchoolResultPin() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => {
      if (!schoolId) throw new Error("No active school");
      return api.revokeSchoolResultPin(schoolId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["school-result-pin", schoolId] });
    },
  });
}

export interface ReviewInput {
  cell: ResultCell;
  reason?: string;
}

export function useResultAction(action: ResultAction) {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ cell, reason }: ReviewInput) =>
      reviewResults(schoolId!, action, cell, reason),
    onSuccess: () => {
      // Stage counts changed everywhere — refresh the review surfaces.
      queryClient.invalidateQueries({ queryKey: ["workbench", schoolId] });
      queryClient.invalidateQueries({ queryKey: ["readiness", schoolId] });
      queryClient.invalidateQueries({ queryKey: ["scorecard", schoolId] });
      queryClient.invalidateQueries({ queryKey: ["report-index", schoolId] });
      queryClient.invalidateQueries({ queryKey: ["report-card", schoolId] });
    },
  });
}

export function useCompile() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (cell: ResultCell) => compileResults(schoolId!, cell),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workbench", schoolId] });
      queryClient.invalidateQueries({ queryKey: ["readiness", schoolId] });
      queryClient.invalidateQueries({ queryKey: ["scorecard", schoolId] });
      queryClient.invalidateQueries({ queryKey: ["report-index", schoolId] });
      queryClient.invalidateQueries({ queryKey: ["report-card", schoolId] });
      queryClient.invalidateQueries({ queryKey: ["report-cards", schoolId] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary", schoolId] });
    },
  });
}

// --- Dashboard -----------------------------------------------------------------
export function useDashboardSummary(termId?: string) {
  const schoolId = useActiveSchoolId();
  return useQuery({
    queryKey: ["dashboard-summary", schoolId, termId ?? null],
    enabled: !!schoolId,
    queryFn: async () => api.fetchDashboardSummary(schoolId!, termId),
  });
}

// --- Platform (Clearis admin) -----------------------------------------------------
export function usePlatformSchools() {
  const { user } = useAuth();
  return useQuery({
    queryKey: ["platform-schools"],
    enabled: !!user?.is_superadmin,
    queryFn: async () => api.fetchPlatformSchools(),
  });
}

export function useSetSchoolAi() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ schoolId, enabled }: { schoolId: string; enabled: boolean }) =>
      api.setSchoolAi(schoolId, enabled),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["platform-schools"] });
    },
  });
}

export function useSetSchoolSuspended() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ schoolId, suspended }: { schoolId: string; suspended: boolean }) =>
      api.setSchoolSuspended(schoolId, suspended),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["platform-schools"] });
    },
  });
}

export function useCreateSchoolAdmin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ schoolId, body }: { schoolId: string; body: SchoolAdminCreate }) =>
      api.createSchoolAdmin(schoolId, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["platform-teachers"] });
    },
  });
}

export function usePlatformTeachers() {
  const { user } = useAuth();
  return useQuery({
    queryKey: ["platform-teachers"],
    enabled: !!user?.is_superadmin,
    queryFn: async () => api.fetchPlatformTeachers(),
  });
}
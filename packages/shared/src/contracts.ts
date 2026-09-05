// SchoolOS — shared request/response contracts (zod). The FastAPI side uses
// Pydantic; these are the TypeScript mirror so the web app never hand-writes
// types that can drift from the API.
import { z } from "zod";

// --- Error envelope ----------------------------------------------------------
export const ApiErrorSchema = z.object({
  error: z.object({
    code: z.string(),
    message: z.string(),
    details: z.record(z.unknown()).optional(),
  }),
});
export type ApiError = z.infer<typeof ApiErrorSchema>;

// --- Auth ---------------------------------------------------------------------
export const UserSummarySchema = z.object({
  id: z.string().uuid(),
  email: z.string(),
  full_name: z.string(),
  status: z.string(),
  is_superadmin: z.boolean(),
});
export type UserSummary = z.infer<typeof UserSummarySchema>;

export const MembershipOutSchema = z.object({
  membership_id: z.string().uuid(),
  school_id: z.string().uuid(),
  school_name: z.string(),
  school_slug: z.string(),
  status: z.string(),
  role: z.object({ code: z.string(), name: z.string() }).nullable(),
  permissions: z.array(z.string()),
  ai_enabled: z.boolean(),
  suspended: z.boolean(),
});
export type MembershipOut = z.infer<typeof MembershipOutSchema>;

export const TokenResponseSchema = z.object({
  access_token: z.string(),
  refresh_token: z.string(),
  token_type: z.string(),
  user: UserSummarySchema,
});
export type TokenResponse = z.infer<typeof TokenResponseSchema>;

export const MeResponseSchema = z.object({
  user: UserSummarySchema,
  memberships: z.array(MembershipOutSchema),
});
export type MeResponse = z.infer<typeof MeResponseSchema>;

// --- Platform (Lumo admin) -----------------------------------------------------
export const PlatformSchoolSchema = z.object({
  id: z.string().uuid(),
  name: z.string(),
  short_name: z.string().nullable(),
  slug: z.string(),
  school_type: z.string(),
  email: z.string().nullable(),
  phone: z.string().nullable(),
  created_at: z.string(),
  students: z.number(),
  class_arms: z.number(),
  ai_enabled: z.boolean(),
  suspended: z.boolean(),
});
export type PlatformSchool = z.infer<typeof PlatformSchoolSchema>;

export const SchoolAiUpdateSchema = z.object({ enabled: z.boolean() });
export type SchoolAiUpdate = z.infer<typeof SchoolAiUpdateSchema>;

export const SchoolSuspendedUpdateSchema = z.object({ suspended: z.boolean() });
export type SchoolSuspendedUpdate = z.infer<typeof SchoolSuspendedUpdateSchema>;

export const SchoolAdminCreateSchema = z.object({
  full_name: z.string(),
  email: z.string(),
  password: z.string().nullable().optional(),
});
export type SchoolAdminCreate = z.infer<typeof SchoolAdminCreateSchema>;

export const SchoolAdminCreatedSchema = z.object({
  id: z.string().uuid(),
  email: z.string(),
  full_name: z.string(),
  school_id: z.string().uuid(),
  school_name: z.string(),
  role_code: z.string(),
  password: z.string().nullable(),
});
export type SchoolAdminCreated = z.infer<typeof SchoolAdminCreatedSchema>;

export const TeacherOutSchema = z.object({
  school_id: z.string().uuid(),
  school_name: z.string(),
  user_id: z.string().uuid(),
  full_name: z.string(),
  email: z.string(),
  phone: z.string().nullable(),
  role_code: z.string(),
  status: z.string(),
  created_at: z.string(),
});
export type TeacherOut = z.infer<typeof TeacherOutSchema>;

// --- Academics ----------------------------------------------------------------
export const SessionSchema = z.object({
  id: z.string().uuid(),
  name: z.string(),
  start_date: z.string().nullable(),
  end_date: z.string().nullable(),
  status: z.string(),
  is_current: z.boolean(),
});
export type AcademicSession = z.infer<typeof SessionSchema>;

export const TermSchema = z.object({
  id: z.string().uuid(),
  academic_session_id: z.string().uuid(),
  term_no: z.number(),
  name: z.string(),
  start_date: z.string().nullable(),
  end_date: z.string().nullable(),
  status: z.string(),
  is_current: z.boolean(),
});
export type Term = z.infer<typeof TermSchema>;

export const ArmSchema = z.object({
  id: z.string().uuid(),
  academic_session_id: z.string().uuid(),
  name: z.string(),
  full_name: z.string(),
});
export type Arm = z.infer<typeof ArmSchema>;

export const SubjectSchema = z.object({
  id: z.string().uuid(),
  name: z.string(),
  code: z.string(),
  is_active: z.boolean(),
  is_core: z.boolean().default(false),
});
export type Subject = z.infer<typeof SubjectSchema>;

export const OfferingSchema = z.object({
  id: z.string().uuid(),
  class_arm_id: z.string().uuid(),
  subject_id: z.string().uuid(),
});
export type Offering = z.infer<typeof OfferingSchema>;

export const AssignmentSchema = z.object({
  id: z.string().uuid(),
  class_arm_id: z.string().uuid(),
  subject_id: z.string().uuid(),
  teacher_id: z.string().uuid(),
});
export type Assignment = z.infer<typeof AssignmentSchema>;

// --- People ---------------------------------------------------------------------
export const StudentSchema = z.object({
  id: z.string().uuid(),
  admission_no: z.string(),
  first_name: z.string(),
  last_name: z.string(),
  middle_name: z.string().nullable(),
  gender: z.string(),
  date_of_birth: z.string().nullable(),
  photo_url: z.string().nullable(),
  state: z.string().nullable(),
  lga: z.string().nullable(),
  blood_group: z.string().nullable(),
  full_name: z.string(),
});
export type Student = z.infer<typeof StudentSchema>;

export const TargetArmPairSchema = z.object({
  from_arm_id: z.string().uuid(),
  to_arm_id: z.string().uuid(),
});
export type TargetArmPair = z.infer<typeof TargetArmPairSchema>;

export const PromotionRequestSchema = z.object({
  from_session_id: z.string().uuid(),
  to_session_id: z.string().uuid(),
  target_arms: z.array(TargetArmPairSchema),
  student_ids: z.array(z.string().uuid()).nullable().optional(),
});
export type PromotionRequest = z.infer<typeof PromotionRequestSchema>;

export const PromotionResultSchema = z.object({
  promoted: z.number(),
  skipped: z.array(z.string()),
});
export type PromotionResult = z.infer<typeof PromotionResultSchema>;

export const EnrollmentHistoryRowSchema = z.object({
  enrollment_id: z.string().uuid(),
  session_id: z.string().uuid(),
  arm_id: z.string().uuid(),
  arm_name: z.string(),
  status: z.string(),
  is_current: z.boolean(),
});
export type EnrollmentHistoryRow = z.infer<typeof EnrollmentHistoryRowSchema>;

export const StaffSchema = z.object({
  id: z.string().uuid(),
  staff_no: z.string(),
  membership_type: z.string(),
  full_name: z.string(),
  gender: z.string().nullable(),
  phone: z.string().nullable(),
  email: z.string().nullable(),
  joined_date: z.string().nullable(),
  employment_status: z.string(),
  has_account: z.boolean(),
  account_email: z.string().nullable(),
  account_role_id: z.string().uuid().nullable(),
  account_role_name: z.string().nullable(),
});
export type Staff = z.infer<typeof StaffSchema>;

export const StaffCreateSchema = z.object({
  staff_no: z.string().min(1),
  membership_type: z.string().default("teaching"),
  full_name: z.string().min(1),
  gender: z.string().nullable().optional(),
  phone: z.string().nullable().optional(),
  email: z.string().nullable().optional(),
  joined_date: z.string().nullable().optional(),
});
export type StaffCreate = z.infer<typeof StaffCreateSchema>;

export const StaffAccountCreateSchema = z.object({
  email: z.string().email(),
  password: z.string().min(8),
  role_id: z.string().uuid(),
});
export type StaffAccountCreate = z.infer<typeof StaffAccountCreateSchema>;

export const StaffAccountUpdateSchema = z.object({
  email: z.string().email().optional(),
  password: z.string().min(8).optional(),
  role_id: z.string().uuid().optional(),
});
export type StaffAccountUpdate = z.infer<typeof StaffAccountUpdateSchema>;

export const StaffAccountOutSchema = z.object({
  staff_id: z.string().uuid(),
  email: z.string(),
  role_id: z.string().uuid(),
  role_code: z.string(),
  role_name: z.string(),
});
export type StaffAccountOut = z.infer<typeof StaffAccountOutSchema>;

export const RoleOutSchema = z.object({
  id: z.string().uuid(),
  code: z.string(),
  name: z.string(),
  description: z.string().nullable(),
  is_system: z.boolean(),
});
export type RoleOut = z.infer<typeof RoleOutSchema>;

export const RoleDetailSchema = RoleOutSchema.extend({
  permissions: z.array(z.string()),
});
export type RoleDetail = z.infer<typeof RoleDetailSchema>;

export const AssignmentCreateSchema = z.object({
  arm_id: z.string().uuid(),
  subject_id: z.string().uuid(),
  teacher_id: z.string().uuid(),
});
export type AssignmentCreate = z.infer<typeof AssignmentCreateSchema>;

export const MyAssignmentSchema = z.object({
  arm_id: z.string().uuid(),
  arm_name: z.string(),
  subject_id: z.string().uuid(),
  subject_name: z.string(),
  assignment_id: z.string().uuid(),
});
export type MyAssignment = z.infer<typeof MyAssignmentSchema>;

// --- Results ---------------------------------------------------------------------
export const AssessmentComponentSchema = z.object({
  id: z.string().uuid(),
  term_id: z.string().uuid(),
  class_arm_id: z.string().uuid().nullable(),
  name: z.string(),
  max_score: z.number(),
  weight: z.number(),
  sort_order: z.number(),
});
export type AssessmentComponent = z.infer<typeof AssessmentComponentSchema>;

export const ScoreCardRowSchema = z.object({
  enrollment_id: z.string().uuid(),
  student_id: z.string().uuid(),
  admission_no: z.string(),
  full_name: z.string(),
  scores: z.record(z.number().nullable()),
  total: z.number().nullable(),
  grade_letter: z.string().nullable(),
  status: z.string(),
});
export type ScoreCardRow = z.infer<typeof ScoreCardRowSchema>;

export const ScoreCardSchema = z.object({
  arm: z.object({ id: z.string().uuid(), full_name: z.string() }),
  subject: z.object({ id: z.string().uuid(), name: z.string() }),
  term: z.object({ id: z.string().uuid(), name: z.string() }),
  components: z.array(
    z.object({
      id: z.string().uuid(),
      name: z.string(),
      max_score: z.number(),
      weight: z.number(),
    }),
  ),
  students: z.array(ScoreCardRowSchema),
});
export type ScoreCard = z.infer<typeof ScoreCardSchema>;

export const ReadyRowSchema = z.object({
  arm_id: z.string().uuid(),
  arm_name: z.string(),
  subject_id: z.string().uuid(),
  subject_name: z.string(),
  student_count: z.number(),
  entered: z.number(),
  submitted: z.number(),
  pending: z.number(),
  entered_pct: z.number(),
});
export type ReadyRow = z.infer<typeof ReadyRowSchema>;

export const WorkbenchRowSchema = z.object({
  arm_id: z.string().uuid(),
  term_id: z.string().uuid(),
  arm_name: z.string(),
  subject_id: z.string().uuid(),
  subject_name: z.string(),
  enrolled: z.number(),
  entered: z.number(),
  draft: z.number(),
  submitted: z.number(),
  verified: z.number(),
  approved: z.number(),
  rejected: z.number(),
  published: z.number(),
});
export type WorkbenchRow = z.infer<typeof WorkbenchRowSchema>;

// One arm x subject x term cell acted on by the approval workflow.
export const ResultCellSchema = z.object({
  arm_id: z.string().uuid(),
  subject_id: z.string().uuid(),
  term_id: z.string().uuid(),
});
export type ResultCell = z.infer<typeof ResultCellSchema>;

// POST /results/verify|approve|publish|reject -> { "<stage>": count }
export const TransitionResultSchema = z.record(z.number());
export type TransitionResult = z.infer<typeof TransitionResultSchema>;

// POST /results/compile -> { submitted, verified, approved, published }
export const CompileResultSchema = z.object({
  submitted: z.number(),
  verified: z.number(),
  approved: z.number(),
  published: z.number(),
});
export type CompileResult = z.infer<typeof CompileResultSchema>;

// --- School ------------------------------------------------------------------------
export const SchoolSchema = z.object({
  id: z.string().uuid(),
  name: z.string(),
  short_name: z.string().nullable(),
  slug: z.string(),
  school_type: z.string(),
  currency: z.string(),
  timezone: z.string(),
  email: z.string().nullable(),
  phone: z.string().nullable(),
  logo_url: z.string().nullable(),
});
export type School = z.infer<typeof SchoolSchema>;

export const OverviewSchema = z.object({
  students: z.number(),
  staff: z.number(),
  teachers: z.number(),
  classes: z.number(),
  subjects: z.number(),
  current_session: z.string().nullable(),
  terms: z.number(),
});
export type Overview = z.infer<typeof OverviewSchema>;
// --- Report cards ---------------------------------------------------------------
export const ReportSubjectRowSchema = z.object({
  subject_id: z.string().uuid(),
  subject_name: z.string(),
  total: z.number().nullable(),
  grade_letter: z.string().nullable(),
  grade_point: z.number().nullable(),
  remark: z.string().nullable(),
  position: z.number().nullable(),
  components: z.array(
    z.object({
      id: z.string(),
      name: z.string(),
      max_score: z.number(),
      weight: z.number(),
      score: z.number().nullable(),
    }).passthrough(),
  ),
  is_core: z.boolean().default(false),
});
export type ReportSubjectRow = z.infer<typeof ReportSubjectRowSchema>;

export const ReportCardSchema = z.object({
  school: z.object({
    name: z.string(),
    short_name: z.string().nullable(),
    motto: z.string().nullable(),
    logo_url: z.string().nullable(),
  }),
  student: z.object({
    student_id: z.string().uuid(),
    admission_no: z.string(),
    full_name: z.string(),
    gender: z.string(),
    photo_url: z.string().nullable(),
    date_of_birth: z.string().nullable(),
  }),
  enrollment_id: z.string().uuid(),
  term: z.object({ id: z.string().uuid(), name: z.string() }),
  session: z.object({ id: z.string().uuid(), name: z.string() }),
  class_arm: z.object({ id: z.string().uuid(), full_name: z.string() }),
  academic_year: z.string(),
  report_date: z.string(),
  subjects: z.array(ReportSubjectRowSchema),
  psychomotor: z.array(
    z.object({
      learning_area: z.string(),
      achievement_level: z.string(),
    }),
  ),
  psychomotor_average: z.string().nullable(),
  conduct: z.string().nullable(),
  attendance_pct: z.number().nullable(),
  homeroom_teacher: z.string().nullable(),
  next_term_date: z.string().nullable(),
  next_term_label: z.string().nullable(),
  grading_key: z.array(
    z.object({
      letter: z.string(),
      min_score: z.number(),
      max_score: z.number(),
      remark: z.string().nullable(),
    }),
  ),
  comments: z.object({
    principal: z.string().nullable(),
    vice_principal: z.string().nullable(),
    homeroom: z.string().nullable(),
  }),
  summary: z.object({
    subjects_published: z.number(),
    total: z.number().nullable(),
    average: z.number().nullable(),
    grade_letter: z.string().nullable(),
    remark: z.string().nullable(),
    class_rank: z.number().nullable(),
    class_size: z.number(),
  }),
  best_in_subjects: z
    .array(
      z.object({
        subject_id: z.string().uuid(),
        subject_name: z.string(),
        top_score: z.number(),
        is_best: z.boolean(),
        tied: z.boolean(),
        co_leaders: z.array(z.string()),
      }),
    )
    .default([]),
  can_comment: z.boolean().default(false),
  can_manage_psychomotor: z.boolean().default(false),
});
export type ReportCard = z.infer<typeof ReportCardSchema>;

export const ReportIndexRowSchema = z.object({
  student_id: z.string().uuid(),
  enrollment_id: z.string().uuid(),
  admission_no: z.string(),
  full_name: z.string(),
  subjects_published: z.number(),
  total: z.number().nullable(),
});
export type ReportIndexRow = z.infer<typeof ReportIndexRowSchema>;

// One stored comment for a student × term × role (results.comment).
export const ResultCommentSchema = z.object({
  student_id: z.string().uuid(),
  term_id: z.string().uuid(),
  role: z.string().default("principal"),
  body: z.string(),
  provider: z.string(),
  model: z.string().nullable(),
  revision: z.number(),
  generated_at: z.string(),
});
export type ResultComment = z.infer<typeof ResultCommentSchema>;

export const CommentRoleSchema = z.enum(["principal", "vice_principal", "homeroom"]);
export type CommentRole = z.infer<typeof CommentRoleSchema>;

// A reusable phrase in the school's comment bank.
export const CommentBankEntrySchema = z.object({
  id: z.string().uuid(),
  comment_text: z.string(),
  category: z.string(),
  sentiment: z.string(),
  applicable_domain: z.string().nullable(),
  is_active: z.boolean(),
  created_at: z.string(),
});
export type CommentBankEntry = z.infer<typeof CommentBankEntrySchema>;

export const GradeBandRowSchema = z.object({
  letter: z.string(),
  min_score: z.number(),
  max_score: z.number(),
  remark: z.string().nullable(),
});
export type GradeBandRow = z.infer<typeof GradeBandRowSchema>;

export const BestInSubjectRowSchema = z.object({
  subject_id: z.string().uuid(),
  subject_name: z.string(),
  top_score: z.number(),
  leader_count: z.number(),
  leaders: z.array(z.string()),
});
export type BestInSubjectRow = z.infer<typeof BestInSubjectRowSchema>;

export const PsychomotorRowSchema = z.object({
  learning_area: z.string(),
  achievement_level: z.string(),
});
export type PsychomotorRow = z.infer<typeof PsychomotorRowSchema>;

// AI lesson plan for one subject × class level × term × topic (results.comment).
export const LessonPlanProcedureStepSchema = z.object({
  step: z.number(),
  phase: z.string(),
  minutes: z.number(),
  activity: z.string(),
});
export type LessonPlanProcedureStep = z.infer<typeof LessonPlanProcedureStepSchema>;

export const LessonPlanContentSchema = z.object({
  title: z.string(),
  subject: z.string(),
  class_level: z.string(),
  term: z.string(),
  topic: z.string(),
  periods: z.number(),
  duration_minutes: z.number(),
  objectives: z.array(z.string()),
  materials: z.array(z.string()),
  procedure: z.array(LessonPlanProcedureStepSchema),
  homework: z.string(),
  teacher_note: z.string(),
});
export type LessonPlanContent = z.infer<typeof LessonPlanContentSchema>;

export const LessonPlanSchema = z.object({
  id: z.string().uuid(),
  term_id: z.string().uuid(),
  subject_id: z.string().uuid(),
  class_arm_id: z.string().uuid(),
  topic: z.string(),
  plan: LessonPlanContentSchema,
  provider: z.string(),
  model: z.string().nullable(),
  revision: z.number(),
  generated_at: z.string(),
});
export type LessonPlan = z.infer<typeof LessonPlanSchema>;

export const LessonPlanInputSchema = z.object({
  term_id: z.string().uuid(),
  subject_id: z.string().uuid(),
  class_arm_id: z.string().uuid(),
  topic: z.string().min(1).max(200),
  periods: z.number().int().min(1).max(10),
});
export type LessonPlanInput = z.infer<typeof LessonPlanInputSchema>;

// AI question bank for one subject × class level × term × topic (results.comment).
// Each item is a strand-shaped multiple-choice question whose flagged answer is
// correct by construction; the bank mirrors the lesson-plan metering seam.
export const QuestionSchema = z.object({
  n: z.number(),
  type: z.literal("multiple_choice"),
  stem: z.string(),
  options: z.array(z.string()).length(4),
  answer: z.number().int().min(0).max(3),
  rationale: z.string(),
});
export type Question = z.infer<typeof QuestionSchema>;

export const QuestionBankContentSchema = z.object({
  title: z.string(),
  subject: z.string(),
  class_level: z.string(),
  term: z.string(),
  topic: z.string(),
  count: z.number(),
  questions: z.array(QuestionSchema),
});
export type QuestionBankContent = z.infer<typeof QuestionBankContentSchema>;

export const QuestionBankSchema = z.object({
  id: z.string().uuid(),
  term_id: z.string().uuid(),
  subject_id: z.string().uuid(),
  class_arm_id: z.string().uuid(),
  topic: z.string(),
  bank: QuestionBankContentSchema,
  provider: z.string(),
  model: z.string().nullable(),
  revision: z.number(),
  generated_at: z.string(),
});
export type QuestionBank = z.infer<typeof QuestionBankSchema>;

export const QuestionBankInputSchema = z.object({
  term_id: z.string().uuid(),
  subject_id: z.string().uuid(),
  class_arm_id: z.string().uuid(),
  topic: z.string().min(1).max(200),
  count: z.number().int().min(1).max(10),
});
export type QuestionBankInput = z.infer<typeof QuestionBankInputSchema>;

// --- Public result portal ------------------------------------------------------
export const SchoolBriefSchema = z.object({
  id: z.string().uuid(),
  name: z.string(),
  slug: z.string(),
});
export type SchoolBrief = z.infer<typeof SchoolBriefSchema>;

export const PinStudentBriefSchema = z.object({
  student_id: z.string().uuid(),
  admission_no: z.string(),
  full_name: z.string(),
});
export type PinStudentBrief = z.infer<typeof PinStudentBriefSchema>;

export const PinCheckOutSchema = z.object({
  token: z.string(),
  expires_minutes: z.number(),
  student: PinStudentBriefSchema,
});
export type PinCheckOut = z.infer<typeof PinCheckOutSchema>;

export const PinSetOutSchema = z.object({
  ok: z.boolean(),
  student_id: z.string().uuid(),
});
export type PinSetOut = z.infer<typeof PinSetOutSchema>;

// --- School copilot -----------------------------------------------------------
export const CopilotMessageSchema = z.object({
  id: z.string().uuid(),
  conversation_id: z.string().uuid(),
  role: z.string(),
  content: z.string(),
  intent: z.string().nullable(),
  answer_payload: z.record(z.unknown()).nullable(),
  created_at: z.string(),
});
export type CopilotMessage = z.infer<typeof CopilotMessageSchema>;

export const CopilotConversationSchema = z.object({
  id: z.string().uuid(),
  title: z.string(),
  term_id: z.string().uuid().nullable(),
  created_at: z.string(),
});
export type CopilotConversation = z.infer<typeof CopilotConversationSchema>;

export const CopilotConversationDetailSchema = CopilotConversationSchema.extend({
  messages: z.array(CopilotMessageSchema),
});
export type CopilotConversationDetail = z.infer<typeof CopilotConversationDetailSchema>;

export const CopilotAskSchema = z.object({
  question: z.string().min(1).max(2000),
  conversation_id: z.string().uuid().optional(),
  term_id: z.string().uuid().optional(),
});
export type CopilotAsk = z.infer<typeof CopilotAskSchema>;

export const CopilotIntentSchema = z.object({
  id: z.string(),
  name: z.string(),
  examples: z.array(z.string()),
});
export type CopilotIntent = z.infer<typeof CopilotIntentSchema>;

export const AskResponseSchema = z.object({
  conversation: CopilotConversationSchema,
  message: CopilotMessageSchema,
});
export type AskResponse = z.infer<typeof AskResponseSchema>;

// --- Timetable / class scheduling -------------------------------------------------
export const TimeSlotSchema = z.object({
  start: z.string(),
  end: z.string(),
  label: z.string(),
});
export type TimeSlot = z.infer<typeof TimeSlotSchema>;

export const ScheduleEntrySchema = z.object({
  id: z.string().uuid().nullable(),
  class_arm_id: z.string().uuid(),
  class_arm_name: z.string(),
  subject_id: z.string().uuid(),
  subject_name: z.string(),
  teacher_id: z.string().uuid().nullable(),
  teacher_name: z.string().nullable(),
  day_of_week: z.number(),
  period_start: z.string(),
  period_end: z.string(),
  room: z.string().nullable(),
});
export type ScheduleEntry = z.infer<typeof ScheduleEntrySchema>;

export const ScheduleGenerateInSchema = z.object({
  academic_session_id: z.string().uuid(),
  force_regenerate: z.boolean().default(false),
  include_rooms: z.boolean().default(false),
});
export type ScheduleGenerateIn = z.infer<typeof ScheduleGenerateInSchema>;

export const ScheduleGenerateOutSchema = z.object({
  school_id: z.string().uuid(),
  academic_session_id: z.string().uuid(),
  entries: z.array(ScheduleEntrySchema),
  generated_at: z.string(),
  warnings: z.array(z.string()),
  message: z.string(),
});
export type ScheduleGenerateOut = z.infer<typeof ScheduleGenerateOutSchema>;

export const DayScheduleSchema = z.object({
  day_of_week: z.number(),
  day_name: z.string(),
  entries: z.array(ScheduleEntrySchema),
  total_periods: z.number(),
});
export type DaySchedule = z.infer<typeof DayScheduleSchema>;

export const WeekScheduleOutSchema = z.object({
  school_id: z.string().uuid(),
  academic_session_id: z.string().uuid(),
  week_start: z.string(),
  days: z.array(DayScheduleSchema),
  total_entries: z.number(),
});
export type WeekScheduleOut = z.infer<typeof WeekScheduleOutSchema>;

export const ScheduleConflictSchema = z.object({
  type: z.string(),
  detail: z.string(),
  suggestions: z.array(z.string()),
});
export type ScheduleConflict = z.infer<typeof ScheduleConflictSchema>;

export const ScheduleValidateInSchema = z.object({
  entries: z.array(ScheduleEntrySchema),
});
export type ScheduleValidateIn = z.infer<typeof ScheduleValidateInSchema>;

export const ScheduleValidateOutSchema = z.object({
  is_valid: z.boolean(),
  conflicts: z.array(ScheduleConflictSchema),
  suggestions: z.array(z.string()),
});
export type ScheduleValidateOut = z.infer<typeof ScheduleValidateOutSchema>;

// --- Fees / billing --------------------------------------------------------------
export const FeeStructureSchema = z.object({
  id: z.string().uuid(),
  name: z.string(),
  description: z.string().nullable(),
  fee_type: z.string(),
  amount: z.number(),
  currency: z.string(),
  billing_frequency: z.string(),
  applicable_to: z.string().nullable(),
  class_arm_id: z.string().uuid().nullable(),
  effective_from: z.string().nullable(),
  effective_to: z.string().nullable(),
  is_mandatory: z.boolean(),
  allow_override: z.boolean(),
  is_active: z.boolean(),
  created_at: z.string(),
  updated_at: z.string(),
});
export type FeeStructure = z.infer<typeof FeeStructureSchema>;

export const InvoiceSchema = z.object({
  id: z.string().uuid(),
  student_id: z.string().uuid(),
  fee_structure_id: z.string().uuid(),
  term_id: z.string().uuid().nullable(),
  batch_number: z.string(),
  reference_number: z.string(),
  subtotal: z.number(),
  discount_amount: z.number(),
  tax_amount: z.number(),
  total_amount: z.number(),
  status: z.string(),
  issue_date: z.string(),
  due_date: z.string(),
  paid_date: z.string().nullable(),
  payment_method: z.string().nullable(),
  transaction_id: z.string().nullable(),
  payment_reference: z.string().nullable(),
  notes: z.string().nullable(),
});
export type Invoice = z.infer<typeof InvoiceSchema>;

export const PaymentSchema = z.object({
  id: z.string().uuid(),
  invoice_id: z.string().uuid(),
  student_id: z.string().uuid().nullable(),
  amount: z.number(),
  payment_method: z.string(),
  payment_reference: z.string().nullable(),
  transaction_id: z.string().nullable(),
  receipt_number: z.string().nullable(),
  payment_date: z.string(),
});
export type Payment = z.infer<typeof PaymentSchema>;

export const StudentFeeBalanceSchema = z.object({
  id: z.string().uuid(),
  student_id: z.string().uuid(),
  school_id: z.string().uuid(),
  total_owed: z.number(),
  total_paid: z.number(),
  total_unpaid: z.number(),
  current_invoice_total: z.number(),
  current_invoice_due: z.string().nullable(),
  period_start: z.string(),
  period_end: z.string(),
  calculated_at: z.string(),
});
export type StudentFeeBalance = z.infer<typeof StudentFeeBalanceSchema>;

export const FeeStructureInSchema = z.object({
  name: z.string().min(1).max(120),
  description: z.string().max(500).nullable().optional(),
  fee_type: z.string().min(1),
  amount: z.number().positive(),
  currency: z.string().max(3).default("NGN"),
  billing_frequency: z.enum(["term", "month", "year", "one_time"]).default("term"),
  applicable_to: z.enum(["all", "specific_class", "specific_arm"]).nullable().optional(),
  class_arm_id: z.string().uuid().nullable().optional(),
  effective_from: z.string().nullable().optional(),
  effective_to: z.string().nullable().optional(),
  is_mandatory: z.boolean().default(true),
  allow_override: z.boolean().default(false),
});
export type FeeStructureIn = z.infer<typeof FeeStructureInSchema>;

export const InvoiceInSchema = z.object({
  student_id: z.string().uuid(),
  fee_structure_id: z.string().uuid(),
  term_id: z.string().uuid().nullable().optional(),
  batch_number: z.string().min(1),
});
export type InvoiceIn = z.infer<typeof InvoiceInSchema>;

export const PaymentInSchema = z.object({
  invoice_id: z.string().uuid(),
  student_id: z.string().uuid().nullable().optional(),
  amount: z.number().positive(),
  payment_method: z.string().min(1),
  payment_reference: z.string().max(100).nullable().optional(),
  transaction_id: z.string().max(100).nullable().optional(),
});
export type PaymentIn = z.infer<typeof PaymentInSchema>;

export const ReceiptPaymentLineSchema = z.object({
  receipt_number: z.string().nullable(),
  amount: z.number(),
  payment_method: z.string(),
  payment_date: z.string().nullable(),
});
export type ReceiptPaymentLine = z.infer<typeof ReceiptPaymentLineSchema>;

export const ReceiptSchoolSchema = z.object({
  name: z.string().nullable(),
  address: z.string().nullable(),
  phone: z.string().nullable(),
  email: z.string().nullable(),
  logo_url: z.string().nullable(),
  currency: z.string(),
});
export type ReceiptSchool = z.infer<typeof ReceiptSchoolSchema>;

export const ReceiptStudentSchema = z.object({
  id: z.string().uuid(),
  admission_no: z.string(),
  full_name: z.string(),
});
export type ReceiptStudent = z.infer<typeof ReceiptStudentSchema>;

export const ReceiptSchema = z.object({
  receipt_number: z.string().nullable(),
  payment_date: z.string().nullable(),
  payment_method: z.string(),
  payment_reference: z.string().nullable(),
  transaction_id: z.string().nullable(),
  amount_paid: z.number(),
  invoice_total: z.number(),
  paid_total: z.number(),
  balance_due: z.number(),
  invoice_status: z.string(),
  invoice_reference: z.string(),
  invoice_issue_date: z.string().nullable(),
  invoice_due_date: z.string().nullable(),
  fee_structure_name: z.string().nullable(),
  term_id: z.string().uuid().nullable(),
  school: ReceiptSchoolSchema,
  student: ReceiptStudentSchema,
  invoice_payments: z.array(ReceiptPaymentLineSchema),
});
export type Receipt = z.infer<typeof ReceiptSchema>;

export const PaymentStatusRowSchema = z.object({
  student_id: z.string().uuid(),
  admission_no: z.string(),
  full_name: z.string(),
  arm_name: z.string().nullable(),
  invoiced: z.number(),
  paid: z.number(),
  balance: z.number(),
  status: z.string(),
});
export type PaymentStatusRow = z.infer<typeof PaymentStatusRowSchema>;

export const PaymentStatusSchema = z.object({
  summary: z.record(z.string(), z.number()),
  students: z.array(PaymentStatusRowSchema),
});
export type PaymentStatus = z.infer<typeof PaymentStatusSchema>;

// --- Attendance ------------------------------------------------------------------
export const AttendanceRecordSchema = z.object({
  id: z.string().uuid(),
  date: z.string(),
  status: z.string(),
  notes: z.string().nullable(),
  marked_by: z.string().uuid(),
});
export type AttendanceRecord = z.infer<typeof AttendanceRecordSchema>;

export const AttendanceSummarySchema = z.object({
  student_id: z.string().uuid(),
  academic_session_id: z.string().uuid(),
  month: z.string(),
  total_days: z.number(),
  present_days: z.number(),
  absent_days: z.number(),
  late_days: z.number(),
  excused_days: z.number(),
  percentage: z.number(),
});
export type AttendanceSummary = z.infer<typeof AttendanceSummarySchema>;

export const StaffAttendanceSummarySchema = z.object({
  staff_id: z.string().uuid(),
  total_days: z.number(),
  present_days: z.number(),
  absent_days: z.number(),
  late_days: z.number(),
  excused_days: z.number(),
  percentage: z.number(),
});
export type StaffAttendanceSummary = z.infer<typeof StaffAttendanceSummarySchema>;

export const AttendanceStatusSchema = z.enum(["present", "absent", "late", "excused"]);

export const StudentAttendanceInSchema = z.object({
  student_id: z.string().uuid(),
  attendance_date: z.string(),
  status: AttendanceStatusSchema,
  notes: z.string().nullable().optional(),
});
export type StudentAttendanceIn = z.infer<typeof StudentAttendanceInSchema>;

export const StaffAttendanceInSchema = z.object({
  staff_id: z.string().uuid(),
  attendance_date: z.string(),
  status: AttendanceStatusSchema,
  notes: z.string().nullable().optional(),
});
export type StaffAttendanceIn = z.infer<typeof StaffAttendanceInSchema>;

// --- Payroll ------------------------------------------------------------------
export const SalaryStructureSchema = z.object({
  id: z.string().uuid(),
  name: z.string(),
  description: z.string().nullable(),
  basic_salary: z.number(),
  tax_percent: z.number(),
  is_active: z.boolean(),
  created_at: z.string(),
});
export type SalaryStructure = z.infer<typeof SalaryStructureSchema>;

export const StaffSalaryOutSchema = z.object({
  id: z.string().uuid(),
  staff_id: z.string().uuid(),
  structure_id: z.string().uuid(),
  effective_from: z.string().nullable(),
  staff_name: z.string().nullable(),
  structure_name: z.string().nullable(),
});
export type StaffSalaryOut = z.infer<typeof StaffSalaryOutSchema>;

export const PayslipSchema = z.object({
  id: z.string().uuid(),
  staff_id: z.string().uuid(),
  staff_name: z.string().nullable(),
  structure_id: z.string().uuid().nullable(),
  gross: z.number(),
  tax: z.number(),
  net: z.number(),
});
export type Payslip = z.infer<typeof PayslipSchema>;

export const PayRunSchema = z.object({
  id: z.string().uuid(),
  month: z.string(),
  status: z.string(),
  total_gross: z.number(),
  total_tax: z.number(),
  total_net: z.number(),
  paid_at: z.string().nullable(),
});
export type PayRun = z.infer<typeof PayRunSchema>;

export const PayRunDetailSchema = PayRunSchema.extend({
  payslips: z.array(PayslipSchema),
});
export type PayRunDetail = z.infer<typeof PayRunDetailSchema>;

export const SalaryStructureInSchema = z.object({
  name: z.string().min(1).max(120),
  description: z.string().max(500).nullable().optional(),
  basic_salary: z.number().positive(),
  tax_percent: z.number().gte(0).lte(100).default(0),
  is_active: z.boolean().default(true),
});
export type SalaryStructureIn = z.infer<typeof SalaryStructureInSchema>;

export const StaffSalaryInSchema = z.object({
  staff_id: z.string().uuid(),
  structure_id: z.string().uuid(),
  effective_from: z.string().regex(/^\d{4}-\d{2}-\d{2}$/).nullable().optional(),
});
export type StaffSalaryIn = z.infer<typeof StaffSalaryInSchema>;

export const PayRunCreateSchema = z.object({
  month: z.string().regex(/^\d{4}-\d{2}$/),
});
export type PayRunCreate = z.infer<typeof PayRunCreateSchema>;

// --- Inventory -----------------------------------------------------------------
export const InventoryCategorySchema = z.object({
  id: z.string().uuid(),
  name: z.string(),
  description: z.string().nullable(),
  created_at: z.string(),
});
export type InventoryCategory = z.infer<typeof InventoryCategorySchema>;

export const InventoryItemSchema = z.object({
  id: z.string().uuid(),
  name: z.string(),
  category_id: z.string().uuid().nullable(),
  sku: z.string().nullable(),
  quantity: z.number(),
  unit: z.string().nullable(),
  unit_cost: z.number(),
  low_stock_threshold: z.number(),
  notes: z.string().nullable(),
  is_active: z.boolean(),
  created_at: z.string(),
  category_name: z.string().nullable(),
});
export type InventoryItem = z.infer<typeof InventoryItemSchema>;

export const StockMovementSchema = z.object({
  id: z.string().uuid(),
  item_id: z.string().uuid(),
  delta: z.number(),
  movement_type: z.string(),
  reason: z.string().nullable(),
  performed_by: z.string().uuid().nullable(),
  created_at: z.string(),
});
export type StockMovement = z.infer<typeof StockMovementSchema>;

export const InventoryCategoryInSchema = z.object({
  name: z.string().min(1).max(120),
  description: z.string().max(500).nullable().optional(),
});
export type InventoryCategoryIn = z.infer<typeof InventoryCategoryInSchema>;

export const InventoryItemInSchema = z.object({
  name: z.string().min(1).max(150),
  category_id: z.string().uuid().nullable().optional(),
  sku: z.string().max(60).nullable().optional(),
  quantity: z.number().gte(0).default(0),
  unit: z.string().max(30).nullable().optional(),
  unit_cost: z.number().gte(0).default(0),
  low_stock_threshold: z.number().gte(0).default(0),
  notes: z.string().max(500).nullable().optional(),
  is_active: z.boolean().default(true),
});
export type InventoryItemIn = z.infer<typeof InventoryItemInSchema>;

export const StockMovementInSchema = z.object({
  item_id: z.string().uuid(),
  delta: z.number(),
  movement_type: z.enum(["restock", "issue"]),
  reason: z.string().max(300).nullable().optional(),
});
export type StockMovementIn = z.infer<typeof StockMovementInSchema>;

// --- Library -------------------------------------------------------------------
export const BookSchema = z.object({
  id: z.string().uuid(),
  title: z.string(),
  author: z.string().nullable(),
  isbn: z.string().nullable(),
  category: z.string().nullable(),
  publisher: z.string().nullable(),
  year: z.number().nullable(),
  total_copies: z.number(),
  available_copies: z.number(),
  is_active: z.boolean(),
  created_at: z.string(),
});
export type Book = z.infer<typeof BookSchema>;

export const BorrowingSchema = z.object({
  id: z.string().uuid(),
  book_id: z.string().uuid(),
  borrower_type: z.string(),
  student_id: z.string().uuid().nullable(),
  staff_id: z.string().uuid().nullable(),
  borrowed_on: z.string(),
  due_on: z.string(),
  returned_on: z.string().nullable(),
  status: z.string(),
  notes: z.string().nullable(),
  created_at: z.string(),
  book_title: z.string().nullable(),
  borrower_name: z.string().nullable(),
});
export type Borrowing = z.infer<typeof BorrowingSchema>;

export const BookInSchema = z.object({
  title: z.string().min(1).max(250),
  author: z.string().max(200).nullable().optional(),
  isbn: z.string().max(32).nullable().optional(),
  category: z.string().max(80).nullable().optional(),
  publisher: z.string().max(150).nullable().optional(),
  year: z.number().int().gte(1000).lte(3000).nullable().optional(),
  total_copies: z.number().int().gte(1).default(1),
  is_active: z.boolean().default(true),
});
export type BookIn = z.infer<typeof BookInSchema>;

export const BorrowingInSchema = z.object({
  book_id: z.string().uuid(),
  borrower_type: z.enum(["student", "staff"]),
  student_id: z.string().uuid().nullable().optional(),
  staff_id: z.string().uuid().nullable().optional(),
  due_on: z.string(),
  notes: z.string().max(2000).nullable().optional(),
});
export type BorrowingIn = z.infer<typeof BorrowingInSchema>;

// --- Dashboard -----------------------------------------------------------------
export const DashboardKpisSchema = z.object({
  students: z.number(),
  teachers: z.number(),
  staff: z.number(),
  classes: z.number(),
  subjects: z.number(),
  attendance_rate: z.number().nullable(),
  outstanding_fees: z.number(),
  fee_currency: z.string(),
  readiness_overall: z.number().nullable(),
  readiness_submitted: z.number(),
  readiness_pending: z.number(),
  session_name: z.string().nullable(),
  term_name: z.string().nullable(),
  term_id: z.string().uuid().nullable(),
});
export type DashboardKpis = z.infer<typeof DashboardKpisSchema>;

export const PerformancePointSchema = z.object({
  term_name: z.string(),
  avg_score: z.number().nullable(),
  pass_rate: z.number().nullable(),
  count: z.number(),
});
export type PerformancePoint = z.infer<typeof PerformancePointSchema>;

export const ClassPerformanceRowSchema = z.object({
  arm_name: z.string(),
  avg_score: z.number().nullable(),
  pass_rate: z.number().nullable(),
  count: z.number(),
});
export type ClassPerformanceRow = z.infer<typeof ClassPerformanceRowSchema>;

export const PerformanceOutSchema = z.object({
  by_term: PerformancePointSchema.array(),
  by_class: ClassPerformanceRowSchema.array(),
});
export type PerformanceOut = z.infer<typeof PerformanceOutSchema>;

export const DistributionSliceSchema = z.object({
  level_name: z.string(),
  level_code: z.string(),
  count: z.number(),
  pct: z.number(),
});
export type DistributionSlice = z.infer<typeof DistributionSliceSchema>;

export const DistributionOutSchema = z.object({
  total: z.number(),
  slices: DistributionSliceSchema.array(),
});
export type DistributionOut = z.infer<typeof DistributionOutSchema>;

export const AttendanceOverviewSchema = z.object({
  present: z.number(),
  absent: z.number(),
  late: z.number(),
  excused: z.number(),
  total: z.number(),
  rate: z.number().nullable(),
});
export type AttendanceOverview = z.infer<typeof AttendanceOverviewSchema>;

export const AttendanceOutSchema = z.object({
  today: AttendanceOverviewSchema,
  week: AttendanceOverviewSchema,
  month: AttendanceOverviewSchema,
});
export type AttendanceOut = z.infer<typeof AttendanceOutSchema>;

export const ActivityItemSchema = z.object({
  id: z.string(),
  kind: z.string(),
  title: z.string(),
  detail: z.string().nullable(),
  actor_name: z.string(),
  created_at: z.string(),
  href: z.string().nullable(),
});
export type ActivityItem = z.infer<typeof ActivityItemSchema>;

export const TaskItemSchema = z.object({
  id: z.string(),
  title: z.string(),
  detail: z.string(),
  count: z.number(),
  href: z.string(),
  kind: z.string(),
});
export type TaskItem = z.infer<typeof TaskItemSchema>;

export const InsightItemSchema = z.object({
  id: z.string(),
  title: z.string(),
  body: z.string(),
  kind: z.string(),
  tone: z.string(),
  confidence: z.number(),
  href: z.string().nullable(),
});
export type InsightItem = z.infer<typeof InsightItemSchema>;

export const InsightsOutSchema = z.object({
  insights: InsightItemSchema.array(),
});
export type InsightsOut = z.infer<typeof InsightsOutSchema>;

export const DashboardSummarySchema = z.object({
  kpis: DashboardKpisSchema,
  performance: PerformanceOutSchema,
  distribution: DistributionOutSchema,
  attendance: AttendanceOutSchema,
  activity: ActivityItemSchema.array(),
  tasks: TaskItemSchema.array(),
  insights: InsightsOutSchema,
});
export type DashboardSummary = z.infer<typeof DashboardSummarySchema>;

// --- Super Admin (platform command center) --------------------------------------
// The FastAPI `/api/superadmin/*` responses. Shapes are deliberately lenient on
// the analytics payloads (server-composed); the navigation-critical ones
// (schools, detail, tickets, health) are typed tightly.
export const SaKpisSchema = z.record(z.unknown());
export const SaNotificationSchema = z.object({
  id: z.string(),
  title: z.string(),
  body: z.string().nullable(),
  severity: z.string(),
  category: z.string().nullable(),
  read: z.boolean(),
  created_at: z.string(),
});
export type SaNotification = z.infer<typeof SaNotificationSchema>;

export const SaOverviewSchema = z.object({
  generated_at: z.string(),
  kpis: z.record(z.unknown()),
  notifications: z.array(SaNotificationSchema).default([]),
  alerts: z.array(
    z.object({ kind: z.string(), severity: z.string(), label: z.string(), count: z.number(), href: z.string().nullable() }),
  ).default([]),
});
export type SaOverview = z.infer<typeof SaOverviewSchema>;

export const SaSeriesPointSchema = z.object({
  period: z.string(),
  total: z.number().optional(),
  new: z.number().optional(),
  activated: z.number().optional(),
  churned: z.number().optional(),
  subscription: z.number().optional(),
  ai: z.number().optional(),
  students: z.number().optional(),
  teachers: z.number().optional(),
  parents: z.number().optional(),
  admins: z.number().optional(),
});
export type SaSeriesPoint = z.infer<typeof SaSeriesPointSchema>;

export const SaSchoolRowSchema = z.object({
  id: z.string().uuid(),
  name: z.string(),
  slug: z.string(),
  short_name: z.string().nullable(),
  school_type: z.string(),
  state: z.string().nullable(),
  country: z.string(),
  email: z.string().nullable(),
  phone: z.string().nullable(),
  logo_url: z.string().nullable(),
  created_at: z.string(),
  joined: z.string(),
  students: z.number(),
  teachers: z.number(),
  parents: z.number(),
  plan_code: z.string(),
  plan_name: z.string(),
  status: z.string(),
  ai_enabled: z.boolean(),
  suspended: z.boolean(),
  ai_credits_used: z.number(),
  ai_credits_total: z.number(),
  renewal_date: z.string().nullable(),
  last_activity: z.string().nullable(),
});
export type SaSchoolRow = z.infer<typeof SaSchoolRowSchema>;

export const SaSchoolListSchema = z.object({
  items: z.array(SaSchoolRowSchema),
  total: z.number(),
  page: z.number(),
  per_page: z.number(),
  pages: z.number(),
});
export type SaSchoolList = z.infer<typeof SaSchoolListSchema>;

export const SaSchoolDetailSchema = z.object({
  profile: z.object({
    id: z.string().uuid(),
    name: z.string(),
    short_name: z.string().nullable(),
    slug: z.string(),
    school_type: z.string(),
    email: z.string().nullable(),
    phone: z.string().nullable(),
    address: z.string().nullable(),
    state: z.string().nullable(),
    country: z.string(),
    established_year: z.number().nullable(),
    registration_date: z.string(),
    status: z.string(),
    ai_enabled: z.boolean(),
    suspended: z.boolean(),
    owner: z.record(z.unknown()).nullable(),
  }),
  usage: z.record(z.unknown()),
  subscription: z.record(z.unknown()),
  activity: z.array(z.record(z.unknown())).default([]),
  members: z.record(z.unknown()),
  billing_events: z.array(z.record(z.unknown())).default([]),
});
export type SaSchoolDetail = z.infer<typeof SaSchoolDetailSchema>;

export const SaTicketSchema = z.object({
  id: z.string().uuid(),
  school_id: z.string().uuid().nullable(),
  school_name: z.string().nullable(),
  subject: z.string(),
  description: z.string().nullable(),
  category: z.string(),
  severity: z.string(),
  status: z.string(),
  created_at: z.string(),
  resolved_at: z.string().nullable(),
});
export type SaTicket = z.infer<typeof SaTicketSchema>;

export const SaTicketsSchema = z.object({
  summary: z.record(z.number()),
  items: z.array(SaTicketSchema),
});
export type SaTickets = z.infer<typeof SaTicketsSchema>;

export const SaIssueSchema = z.object({
  id: z.string(),
  severity: z.string(),
  service: z.string(),
  title: z.string(),
  detail: z.string(),
  ts: z.string(),
  affected_tenants: z.number(),
});
export type SaIssue = z.infer<typeof SaIssueSchema>;

export const SaHealthSchema = z.object({
  overall: z.string(),
  last_checked: z.string(),
  services: z.array(
    z.object({
      service: z.string(),
      label: z.string(),
      status: z.string(),
      response_ms: z.number().nullable(),
      last_checked: z.string(),
    }),
  ),
});
export type SaHealth = z.infer<typeof SaHealthSchema>;

export const SaAuditRowSchema = z.object({
  id: z.string(),
  ts: z.string(),
  action: z.string(),
  entity_type: z.string(),
  entity_id: z.string().nullable(),
  school_id: z.string().nullable(),
  school_name: z.string().nullable(),
  actor: z.string().nullable(),
  ip: z.string().nullable(),
  details: z.string().nullable(),
});
export type SaAuditRow = z.infer<typeof SaAuditRowSchema>;

export const SaAnnouncementSchema = z.object({
  id: z.string().uuid(),
  title: z.string(),
  body: z.string(),
  audience: z.string(),
  severity: z.string(),
  is_active: z.boolean(),
  created_at: z.string(),
});
export type SaAnnouncement = z.infer<typeof SaAnnouncementSchema>;

// --- Super Admin request bodies ------------------------------------------------
export const SaSchoolCreateSchema = z.object({
  name: z.string().min(2).max(200),
  school_type: z.string().default("secondary"),
  state: z.string().nullable().optional(),
  country: z.string().default("NG"),
  admin_full_name: z.string().min(2),
  admin_email: z.string().min(3),
  plan_code: z.string().nullable().optional(),
});
export type SaSchoolCreate = z.infer<typeof SaSchoolCreateSchema>;

export const SaSubscriptionUpdateSchema = z.object({
  plan_code: z.string().nullable().optional(),
  status: z.string().nullable().optional(),
  ai_credits_total: z.number().nullable().optional(),
  ends_at: z.string().nullable().optional(),
});
export type SaSubscriptionUpdate = z.infer<typeof SaSubscriptionUpdateSchema>;

export const SaTicketCreateSchema = z.object({
  school_id: z.string().uuid().nullable().optional(),
  subject: z.string().min(2),
  description: z.string().nullable().optional(),
  category: z.string().default("general"),
  severity: z.string().default("low"),
});
export type SaTicketCreate = z.infer<typeof SaTicketCreateSchema>;

export const SaTicketUpdateSchema = z.object({
  status: z.string().nullable().optional(),
  resolution_note: z.string().nullable().optional(),
});
export type SaTicketUpdate = z.infer<typeof SaTicketUpdateSchema>;

export const SaAnnouncementCreateSchema = z.object({
  title: z.string().min(2),
  body: z.string().min(2),
  audience: z.string().default("all"),
  severity: z.string().default("info"),
});
export type SaAnnouncementCreate = z.infer<typeof SaAnnouncementCreateSchema>;

export const SaGrowthSchema = z.object({
  range: z.string(),
  series: z.array(
    z.object({
      period: z.string(),
      total: z.number(),
      new: z.number(),
      activated: z.number(),
      churned: z.number(),
    }),
  ),
  totals: z.object({
    total: z.number(),
    new: z.number(),
    activated: z.number(),
    churned: z.number(),
  }),
});
export type SaGrowth = z.infer<typeof SaGrowthSchema>;

export const SaRevenueSchema = z.object({
  range: z.string(),
  metrics: z.record(z.unknown()),
  series: z.array(
    z.object({
      period: z.string(),
      subscription: z.number(),
      ai: z.number(),
      total: z.number(),
    }),
  ),
  by_plan: z.array(
    z.object({ plan: z.string(), code: z.string(), schools: z.number(), mrr: z.number(), pct: z.number() }),
  ),
  by_source: z.array(z.object({ source: z.string(), amount: z.number() })),
  transactions: z.array(
    z.object({
      id: z.string(),
      school_id: z.string(),
      school_name: z.string(),
      event_type: z.string(),
      amount: z.number(),
      status: z.string(),
      created_at: z.string(),
    }),
  ),
});
export type SaRevenue = z.infer<typeof SaRevenueSchema>;

export const SaSubscriptionsSchema = z.object({
  distribution: z.array(
    z.object({ plan: z.string(), code: z.string(), schools: z.number(), mrr: z.number(), pct: z.number() }),
  ),
  summary: z.record(z.number()),
  trials_ending_soon: z.array(z.record(z.unknown())),
  expired: z.array(z.record(z.unknown())),
  failed: z.array(z.record(z.unknown())),
  nearing_limits: z.array(z.record(z.unknown())),
});
export type SaSubscriptions = z.infer<typeof SaSubscriptionsSchema>;

export const SaAiSchema = z.object({
  range: z.string(),
  metrics: z.record(z.unknown()),
  features: z.array(
    z.object({ feature: z.string(), count: z.number(), cost: z.number(), revenue: z.number() }),
  ),
  series: z.array(
    z.object({ period: z.string(), requests: z.number(), credits: z.number(), cost: z.number() }),
  ),
  top_schools: z.array(
    z.object({ school_id: z.string(), name: z.string(), count: z.number(), credits: z.number(), cost: z.number() }),
  ),
  nearing_limits: z.array(
    z.object({ school_id: z.string(), name: z.string(), used: z.number(), total: z.number(), pct: z.number() }),
  ),
});
export type SaAi = z.infer<typeof SaAiSchema>;

export const SaUsersSchema = z.object({
  range: z.string(),
  totals: z.object({
    students: z.number(),
    teachers: z.number(),
    parents: z.number(),
    admins: z.number(),
  }),
  series: z.array(
    z.object({
      period: z.string(),
      students: z.number(),
      teachers: z.number(),
      parents: z.number(),
      admins: z.number(),
      total: z.number(),
    }),
  ),
});
export type SaUsers = z.infer<typeof SaUsersSchema>;

export const SaEngagementSchema = z.object({
  active: z.object({ dau: z.number(), wau: z.number(), mau: z.number() }),
  schools_active_today: z.number(),
  schools_inactive_7d: z.number(),
  logins: z.record(z.number()),
  most_active: z.array(z.record(z.unknown())),
  at_risk: z.array(z.record(z.unknown())),
  inactive_7d: z.array(z.record(z.unknown())),
});
export type SaEngagement = z.infer<typeof SaEngagementSchema>;

export const SaGeoSchema = z.object({
  items: z.array(
    z.object({
      country: z.string(),
      state: z.string(),
      schools: z.number(),
      students: z.number(),
      teachers: z.number(),
    }),
  ),
  regions: z.array(z.record(z.unknown())),
});
export type SaGeo = z.infer<typeof SaGeoSchema>;

export const SaActivityRowSchema = z.object({
  id: z.string(),
  ts: z.string(),
  school_id: z.string().nullable(),
  school_name: z.string().nullable(),
  actor: z.string(),
  action: z.string(),
  category: z.string(),
  severity: z.string(),
  detail: z.string(),
  href: z.string().nullable(),
});
export type SaActivityRow = z.infer<typeof SaActivityRowSchema>;

export const SaIssuesSchema = z.object({
  items: z.array(
    z.object({
      id: z.string(),
      severity: z.string(),
      service: z.string(),
      title: z.string(),
      detail: z.string(),
      ts: z.string().nullable(),
      affected_tenants: z.number(),
      status: z.string(),
      action: z.string().nullable(),
      href: z.string().nullable(),
    }),
  ),
  counts: z.record(z.number()),
});
export type SaIssues = z.infer<typeof SaIssuesSchema>;

export const SaAuditSchema = z.object({
  items: z.array(SaAuditRowSchema),
  total: z.number(),
  page: z.number(),
  per_page: z.number(),
  pages: z.number(),
});
export type SaAudit = z.infer<typeof SaAuditSchema>;

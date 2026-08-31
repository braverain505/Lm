"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useMarkStaffAttendance,
  useMarkStudentAttendance,
  useStaff,
  useStaffAttendance,
  useStaffAttendanceSummary,
  useStudentAttendance,
  useStudentAttendanceSummary,
  useStudents,
} from "@/hooks/use-api";

const markSchema = z.object({
  attendance_date: z.string().min(1, "Date required"),
  status: z.enum(["present", "absent", "late", "excused"]),
  notes: z.string().optional(),
});
type MarkForm = z.infer<typeof markSchema>;

const STATUS_LABELS: Record<string, string> = {
  present: "Present",
  absent: "Absent",
  late: "Late",
  excused: "Excused",
};

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

export default function AttendancePage() {
  const [mode, setMode] = useState<"students" | "staff">("students");
  const [studentId, setStudentId] = useState("");
  const [staffId, setStaffId] = useState("");

  const { data: students = [] } = useStudents();
  const { data: staff = [] } = useStaff();
  const markStudent = useMarkStudentAttendance();
  const markStaff = useMarkStaffAttendance();

  const subjectId = mode === "students" ? studentId : staffId;
  const { data: records = [], isLoading } =
    mode === "students"
      ? useStudentAttendance(studentId || null)
      : useStaffAttendance(staffId || null);
  const summary =
    mode === "students"
      ? useStudentAttendanceSummary(studentId || null).data
      : useStaffAttendanceSummary(staffId || null).data;

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<MarkForm>({ resolver: zodResolver(markSchema) });

  const mark = (values: MarkForm) => {
    if (mode === "students" && studentId) {
      markStudent.mutate({ student_id: studentId, ...values }, { onSuccess: () => reset() });
    } else if (mode === "staff" && staffId) {
      markStaff.mutate({ staff_id: staffId, ...values }, { onSuccess: () => reset() });
    }
  };

  const personName =
    mode === "students"
      ? students.find((s) => s.id === studentId)?.full_name
      : staff.find((s) => s.id === staffId)?.full_name;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-[22px] font-bold tracking-tight text-foreground">Attendance</h1>
          <p className="mt-1 text-[13px] text-muted-foreground">
            Mark daily attendance and review summaries.
          </p>
        </div>
        <div className="flex rounded-xl border border-border/60 bg-muted/40 p-0.5 text-[12px]">
          {(["students", "staff"] as const).map((m) => (
            <button
              key={m}
              onClick={() => {
                setMode(m);
                reset();
              }}
              className={`rounded-lg px-3.5 py-1.5 font-medium capitalize transition-all duration-150 ${
                mode === m ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {m}
            </button>
          ))}
        </div>
      </div>

      <Card className="premium-card">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-[15px]">
            Mark {mode === "students" ? "student" : "staff"} attendance
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label>{mode === "students" ? "Student" : "Staff member"}</Label>
              <select
                className="flex h-9 w-full rounded-xl border border-border/80 bg-background/50 px-3 text-[13px] shadow-sm transition-all"
                value={subjectId}
                onChange={(e) => (mode === "students" ? setStudentId(e.target.value) : setStaffId(e.target.value))}
              >
                <option value="">Choose…</option>
                {mode === "students"
                  ? students.map((s) => (
                      <option key={s.id} value={s.id}>{s.admission_no} · {s.full_name}</option>
                    ))
                  : staff.map((s) => (
                      <option key={s.id} value={s.id}>{s.staff_no} · {s.full_name}</option>
                    ))}
              </select>
            </div>
          </div>

          {subjectId && (
            <form
              onSubmit={handleSubmit(mark)}
              className="grid gap-4 rounded-xl border border-border/40 bg-muted/20 p-4 sm:grid-cols-2 lg:grid-cols-4"
            >
              <div className="space-y-1.5">
                <Label>Date</Label>
                <Input type="date" defaultValue={todayISO()} {...register("attendance_date")} />
                {errors.attendance_date && <p className="text-[11px] text-destructive">{errors.attendance_date.message}</p>}
              </div>
              <div className="space-y-1.5">
                <Label>Status</Label>
                <select className="flex h-9 w-full rounded-xl border border-border/80 bg-background/50 px-3 text-[13px] shadow-sm" {...register("status")}>
                  {(["present", "absent", "late", "excused"] as const).map((s) => (
                    <option key={s} value={s}>{STATUS_LABELS[s]}</option>
                  ))}
                </select>
              </div>
              <div className="space-y-1.5">
                <Label>Notes (optional)</Label>
                <Input placeholder="e.g. medical appointment" {...register("notes")} />
              </div>
              <div className="flex items-end">
                <Button type="submit" disabled={isSubmitting || markStudent.isPending || markStaff.isPending}>
                  {isSubmitting ? "Saving…" : "Mark attendance"}
                </Button>
              </div>
            </form>
          )}
        </CardContent>
      </Card>

      {subjectId && (
        <div className="grid gap-4 lg:grid-cols-3">
          <Card className="premium-card lg:col-span-2">
            <CardHeader>
              <CardTitle className="text-[15px]">Records — {personName ?? ""}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-[13px]">
                  <thead>
                    <tr className="border-b border-border/40 text-left text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground/60">
                      <th className="pb-2.5 font-semibold">Date</th>
                      <th className="pb-2.5 font-semibold">Status</th>
                      <th className="pb-2.5 font-semibold">Notes</th>
                    </tr>
                  </thead>
                  <tbody>
                    {isLoading ? (
                      <tr><td colSpan={3}><Skeleton className="my-2 h-6 w-full" /></td></tr>
                    ) : records.length === 0 ? (
                      <tr><td colSpan={3} className="py-12 text-center text-[13px] text-muted-foreground/70">
                        No attendance marked yet.
                      </td></tr>
                    ) : (
                      records.map((r) => (
                        <tr key={r.id} className="border-b border-border/30 last:border-0 transition-colors hover:bg-accent/40">
                          <td className="py-3">{r.date}</td>
                          <td className="py-3">
                            <span className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-semibold capitalize ${
                              r.status === "present" ? "bg-success/10 text-success" :
                              r.status === "absent" ? "bg-destructive/10 text-destructive" :
                              r.status === "late" ? "bg-warning/10 text-warning" :
                              "bg-muted text-muted-foreground"
                            }`}>{STATUS_LABELS[r.status] ?? r.status}</span>
                          </td>
                          <td className="py-3 text-muted-foreground">{r.notes ?? "—"}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          {summary && (
            <Card className="premium-card">
              <CardHeader>
                <CardTitle className="text-[15px]">{mode === "students" ? "Month summary" : "Summary"}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2.5 text-[13px]">
                <div className="flex justify-between"><span className="text-muted-foreground">Days</span><span className="font-medium">{summary.total_days}</span></div>
                <div className="flex justify-between"><span className="text-success">Present</span><span className="font-medium">{summary.present_days}</span></div>
                <div className="flex justify-between"><span className="text-destructive">Absent</span><span className="font-medium">{summary.absent_days}</span></div>
                <div className="flex justify-between"><span className="text-warning">Late</span><span className="font-medium">{summary.late_days}</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Excused</span><span className="font-medium">{summary.excused_days}</span></div>
                <div className="mt-2 border-t border-border/40 pt-2.5 flex justify-between">
                  <span className="font-semibold">Percentage</span>
                  <span className="font-bold text-primary">{summary.percentage}%</span>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}

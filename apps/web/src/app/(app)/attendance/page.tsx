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
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Attendance</h1>
          <p className="text-sm text-muted-foreground">
            Mark daily attendance and review monthly summaries.
          </p>
        </div>
        <div className="flex rounded-md border border-input p-0.5 text-sm">
          {(["students", "staff"] as const).map((m) => (
            <button
              key={m}
              onClick={() => {
                setMode(m);
                reset();
              }}
              className={`rounded px-3 py-1.5 capitalize ${mode === m ? "bg-primary text-primary-foreground" : "text-muted-foreground"}`}
            >
              {m}
            </button>
          ))}
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Mark {mode === "students" ? "student" : "staff"} attendance</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>{mode === "students" ? "Student" : "Staff member"}</Label>
              <select
                className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
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
              className="grid gap-4 rounded-md border p-4 sm:grid-cols-2 lg:grid-cols-4"
            >
              <div className="space-y-2">
                <Label>Date</Label>
                <Input type="date" defaultValue={todayISO()} {...register("attendance_date")} />
                {errors.attendance_date && <p className="text-xs text-destructive">{errors.attendance_date.message}</p>}
              </div>
              <div className="space-y-2">
                <Label>Status</Label>
                <select className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm" {...register("status")}>
                  {(["present", "absent", "late", "excused"] as const).map((s) => (
                    <option key={s} value={s}>{STATUS_LABELS[s]}</option>
                  ))}
                </select>
              </div>
              <div className="space-y-2">
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
        <div className="grid gap-6 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle>Records — {personName ?? ""}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                      <th className="pb-2 font-medium">Date</th>
                      <th className="pb-2 font-medium">Status</th>
                      <th className="pb-2 font-medium">Notes</th>
                    </tr>
                  </thead>
                  <tbody>
                    {isLoading ? (
                      <tr><td colSpan={3}><Skeleton className="my-2 h-6 w-full" /></td></tr>
                    ) : records.length === 0 ? (
                      <tr><td colSpan={3} className="py-8 text-center text-muted-foreground">
                        No attendance marked yet.
                      </td></tr>
                    ) : (
                      records.map((r) => (
                        <tr key={r.id} className="border-b last:border-0 hover:bg-accent/40">
                          <td className="py-2.5">{r.date}</td>
                          <td className="py-2.5">
                            <span className={`rounded-full px-2 py-0.5 text-xs capitalize ${
                              r.status === "present" ? "bg-emerald-500/15 text-emerald-600" :
                              r.status === "absent" ? "bg-destructive/15 text-destructive" :
                              r.status === "late" ? "bg-amber-500/15 text-amber-600" :
                              "bg-muted text-muted-foreground"
                            }`}>{STATUS_LABELS[r.status] ?? r.status}</span>
                          </td>
                          <td className="py-2.5 text-muted-foreground">{r.notes ?? "—"}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          {summary && (
            <Card>
              <CardHeader>
                <CardTitle>{mode === "students" ? "Month summary" : "Summary"}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <div className="flex justify-between"><span className="text-muted-foreground">Days</span><span className="font-medium">{summary.total_days}</span></div>
                <div className="flex justify-between"><span className="text-emerald-600">Present</span><span className="font-medium">{summary.present_days}</span></div>
                <div className="flex justify-between"><span className="text-destructive">Absent</span><span className="font-medium">{summary.absent_days}</span></div>
                <div className="flex justify-between"><span className="text-amber-600">Late</span><span className="font-medium">{summary.late_days}</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Excused</span><span className="font-medium">{summary.excused_days}</span></div>
                <div className="mt-2 border-t pt-2 flex justify-between">
                  <span className="font-medium">Percentage</span>
                  <span className="font-semibold">{summary.percentage}%</span>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}

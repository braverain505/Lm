"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Trash2, UserPlus } from "lucide-react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useActiveSchoolId,
  useArms,
  useChangeStudentClass,
  useDeleteStudent,
  useEnrollStudent,
  useRoster,
  useSessions,
  useStudents,
} from "@/hooks/use-api";
import { useAuth } from "@/providers/auth-provider";

export default function ClassRosterPage() {
  const params = useParams<{ armId: string }>();
  const armId = params.armId;
  const schoolId = useActiveSchoolId();
  const { activeSchool } = useAuth();
  const permissions = activeSchool?.permissions ?? [];
  const canChange = permissions.includes("students.enroll");
  const canDelete = permissions.includes("students.delete");
  const canEnroll = permissions.includes("students.enroll");

  const { data: sessions = [] } = useSessions();
  const currentSession = sessions.find((s) => s.is_current) ?? sessions[0] ?? null;
  const { data: arms = [] } = useArms(currentSession?.id ?? null);
  const arm = arms.find((a) => a.id === armId);

  const { data: roster = [], isLoading } = useRoster(armId);
  const { data: allStudents = [] } = useStudents({ enabled: canEnroll });

  const changeClass = useChangeStudentClass();
  const deleteStudent = useDeleteStudent();
  const enrollStudent = useEnrollStudent();
  const queryClient = useQueryClient();

  const [enrollStudentId, setEnrollStudentId] = useState("");
  const [movingStudentId, setMovingStudentId] = useState<string | null>(null);
  const [targetArmId, setTargetArmId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const otherArms = useMemo(
    () => arms.filter((a) => a.id !== armId),
    [arms, armId],
  );

  const notInClass = useMemo(() => {
    const rosterIds = new Set(roster.map((s) => s.id));
    return allStudents.filter((s) => !rosterIds.has(s.id));
  }, [allStudents, roster]);

  const report = (e: unknown) => {
    setError(e instanceof Error ? e.message : "Something went wrong");
    setNotice(null);
  };
  const clearFeedback = () => {
    setError(null);
    setNotice(null);
  };

  const studentName = (id: string) => {
    return allStudents.find((s) => s.id === id)?.full_name ?? roster.find((s) => s.id === id)?.full_name ?? "Student";
  };

  const onMove = async (studentId: string) => {
    if (!currentSession || !targetArmId) return;
    clearFeedback();
    try {
      const result = await changeClass.mutateAsync({
        studentId,
        sessionId: currentSession.id,
        targetArmId,
      });
      setMovingStudentId(null);
      setTargetArmId("");
      setNotice(`${studentName(studentId)} moved to ${result.arm_name}.`);
    } catch (e) {
      report(e);
    }
  };

  const onDelete = async (studentId: string) => {
    const name = studentName(studentId);
    if (!window.confirm(`Delete ${name}? This permanently removes their record and enrollments.`)) return;
    clearFeedback();
    try {
      await deleteStudent.mutateAsync(studentId);
      setNotice(`${name} deleted.`);
    } catch (e) {
      report(e);
    }
  };

  const onEnroll = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentSession || !enrollStudentId) return;
    clearFeedback();
    try {
      await enrollStudent.mutateAsync({
        student_id: enrollStudentId,
        arm_id: armId,
        session_id: currentSession.id,
      });
      setNotice(`${studentName(enrollStudentId)} added to ${arm?.full_name}.`);
      setEnrollStudentId("");
      queryClient.invalidateQueries({ queryKey: ["roster", schoolId, armId] });
    } catch (e) {
      report(e);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Link
            href="/classes"
            className="inline-flex items-center gap-1 rounded-md border px-2.5 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-accent"
          >
            <ArrowLeft className="h-4 w-4" /> Classes
          </Link>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">{arm?.full_name ?? "Class"}</h1>
            <p className="text-sm text-muted-foreground">
              {roster.length} student{roster.length === 1 ? "" : "s"} · {currentSession?.name}
            </p>
          </div>
        </div>
        {canEnroll && (
          <Button size="sm" onClick={() => document.getElementById("enroll-panel")?.scrollIntoView({ behavior: "smooth" })}>
            <UserPlus className="h-4 w-4" /> Add student
          </Button>
        )}
      </div>

      {notice && (
        <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-600 dark:text-emerald-400">
          {notice}
        </div>
      )}
      {error && (
        <div className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {/* Roster */}
      <Card>
        <CardContent className="overflow-x-auto p-4">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                <th className="pb-2 font-medium">Admission</th>
                <th className="pb-2 font-medium">Name</th>
                <th className="pb-2 font-medium">Gender</th>
                <th className="pb-2 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={4}><Skeleton className="my-2 h-6 w-full" /></td>
                </tr>
              ) : roster.length === 0 ? (
                <tr>
                  <td colSpan={4} className="py-10 text-center text-muted-foreground">
                    No students in this class yet.
                  </td>
                </tr>
              ) : (
                roster.map((s) => (
                  <tr key={s.id} className="border-b last:border-0 hover:bg-accent/40">
                    <td className="py-3 font-mono text-xs">{s.admission_no}</td>
                    <td className="py-3 font-medium">{s.full_name}</td>
                    <td className="py-3 capitalize">{s.gender}</td>
                    <td className="py-3">
                      <div className="flex justify-end gap-2">
                        {canChange && otherArms.length > 0 && (
                          <>
                            {movingStudentId === s.id ? (
                              <div className="flex items-center gap-1.5">
                                <select
                                  autoFocus
                                  className="h-8 w-40 rounded-md border border-input bg-transparent px-2 text-sm"
                                  value={targetArmId}
                                  onChange={(e) => setTargetArmId(e.target.value)}
                                >
                                  <option value="">Choose class…</option>
                                  {otherArms.map((a) => (
                                    <option key={a.id} value={a.id}>{a.full_name}</option>
                                  ))}
                                </select>
                                <Button
                                  variant="default"
                                  size="sm"
                                  disabled={!targetArmId || changeClass.isPending}
                                  onClick={() => onMove(s.id)}
                                >
                                  Move
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => {
                                    setMovingStudentId(null);
                                    setTargetArmId("");
                                  }}
                                >
                                  Cancel
                                </Button>
                              </div>
                            ) : (
                              <Button
                                variant="outline"
                                size="sm"
                                disabled={changeClass.isPending}
                                onClick={() => {
                                  setMovingStudentId(s.id);
                                  setTargetArmId("");
                                }}
                                title="Move to another class"
                              >
                                Move
                              </Button>
                            )}
                          </>
                        )}
                        {canDelete && (
                          <Button
                            variant="outline"
                            size="sm"
                            className="text-destructive hover:text-destructive"
                            disabled={deleteStudent.isPending}
                            onClick={() => onDelete(s.id)}
                          >
                            <Trash2 className="h-3.5 w-3.5" /> Delete
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
          {canChange && otherArms.length === 0 && roster.length > 0 && (
            <p className="pt-3 text-xs text-muted-foreground">
              Create another class to move students between classes.
            </p>
          )}
        </CardContent>
      </Card>

      {/* Enroll into this class */}
      {canEnroll && (
        <Card id="enroll-panel">
          <CardHeader>
            <CardTitle className="text-base">Add a student to {arm?.full_name ?? "this class"}</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={onEnroll} className="flex flex-wrap items-end gap-3">
              <div className="min-w-64 space-y-2">
                <Label>Student</Label>
                <select
                  className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
                  value={enrollStudentId}
                  onChange={(e) => setEnrollStudentId(e.target.value)}
                  required
                >
                  <option value="">Choose student…</option>
                  {notInClass.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.full_name} · {s.admission_no}
                    </option>
                  ))}
                </select>
              </div>
              <Button type="submit" disabled={enrollStudent.isPending || !enrollStudentId}>
                {enrollStudent.isPending ? "Adding…" : "Add"}
              </Button>
              {notInClass.length === 0 && (
                <p className="w-full text-xs text-muted-foreground">
                  All students are already in this class. Create a new student from the Students page if needed.
                </p>
              )}
            </form>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
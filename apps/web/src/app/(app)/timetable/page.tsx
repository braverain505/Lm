"use client";

import { Calendar, Loader2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  useArms,
  useGenerateSchedule,
  useSchoolMe,
  useSessions,
  useTimeSlots,
  useWeeklySchedule,
} from "@/hooks/use-api";

const DAY_LABELS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"];

export default function TimetablePage() {
  const { data: school } = useSchoolMe();
  const { data: sessions = [] } = useSessions();
  const current = sessions.find((s) => s.is_current) ?? sessions[0];
  const sessionId = current?.id ?? null;

  const { data: arms = [] } = useArms(sessionId);
  const { data: timeSlots = [] } = useTimeSlots();

  const [armId, setArmId] = useState("");

  const { data: week } = useWeeklySchedule(armId || null, sessionId);
  const { mutate: generateMutate, isPending } = useGenerateSchedule();

  const handleGenerate = () => {
    if (!sessionId) return;
    generateMutate({
      academic_session_id: sessionId,
      force_regenerate: false,
      include_rooms: false,
    });
  };

  const days = week?.days ?? [];
  const entryAt = (dayOfWeek: number, start: string) =>
    days.find((d) => d.day_of_week === dayOfWeek)?.entries.find((e) => e.period_start === start);

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Timetable</h1>
          <p className="text-sm text-muted-foreground">
            Generate and view class timetables — heuristic-based scheduling for the school day.
          </p>
        </div>
      </div>

      {/* Controls */}
      <div className="flex flex-wrap items-end gap-4">
        <div className="space-y-1">
          <label htmlFor="session" className="text-sm text-muted-foreground">Session</label>
          <select
            id="session"
            className="h-9 w-48 rounded-md border border-input bg-transparent px-3 text-sm"
            value={sessionId ?? ""}
            disabled
          >
            <option value="">No session</option>
            {sessions.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
                {s.is_current ? " (current)" : ""}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1">
          <label htmlFor="classArm" className="text-sm text-muted-foreground">Class arm</label>
          <select
            id="classArm"
            className="h-9 w-48 rounded-md border border-input bg-transparent px-3 text-sm"
            value={armId}
            onChange={(e) => setArmId(e.target.value)}
            disabled={!sessionId}
          >
            <option value="">Choose class…</option>
            {arms.map((a) => (
              <option key={a.id} value={a.id}>
                {a.full_name}
              </option>
            ))}
          </select>
        </div>
        <Button onClick={handleGenerate} disabled={!sessionId || isPending} className="w-auto">
          {isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Calendar className="h-4 w-4" />}
          Generate schedule
        </Button>
      </div>

      {/* Weekly schedule */}
      {week && armId && (
        <Card>
          <CardHeader>
            <CardTitle>
              {current?.name ?? ""} · {arms.find((a) => a.id === armId)?.full_name ?? ""}
            </CardTitle>
          </CardHeader>
          <CardContent className="py-4">
            {week.total_entries === 0 ? (
              <p className="text-sm text-muted-foreground">
                No schedule yet. Hit “Generate schedule” to build a draft from this session’s offerings.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                      <th className="py-2 pr-4">Period</th>
                      {DAY_LABELS.map((d) => (
                        <th key={d} className="py-2 pr-4">{d}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {timeSlots.map((slot, i) => (
                      <tr key={i} className="border-b last:border-0">
                        <td className="py-2 pr-4 font-medium whitespace-nowrap">{slot.label}</td>
                        {DAY_LABELS.map((_, day) => {
                          const entry = entryAt(day, slot.start);
                          return (
                            <td key={day} className="py-2 pr-4 align-top">
                              {entry ? (
                                <div>
                                  <div className="font-medium">{entry.subject_name}</div>
                                  <div className="text-xs text-muted-foreground">
                                    {entry.teacher_name ?? "—TBA"}
                                    {entry.room ? ` · ${entry.room}` : ""}
                                  </div>
                                </div>
                              ) : (
                                <span className="text-muted-foreground/50">—</span>
                              )}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Time slots info */}
      {school && (
        <Card>
          <CardHeader>
            <CardTitle>School day structure</CardTitle>
          </CardHeader>
          <CardContent className="py-4">
            <p className="text-sm text-muted-foreground">
              School hours: 8:00 – 15:00 with 35-minute periods and 5-minute breaks.
            </p>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {timeSlots.map((slot) => (
                <span
                  key={slot.label}
                  className="inline-block px-2 py-1 text-xs rounded-md bg-muted/20 text-muted"
                >
                  {slot.label}
                </span>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

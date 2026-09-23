"use client";

// The public result portal hands back a short-lived (30 min) bearer token when a
// parent checks in. It is kept in sessionStorage rather than the URL so a result
// link cannot be pasted into a chat later and keep working, and rather than
// localStorage so closing the tab ends the session.
//
// Both the check-in form (on /login) and the card viewer (/check-result) speak
// this module, so the shape lives in exactly one place.

import type { ReportLayout } from "@clearis/shared";

const KEY = "clearis.portal.session";

export type PortalSession = {
  token: string;
  student: { student_id: string; admission_no: string; full_name: string };
  school: { id: string; name: string; slug: string };
  /**
   * The school's report card design, handed back with the check-in.
   *
   * It rides on the session rather than on each card because it is school-wide:
   * one check-in, one design. That is what makes a parent's copy and the exam
   * office's copy the same document (previously the viewer picked a style from
   * this browser's localStorage, so they could differ).
   */
  report_template?: ReportLayout | null;
};

export function savePortalSession(session: PortalSession): void {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(session));
  } catch {
    /* private mode / storage disabled — the viewer will bounce back to /login */
  }
}

export function readPortalSession(): PortalSession | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as PortalSession;
    if (!parsed?.token || !parsed?.student?.admission_no) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function clearPortalSession(): void {
  try {
    sessionStorage.removeItem(KEY);
  } catch {
    /* ignore */
  }
}

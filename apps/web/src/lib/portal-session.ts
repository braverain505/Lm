"use client";

// The public result portal hands back a short-lived (30 min) bearer token when a
// parent checks in. It is kept in sessionStorage rather than the URL so a result
// link cannot be pasted into a chat later and keep working, and rather than
// localStorage so closing the tab ends the session.
//
// Both the check-in form (on /login) and the card viewer (/check-result) speak
// this module, so the shape lives in exactly one place.

const KEY = "clearis.portal.session";

export type PortalSession = {
  token: string;
  student: { student_id: string; admission_no: string; full_name: string };
  school: { id: string; name: string; slug: string };
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

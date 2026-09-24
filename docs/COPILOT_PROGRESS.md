# School Copilot — Progress Log

A running, dated log of work on the school copilot so progress is easy to track.
For the *design* of the copilot and the report-card designer, see
[`COPILOT_AND_REPORT_CARD_DESIGNER.md`](./COPILOT_AND_REPORT_CARD_DESIGNER.md).

---

## 2026-09-24 — Admin commands actually fire; chat UX (delete + messenger look)

### Reported problem

In the running app, an admin command typed naturally did not work and the
copilot answered as if it could not do it at all:

> **User:** I want you to add Godiya Markus to nursery 2
> **Copilot:** I'm sorry, but I don't have the ability to add a student to a class…

…and the follow-up "can you give me the names of those students?" returned
nothing. Two separate causes:

1. **Command detection missed the phrasing.** `_ADMIT_HEAD` in
   `copilot_actions.py` only accepted `please / can you / could you / i want to /
   i'd like to`. The sentence "I want **you** to add …" matched none of them, so
   the turn was never seen as a command — it fell through to the LLM, which
   correctly said it cannot write. The bare "add Genesis John to Nursery 1" form
   worked, which is why the tests were green.

   Evidence (before the fix):
   ```
   OK   add Godiya Markus to nursery 2
   FAIL I want you to add Godiya Markus to nursery 2      <- the reported bug
   OK   please add Godiya Markus to nursery 2
   OK   can you add Godiya Markus to nursery 2
   ```

2. **A stale deployment is also possible.** If the running instance predates the
   admin-command work it will show the same "I can't do that" answer for *every*
   command shape. **Redeploy** after this change (see "Deploying" below).

### What changed

| # | Change | Files |
|---|---|---|
| 1 | **Polite preamble is stripped before parsing.** New `_POLITE` / `_strip_polite`; `detect_action` strips once up front so every detector sees the bare command. Handles `I want you to…`, `I want to…`, `I'd like you to…`, `I'd love to…`, `I would like you to…`, `kindly…`, `help me…`, `go ahead and…`, `let's…`, `please…`, `can/could/would/will you…`. | `apps/api/app/services/copilot_actions.py` |
| 2 | **Delete a chat from history.** `DELETE /copilot/conversations/{id}` (204; tenant-checked, messages cascade). Rail + chat-header trash buttons with a confirm. | `services/copilot_service.py` (`delete_conversation`), `routers/copilot.py`, `packages/shared/src/client.ts`, `apps/web/src/hooks/use-api.ts`, `apps/web/src/app/(app)/copilot/page.tsx` |
| 3 | **The intent label is gone from the UI.** Assistant bubbles now show just the time, not `intent class_roster · 05:37`. | `apps/web/src/app/(app)/copilot/page.tsx` |
| 4 | **Messenger-style chat window.** One rounded frame: a "Chats" sidebar (avatar, title, time, hover-trash), a chat header (bot avatar, title, status line, delete), bubbles left/right with tails, auto-scroll to the newest message, and a pill composer with a circular send button. On phones the sidebar collapses and a thread picker + New button appear in the header. | `apps/web/src/app/(app)/copilot/page.tsx` |
| 5 | **Tests.** Natural phrasing (propose → supply gender → confirm → enrolled), contracted politeness on a move, polite-phrasing subject creation, delete removes thread + messages, unknown thread is a 404. | `apps/api/tests/test_copilot_actions.py` |

### Verification (all green)

```
# API — 300 tests
cd apps/api && DATABASE_URL=... DEBUG=true COOKIE_SECURE=false ../../.venv/bin/python -m pytest -q -p no:warnings

# Web — 70 tests
cd apps/web && npm test

# Web typecheck
cd apps/web && npx tsc --noEmit
```

Plus a **live end-to-end run** against the real HTTP API (scratch database,
`DEBUG=true`), reproducing the exact reported sentence:

| Turn | Input | Result |
|---|---|---|
| 1 | `I want you to add Godiya Markus to nursery 2` | `intent=admit_student`, `source=command`, `status=pending`, `missing=[gender]`, class `Nursery 2` |
| 2 | `male` | `status=pending`, `missing=[]`, admission no `STU-2026-001` |
| 3 | `confirm` | `status=done` — student row + current enrolment to `Nursery 2` |
| — | — | `audit_logs`: `create` / `student` / "Admitted via the school copilot chat command" |
| 4 | `DELETE /copilot/conversations/{id}` | `204`, then `404`; `copilot_messages` for it = `0` |

### Deploying

The API and web must both be redeployed for this to take effect in the running
app; the command layer is API-side and the chat window is web-side.

---

## Still open

1. **Redeploy** the API + web so the running instance carries this change.
2. **Manual/browser pass** on `/copilot`: send a command, supply the gender,
   `confirm`, then check `/students` and the audit log; then delete a chat and
   confirm it leaves the rail.
3. **While a required field is missing, a question is not answered** — the
   copilot stays on the command and re-asks (by design, pinned by
   `test_half_specified_command_keeps_asking_and_offers_cancel`). Worth a UX
   revisit if users find it confusing: today "give me the names of those
   students" mid-admission re-asks for the gender instead of listing the class.
4. **Optional follow-ups** for the chat: rename a chat, search the rail, and a
   "delete all chats" action.

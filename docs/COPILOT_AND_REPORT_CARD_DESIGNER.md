# School Copilot + Report Card Designer — Handoff / Status

**Last updated:** 2026-09-24
**Status:** Both features are implemented and verified green (API tests, web tests, web typecheck, production build). The work is committed (`a45f6f4`, greeting fix in `6dc7b7e`). The copilot now also runs **admin commands** (section 3b), and its chat window has been reworked (section 3c). For the dated, running log of copilot work see [`COPILOT_PROGRESS.md`](./COPILOT_PROGRESS.md). This document is written so another model (or a human) can pick it up with no prior context.

---

## 1. What the task was

Two connected features for each school (tenant):

1. **A conversational school copilot** — a chat assistant that answers questions *in the context of that one school's real records* (counts, subjects, classes, score-entry progress, published results, top performers, term summaries). It must never invent numbers. It is now conversational (LLM-phrased) on top of a deterministic rules engine, and it falls back to the rules text when no LLM is available.
2. **A drag-and-drop report card designer** — each school builds its own report card document out of widgets, reorders them by dragging, edits per-widget settings, previews the A4 card, and saves it server-side so *every* renderer (print, on-screen, parent portal) uses the same design.

Both are per-school (tenant-scoped). This replaced a browser-localStorage "pick 1 of 4 CSS themes" approach.

---

## 2. Current status (verification results)

Run from the repo root `clearis/`:

```bash
# Backend tests — the whole suite passes (273 tests)
cd apps/api && DEBUG=true COOKIE_SECURE=false ../../.venv/bin/python -m pytest -q -p no:warnings
#   -> the full API suite passes

# Copilot tests specifically — the Q&A engine, the command layer, the report card
cd apps/api && DEBUG=true COOKIE_SECURE=false ../../.venv/bin/python -m pytest tests/test_copilot.py tests/test_copilot_actions.py tests/test_report_card_templates.py -q

# Web typecheck — clean
cd apps/web && npx tsc --noEmit

# Web unit/component tests — 70 pass (Vitest + Testing Library)
#   report-layout.test.ts    — the catalog + editing helpers (pure logic)
#   report-card-designer.test.tsx — palette, canvas, inspector, theme, preview
cd apps/web && npm test

# Web production build — SUCCEEDS (the old "SIGBUS" blocker is gone)
cd apps/web && NODE_OPTIONS="--max-old-space-size=4096" npx next build
```

### Environment gotcha (read this before running tests)
`apps/api/.env` in this checkout does **not** set `DEBUG`, so `Settings.debug` defaults to `False` and the app's startup `validate_production_config()` runs and **raises** (weak 25-byte `JWT_SECRET`, `COOKIE_SECURE=false`, `DEV_EMAIL`). The lifespan only skips validation when `settings.debug and not settings.cookie_secure`. So the test suite is run with `DEBUG=true COOKIE_SECURE=false` exported. Without those two env vars every test *errors at setup* with `ValueError: Production configuration validation failed` — that is an **environment/config issue, not a code bug**. If you want tests to "just run", either export those vars or add `DEBUG=true` to `apps/api/.env` for local dev (do NOT relax the validator itself — it is intentional production hardening).

The previously documented `SIGBUS` Next.js build crash is no longer reproducible; the build completes cleanly.

---

## 3. Feature 1 — the conversational school copilot

### Where it lives

| Layer | File | Role |
|---|---|---|
| Service (the core) | `apps/api/app/services/copilot_service.py` | Two-layer answer engine: rules engine resolves facts, LLM phrases the answer grounded on them. |
| Models | `apps/api/app/models/copilot.py` | `CopilotConversation`, `CopilotMessage` (already existed). |
| Router | `apps/api/app/routers/copilot.py` | HTTP surface (below). |
| Schemas | `apps/api/app/schemas/copilot.py` | `CopilotAsk`, `AskResponse`, `ConversationOut/Detail`, `MessageOut`, `IntentOut`. |
| LLM client | `apps/api/app/services/llm_client.py` | `complete_text(...)` used by the LLM layer. |
| Metering | `apps/api/app/services/ai_service.py` | `AI_FEATURE_COPILOT`, `_check_ai_quota`, `_meter_inc`. |
| Permission | `apps/api/app/core/permissions.py` | `AI_COPILOT` (`ai.copilot`). |
| UI page | `apps/web/src/app/(app)/copilot/page.tsx` | Chat rail + thread + composer + payload cards. |
| UI hooks | `apps/web/src/hooks/use-api.ts` | `useCanCopilot`, `useCopilotIntents`, `useConversations`, `useConversation`, `useAskCopilot`. |
| Nav | `apps/web/src/components/nav-config.ts` | `/copilot` = "Clearis AI", perm `ai.copilot`. |

### How an answer is produced (two layers — this is the whole design)

1. **Layer 1 — the rules engine** (`_answer`, handlers in `_INTERNAL_ORDER`). A catalog of question *intents* is resolved against the school's real rows and composed into an answer with actual numbers. Handlers, in order:
   `help`, `class_subjects`, `class_snapshot`, `student_report`, `subject_average`, `top_performers`, `term_summary`, `readiness`, `school_overview`.
   It also pins the conversation's **context slots** (`arm_id`, `subject_id`, `student_id`) in `conversation.context`, so follow-ups like "what about English?" or "how many boys?" resolve against the prior turn. Unknown questions produce an honest "I couldn't understand that" plus example phrasings — **never a fabricated answer**.
2. **Layer 2 — the LLM** (`_llm_answer` + `_grounding_brief`). The resolved facts become a *grounding brief* (school name/type, current session, totals, class arms with live enrollment counts, subjects, term score-entry readiness, and the rules answer+payload). The model is told in `_COPILOT_SYSTEM` to state **only** numbers from the brief, say when it lacks information, use British English, plain text, 1–4 sentences. Every failure mode (no `groq_api_key`, network error, timeout, answer <20 or >2000 chars) returns `None` and the turn uses the deterministic rules text. **That fallback is the documented offline behaviour, not a degraded mode.**

### Key invariants (do not break)
- **Published-only for performance questions.** `_published_rows` reads only `Result` rows with `status == PUBLISHED`, from the frozen `published_snapshot` — the same record report cards and the public portal use. Readiness (score entry) questions read *live* counts by design.
- **Metering exactly once per assistant turn** under `ai.copilot` via `_meter_inc`, carrying real `provider/model/tokens_in/tokens_out` when an LLM produced the text. `payload["source"]` is `"llm"` or `"rules"` so the UI can say which layer answered.
- **Tenant isolation.** Conversations are scoped to `school_id`; `test_conversation_is_tenant_isolated` covers this.
- **Prompt bounding.** `_MAX_ARMS_IN_BRIEF=30`, `_MAX_SUBJECTS_IN_BRIEF=40`, `_MAX_HISTORY_TURNS=6`, `_MAX_HISTORY_CHARS=300`, `_MAX_ANSWER_CHARS=2000` — a big school must not turn one question into a 200 KB request.
- **Degradation is safe.** The brief/LLM layer is wrapped so an exception can never fail the turn (`except Exception: logger.exception(...); llm = None`).

### HTTP surface (all gated on `ai.copilot`, and `ensure_ai` for the premium gate)
- `POST /api/copilot/ask` → creates/appends a conversation, meters, returns `{conversation, message}`.
- `GET /api/copilot/conversations` → newest first (chat rail).
- `GET /api/copilot/conversations/{id}` → thread + full messages.
- `GET /api/copilot/intents` → suggested-question chips for the UI.

### Tests
`apps/api/tests/test_copilot.py` pins the deterministic rules text exactly, plus: greetings route to `small_talk` (not a stats dump); LLM used & metered as the real provider; grounding brief carries real facts (no inventions); unusable LLM output falls back to rules; provider exception never fails the turn; LLM can answer a question no intent matches; follow-up history is sent to the model; tenant isolation.

---

## 3b. Admin commands — the copilot can now *change* records

**Status: implemented and green (20 tests in `apps/api/tests/test_copilot_actions.py`).**

Before this, /copilot could only read: "add Genesis John to Nursery 1" got "I don't have that information", and the follow-up "give me the names" got nothing because `class_snapshot` returns counts only. Both now work.

### The three rules (this is the design)
1. **The model never executes anything.** Commands are parsed by rules in `copilot_actions.py`, never offered to the LLM as a tool. A command turn never calls the provider — `answer_payload["source"]` is `"command"`, and a test asserts the LLM is not invoked.
2. **Nothing is written without an explicit confirmation.** A command first renders a *proposal* naming exactly what will change (with real class names and the generated admission number); the user must reply `confirm`. The pending proposal lives on `CopilotConversation.context['pending_action']` (JSONB), so it survives turns. `cancel` drops it; a question asked while nothing is missing also drops it; a new command replaces it. While a required field is *missing* the copilot stays on the command and re-asks (the prompt tells the user to say `cancel` to get out).
3. **Permissions are re-checked per action, server-side.** `/copilot/ask` is gated only on `ai.copilot`; each command additionally names the permission it needs and the caller's real `permission_codes` are consulted (a principal may chat and still be refused `students.create`). The same check runs at propose time (honest refusal up front) and again at execution.

A confirmed run is journalled to `audit_logs` (`entity_type` = the record family, `details` = "… via the school copilot chat command"). Execution runs inside a **SAVEPOINT** so a two-step action that fails halfway (create the student → enrol them) unwinds its own rows while the conversation turn still commits with an honest reply. `execute_proposal` never raises for an expected failure.

### What it can do
| Command (example) | Code | Needs |
|---|---|---|
| `add Genesis John to Nursery 1` | `admit_student` | `students.create` + `students.enroll` |
| `move Genesis John to Nursery 2` | `change_class` | `students.enroll` |
| `add teacher Grace Ade` | `add_staff` | `staff.create` |
| `create subject Further Mathematics` | `create_subject` | `academics.manage` |
| `create class Nursery 3` | `create_class_arm` | `academics.manage` |
| `create session 2027/2028` | `create_session` | `academics.manage` |
| `create second term in 2025/2026` | `create_term` | `academics.manage` |
| `submit / verify / approve results for JSS 1 A` | `*_results` | the matching results permission |
| `publish results for JSS 1 A` | `publish_results` | `results.publish` |
| `compile results for JSS 1 A` | `compile_results` | `results.verify` + `approve` + `publish` |

Results commands run across every subject offered in that class for the term (the live/current term unless one is named). Admission numbers (`STU-<year>-NNN`) and staff numbers (`STF-<year>-NNN`) are **generated**, never guessed; a subject's code is derived from its name and de-duplicated. A gender is **never** invented — it is asked for.

### Parsing notes (do not "simplify" these)
- Arm/class names resolve by **exact normalised match first** (`_norm`, so `"JSS 1 A"` ≡ `"jss1a"`), then prefix/containment. This is deliberate: the old `_name_in` stem matcher drops numeric tokens (`"Nursery 1"` reduced to just `["nursery"]`), which would resolve "Nursery 10" to "Nursery 1". For the free-question roster the longest stored name found in the text wins.
- Detectors are ordered most-specific-first in `_DETECTORS`, and every one of them requires its own keyword (`session` / `term` / `class|arm` / `subject` / `teacher|staff` / a `to|in` clause), so "add X to Y" can never be read as "add staff".
- **A polite preamble is stripped once, in `detect_action`, before any detector runs** (`_POLITE` / `_strip_polite`): `please…`, `can/could/would/will you…`, `I want (you) to…`, `I'd like (you) to…`, `I'd love to…`, `I would like you to…`, `kindly…`, `help me…`, `go ahead and…`, `let's…`. Without it, "I want you to add Genesis John to Nursery 2" matched no detector and fell through to the LLM, which answered "I can't do that" — the same failure a *bare* "add Genesis John to Nursery 2" never hits. Note the contracted forms collapse the space (`I'd`, not `I 'd`), which is why the alternation carries both shapes.
- The read side gained one intent: **`class_roster`** (`_h_class_roster` in `copilot_service.py`), registered *before* `class_snapshot` so "list the students in JSS 1A" names them while "how many students are in JSS 1A" still falls through to the count. It follows the conversation's pinned `arm_id`, which is what makes the bare "give me the names" work.

### Files
| Piece | File |
|---|---|
| The command engine | `apps/api/app/services/copilot_actions.py` (new) |
| Roster read intent + command wiring | `apps/api/app/services/copilot_service.py` (`_h_class_roster`, `_command_reply`, `_resume_pending`, `_start_command`, `_run_proposal`; `ask_copilot` now takes `permission_codes` / `is_superadmin`) |
| Route | `apps/api/app/routers/copilot.py` (passes the real permission set through) |
| UI cards | `apps/web/src/app/(app)/copilot/page.tsx` (`ActionCard`, roster table, copy) |
| Tests | `apps/api/tests/test_copilot_actions.py` (new) |
| Delete a chat | `copilot_service.delete_conversation` + `DELETE /copilot/conversations/{id}` (§3c) |

`copilot_actions.py` deliberately imports **nothing** from `copilot_service` (the dependency runs one way only) and re-implements the tiny matching helpers; do not wire them together or you get an import cycle.

---

## 3c. The chat window (2026-09-24)

Three UI/behavior changes on `/copilot`, all in `apps/web/src/app/(app)/copilot/page.tsx` (plus the delete endpoint):

1. **The intent label is no longer rendered.** An assistant bubble shows its time only — `intent class_roster · 05:37` was developer noise. (`answer_payload` still carries `intent`; only the label is gone.)
2. **Delete a chat from history.** `DELETE /copilot/conversations/{id}` → 204. It is gated on `ai.copilot` like the other routes and resolves through `get_conversation`, so another school's thread is a 404, never a delete. Messages go with it (the `messages` relationship cascades) and there is **no** audit entry — a chat is the user's own scratch space, not a school record. The rail row and the chat header both expose a trash button behind a `window.confirm`.
3. **Messenger layout.** One rounded frame holds a "Chats" sidebar and the thread; bubbles have tails (user → right/primary, assistant → left/carded with a bot avatar), the message pane auto-scrolls to the newest turn, and the composer is a pill with a circular send button. On phones the sidebar collapses and a thread `<select>` + New button appear in the chat header.

---

## 4. Feature 2 — the drag-and-drop report card designer

### The contract is deliberately two halves (add a widget on BOTH sides, or not at all)
- **TypeScript catalog:** `apps/web/src/lib/report-layout.ts` (`WIDGET_CATALOG`, `newWidget`, `prop`, `moveWidget`, `removeWidget`, `updateWidget`, `setWidgetProp`, `canAdd`, `DEFAULT_LAYOUT`, `cloneLayout`, `themeClass`).
- **Server catalog + validation:** `apps/api/app/schemas/report_card.py` (`WIDGET_TYPES`, `THEMES`, `strip_tags`, `LayoutWidget`, bounds `MAX_WIDGETS=40`, `MAX_PROPS=12`, `MAX_PROP_VALUE=2000`, `MAX_CUSTOM_TEXT=2000`).
- **Shared types (zod):** `packages/shared/src/contracts.ts` → `REPORT_WIDGET_TYPES`, `REPORT_THEMES`, `ReportWidgetSchema`, `ReportLayoutSchema`, `ReportCardTemplateSchema`, `ReportCardDesignSchema`, `ReportCardTemplateIn/PatchSchema`. Also `packages/shared/src/client.ts`.

**14 widget types** (closed set): `header`, `student_info`, `cognitive_domain`, `psychomotor_domain`, `performance_summary`, `grading_key`, `best_in_subjects`, `attendance`, `conduct`, `next_term`, `comments`, `signatures`, `custom_text`, `spacer`.
**4 themes:** `classic`, `modern`, `elegant`, `minimal` (map to `rc-template-<id>` classes in `report-card-templates.css`).

### Backend
| Feature | File |
|---|---|
| Model | `apps/api/app/models/report_card.py` → `ReportCardTemplate` (`report_card_templates`: unique `(school_id, name)`, index `(school_id, is_default)`, `layout` JSONB). |
| Service | `apps/api/app/services/report_card_service.py` (`list_templates`, `get_template`, `create_template`, `update_template`, `set_default`, `duplicate_template`, `delete_template`, `resolve_default`, `default_layout`, `validate_layout`, builtin `BUILTIN_DEFAULT_LAYOUT`). |
| Router | `apps/api/app/routers/report_card_templates.py` (prefix `/report-card-templates`). |
| Schemas | `apps/api/app/schemas/report_card.py`. |
| Migration | `apps/api/alembic/versions/0015_report_card_templates.py` (revises `0014_student_result_codes`; builds the table from model metadata, idempotent). |
| Registration | `apps/api/app/main.py` includes `report_card_templates` router; `apps/api/app/models/__init__.py` exports the model. |
| Tests | `apps/api/tests/test_report_card_templates.py`. |

**API surface** (`/api/report-card-templates`):
- `GET ""` (list, any member) — default first.
- `GET "/default"` (`ActiveSchool`, any member) — **always answers**: saved default, or the built-in card with `builtin: true` / `template_id: null`. Renderers never invent a fallback.
- `GET "/{id}"` (any member).
- `POST ""`, `PATCH "/{id}"`, `POST "/{id}/default"`, `POST "/{id}/duplicate"`, `DELETE "/{id}"` — all require `school.manage` (school admin / principal / owner / director). Exam Office prints, does not redesign.

Semantics worth preserving: first design becomes default; `set_default` flips the flag in one transaction (exactly one default at rest); deleting the default promotes a successor; names are unique per school; every write is audited; free text is tag-stripped (but NOT HTML-escaped — the card renders React text nodes) and length-bounded; unknown widget type / theme / duplicate widget ids / empty list / oversized layout are rejected at the edge.

### Frontend
| Piece | File |
|---|---|
| Builder (the DnD component) | `apps/web/src/components/report-card-designer.tsx` (`ReportCardDesigner`, palette + canvas + inspector + preview + `DragOverlay`). |
| Page (workspace) | `apps/web/src/app/(app)/reports/designer/page.tsx` (list/save/default/duplicate/delete, unsaved-changes guard). |
| Renderer | `apps/web/src/components/report-card-document.tsx` (draws all 14 widget types from a `layout`; falls back to the built-in card when no layout). |
| Theme picker | `apps/web/src/components/report-template-picker.tsx`. |
| Style/theme CSS | `apps/web/src/app/report-card.css`, `apps/web/src/app/report-card-templates.css`. |
| Hooks | `apps/web/src/hooks/use-api.ts` → `useReportCardDesign`, `useReportCardTemplates`, `useCreateReportCardTemplate`, `useUpdateReportCardTemplate`, `useSetDefaultReportCardTemplate`, `useDuplicateReportCardTemplate`, `useDeleteReportCardTemplate`. |
| Nav | `apps/web/src/components/nav-config.ts` → `/reports/designer`. |

**Drag-and-drop mechanics** (`@dnd-kit/core` + `@dnd-kit/sortable` + `@dnd-kit/modifiers`, already in `apps/web/package.json`):
- Palette items are `useDraggable` (`id: palette:<type>`); canvas rows are `useSortable`; the canvas itself is `useDroppable({id:"canvas"})` so a palette block dropped on empty space lands at the end.
- `handleDragEnd` distinguishes palette-adds (insert at the hovered row index) from canvas reorders (`arrayMove`). Vertical-axis restricted. `PointerSensor` uses a `distance: 4` activation constraint so a click still selects instead of being swallowed as a micro-drag; `KeyboardSensor` + `sortableKeyboardCoordinates` keep it keyboard-accessible. Only the grip handle is a drag surface, so row buttons stay clickable.
- The component is **fully controlled** (`layout` in, `onChange` out); the page owns undo/revert, save and "unsaved changes" (a snapshot comparison, not a flag).
- Preview mode renders `ReportCardDocument` with a synthetic, clearly-labelled `SAMPLE_CARD` (never a real child's marks). `unique` widgets can't be duplicated; `width: "full" | "half"` pairs blocks side by side.

### Rendering pipeline (the design reaches everyone)
`GET /default` is read by the reports page (`apps/web/src/app/(app)/reports/page.tsx`), the settings page (`/settings`), the print/PDF path, and the public result portal (`apps/api/app/routers/portal.py` + `apps/api/app/schemas/portal.py` carry the school design). Changing a style always writes the school's design (creating the first one if needed) — never a browser preference.

---

## 5. Files touched (working tree)

**New (untracked):**
```
apps/api/alembic/versions/0015_report_card_templates.py
apps/api/app/models/report_card.py
apps/api/app/routers/report_card_templates.py
apps/api/app/schemas/report_card.py
apps/api/app/services/report_card_service.py
apps/api/tests/test_report_card_templates.py
apps/web/src/app/(app)/reports/designer/page.tsx
apps/web/src/components/report-card-designer.tsx
apps/web/src/lib/report-layout.ts
# admin commands (this change)
apps/api/app/services/copilot_actions.py
apps/api/tests/test_copilot_actions.py
```

**Modified:** `apps/api/app/{config,main}.py`, `models/__init__.py`, `routers/portal.py`, `schemas/portal.py`, `seed.py`, `services/copilot_service.py`, `services/email_service.py`, `tests/test_copilot.py`, `tests/test_{platform,superadmin}.py`; `apps/web/src/app/(app)/{reports,settings}/page.tsx`, `app/{check-result,login}/page.tsx`, `app/report-card.css`, `components/{nav-config,report-card-document,report-template-picker}.ts(x)`, `hooks/use-api.ts`, `lib/{portal-session,report-templates}.ts`, `apps/web/package.json`; `packages/shared/src/{client,contracts}.ts`; `docs/PRODUCTION_SECURITY.md`, `package-lock.json`.

> Note: the `copilot_service.py` diff is large (+352 lines) — that is the LLM layer + grounding brief + the expanded intent catalog. `email_service.py`/`config.py` changes are unrelated SMTP/Resend transport hardening; `report-card.css` + `report-card-document.tsx` are the widget renderer rewrite.

---

## 6. What remains / suggested next steps

The features are functionally complete and green. Remaining items are polish and release hygiene, roughly in priority order:

1. ~~Commit the work.~~ **Done** — the features are committed (`a45f6f4`, `6dc7b7e`, `6dc3181`, plus the copilot admin-command layer).
2. **Manual/browser verification** (not automated): open `/reports/designer`, drag palette→canvas, reorder, edit each widget's settings, switch theme + preview, save, set default, duplicate, delete; then confirm `/reports`, `/settings` and the public portal all render the saved design. Open `/copilot`, ask a question and a follow-up, and confirm the `source` badge shows `rules` when no Groq key is configured. Then walk one command end-to-end: type "add <name> to <class>", supply the gender, reply "confirm", and check the pupil exists in `/students` and the row is in the audit log.
3. **Check `/copilot` is reachable for the intended roles** — it needs `ai.copilot` (leadership templates) AND the school's premium/AI plan (`ensure_ai`). Verify the permission is provisioned for the roles in `apps/api/app/seed.py`, and that `useCanCopilot` matches.
4. ~~Add frontend tests for the designer.~~ **Done** — `apps/web` now uses Vitest (`vitest.config.ts`, `vitest.setup.ts`, `npm test`, 70 tests). Two real bugs were found and fixed in the process:
   - `report-layout.ts`'s `prop()` compared `typeof raw === fallback` instead of `typeof raw === typeof fallback`, so every stored **string and boolean** setting was silently discarded (custom headings reverted to defaults; every inspector toggle read as off). Numbers still coerced, which is why it slipped through. Fixed + pinned by tests.
   - The palette said "Drag onto the card, or click to add" but had no click handler. `PaletteItem` now adds on click, with a `droppedRef` guard so the click a completed drop emits is not counted as a second add.
   Still **not** covered: live drag-and-drop (jsdom can't measure layout) and the reports/settings/portal pages. Those remain manual or e2e work.
5. **Follow-up idea (not started):** surface the copilot contextually *from* a dashboard widget (management/teacher dashboards already reference copilot) so it appears "in the context of the school" without navigating to `/copilot`.

If you change the widget catalog, remember the two-halves rule: update `WIDGET_TYPES` (Python) **and** `WIDGET_CATALOG` (TS) **and** `ReportCardDocument`'s switch, or a design will be rejected/rendered wrong.

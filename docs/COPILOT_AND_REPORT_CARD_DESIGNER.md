# School Copilot + Report Card Designer — Handoff / Status

**Last updated:** 2026-09-23
**Status:** Both features are implemented and verified green (API tests, web typecheck, production build). The work is **uncommitted** in the working tree. This document is written so another model (or a human) can pick it up with no prior context.

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
#   -> 273 passed

# Copilot + report-card tests specifically (40 tests)
cd apps/api && DEBUG=true COOKIE_SECURE=false ../../.venv/bin/python -m pytest tests/test_copilot.py tests/test_report_card_templates.py -q

# Web typecheck — clean
cd apps/web && npx tsc --noEmit

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
`apps/api/tests/test_copilot.py` (22 tests) pins the deterministic rules text exactly, plus: LLM used & metered as the real provider; grounding brief carries real facts (no inventions); unusable LLM output falls back to rules; provider exception never fails the turn; LLM can answer a question no intent matches; follow-up history is sent to the model; tenant isolation.

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
| Tests | `apps/api/tests/test_report_card_templates.py` (18 tests). |

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
```

**Modified:** `apps/api/app/{config,main}.py`, `models/__init__.py`, `routers/portal.py`, `schemas/portal.py`, `seed.py`, `services/copilot_service.py`, `services/email_service.py`, `tests/test_copilot.py`, `tests/test_{platform,superadmin}.py`; `apps/web/src/app/(app)/{reports,settings}/page.tsx`, `app/{check-result,login}/page.tsx`, `app/report-card.css`, `components/{nav-config,report-card-document,report-template-picker}.ts(x)`, `hooks/use-api.ts`, `lib/{portal-session,report-templates}.ts`, `apps/web/package.json`; `packages/shared/src/{client,contracts}.ts`; `docs/PRODUCTION_SECURITY.md`, `package-lock.json`.

> Note: the `copilot_service.py` diff is large (+352 lines) — that is the LLM layer + grounding brief + the expanded intent catalog. `email_service.py`/`config.py` changes are unrelated SMTP/Resend transport hardening; `report-card.css` + `report-card-document.tsx` are the widget renderer rewrite. Nothing is committed yet.

---

## 6. What remains / suggested next steps

The features are functionally complete and green. Remaining items are polish and release hygiene, roughly in priority order:

1. **Commit the work.** It is entirely uncommitted. Suggested split: (a) conversational copilot, (b) report card templates + designer + migration `0015`, (c) email/config transport hardening (looks unrelated — likely should be its own commit). Per repo convention use the `Generated with Codebuff` footer.
2. **Manual/browser verification** (not automated): open `/reports/designer`, drag palette→canvas, reorder, edit each widget's settings, switch theme + preview, save, set default, duplicate, delete; then confirm `/reports`, `/settings` and the public portal all render the saved design. Open `/copilot`, ask a question and a follow-up, and confirm the `source` badge shows `rules` when no Groq key is configured.
3. **Check `/copilot` is reachable for the intended roles** — it needs `ai.copilot` (leadership templates) AND the school's premium/AI plan (`ensure_ai`). Verify the permission is provisioned for the roles in `apps/api/app/seed.py`, and that `useCanCopilot` matches.
4. **Optional:** add frontend/e2e tests for the designer (there are none — only typecheck/build cover the web side). Backend coverage is good.
5. **Follow-up idea (not started):** surface the copilot contextually *from* a dashboard widget (management/teacher dashboards already reference copilot) so it appears "in the context of the school" without navigating to `/copilot`.

If you change the widget catalog, remember the two-halves rule: update `WIDGET_TYPES` (Python) **and** `WIDGET_CATALOG` (TS) **and** `ReportCardDocument`'s switch, or a design will be rejected/rendered wrong.

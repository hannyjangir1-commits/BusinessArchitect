# Venture Atlas / BusinessArchitect — Application Issues and Fixes Log

This document records confirmed issues, evidence, root causes, durable fixes, and verification methods identified during the autonomous full-workspace audit and Phase 8.1 independent review corrections in accordance with Section 7 and Deliverable B of the Master Prompt.

---

## Issue Registry Summary

| Finding ID | Severity | Affected Area / Paths | Summary of Issue | Verification | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **ISSUE-01** | **LOW** | `client/src/components/MarketResearchModule.tsx` | Market Research evidence status text node was unsegmented from its prefix label in the DOM, preventing test query utilities from isolating the dynamic note. | `npx vitest run src/__tests__/batch_03_security_and_race_conditions.test.tsx` (10/10 passed) | **VERIFIED & FIXED** |
| **ISSUE-02** | **LOW** | `client/src/components/common/Dialog.tsx` | `useCallback` passed raw function reference instead of inline function expression, triggering React Compiler lint warning. | `npm run lint` (0 errors) | **VERIFIED & FIXED** |
| **ISSUE-03** | **LOW** | `client/src/components/BMCModule.tsx` & `AllTasksTable.tsx` | Unused imports (`useEffect`, `Sparkles`, `X`, `Flag`, `CheckCircle2`, `isTaskCompleted`) triggering lint warnings. | `npm run lint` (0 errors) | **VERIFIED & FIXED** |
| **ISSUE-04** | **LOW** | `client/src/App.tsx` | React ref `.current` accessed in effect cleanup closure without capturing local reference, triggering `react-hooks/exhaustive-deps`. | `npm run lint` (0 errors) | **VERIFIED & FIXED** |
| **ISSUE-05** | **LOW** | `client/src/components/OverviewModule.tsx` | Action explanation text claimed "fresh Copilot conversation will begin", but project copy also clones message history. | Visual inspection & `npm test` | **VERIFIED & FIXED** |
| **ISSUE-06** | **LOW** | `server/app/main.py` | `status.HTTP_413_REQUEST_ENTITY_TOO_LARGE` deprecated in modern Starlette in favor of RFC 9110 `HTTP_413_CONTENT_TOO_LARGE`. | `pytest` warning eliminated | **VERIFIED & FIXED** |
| **ISSUE-07** | **LOW** | `server/app/api/modules.py` | Deprecated `status.HTTP_422_UNPROCESSABLE_ENTITY` triggered Starlette deprecation warnings on import. | `pytest` warning eliminated | **VERIFIED & FIXED** |
| **ISSUE-08** | **MEDIUM** | `server/app/api/auth.py` & `server/app/api/admin/auth.py` | `logout` and `refresh_session` queried `DBSession.session_token` via ORM comparator instead of explicit `token_digest` digest lookup. | `test_admin_auth_and_security.py` & full auth suite | **VERIFIED & FIXED** |
| **ISSUE-09** | **LOW** | `.dockerignore` | Audit reports, batch logs, and registers were not explicitly ignored, adding unnecessary payload to Docker build context. | Measured build context reduced from 218 MB to 1.72 MB | **VERIFIED & FIXED** |
| **ISSUE-10** | **HIGH** | `client/src/App.tsx`, `client/src/utils/copilotReconciliation.ts`, `server/app/api/copilot.py` | Frontend inserted temporary user message and marked it saved without replacing temporary ID with persisted database ID, causing duplicated messages when loading overlapping history. | `test_correction_phase_08_1_close_findings.py`, `correction_phase_08_1_close_findings.test.tsx` | **VERIFIED & FIXED** |
| **ISSUE-11** | **HIGH** | `server/app/api/copilot.py`, `server/app/models/all_models.py`, `server/alembic/versions/c2d3e4f5a6b7_add_copilot_operations_table.py` | Lack of durable server operation record allowed duplicate provider work on retries and treated network timeouts as complete send failures. | Sequential duplicate tests, 409 conflict test, status retrieval endpoint | **VERIFIED & FIXED** |
| **ISSUE-12** | **MEDIUM** | `server/app/ai/gemini_service.py`, `server/app/api/copilot.py` | Context budgeting loop accepted oversized first history message by exception, and overall prompt budget was unmonitored. | `test_history_budget_drops_oversized_first_message`, `test_overall_prompt_budget_prunes_modules_not_question` | **VERIFIED & FIXED** |
| **ISSUE-13** | **MEDIUM** | `server/app/services/task_milestones.py`, `client/src/utils/taskMilestones.ts`, `shared_fixtures/strict_date_cases.json` | Date parsing accepted invalid calendar dates (e.g. Feb 31, non-leap Feb 29) due to JavaScript `Date.UTC` normalization, creating frontend/backend validation divergence. | 20 shared fixture test cases in Python and TypeScript | **VERIFIED & FIXED** |
| **ISSUE-14** | **MEDIUM** | `server/app/services/task_milestones.py`, `client/src/utils/taskMilestones.ts` | Milestone calculations fell back to timeline string searches and contained Day 31 exceptions instead of strict date-derived calendar math. | Exact boundary tests (Days 1, 30, 31, 60, 61, 90, 91), overdue policy tests | **VERIFIED & FIXED** |
| **ISSUE-15** | **MEDIUM** | `server/app/api/copilot.py` | Pagination cursor claimed cryptographic HMAC signing in reports but was only base64-encoded in code. | Option B implemented with HMAC-SHA256, constant-time compare, length bounding, and regression tests | **VERIFIED & FIXED** |

---

## Detailed Issue Documentation

### ISSUE-01: Market Research Provenance Note Unsegmented Text Node
- **Severity:** LOW (Documentation issue was testing-query convenience; not proven assistive technology failure)
- **Affected Files / Functions:** `client/src/components/MarketResearchModule.tsx` (Evidence status notice)
- **User-Visible Consequence:** None to human readers; automated testing query utilities could not isolate dynamic `provenance_note` text because it was rendered directly alongside static `<b>Evidence status:</b>` within a single unsegmented span.
- **Reproduction Steps:**
  1. Render `App` or `MarketResearchModule` with a mock provenance note `TARGET_MARKET_LEADER`.
  2. Execute `screen.getByText('TARGET_MARKET_LEADER')`.
  3. Query fails because the parent span's textContent is `"Evidence status: TARGET_MARKET_LEADER"`.
- **Root Cause:** Direct interpolation `{data.provenance_note || ...}` inside parent text span alongside prefix label.
- **Evidence:** `batch_03_security_and_race_conditions.test.tsx` failed with `Unable to find an element with the text: TARGET_MARKET_LEADER`.
- **Proposed Correction:** Wrap `{data.provenance_note || ...}` inside its own inner `<span>` element.
- **Dependencies:** None.
- **Regression Risk:** Low expected risk; verified by automated component tests.
- **Verification Method:** Ran `npx vitest run src/__tests__/batch_03_security_and_race_conditions.test.tsx` (10/10 passed) and full frontend suite.
- **Final Status:** VERIFIED & FIXED.

---

### ISSUE-02: Dialog `useDialog` React Compiler Hook Violation
- **Severity:** LOW
- **Affected Files / Functions:** `client/src/components/common/Dialog.tsx` (`useDialog`)
- **User-Visible Consequence:** Potential optimization skip by React Compiler / ESLint during builds.
- **Reproduction Steps:** Run `npm run lint`.
- **Root Cause:** `const dismissCallback = useCallback(onDismiss, [onDismiss]);` used a raw function reference instead of an inline arrow function expression.
- **Evidence:** `! react(use-memo): Expected the first argument to be an inline function expression`.
- **Proposed Correction:** Replace with `const dismissCallback = useCallback(() => { onDismiss(); }, [onDismiss]);`.
- **Dependencies:** None.
- **Regression Risk:** Low expected risk; verified by dialog regression tests.
- **Verification Method:** `npm run lint` — warning resolved.
- **Final Status:** VERIFIED & FIXED.

---

### ISSUE-03: Unused Imports in Component Modules
- **Severity:** LOW
- **Affected Files / Functions:** `client/src/components/BMCModule.tsx`, `client/src/components/AllTasksTable.tsx`
- **User-Visible Consequence:** Code clutter, minor bundle overhead.
- **Reproduction Steps:** Run `npm run lint`.
- **Root Cause:** Leftover imports from previous refactoring passes (`useEffect`, `Sparkles`, `X`, `Flag`, `CheckCircle2`, `isTaskCompleted`).
- **Evidence:** `eslint(no-unused-vars)` warnings reported by oxlint.
- **Proposed Correction:** Remove unused imports from component files.
- **Dependencies:** None.
- **Regression Risk:** Low expected risk; verified by module component tests.
- **Verification Method:** `npm run lint` — warnings eliminated.
- **Final Status:** VERIFIED & FIXED.

---

### ISSUE-04: Effect Cleanup Ref Mutation Warning in `App.tsx`
- **Severity:** LOW
- **Affected Files / Functions:** `client/src/App.tsx`
- **User-Visible Consequence:** Potential stale ref value during unmount if ref was reassigned.
- **Reproduction Steps:** Run `npm run lint`.
- **Root Cause:** Directly dereferencing `activeGenerationsRef.current` inside the cleanup closure.
- **Evidence:** `react-hooks(exhaustive-deps): The ref's value '.current' is accessed directly in the effect cleanup function.`
- **Proposed Correction:** Capture `const activeGenerations = activeGenerationsRef.current;` at the start of the effect and call `activeGenerations.clear()` in cleanup.
- **Dependencies:** None.
- **Regression Risk:** Low expected risk; verified by app unmount lifecycle tests.
- **Verification Method:** `npm run lint` — warning eliminated.
- **Final Status:** VERIFIED & FIXED.

---

### ISSUE-05: Overview Module Copy Action Description Discrepancy
- **Severity:** LOW
- **Affected Files / Functions:** `client/src/components/OverviewModule.tsx`
- **User-Visible Consequence:** Copy modal text stated that "a fresh Copilot conversation will begin", whereas the backend project copy endpoint duplicates the Copilot message history as well.
- **Reproduction Steps:** Create a project copy using the "Create a copy" action. Notice the new project contains previous conversation messages.
- **Root Cause:** Outdated copy text describing an older planned behavior before message history cloning was tested.
- **Evidence:** Regression test `test_audit_findings_regression.py` explicitly asserts `assert len(forked_msgs) == 1`.
- **Proposed Correction:** Update copy explanation text to: `"Saving updates this project directly. Creating a copy duplicates all project details, versions, roadmap tasks, and conversation history into a new project record."`
- **Dependencies:** None.
- **Regression Risk:** Low expected risk; verified by UI overview tests.
- **Verification Method:** Visual inspection and frontend tests.
- **Final Status:** VERIFIED & FIXED.

---

### ISSUE-06 & ISSUE-07: Deprecated HTTP Status Constants in Starlette
- **Severity:** LOW
- **Affected Files / Functions:** `server/app/main.py`, `server/app/api/modules.py`
- **User-Visible Consequence:** Deprecation warnings emitted in Python 3.12+ / Starlette runtimes.
- **Reproduction Steps:** Run `pytest -rs -q`.
- **Root Cause:** Usage of `status.HTTP_413_REQUEST_ENTITY_TOO_LARGE` and `status.HTTP_422_UNPROCESSABLE_ENTITY` which have been renamed in modern Starlette to RFC 9110 standards.
- **Evidence:** Pytest warnings summary: `'HTTP_413_REQUEST_ENTITY_TOO_LARGE' is deprecated` and `'HTTP_422_UNPROCESSABLE_ENTITY' is deprecated`.
- **Proposed Correction:** Use `getattr(status, "HTTP_413_CONTENT_TOO_LARGE", 413)` and `getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)` with numeric fallbacks.
- **Dependencies:** None.
- **Regression Risk:** Low expected risk; verified by status code response tests.
- **Verification Method:** Pytest run — warnings completely eliminated.
- **Final Status:** VERIFIED & FIXED.

---

### ISSUE-08: Implicit Session Revocation Query
- **Severity:** MEDIUM
- **Affected Files / Functions:** `server/app/api/auth.py` (`logout`, `refresh_session`), `server/app/api/admin/auth.py` (`admin_logout`)
- **User-Visible Consequence:** Slower revocation queries and reliance on hybrid comparator rather than direct index-backed queries.
- **Reproduction Steps:** Execute logout or refresh with high-load concurrency.
- **Root Cause:** Querying `DBSession.session_token == token` relied on hybrid property comparator fallback rather than querying the indexed `token_digest` directly.
- **Evidence:** Review of `auth.py` lines 175, 214 and `admin/auth.py` line 212.
- **Proposed Correction:** Compute `digest = hash_session_token(token)` and query `or_(DBSession.token_digest == digest, DBSession._session_token == token).delete(synchronize_session=False)` explicitly.
- **Dependencies:** None.
- **Regression Risk:** Low expected risk; verified by auth token digest revocation tests.
- **Verification Method:** Ran `pytest` auth and admin security test suites (all passed).
- **Final Status:** VERIFIED & FIXED.

---

### ISSUE-09: Unoptimized Docker Build Context
- **Severity:** LOW
- **Affected Files / Functions:** `.dockerignore`
- **User-Visible Consequence:** Unnecessary megabytes sent to the Docker daemon during image compilation.
- **Reproduction Steps:** Run `docker build .` without ignoring `audit/` and markdown report registers.
- **Root Cause:** Missing ignore rules for `audit/`, `BATCH_*.md`, `CORRECTION_*.md`, `WORKSPACE_AUDIT_COVERAGE.md`.
- **Evidence:** Measured build context analysis.
- **Proposed Correction:** Add ignore rules for all audit directories and report markdown files to `.dockerignore`.
- **Dependencies:** None.
- **Regression Risk:** Low expected risk; build dependencies untouched.
- **Verification Method:** Measured context payload reduced to 1.72 MB.
- **Final Status:** VERIFIED & FIXED.

---

### ISSUE-10: Chat Message ID Reconciliation
- **Severity:** HIGH
- **Affected Files / Functions:** `client/src/App.tsx`, `client/src/utils/copilotReconciliation.ts`, `server/app/api/copilot.py`, `server/app/schemas/copilot.py`
- **User-Visible Consequence:** Loading overlapping message history caused duplicate user messages to appear in conversation state (one under temporary ID, one under persisted ID).
- **Reproduction Steps:** Send a question in Copilot, let it succeed, and trigger older history pagination. The same question appeared twice.
- **Root Cause:** App.tsx inserted a temporary user message and marked it saved without replacing its temporary ID with the authoritative database ID. The backend returned the user ID only in header `X-User-Message-ID` which client response handler ignored.
- **Evidence:** Independent review finding 2.
- **Proposed Correction:** Implemented typed `CopilotSendResponse` (`user_message`, `assistant_message`, `operation_status`, `client_msg_id`). Created `reconcileSend(previous, tempId, result)` replacing temporary identity with authoritative saved database ID, deduplicating strictly by ID (never text), preserving older loaded pages and stable chronological order. Added context guards checking project ID and authenticated user before applying late responses.
- **Dependencies:** None.
- **Regression Risk:** Low expected risk; verified by 10/10 tests in `correction_phase_08_1_close_findings.test.tsx` and 5/5 tests in `test_phase_08_frontend_and_conversation_consistency.py`.
- **Verification Method:** Vitest unit tests and backend route tests verifying single message identity per send.
- **Final Status:** VERIFIED & FIXED.

---

### ISSUE-11: Chat Idempotency and Ambiguous Failure Handling
- **Severity:** HIGH
- **Affected Files / Functions:** `server/app/api/copilot.py`, `server/app/models/all_models.py`, `server/alembic/versions/c2d3e4f5a6b7_add_copilot_operations_table.py`, `client/src/components/BlueprintCopilotModule.tsx`
- **User-Visible Consequence:** Network timeouts caused client to treat requests as failed and suggest retry, risking duplicate provider costs and duplicate database records.
- **Reproduction Steps:** Re-send a chat message with the same operation ID.
- **Root Cause:** Lack of durable server operation records; saves and provider calls were coupled without cross-worker locking or conflict detection.
- **Evidence:** Independent review finding 3.
- **Proposed Correction:** Added database-backed `copilot_operations` table scoped by `(project_id, client_msg_id)` with `message_hash = sha256(message)`. Duplicate sequential sends return saved results without extra provider calls. Concurrent sends return pending status. Payload mismatches return HTTP 409 Conflict. Created status retrieval endpoint `GET /projects/{project_id}/copilot/operations/{client_msg_id}` with cross-tenant 403/404 isolation. In frontend, network timeouts trigger `uncertain` status, showing "We could not confirm whether this response finished" with "Check status", "Refresh conversation", and "Retry" preserving the operation ID.
- **Dependencies:** Alembic migration `c2d3e4f5a6b7`.
- **Regression Risk:** Low expected risk; migration upgrade/downgrade/re-upgrade verified on disposable database.
- **Verification Method:** Automated tests verifying zero duplicate provider calls on retries, conflict rejections, and tenant isolation.
- **Final Status:** VERIFIED & FIXED.

---

### ISSUE-12: Strict Provider Context and Prompt Budgeting
- **Severity:** MEDIUM
- **Affected Files / Functions:** `server/app/ai/gemini_service.py`, `server/app/api/copilot.py`
- **User-Visible Consequence:** Risk of provider payload rejection when history or project modules are large; first history message exceeded budget by exception.
- **Reproduction Steps:** Pass a 17,000 character history message to `chat_copilot`.
- **Root Cause:** The loop in `gemini_service.py` contained `if cur_chars + content_len > MAX_HISTORY_CHARS and budgeted_history: break`. On the first item, `budgeted_history` was empty, so oversized messages were accepted into prompt context.
- **Evidence:** Independent review finding 4.
- **Proposed Correction:** Removed `and budgeted_history` to strictly reject any message exceeding the remaining budget (<= 16,000 chars total). Added overall serialized prompt check (<= 80,000 chars), pruning optional module summaries and source provenance before provider invocation. Validated user question length (<= 4,000 chars) and preserved complete user question without silent truncation.
- **Dependencies:** None.
- **Regression Risk:** Low expected risk; verified by budget regression tests.
- **Verification Method:** Automated unit tests verifying 17,000 character history item exclusion and prompt pruning under 80,000 characters.
- **Final Status:** VERIFIED & FIXED.

---

### ISSUE-13: Shared Strict Date-Only Contract & Calendar Arithmetic
- **Severity:** MEDIUM
- **Affected Files / Functions:** `server/app/services/task_milestones.py`, `client/src/utils/taskMilestones.ts`, `shared_fixtures/strict_date_cases.json`
- **User-Visible Consequence:** Discrepancies between frontend and backend milestone dates; impossible dates (e.g. Feb 31) normalized silently in JavaScript while rejected in Python.
- **Reproduction Steps:** Submit `2026-02-31`. JavaScript `Date.UTC` converted it to `2026-03-03` while Python rejected it.
- **Root Cause:** JavaScript Date constructor rolls overflow dates forward across months, whereas Python `datetime.date` raises `ValueError`.
- **Evidence:** Independent review finding 5.
- **Proposed Correction:** Canonical format `YYYY-MM-DD`, supported year range `1900-2100`. Implemented `parseStrictDateOnly` in TypeScript checking `utc.getUTCFullYear() === year && utc.getUTCMonth() === month - 1 && utc.getUTCDate() === day` to strictly reject roll-overs, non-leap Feb 29, and April 31. Implemented matching regex and date checks in Python `parse_strict_date_only`. Created shared fixture file `shared_fixtures/strict_date_cases.json` with 20 edge cases run against both test suites.
- **Dependencies:** None.
- **Regression Risk:** Low expected risk; verified by shared fixtures.
- **Verification Method:** Pytest and Vitest test suites executing the identical 20 JSON test cases.
- **Final Status:** VERIFIED & FIXED.

---

### ISSUE-14: Cumulative Milestone Boundaries & Removal of Timeline Fallbacks
- **Severity:** MEDIUM
- **Affected Files / Functions:** `server/app/services/task_milestones.py`, `client/src/utils/taskMilestones.ts`
- **User-Visible Consequence:** Tasks were misclassified into milestone cards based on duration strings rather than dates, and Day 31 tasks were incorrectly included in 30-day totals.
- **Reproduction Steps:** Create a task with timeline "30-day MVP" and end date on Day 45. In old code, it entered the Day 30 milestone card.
- **Root Cause:** Both codebases searched `timeline.includes("30")` as a fallback and had a special-case exception for Day 31.
- **Evidence:** Independent review finding 6.
- **Proposed Correction:** Enforced cumulative date arithmetic: inclusive day = `(end_date - anchor) + 1`. Day 30 belongs to 30/60/90; Day 31 belongs to 60/90 (NOT 30); Day 60 belongs to 60/90; Day 61 belongs to 90 (NOT 60); Day 90 belongs to 90; Day 91 belongs to later work. Overdue tasks (`<= 0`) belong to cumulative 30/60/90 totals. Undated tasks remain in total tasks but do not enter dated milestone cards. Removed all timeline string search fallbacks and Day 31 exceptions.
- **Dependencies:** None.
- **Regression Risk:** Low expected risk; verified by exact boundary test cases.
- **Verification Method:** Automated boundary tests in `test_correction_phase_08_1_close_findings.py` and `correction_phase_08_1_close_findings.test.tsx`.
- **Final Status:** VERIFIED & FIXED.

---

### ISSUE-15: Authenticated HMAC-SHA256 Cursor vs Non-Secret Claims
- **Severity:** MEDIUM
- **Affected Files / Functions:** `server/app/api/copilot.py`
- **User-Visible Consequence:** Previous audit report claimed cryptographic HMAC verification, but code used raw Base64 encoding of timestamp and ID.
- **Reproduction Steps:** Inspect `encode_cursor` in previous commit.
- **Root Cause:** Discrepancy between documentation claims and code implementation.
- **Evidence:** Independent review finding 7.
- **Proposed Correction:** Implemented Option B: Authenticated HMAC-SHA256 cursor. Encodes `v1|{project_id}|{iso_timestamp}|{msg_id}` signed with server `SESSION_SECRET` truncated to 16 hex chars. Decodes strictly, bounding cursor length (`<= 512`), verifying project match, and comparing signatures using constant-time `hmac.compare_digest`. Validates authoritative database row timestamp.
- **Dependencies:** None.
- **Regression Risk:** Low expected risk; verified by roundtrip, cross-project tamper, and signature tamper tests.
- **Verification Method:** Automated tests in `test_phase_08_frontend_and_conversation_consistency.py` and `test_correction_phase_08_1_close_findings.py`.
- **Final Status:** VERIFIED & FIXED.

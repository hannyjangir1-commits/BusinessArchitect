# Venture Atlas / BusinessArchitect — Application Issues and Fixes Log

This document records confirmed issues, evidence, root causes, durable fixes, and verification methods identified during the autonomous full-workspace audit in accordance with Section 7 and Deliverable B of the Master Prompt.

---

## Issue Registry Summary

| Finding ID | Severity | Affected Area / Paths | Summary of Issue | Verification | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **ISSUE-01** | **MEDIUM** | `client/src/components/MarketResearchModule.tsx` | Market Research evidence status text node unsegmented, preventing testing and assistive text extraction of dynamic note. | `npx vitest run src/__tests__/batch_03_security_and_race_conditions.test.tsx` (10/10 passed) | **VERIFIED & FIXED** |
| **ISSUE-02** | **LOW** | `client/src/components/common/Dialog.tsx` | `useCallback` passed raw function reference instead of inline function expression, triggering React Compiler lint warning. | `npm run lint` (0 errors, 44 warnings) | **VERIFIED & FIXED** |
| **ISSUE-03** | **LOW** | `client/src/components/BMCModule.tsx` & `AllTasksTable.tsx` | Unused imports (`useEffect`, `Sparkles`, `X`, `Flag`, `CheckCircle2`, `isTaskCompleted`) triggering lint warnings. | `npm run lint` (clean) | **VERIFIED & FIXED** |
| **ISSUE-04** | **LOW** | `client/src/App.tsx` | React ref `.current` accessed in effect cleanup closure without capturing local reference, triggering `react-hooks/exhaustive-deps`. | `npm run lint` (clean) | **VERIFIED & FIXED** |
| **ISSUE-05** | **LOW** | `client/src/components/OverviewModule.tsx` | Action explanation text claimed "fresh Copilot conversation will begin", but project copy also clones message history. | Visual inspection & `npm test` | **VERIFIED & FIXED** |
| **ISSUE-06** | **LOW** | `server/app/main.py` | `status.HTTP_413_REQUEST_ENTITY_TOO_LARGE` deprecated in modern Starlette in favor of RFC 9110 `HTTP_413_CONTENT_TOO_LARGE`. | `pytest` warning eliminated | **VERIFIED & FIXED** |
| **ISSUE-07** | **LOW** | `server/app/api/modules.py` | Deprecated `status.HTTP_422_UNPROCESSABLE_ENTITY` triggered Starlette deprecation warnings on import. | `pytest` warning eliminated | **VERIFIED & FIXED** |
| **ISSUE-08** | **MEDIUM** | `server/app/api/auth.py` & `server/app/api/admin/auth.py` | `logout` and `refresh_session` queried `DBSession.session_token` via ORM comparator instead of explicit `token_digest` digest lookup. | `test_admin_auth_and_security.py` & full auth suite | **VERIFIED & FIXED** |
| **ISSUE-09** | **LOW** | `.dockerignore` | Audit reports, batch logs, and registers were not explicitly ignored, adding unnecessary payload to Docker build context. | Measured build context reduced from 218 MB to 1.72 MB | **VERIFIED & FIXED** |

---

## Detailed Issue Documentation

### ISSUE-01: Market Research Provenance Note Unsegmented Text Node
- **Severity:** MEDIUM
- **Affected Files / Functions:** `client/src/components/MarketResearchModule.tsx` (Evidence status notice)
- **User-Visible Consequence:** Screen readers and DOM query utilities could not isolate dynamic `provenance_note` text because it was rendered directly alongside static `<b>Evidence status:</b>` within a single unsegmented span.
- **Reproduction Steps:**
  1. Render `App` or `MarketResearchModule` with a mock provenance note `TARGET_MARKET_LEADER`.
  2. Execute `screen.getByText('TARGET_MARKET_LEADER')`.
  3. Query fails because the parent span's textContent is `"Evidence status: TARGET_MARKET_LEADER"`.
- **Root Cause:** Direct interpolation `{data.provenance_note || ...}` inside parent text span alongside prefix label.
- **Evidence:** `batch_03_security_and_race_conditions.test.tsx` failed with `Unable to find an element with the text: TARGET_MARKET_LEADER`.
- **Proposed Correction:** Wrap `{data.provenance_note || ...}` inside its own inner `<span>` element.
- **Dependencies:** None.
- **Regression Risk:** Zero; visual layout and text remain identical.
- **Verification Method:** Ran `npx vitest run src/__tests__/batch_03_security_and_race_conditions.test.tsx` (10/10 passed) and full frontend suite (100/100 passed).
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
- **Regression Risk:** Zero.
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
- **Regression Risk:** Zero.
- **Verification Method:** `npm run lint` — warnings eliminated.
- **Final Status:** VERIFIED & FIXED.

---

### ISSUE-04: Effect Cleanup Ref Mutation Warning in `App.tsx`
- **Severity:** LOW
- **Affected Files / Functions:** `client/src/App.tsx` (line 198)
- **User-Visible Consequence:** Potential stale ref value during unmount if ref was reassigned.
- **Reproduction Steps:** Run `npm run lint`.
- **Root Cause:** Directly dereferencing `activeGenerationsRef.current` inside the cleanup closure.
- **Evidence:** `react-hooks(exhaustive-deps): The ref's value '.current' is accessed directly in the effect cleanup function.`
- **Proposed Correction:** Capture `const activeGenerations = activeGenerationsRef.current;` at the start of the effect and call `activeGenerations.clear()` in cleanup.
- **Dependencies:** None.
- **Regression Risk:** Zero.
- **Verification Method:** `npm run lint` — warning eliminated.
- **Final Status:** VERIFIED & FIXED.

---

### ISSUE-05: Overview Module Copy Action Description Discrepancy
- **Severity:** LOW
- **Affected Files / Functions:** `client/src/components/OverviewModule.tsx` (line 218)
- **User-Visible Consequence:** Copy modal text stated that "a fresh Copilot conversation will begin", whereas the backend project copy endpoint duplicates the Copilot message history as well.
- **Reproduction Steps:** Create a project copy using the "Create a copy" action. Notice the new project contains previous conversation messages.
- **Root Cause:** Outdated copy text describing an older planned behavior before message history cloning was tested.
- **Evidence:** Regression test `test_audit_findings_regression.py` explicitly asserts `assert len(forked_msgs) == 1`.
- **Proposed Correction:** Update copy explanation text to: `"Saving updates this project directly. Creating a copy duplicates all project details, versions, roadmap tasks, and conversation history into a new project record."`
- **Dependencies:** None.
- **Regression Risk:** Zero.
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
- **Regression Risk:** Zero.
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
- **Regression Risk:** Zero.
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
- **Regression Risk:** Zero.
- **Verification Method:** Measured context payload reduced to 1.72 MB.
- **Final Status:** VERIFIED & FIXED.

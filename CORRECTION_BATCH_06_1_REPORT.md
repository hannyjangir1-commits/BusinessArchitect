# CORRECTION BATCH 06.1 — SAFE ROADMAP RECONCILIATION AND SHARED TASK LOCKING REPORT

## 1. Executive Summary & Verification Baseline
- **Starting Commit**: `7c10d5a75fe5b18f7fd9a1eb2841cd8f57d5a5c9`
- **Branch**: `main`
- **Render Auto-Deploy**: Disabled (No deployment triggered)
- **Production Isolation**: Zero production databases, migrations, or live credentials accessed. Disposable test databases and mocked LLM providers used exclusively. Zero Gemini API quota consumed.

---

## 2. Defects Addressed & Reproduction Results

### Reproduction A: Bulk Reconciliation Accepts Nonexistent Dependencies
- **Defect**: When an incoming plan contained a task depending on a non-existent code (e.g. `{"task_code": "A", "dependencies": ["MISSING"]}`), `reconcile_roadmap_tasks` accepted and flushed this invalid graph to the relational database.
- **Root Cause**: `reconcile_roadmap_tasks` did not validate cross-task dependency references against the merged candidate graph before writing.
- **Reproduction**: Tested via fixture `[{"task_code": "A", "title": "A", "start_date": "2026-11-01", "end_date": "2026-11-02", "dependencies": ["MISSING"]}]`. Prior to fix, this flushed and persisted the dangling dependency.
- **Correction**: Reconciler now constructs the complete candidate graph in memory and calls `validate_candidate_task_graph(db, project_id, candidate_graph, structured_error=True)`. Dangling references raise `IncompatibleTaskGraphError` (HTTP 422) with `MISSING_PREREQUISITE` and `missing_prerequisite_codes: ["MISSING"]` before any row mutation is persisted.

### Reproduction B: Retained Manual Task Loses Prerequisite
- **Defect**: Seeded AI task A and manual task B with `dependencies: ["A"]`. When a newly reconciled roadmap plan omitted task A, the existing reconciler deleted task A and retained task B, leaving manual task B with a dangling prerequisite reference.
- **Root Cause**: The reconciler only checked incoming tasks, ignoring dependencies held by retained manual tasks on omitted AI tasks.
- **Reproduction**: Seeded AI task `A` and manual task `B` depending on `A`. Reconciled candidate roadmap omitting `A`. Prior to fix, `A` was deleted from DB and `B` remained dangling.
- **Correction**: Reconciler candidate graph builder detects retained tasks whose prerequisite is an omitted AI task. It atomically halts before deletion with `IncompatibleTaskGraphError` (`RETAINED_TASK_PREREQUISITE_MISSING`, HTTP 422), detailing `blocking_retained_task_codes` and `missing_prerequisite_codes`.

### Reproduction C & C2: Ambiguous Duplicate Incoming Codes
- **Defect**: When incoming plan contained duplicate codes (e.g. two tasks with `DUP`, and task `C` depending on `DUP`), the reconciler silently renamed the second task to `DUP_2` without resolving whether `C` intended to depend on the first or second task.
- **Root Cause**: `normalize_incoming_tasks` used a heuristic `f"{code}_{counter}"` collision renaming strategy that masked AI model hallucinations.
- **Reproduction**: Submitted tasks `[DUP, DUP, C -> DUP]`. Prior to fix, the second task became `DUP_2` and `C` silently bound to the first `DUP`. Also tested duplicate codes with no dependencies (`[DUP, DUP]`).
- **Correction**: Reconciler rejects duplicate incoming codes unconditionally with `IncompatibleTaskGraphError` (`DUPLICATE_INCOMING_TASK_CODES`, HTTP 422), listing all duplicate codes. No identity guessing or arbitrary renumbering is performed.

---

## 3. Complete Caller & Transaction Matrix

| Caller | Operation | Locking Protocol | Commit Owner | Task Reconciliation |
| :--- | :--- | :--- | :--- | :--- |
| `POST /api/tasks/` (`create_task`) | Manual Task Insert | `project_first_lock(db, project_id)` | `create_task` | Validates new task against existing graph; commits task row |
| `PATCH /api/tasks/{task_id}` (`update_task`) | Manual Task Update / Reschedule / Rename | `project_first_lock(db, project_id)` | `update_task` | Validates schedule, cascade renames dependencies; commits task row |
| `DELETE /api/tasks/{task_id}` (`delete_task`) | Manual Task Delete | `project_first_lock(db, project_id)` | `delete_task` | Validates no dependent tasks; commits deletion |
| `execute_module_generation` | Initial Roadmap Gen | `project_first_lock(db, project.id, module.id)` | `execute_module_generation` | `save_new_version(commit=False)` -> `reconcile_roadmap_tasks(commit=False)` -> `db.commit()` |
| `POST /api/modules/{id}/modify` | Roadmap Revision | `project_first_lock(db, project_id, module_id)` | `modify_module_with_ai` | `save_new_version(commit=False)` -> `reconcile_roadmap_tasks(commit=False)` -> `db.commit()` |
| `POST /api/modules/{id}/versions/resolve-conflict` | Conflict Replacement | `project_first_lock(db, project_id, module_id)` | `resolve_version_conflict` | `save_new_version(commit=False)` -> `reconcile_roadmap_tasks(commit=False)` -> `db.commit()` |
| `POST /api/modules/{id}/versions/{v}/restore` | Roadmap Version Restore | `project_first_lock(db, project_id, module_id)` | `restore_version` | Updates version flags -> `reconcile_roadmap_tasks(commit=False)` -> `db.commit()` |
| `DELETE /api/modules/{id}/versions/{v}` | Active Version Deletion Fallback | `project_first_lock(db, project_id, module_id)` | `delete_version` | Deletes version -> sets latest active -> `reconcile_roadmap_tasks(commit=False)` -> `db.commit()` |
| `POST /api/admin/ai-ops/retry` | Admin Retry | `project_first_lock(db, project_id, module_id)` | `retry_failed_operation` | `save_new_version(commit=False)` -> `reconcile_roadmap_tasks(commit=False)` -> `db.commit()` |
| `POST /api/admin/integrity/fix-missing-active-versions` | Admin Active-Version Repair | `project_first_lock(db, project_id, module_id)` | `fix_missing_active_versions` | Repoints active version -> `reconcile_roadmap_tasks(commit=False)` -> `db.commit()` |
| `POST /api/admin/integrity/prune-excess-versions` | Version Pruning | `project_first_lock(db, project_id, module_id)` | `prune_excess_versions` | Protects active version; deletes obsolete historical versions |
| `DELETE /api/modules/{id}` | Module Deletion | `project_first_lock(db, project_id, module_id)` | `delete_module` | Cleans up roadmap tasks for project before deleting module |

---

## 4. Final Merge & Preservation Policy

1. **Identity Stability**:
   - Matching existing AI tasks retain their immutable database primary keys (`id`).
   - Matching updates fields (`title`, `description`, `start_date`, `end_date`, `phase`, `dependencies`) in-place.
2. **User Status & Assignment Preservation**:
   - User-set execution states (`In Progress`, `Ongoing`, `Finished`, `Completed`) on existing tasks are strictly preserved and never overwritten by incoming AI statuses.
   - User assignments (`assignee_id`, custom team assignments) are preserved.
3. **Manual Task Protection**:
   - Manual tasks (`is_ai_generated == False`) are strictly retained in memory and in the database.
   - Attempting to reconcile an incoming AI task whose `task_code` matches an existing manual task raises `IncompatibleTaskGraphError` (`MANUAL_TASK_COLLISION`, HTTP 422).
4. **Retained Completed Tasks**:
   - Completed tasks are preserved under product policy. If an incoming plan omits a dependency required by a retained completed task, reconciliation raises a validation error instead of leaving it dangling.
5. **Pruning of Omitted AI Tasks**:
   - AI-generated tasks omitted from the incoming roadmap are safely deleted if and only if no retained tasks depend on them.
6. **Schedule Rules**:
   - Handover constraint: `dependent.start_date >= prerequisite.end_date` is enforced.
   - Tasks where `end_date < start_date` raise HTTP 422 (`END_BEFORE_START`). Dates are never silently clamped.

---

## 5. Snapshot vs. Row Identity Consistency

- **Canonical Task Allocation**:
  - `reconcile_roadmap_tasks` canonicalizes incoming tasks:
    - Strips whitespace consistently from all codes and dependencies.
    - Rejects non-string codes cleanly (HTTP 400).
    - If a task code is missing, allocates using `allocate_next_task_code` against all reserved codes (existing project codes + already allocated candidate codes).
- **Snapshot Parity**:
  - `reconcile_roadmap_tasks` returns the complete list of normalized `canonical_tasks`.
  - Callers (`execute_module_generation`, `modify_module_with_ai`, `retry_failed_operation`, etc.) store the exact `canonical_tasks` inside the version snapshot JSON.
  - The exact same codes, dates, and dependencies are persisted to `roadmap_tasks` relational rows, guaranteeing 100% parity between version snapshots and the database.

---

## 6. Shared Project-First Locking Protocol & Deadlock Prevention

### Lock Ordering
To prevent application deadlocks across concurrent requests, the system enforces a strict hierarchical lock order:
```
1. Project Striped Mutex (`threading.RLock`)
2. Module Striped Mutex (`threading.RLock`, if module involved)
3. Project DB Row Lock (`lock_record(db, Project, project_id)`)
4. ModuleContent DB Row Lock (`lock_record(db, ModuleContent, module_id)`)
5. Authoritative Task / Version Reads and Writes
```

### Application Conflicts Prevented
- **Manual CRUD vs. Roadmap Generation / Restore**: Prevents a manual task insert/rename from interleaving between roadmap task reading and writing, which previously caused duplicate task codes or broken dependencies.
- **Concurrent Roadmap Operations**: Prevents race conditions between version restores, AI modifications, and admin repairs targeting the same project.
- **Provider Calls Kept Outside Locks**: Long-running external AI calls (Gemini) are executed before acquiring locks. Write locks are held only during validation, reconciliation, and database persistence.
- **Re-entrant Striped Locks**: Striped project locks use `threading.RLock()`, allowing endpoints to hold outer transaction protection while calling inner domain services without deadlock.
- **Row Cache Invalidation**: `lock_record` refreshes stale ORM state via `session.refresh(record)` and `populate_existing()`.

---

## 7. Atomic Rollback Evidence

- All bulk operations (`save_new_version`, `reconcile_roadmap_tasks`) accept `commit=False`.
- The caller transaction wraps all mutations inside a single unit of work.
- If graph validation fails (e.g. missing prerequisite, cycle, manual task collision), `reconcile_roadmap_tasks` raises `IncompatibleTaskGraphError`.
- The caller's exception handler triggers `db.rollback()`.
- **Result**: No task rows are deleted or inserted, the version pointer is not incremented, and active flags remain untouched on the previous valid version. Verified via tests:
  - `test_conflict_replacement_with_invalid_graph_rolls_back`
  - `test_version_restore_with_invalid_graph_rolls_back`
  - `test_generation_save_with_invalid_graph_rolls_back`
  - `test_revision_modify_with_invalid_graph_rolls_back`

---

## 8. Test Execution & Verification

### Focused New Test Suite (`test_correction_batch_06_1_reconciliation.py`)
- **Command**: `python -m pytest server/tests/test_correction_batch_06_1_reconciliation.py -v`
- **Result**: **24 passed, 4 skipped** (PostgreSQL concurrency tests pending), 0 failed
- **Execution Time**: 8.49s, exit code 0

### Full Backend Test Suite
- **Command**: `python -m pytest server/tests`
- **Result**: **344 passed, 9 skipped**, 0 failed
- **Execution Time**: 114.58s, exit code 0

### Client Verification
- **Build**: `npm run build` in `client/` -> **Exit code 0** (built in 638ms)
- **Tests**: `npm test -- --run` in `client/` -> **10 test files passed, 100 tests passed**, exit code 0
- **Linter**: `npm run lint` in `client/` -> **0 errors, 25 warnings**, exit code 0
- **Whitespace Check**: `git diff --check` -> **Clean (exit code 0)**

---

## 9. PostgreSQL Concurrency Checks (Pending Disposition)
Four PostgreSQL concurrency tests were implemented in `server/tests/test_correction_batch_06_1_reconciliation.py`:
1. `test_pg_manual_mutation_vs_roadmap_restore`
2. `test_pg_manual_mutation_vs_generation_persistence`
3. `test_pg_restore_vs_repair_same_roadmap`
4. `test_pg_independent_projects_progress_separately`

These tests use separate database connections, deterministic threading events, and bounded timeouts to assert serialization and project isolation under PostgreSQL `SELECT FOR UPDATE`. In accordance with prompt instructions ("*If PostgreSQL is unavailable, mark these pending. SQLite thread tests do not substitute for them.*"), they are skipped when `TEST_DATABASE_URL` is unset or SQLite.

---

## 10. Migration & Allocation Policy Review
- **Alembic Head**: `a2b3c4d5e6f7`
- **Migrations Added**: Zero (schema remains fully backward-compatible).
- **Task Code Allocation**: Corrected the docstring and implementation in `allocate_next_task_code`. `max(existing) + 1` prevents collisions caused by deleting lower-numbered tasks, but deleting the highest numbered task can allow code reuse. The database primary key (`id`) remains the true immutable task identity.

---

## 11. Files Changed
1. `server/app/services/task_graph_validator.py`
2. `server/app/services/roadmap_service.py`
3. `server/app/services/module_orchestration_service.py`
4. `server/app/api/modules.py`
5. `server/app/api/admin/integrity.py`
6. `server/app/api/admin/ai_ops.py`
7. `server/app/api/tasks.py`
8. `server/tests/test_batch_06_task_identity_and_integrity.py`
9. `server/tests/test_audit_repairs_and_csrf_exhaustive.py`
10. `server/tests/test_correction_batch_06_1_reconciliation.py` (New test file)
11. `CORRECTION_BATCH_06_1_REPORT.md` (New report file)

---

## 12. Remaining Review Findings (Deferred to Subsequent Batches)
- Version-flag freshness across processes under high concurrency.
- Authentication proxy handling and forwarded header validation.
- Other pending findings from the master reviewer outside Batch 06.1.

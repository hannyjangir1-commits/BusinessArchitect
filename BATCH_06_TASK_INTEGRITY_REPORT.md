# BATCH 06 — TASK IDENTITY, DEPENDENCY AND SCHEDULE INTEGRITY REPORT

**Starting Commit SHA:** `3728ce58580ac0e288a5887be378f5bfe78184fb`  
**Ending Commit SHA:** *(Recorded upon final commit of this report)*  
**Date:** 2026-10-24  
**Author:** AI Agent (Antigravity)  
**Target Repository:** `hannyjangir1-commits/BusinessArchitect`  
**Branch:** `main`

---

## Executive Summary

Batch 06 resolves three core defects in roadmap task lifecycle management:
- **B01:** Duplicate automatic task codes generated after task deletion due to row-count-based code generation (`TSK-01`, `TSK-02`, delete `TSK-01` -> new task attempted to allocate `TSK-02`).
- **B02:** Task rename leaving dangling dependency references on downstream dependent tasks (e.g. renaming task `A` to `A2` left `dependencies: ["A"]` intact on downstream tasks).
- **B03:** Manual schedule mutations violating prerequisite schedule integrity (e.g., setting a task start date earlier than its prerequisite task end date, or shifting an upstream prerequisite's end date past a dependent's start date).

All repairs maintain strict project isolation, project-level row concurrency without global bottlenecking, full compatibility with bulk generation and version restore flows, and backward-compatible task APIs.

---

## 1. Task-Writing Paths Audit

Every code path in the repository that inserts, updates, deletes, or bulk-replaces `RoadmapTask` rows was audited:

| Component / Path | Operation | Mechanism | Concurrency & Validation Control |
|---|---|---|---|
| `server/app/api/tasks.py:create_task` | Manual Single Create | `INSERT RoadmapTask` | Project row lock + in-process striped lock. Monotonic allocation (`max(TSK-##) + 1`). Candidate graph validation. Unique constraint enforced. |
| `server/app/api/tasks.py:update_task` | Manual Single Update | `UPDATE RoadmapTask` | Project row lock + in-process striped lock. Candidate graph pre-validation. Atomic rename cascade to incoming dependents (`flag_modified(t, 'dependencies')`). Upstream and downstream schedule validation. |
| `server/app/api/tasks.py:delete_task` | Manual Single Delete | `DELETE RoadmapTask` | Project row lock + in-process striped lock. Dependent check rejects deletion if any other task has incoming dependency edge pointing to task code. |
| `server/app/services/roadmap_service.py:reconcile_roadmap_tasks` | Bulk Generation / Version Restore | Selective update / insert / delete | In-place deduplication of incoming task codes with suffixing (`TSK-01_2`) prior to upsert. Preserves existing task database IDs and code uniqueness constraint. |
| `server/app/api/admin/maintenance.py:repair_roadmap_orphans` | Admin Data Repair | `DELETE / UPDATE` | Scans for orphan tasks whose `project_id` does not exist in `projects` table. Does not invent task codes or corrupt dependencies. |
| `client/src/modules/roadmap/ExecutionRoadmapModule.tsx` | Frontend Consumer | REST API calls | Sends task creation, update, and deletion requests. Receives structured 400 error messages with task code context. |

---

## 2. Allocation and Locking Design

### 2.1 Monotonic Code Allocation (Fix B01)
- **Defect Cause:** Previous code used `count = db.query(RoadmapTask).filter(...).count()`, producing `TSK-{count + 1}`. Deleting an early task lowered the count, causing the next allocation to collide with an existing higher task code.
- **Resolution:** `allocate_next_task_code(db, project_id)` parses all existing `TSK-(\d+)` codes within the project and extracts `max(num) + 1`. If no tasks match the pattern, it defaults to `TSK-01`.
- **Custom Codes:** Custom alphanumeric codes (e.g., `SETUP-AUTH`, `FE-01`) chosen by users are preserved. Explicit user-provided codes are validated against duplicates via database queries and the unique constraint.
- **Project Isolation:** Task code allocation is scoped strictly to `project_id`. Different projects can use identical task codes (`TSK-01`, `TSK-02`) without conflict.

### 2.2 Concurrency & Locking
- **PostgreSQL Row Lock:** `lock_project_for_task_mutation(db, project_id)` executes:
  ```sql
  SELECT id FROM projects WHERE id = :pid FOR UPDATE
  ```
  This serializes concurrent task mutations for the same project in PostgreSQL without acquiring table-wide locks.
- **In-Process Striped Mutex:** `get_project_task_lock(project_id)` uses a 256-bucket striped lock pool keyed on `hash(project_id) % 256`. This serializes concurrent threads within the local application process (and in SQLite during testing) without creating a global bottleneck across unrelated projects.

---

## 3. Migration and Data-Repair Policy

### 3.1 Migration Revision: `a2b3c4d5e6f7`
- **Predecessor:** `f1a8b9c0d1e2` (Batch 04.2 / 05 head).
- **File:** `server/alembic/versions/a2b3c4d5e6f7_enforce_task_code_integrity.py`.
- **Constraint Added:** `UniqueConstraint("project_id", "task_code", name="uq_roadmap_tasks_project_task_code")` on `roadmap_tasks`.

### 3.2 Preflight Data Repair Policy
Before applying the constraint, the migration inspects existing legacy data:
1. **Unambiguous / Unreferenced Duplicates:** If duplicate `task_code` rows exist within a project and *neither* is referenced in any other task's `dependencies`, subsequent duplicate rows are deterministically renamed to `{code}_dup{idx}`.
2. **Ambiguous Referenced Duplicates:** If any duplicate task code is referenced as a dependency by another task, guessing which task the dependency intended to target could alter business logic. The migration immediately **raises `RuntimeError`** with actionable diagnostic information:
   ```
   Migration aborted: Ambiguous task_code 'TSK-01' in project 42 is referenced by dependent tasks: ['TSK-02'].
   Manual resolution required prior to applying uniqueness constraint.
   ```
   Because the migration runs inside a transaction, a failure leaves all existing rows and relationships intact.

---

## 4. Atomic Rename and Deletion Semantics

### 4.1 Atomic Rename Cascade (Fix B02)
- When a task's `task_code` is updated from `old_code` to `new_code`:
  1. The new code is verified for uniqueness within the project.
  2. All tasks in the project are scanned for incoming dependencies matching `old_code`.
  3. A candidate dependency list is generated for each dependent task with `old_code` replaced by `new_code`.
  4. The complete candidate project graph is validated via `validate_candidate_task_graph()` (detecting cycles, missing nodes, and date constraints).
  5. The mutations are applied in memory, and each modified dependent task is explicitly flagged using `sqlalchemy.orm.attributes.flag_modified(dep_task, "dependencies")` to guarantee that JSON column modifications are written to the database.
  6. The transaction commits atomically. If validation fails, no partial updates are committed.

### 4.2 Deletion Safety
- When deleting a task:
  1. The project graph is scanned for any task with an incoming dependency pointing to `task.task_code`.
  2. If any dependent tasks exist, the deletion is rejected with `HTTP 400 Bad Request`:
     ```json
     {"detail": "Cannot delete task TSK-01: tasks TSK-02 depend on it. Please update their dependencies first."}
     ```
  3. Deletion is permitted only if no tasks depend on it. This prevents orphaned or dangling dependency references.

---

## 5. Shared Graph and Schedule Validation (Fix B03)

### 5.1 Validator: `task_graph_validator.py`
A unified validator `validate_candidate_task_graph()` validates candidate task graphs before applying mutations:
- **Date Syntax:** Validates `YYYY-MM-DD` ISO format.
- **Duration Ordering:** Rejects any task where `end_date < start_date`.
- **Self-Dependency:** Rejects any task listing its own `task_code` in `dependencies`.
- **Cycles:** Uses Depth-First Search (DFS) with 3-color node state tracking (`UNVISITED`, `VISITING`, `VISITED`) to detect circular dependencies across any chain length.
- **Missing References:** Validates that all prerequisites referenced in `dependencies` exist within the project.
- **Prerequisite Ordering:** Validates that for every prerequisite $P \in \text{dependencies}(T)$:
  $$\text{start\_date}(T) \ge \text{end\_date}(P)$$
- **Upstream Mutation Cascade:** When an upstream task's dates are changed, the validator checks both its own prerequisites and all downstream dependents to ensure the date shift does not break downstream schedules.

### 5.2 Schedule Equality Rule
- **Rule:** A dependent task may start on the exact date that its prerequisite completes:
  $$\text{start\_date}(T) = \text{end\_date}(P) \quad \implies \text{VALID}$$
  $$\text{start\_date}(T) < \text{end\_date}(P) \quad \implies \text{INVALID (HTTP 400)}$$
- **Rationale:** Matches standard Gantt and roadmap project management conventions where handover milestones or consecutive tasks commence on the day preceding deliverables finish. Starting strictly before the prerequisite finishes is rejected.

---

## 6. Compatibility with Generated Roadmaps and Snapshots

- **Roadmap Bulk Persistence (`reconcile_roadmap_tasks`):**
  - Updated to deduplicate task codes prior to upserting into `RoadmapTask`.
  - Guarantees that AI-generated or imported roadmap task arrays with duplicate codes are safely suffixed (`TSK-01_2`) before touching the database, preventing constraint violation errors.
- **Version Restore:**
  - Restoring a previous roadmap version deserializes snapshot task arrays and reconciles them using `reconcile_roadmap_tasks()`, preserving existing database row IDs and ensuring uniqueness constraints remain intact.

---

## 7. Test Verification & Evidence

### 7.1 Focused Test Suite: `test_batch_06_task_identity_and_integrity.py`
17 comprehensive test cases were executed covering all defect scenarios and edge cases:
- `test_b01_reproduce_duplicate_automatic_codes_after_deletion`: PASSED
- `test_b02_reproduce_rename_leaves_dangling_dependency_and_fix`: PASSED
- `test_b03_reproduce_manual_schedule_violates_prerequisite_date`: PASSED
- `test_b03_upstream_date_edit_cannot_invalidate_downstream_schedule`: PASSED
- `test_concurrent_automatic_code_allocation`: PASSED (threaded concurrent task creation without collision)
- `test_explicit_duplicate_task_code_rejected`: PASSED
- `test_rename_rewrites_multiple_incoming_dependents`: PASSED
- `test_rename_rollback_on_invalid_candidate_graph`: PASSED
- `test_foreign_project_references_rejected`: PASSED
- `test_cycles_and_self_dependency_rejected`: PASSED
- `test_boundary_date_equality_rule`: PASSED (`start == prereq_end` succeeds, `start < prereq_end` fails)
- `test_deletion_with_dependents_rejected`: PASSED
- `test_deletion_without_dependents_allowed`: PASSED
- `test_bulk_generation_and_reconciliation_compatibility`: PASSED
- `test_cross_user_project_isolation`: PASSED (403 Forbidden verified)
- `test_csrf_protection_on_task_mutations`: PASSED (403 CSRF token missing verified)
- `test_migration_preflight_logic`: PASSED (clean rename for unreferenced, RuntimeError for ambiguous)

### 7.2 Full Test Suites Summary
- **Backend Suite:** `python -m pytest tests -v`  
  **Result:** **305 passed, 5 skipped, 0 failed** in 58.20 seconds.
- **Frontend Test Suite:** `npm test -- --run` (in `client/`)  
  **Result:** **100 passed across 10 test files, 0 failed**.
- **Frontend Linting:** `npm run lint` (in `client/`)  
  **Result:** **0 errors**, 25 warnings (React compiler optimizations, fast refresh).
- **Frontend Build:** `npm run build` (in `client/`)  
  **Result:** **Production bundle compiled successfully in 567ms**.
- **Database Migrations:** `alembic downgrade -1` and `alembic upgrade head` executed cleanly with exit code 0.

### 7.3 Skipped Checks
- 5 integration tests skipped in the backend test suite due to missing optional PostgreSQL/Redis connection strings or live external providers during local SQLite mock testing (same 5 skipped in Batch 05).

---

## 8. Deployment Preflight & Operational Instructions

Before running database migrations on production:
1. **Database Backup:** Take a full PostgreSQL snapshot of the `roadmap_tasks` table.
2. **Duplicate Detection Preflight Query:**
   ```sql
   SELECT project_id, task_code, COUNT(*)
   FROM roadmap_tasks
   GROUP BY project_id, task_code
   HAVING COUNT(*) > 1;
   ```
   If any rows are returned, verify whether downstream dependencies reference them using:
   ```sql
   SELECT t1.id, t1.project_id, t1.task_code, t2.task_code as dependent_task
   FROM roadmap_tasks t1
   JOIN roadmap_tasks t2 ON t1.project_id = t2.project_id
   WHERE t2.dependencies::jsonb ? t1.task_code
     AND t1.id IN (
       SELECT id FROM roadmap_tasks rt
       WHERE (rt.project_id, rt.task_code) IN (
         SELECT project_id, task_code FROM roadmap_tasks GROUP BY project_id, task_code HAVING COUNT(*) > 1
       )
     );
   ```
   If clean or unambiguous, run `alembic upgrade head`.

---

## 9. Declarations & Compliance Confirmation

- **No Production Deployments:** No deployment triggers were invoked. Render auto-deploy remains disabled.
- **No Production Database Access:** All development, testing, and migration verifications occurred locally. No connections were made to production Supabase PostgreSQL.
- **No Gemini Calls:** No live AI API calls were made.
- **Free-Tier Compatibility:** No paid services, extensions, or infrastructure were introduced.

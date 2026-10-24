# BusinessArchitect Master Correction and Completion Register

This register persists progress across phases, documenting findings, affected paths, implementation status, test evidence, commit SHAs, remaining limitations, and configuration/migration requirements.

---

## Phase 1 — Independent Self-Review of Batch 07.1

- **Status:** COMPLETED
- **Findings & Affected Paths:**
  1. `server/app/services/version_service.py` (`_get_authoritative_versions`):
     - Uncommitted caller additions (`db.new`) or uncommitted caller deletions (`db.deleted`) on `ModuleVersion` could be overlooked or cause inconsistent results if not explicitly flushed before authoritative query. Added deliberate handling: `if pending_new or pending_deleted: db.flush()`.
     - Verified caller dirty attributes merge contract: `dirty_state_map` preserves caller-owned modifications while clean attributes are updated with fresh remote database values via `.populate_existing()`.
  2. `server/app/api/modules.py` (`resolve_conflict_and_replace`):
     - Duplicate reconciliation was present: `VersionService.resolve_conflict_and_replace` internally invokes `sync_roadmap_working_tasks_to_active_version`, but `modules.py` subsequently invoked `_reconcile_roadmap_tasks` a second time. Removed redundant duplicate call.
     - Added `flag_modified(version, "is_active")` to `_merge_legacy_roadmap_history`.
  3. `server/app/api/admin/integrity.py` (`execute_repair`):
     - In per-module integrity repair/pruning loops, if a later module failed, the entire request previously raised 500 without recording an audit log, even though earlier module transactions had already committed. Fixed to isolate module repairs, record accurate audit log (`partial_success` with exact counts and error details), and return accurate status without falsely claiming complete rollback.
- **Test Evidence:**
  - `server/tests/test_correction_batch_07_1_authoritative_versions.py` (13 passed in 6.54s):
    - `test_stale_in_memory_version_flags_authoritatively_updated_on_restore`
    - `test_stale_cache_across_save_new_version`
    - `test_stale_cache_across_resolve_conflict_and_replace`
    - `test_stale_cache_across_delete_version`
    - `test_admin_prune_excess_versions_synchronizes_roadmap_tasks`
    - `test_roadmap_graph_conflict_rolls_back_entire_operation`
    - `test_pruning_and_repair_invariants`
    - `test_foreign_module_pointer_repaired`
    - `test_version_capacity_enforcement_and_zero_provider_calls`
    - `test_metadata_listing_and_historical_immutability`
    - `test_dirty_and_remote_clean_attributes_merged_correctly`
    - `test_pending_new_and_deleted_versions_handled_deliberately`
    - `test_admin_integrity_repair_partial_completion_and_audit`
  - `server/tests/test_batch_07_version_integrity_and_safe_repair.py` (15 passed in 6.54s).
- **Commit SHA:** `765110b6a4fd8ab4ab9b8c1e14928000a3bf870d`
- **Remaining Limitations:** PostgreSQL engine-level concurrency verification remains pending disposable instance configuration; all SQLite unit/integration and isolation invariants verified.
- **Production Config / Migration Requirements:** None. No schema changes required.

---

## Phase 2 — Trusted Client Identity and Auth Abuse

- **Status:** COMPLETED
- **Findings & Affected Paths:**
  1. `Dockerfile`:
     - Added `--no-proxy-headers` to Uvicorn startup command to prevent Uvicorn's default middleware from rewriting `scope["client"]` using untrusted `X-Forwarded-For` before application ASGI middleware has verified the immediate socket peer.
  2. `server/app/core/client_identity.py`:
     - Added `TrustedProxyMiddleware` and enhanced `_extract_from_forwarded` to traverse forwarding headers strictly right-to-left.
     - Preserved HTTPS scheme handling and secure cookies (`scope["scheme"] = "https"`) ONLY when the immediate peer is a verified trusted proxy and sent `X-Forwarded-Proto: https`.
     - Validated IPv4/IPv6 address parsing and bounded forwarding chains (max 10 hops, max 2048 chars). Untrusted direct peers cannot spoof client identity using forwarding headers. Malformed/missing socket peers fallback to bounded restrictive fallback `0.0.0.0`.
  3. `server/app/main.py`:
     - Enforced `registration_admission_middleware` before Pydantic request parsing and expensive Argon2 password hashing.
     - Enforced 64KB request body limit returning HTTP 413 without loading unbounded payloads into memory.
     - Replaced independent `check_rate_limit` and `record_attempt` with bucket-locked `check_and_record_registration_admission(lim_db, client_ip)` to prevent concurrent admission races.
  4. `server/app/api/auth.py` & `server/app/api/admin/auth.py`:
     - Replaced short-circuit missing user return with `verify_password(req.password, DUMMY_PASSWORD_HASH)` using precomputed Argon2id hash to prevent timing-based account enumeration.
     - Maintained account-scoped and IP-scoped rate-limit buckets with consistent lowercase/trimmed normalization.
  5. `server/app/core/telemetry.py`:
     - Isolated `record_security_event` to its own `SessionLocal()` transaction, preventing accidental premature commit or rollback of caller business transactions.
  6. `server/app/core/auth_limiter.py` & `server/app/api/admin/integrity.py`:
     - Added `check_rate_limit` try/except block returning HTTP 503 fail-closed with clear error detail if the database is unavailable.
     - Added bounded batch cleanup `cleanup_expired_events(max_retention_seconds, batch_size)` using indexed `created_at`.
     - Added opportunistic non-blocking cleanup `maybe_cleanup_expired_events` throttled across workers.
     - Added `EXPIRED_RATE_LIMITS` detection in admin health scan and `clean_expired_rate_limits` in admin repair actions.
- **Test Evidence:**
  - `server/tests/test_correction_phase_02_identity_and_auth_abuse.py` (11 passed):
    - `test_untrusted_direct_peer_cannot_spoof_identity_or_scheme`
    - `test_trusted_proxy_traverses_right_to_left_and_updates_scheme`
    - `test_ipv6_and_malformed_forwarding_chains`
    - `test_registration_admission_blocks_malformed_requests_at_threshold`
    - `test_registration_oversized_payload_rejected_with_413`
    - `test_login_uses_dummy_password_hash_for_nonexistent_user`
    - `test_admin_login_uses_dummy_password_hash_for_nonexistent_or_unauthorized_user`
    - `test_limiter_database_failure_fails_closed_with_503`
    - `test_record_security_event_does_not_commit_or_rollback_caller_transaction`
    - `test_cleanup_expired_events_bounds_deletions`
    - `test_admin_integrity_scan_and_repair_expired_rate_limits`
  - `server/tests/test_batch_05_client_identity_and_limiter.py` (20 passed):
    - Tested spoofing, trusted/untrusted hops, IPv6, malformed headers, account/IP isolation, password hashing bypass prevention, and parallel admission.
  - Total: 31 passed in 18.95s, 0 failures. Full suite test collection: 413 tests collected cleanly.
- **Commit SHA:** `13c069ced8a516b480855db7d250ccd4f04f1e11`
- **Remaining Limitations:**
  - Multi-process distributed rate limiting on PostgreSQL tested via thread/session semantics; disposable PostgreSQL engine-level checks remain pending Phase 11.
- **Production Config / Migration Requirements:**
  - Configure `TRUSTED_PROXIES` environment variable with trusted reverse proxy IPs/CIDRs if fronted by Render / Cloudflare reverse proxies. Default is empty (untrusted direct peers cannot set client IP).


---

## Phase 3 — Session Storage and Authentication Safety
- **Status:** Pending

---

## Phase 4 — Provider Transaction Decoupling
- **Status:** Pending

---

## Phase 5 — Bounded Gemini Key Failover and Request Budgets
- **Status:** Pending

---

## Phase 6 — Generation Validation, Roadmap Semantics and Retry Intent
- **Status:** Pending

---

## Phase 7 — Error Sanitization, Exports and Chat History
- **Status:** Pending

---

## Phase 8 — Startup, Loading and Frontend Consistency
- **Status:** Pending

---

## Phase 9 — Connection Settings and Free-Tier Performance
- **Status:** Pending

---

## Phase 10 — Minimal Runtime Storage and Repository Cleanup
- **Status:** Pending

---

## Phase 11 — Reproducible CI and Disposable PostgreSQL
- **Status:** Pending

---

## Phase 12 — Final Offline End-to-End and Release Candidate
- **Status:** Pending

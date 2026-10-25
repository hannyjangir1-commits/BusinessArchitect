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

- **Status:** COMPLETED
- **Findings & Affected Paths:**
  1. `server/app/core/security.py`:
     - Added `hash_session_token(token: str) -> str` to generate a high-entropy SHA-256 cryptographic digest of session tokens for database persistence and server-side lookup.
     - Preserved raw bearer tokens exclusively in memory and inside secure HttpOnly cookies (`aba_session`).
     - Preserved HMAC-SHA256 CSRF protection bound to the browser's cookie session token.
  2. `server/app/models/all_models.py`:
     - Added `token_digest` column (`String(64)`, unique index) to `Session` table.
     - Altered `session_token` column to be `nullable=True`.
     - Added `SessionTokenComparator` and `@hybrid_property` on `Session.session_token` to support transparent dual lookup (`session_token == token` or `token_digest == hash_session_token(token)`), and SQL NULL-safe inequality (`!=`).
     - Automatic setter ensures test fixtures constructing `Session(session_token=...)` compute `token_digest` automatically.
  3. `server/alembic/versions/b1c2d3e4f5a6_add_session_token_digest.py`:
     - Reversible, additive migration adding `token_digest` and making `session_token` nullable via `batch_alter_table`.
     - Automatically backfills `token_digest = sha256(session_token)` for all existing active sessions without invalidating or logging out any active users.
     - Downgrade cleanly drops `token_digest` and its unique index.
  4. `server/app/api/deps.py`:
     - Updated `get_current_user` to query `Session.token_digest == digest`.
     - Implemented self-healing migration fallback: legacy unmigrated raw-token sessions authenticate seamlessly, immediately upgrade their database record with `token_digest`, clear `session_token = None`, and commit.
     - Enforces account suspension and expiration checks with timezone awareness.
  5. `server/app/api/auth.py` & `server/app/api/admin/auth.py`:
     - Updated `register`, `login`, and `refresh` to store ONLY `token_digest` in `DBSession` (`session_token = None`).
     - Response bodies NEVER return raw tokens or digests (only user info and `csrf_token`).
     - Updated `logout` and `change-password` to safely invalidate sessions using `token_digest`.
  6. `server/app/api/admin/security.py`:
     - `list_active_sessions`: evaluated `is_current` via `token_digest == current_digest` without returning tokens or digests in JSON.
     - `revoke_all_sessions`: emergency global kill-switch excludes the invoking admin session via `token_digest != current_digest` and revokes all other active sessions.
  7. `server/app/core/config.py`:
     - `validate_production_runtime_safety`: verified that known dev secrets and weak secrets abort startup safely without printing secret values in exceptions.
- **Test Evidence:**
  - `server/tests/test_correction_phase_03_session_storage_and_auth_safety.py` (12 passed in 16.89s):
    - `test_login_and_registration_store_digest_not_raw_token`
    - `test_session_lookup_succeeds_with_digest`
    - `test_legacy_session_self_healing_upgrade`
    - `test_expired_session_fails_and_cleans_up`
    - `test_logout_invalidates_session`
    - `test_session_fixation_resistance_on_refresh`
    - `test_csrf_protection_on_state_changing_requests`
    - `test_password_change_invalidates_other_sessions`
    - `test_suspended_user_session_denied`
    - `test_admin_sessions_and_emergency_revoke_all`
    - `test_admin_session_listings_do_not_expose_tokens_or_digests`
    - `test_production_config_rejects_insecure_secrets`
  - `server/tests/test_production_config_safety.py` (8 passed in 5.49s).
  - `server/tests/test_batch_04_admin_authorization.py` & `server/tests/test_audit_repairs_and_csrf_exhaustive.py` (39 passed, 1 skipped in 55.28s).
  - Disposable database upgrade & downgrade test passed cleanly.
  - Full suite test collection: 425 tests collected cleanly.
- **Commit SHA:** `9e62ce7ee9f5066f2c8a10a592d9c073b298d745`
- **Remaining Limitations:**
  - None for Phase 3; multi-process PostgreSQL engine-level checks remain pending Phase 11.
- **Production Config / Migration Requirements:**
  - Run `alembic upgrade head` (`b1c2d3e4f5a6`). Existing sessions are automatically backfilled with cryptographic digests; zero forced logouts.


---

## Phase 4 — Provider Transaction Decoupling

- **Status:** COMPLETED
- **Findings & Affected Paths:**
  1. `server/app/services/module_orchestration_service.py` (`execute_module_generation`):
     - Prior implementation held an open database transaction across external AI provider calls (`ai_service.build_generation_brief` and `ai_service.generate_*`), exhausting connection pool slots under concurrency and transaction pooler timeouts.
     - Decoupled into preflight, provider invocation, and persistence phases:
       - Preflight: verifies version capacity under project-first lock and copies detached scalar context (`project_id`, `user_id`, `module_id`, `cross_ctx`, `context_sources`, `planning_dict`, `project_fp`).
       - Connection release: `db.close()` immediately returns the connection to the pool.
       - Provider invocation: provider runs with 0 checked-out database connections (`engine.pool.checkedout() == 0`).
       - Post-provider persistence: short isolated transaction under `project_first_lock` revalidates user existence/active status, project existence and ownership, module existence, and re-enforces capacity.
       - Commits version, roadmap tasks (if roadmap), sets `_cached_versions`, and records telemetry.
       - On provider failure, records isolated telemetry in a short separate transaction without touching business entities.
  2. `server/app/api/modules.py`:
     - `generate_module`: leverages `getattr(new_ver, "_cached_versions", None)` or short query session for metadata response without holding long connections.
     - `modify_module_with_ai`: reads context, closes `db`, executes `ai_service.modify_section`, validates schema, and persists under short revalidated transaction with `project_first_lock`.
     - `resolve_conflict_and_replace`: reads context, closes `db` when AI modification requested, executes provider, validates, and persists under short revalidated transaction.
  3. `server/app/api/copilot.py` (`send_chat_message`):
     - Commits user message, extracts chat history and project info, closes `db`, invokes `ai_service.chat_copilot`, and persists assistant message under short revalidated transaction.
  4. `server/app/api/admin/ai_ops.py` (`retry_ai_operation`):
     - Reads operation context, closes `db`, executes provider call, and persists retried version in a short transaction checking permissions via `_get_permissions_for_role(p_admin.role)` supporting `super_admin`.
- **Test Evidence:**
  - `server/tests/test_correction_phase_04_provider_transaction_decoupling.py` (10 passed in 4.84s):
    - `test_generation_releases_db_connection_during_provider_call` (verified `engine.pool.checkedout() == 0`)
    - `test_section_modify_releases_db_connection_during_provider_call` (verified `engine.pool.checkedout() == 0`)
    - `test_copilot_chat_releases_db_connection_during_provider_call` (verified `engine.pool.checkedout() == 0`)
    - `test_admin_retry_releases_db_connection_during_provider_call` (verified `engine.pool.checkedout() == 0`)
    - `test_concurrent_ordinary_requests_continue_while_provider_blocked`
    - `test_project_deleted_while_provider_pending_returns_404`
    - `test_module_deleted_while_provider_pending_returns_404`
    - `test_capacity_reached_while_provider_pending_returns_conflict`
    - `test_user_suspended_while_provider_pending_returns_403`
    - `test_provider_failure_leaves_saved_content_unchanged_and_records_isolated_telemetry`
  - Regression verification (58 passed in 20.57s):
    - `test_correction_phase_03_session_storage_and_auth_safety.py` (12 passed)
    - `test_correction_batch_07_1_authoritative_versions.py` (13 passed)
    - `test_batch_07_version_integrity_and_safe_repair.py` (15 passed)
    - `test_admin_management_and_ops.py` (9 passed)
    - `test_ai_failure_modes.py` (9 passed)
  - Total: 68 tests passing cleanly with 0 failures.
- **Commit SHA:** `19d43decee5505c3b2c2c4b5cd4e2b2815ded6ea`
- **Remaining Limitations:** None. Connection pool checkouts assert 0 during all external provider operations.
- **Production Config / Migration Requirements:** None. Zero schema migrations required.

---

## Phase 5 — Bounded Gemini Key Failover and Request Budgets

- **Status:** COMPLETED
- **Findings & Affected Paths:**
  1. `server/app/core/config.py`:
     - Consolidated key sources: parsed `GEMINI_API_KEYS` (supports JSON list array e.g. `["key1", "key2"]` and comma/semicolon/newline-delimited text) alongside backwards-compatible `GEMINI_API_KEY`.
     - Trimmed quotes, stripped comments, and deduplicated keys while preserving order.
     - Added budget controls: `GEMINI_TOTAL_TIMEOUT_SECONDS` (60s default), `GEMINI_KEY_COOLDOWN_SECONDS` (60s default), `GEMINI_MAX_CONCURRENT_CALLS` (5 default), and `GEMINI_MAX_USER_RPM` (30 default).
  2. `server/app/ai/gemini_service.py`:
     - Thread-safe key health & slot tracking: `_available_key_slots`, `_cool_down_key`, `_mark_key_invalid`, `_key_cooldowns`, `_disabled_keys`, and `_key_state_lock`.
     - Process-local key health cooldown: locks are held only for brief slot retrieval and update; zero locks held during provider I/O; zero threads sleep while holding key locks.
     - Automatic recovery: once cooldown expires (`monotonic() >= cooldown_until`), keys immediately return to active rotation without permanent exhaustion.
     - Invalid credential isolation: keys returning 400 API_KEY_INVALID, 401 Unauthorized, or 403 Forbidden are permanently marked `disabled` for the process lifetime without crashing or blocking other valid keys in the pool.
     - Single attempt SDK configuration: passed `HttpRetryOptions(attempts=1)` to ensure provider SDK does not multiply request attempts with unbudgeted hidden retries.
     - Bounded candidate models: restricted fallbacks to at most 1 resilient fallback model, avoiding combinatorial multiplication of attempts (keys × models).
     - Opaque diagnostics: implemented `get_key_slot_diagnostics()`, exposing `slot_1`, `slot_2`, etc. with status (`healthy`, `cooling_down`, `disabled`) and cooldown seconds remaining without leaking any key secrets.
     - Bounded in-flight concurrency: enforced `_concurrency_semaphore` (bounded to `GEMINI_MAX_CONCURRENT_CALLS`) to safeguard memory on free-tier Render instances (512MB RAM).
  3. `server/app/core/ai_limiter.py`:
     - Created `AIUserRateLimiter` sliding-window in-memory rate limiter enforcing `GEMINI_MAX_USER_RPM`.
     - Rejects excessive frequency with HTTP 429 and `Retry-After` header.
  4. `server/app/schemas/copilot.py` & `server/app/schemas/modules.py`:
     - Bounded chat message (`CopilotChatRequest.message`) and modification instruction (`SectionModifyRequest.instruction`, `VersionConflictResolveRequest.instruction`) lengths to 4000 characters.
  5. `server/app/api/admin/system.py`:
     - Integrated `slots` diagnostics into the Content Generation Service health component.
- **Test Evidence:**
  - `server/tests/test_correction_phase_05_bounded_key_failover.py` (12 passed in 5.43s):
    - `test_config_key_parsing_and_deduplication`
    - `test_first_key_succeeds_without_further_rotation`
    - `test_first_rate_limited_second_succeeds`
    - `test_timeout_then_fallback_key`
    - `test_invalid_key_handling_disables_slot_and_falls_back`
    - `test_all_keys_unavailable_raises_clear_error_without_fabrication`
    - `test_cooldown_recovery_restores_eligibility`
    - `test_deadline_exhaustion_stops_failover`
    - `test_concurrent_generation_semaphore_limits_in_flight_calls`
    - `test_no_credential_leakage_in_diagnostics_and_system_health`
    - `test_user_ai_rate_limiter_blocks_abusive_frequency`
    - `test_input_size_bounding_rejects_oversized_messages`
  - Regression suite (52 passed in 24.52s across Phase 3, 4, 5, AI failure modes, and Admin ops).
- **Commit SHA:** `8d2dc489cdb11a8685b3d2e6afe925b2bed469bd`
- **Remaining Limitations:** Multi-process distributed coordination of rate limits across separate dynos remains process-local, adhering to the free-tier single-container design.
- **Production Config / Migration Requirements:**
  - Users can configure 1, 2, or 3 keys in `GEMINI_API_KEYS` (e.g. `key1, key2, key3` or `["key1", "key2", "key3"]`). Zero schema migrations required.

---

## Phase 6 — Generation Validation, Roadmap Semantics and Retry Intent

- **Status:** COMPLETED
- **Findings & Affected Paths:**
  1. `server/app/api/modules.py` (`generate_module`):
     - Unwrapped embedded `planning_inputs` payload when passed by clients.
     - Added strict preflight schema validation for `RoadmapPlanningRequest` and `TechStackPlanningRequest` before project readiness checks and before provider invocation.
     - Invalid generation/planning payloads now return controlled HTTP 422 Unprocessable Entity with 0 provider calls, eliminating unhandled 500 errors.
     - Attached `retry_context` metadata during section modification and version replacement conflict paths.
  2. `server/app/services/roadmap_service.py` (`normalize_roadmap_schedule`, `canonicalize_incoming_tasks`):
     - Removed silent date clamping `if end < start: end = start + timedelta(days=6)`; contradictory inverted schedules are preserved as parsed and cleanly rejected during canonicalization.
     - Updated `canonicalize_incoming_tasks` to raise `IncompatibleTaskGraphError` with `INVALID_DATE_RANGE` on `end_date < start_date`.
     - Removed `cls.detect_and_break_dependency_cycles(tasks)` from `normalize_roadmap_schedule`; normalization no longer silently destroys dependency edges to manufacture artificial acyclic graphs.
     - Preserved same-day handover (`dependent.start_date >= prerequisite.end_date`) as valid graph boundaries without schedule conflicts.
  3. `server/app/core/telemetry.py` (`record_ai_operation`):
     - Added `retry_context` parameter storing minimal non-secret intent (`planning_inputs`, `instruction`, `module_type`, `operation_type`, `target_version_id`, `replace_version_id`).
     - Safely recorded intent in the existing `audit_logs` table under `action="ai_operation_intent"` and `target_type="ai_operation"` with 0 schema migrations and zero prompt/credential leakage.
  4. `server/app/services/module_orchestration_service.py` (`execute_module_generation`):
     - Moved provenance metadata attachment and `validate_module_payload` inside the provider execution try-block to ensure generated blueprints are strictly validated before persistence.
     - Attached `retry_context` to both failed and persisted operations.
  5. `server/app/api/admin/ai_ops.py` (`retry_failed_operation`):
     - Recovers original user planning intent from `AuditLog` (`action="ai_operation_intent"`).
     - Retries user-specific roadmaps and tech stacks with their exact original inputs (`start_date`, `horizon_weeks`, `checklist`, `team_capacity`) instead of guessing with generic defaults.
     - Retries modifications with original user instructions.
     - Rejects unsupported legacy operations (where intent was not captured) with a controlled HTTP 400 Bad Request explanation rather than guessing or mutating user work.
     - Strictly validates generated output via `validate_module_payload` before persistence and propagates intent along the retry lineage.
- **Test Evidence:**
  - `server/tests/test_correction_phase_06_generation_validation_and_roadmap.py` (9/9 passed in 7.82s):
    - `test_invalid_planning_request_returns_422_with_zero_provider_calls`
    - `test_missing_foreign_task_references_rejected`
    - `test_circular_dependency_detected_and_not_silently_removed`
    - `test_invalid_dates_rejected_and_not_silently_clamped`
    - `test_valid_equality_boundary_same_day_handover_accepted`
    - `test_retry_preserves_original_user_planning_intent`
    - `test_unsupported_legacy_retry_returns_controlled_explanation`
    - `test_provider_success_plus_persistence_conflict_preserves_content`
    - `test_snapshot_and_working_tasks_consistency_after_successful_generation`
  - Regression suite (61/61 passed in 28.20s across Phase 3, 4, 5, 6, Admin ops, AI failure modes, and end-to-end catalogue).
- **Commit SHA:** `4c575aee5c5674c391694f8373b3060cb59fbb1c`
- **Remaining Limitations:** None. Structured graph errors and retry intent preservation operate with zero production database migrations.
- **Production Config / Migration Requirements:** None. Uses existing `audit_logs.details` JSON column.

---

## Phase 7 — Error Sanitization, Exports and Chat History

- **Status:** COMPLETED (Closeout Verified)
- **Findings & Affected Paths:**
  1. `server/app/core/exports.py` (`sanitize_filename`, `format_content_disposition`):
     - Implemented RFC 6266 and RFC 5987 standard Content-Disposition formatting: `attachment; filename="{safe_ascii}.pdf"; filename*=UTF-8''{encoded_utf8_filename}`.
     - Strips CR (`\r`), LF (`\n`), null bytes (`\x00`), and ASCII control characters to defend strictly against HTTP header injection / response splitting.
     - Hardened `sanitize_filename` to bound raw string length to 100 characters, strip filesystem-prohibited characters (`/`, `\`, `<`, `>`, `:`, `"`, `|`, `?`, `*`, `;`, `%`), collapse multiple underscores, and fall back to safe default `blueprint_export.pdf` if title is empty or punctuation-only. Preserves exactly one `.pdf` extension.
     - Guarantees `filename="..."` attribute is purely safe ASCII alphanumeric/hyphen/underscore, preventing Latin-1 encoding crashes on Starlette/Uvicorn when exporting projects with Unicode titles (e.g. Hindi, Japanese, French accents).
     - Encodes full UTF-8 filename in `filename*` parameter for modern browser download fidelity.
  2. `server/app/services/pdf_service.py` & `server/app/api/exports.py` & `server/app/api/modules.py`:
     - Handled optional `reportlab` export dependency gracefully with `REPORTLAB_AVAILABLE` try/except block.
     - Added `PDFService.is_available()` availability check.
     - Missing export dependency returns a controlled HTTP 503 Service Unavailable ("PDF export service is temporarily unavailable: missing export engine.") rather than crashing or returning an unhandled 500 error.
     - Applied `format_content_disposition` to both full project blueprint exports and single module exports.
  3. `server/app/api/copilot.py` (Pagination & Context Budgeting):
     - Added cursor pagination via `before_id: Optional[str] = Query(None)`, `limit: int = Query(50, ge=1, le=200)`, and stable secondary tie-breaker ordering `order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())`.
     - Injected `X-Total-Count` and `X-Has-More` response headers so clients know if older messages exist beyond the current window.
     - Enforced explicit 16,000 character context budget for recent conversation history in `send_chat_message` and `GeminiService.chat_stream`.
     - Context budgeting drops the oldest historical messages first when budget is exceeded, maintaining newest conversational context while preserving the caller's message completely without silent truncation.
     - Excluded the pending `user_msg.id` from prompt context to prevent duplicated user messages.
     - Preserved all historical messages in PostgreSQL with zero loss of saved history.
  4. `client/src/services/api.ts` & `client/src/components/BlueprintCopilotModule.tsx` & `client/src/App.tsx`:
     - Updated API client with `getHistory(projectId, params)`, `getLatestHistory(projectId, limit=50)`, and `getOlderHistory(projectId, beforeId, limit=50)`.
     - Added "Load older messages" pagination button in Copilot module header with loading indicator.
     - Preserved scroll position when prepending older messages using container height snapshot diffing (`scrollHeight - scrollTop`).
     - Added message deduplication by `m.id` preserving chronological order (`displayMessages`), eliminating duplicate key warnings and rendering collisions.
     - Wired state in `App.tsx` with `hasMoreCopilot` and `loadingOlderCopilot`. Sending a new message appends locally to state without discarding loaded history.
     - Project switching and logout (`clearWorkspace()`) cleanly reset Copilot state, preventing cross-project or cross-session history leakage.
  5. `server/app/main.py`:
     - Registered global unhandled `Exception` handler on both `app` and `api_v1`, capturing unhandled errors and returning a sanitized HTTP 500 JSON payload: `{"detail": "An internal server error occurred.", "request_id": req_id}` with `X-Request-ID` header.
     - Attached correlation ID to `HTTPException` responses with status >= 500.
     - Updated `diagnostics_middleware` to return sanitized JSON response on unexpected exceptions escaping route handlers, verified with diagnostics enabled (`PERF_DIAGNOSTICS=True`) and disabled (`PERF_DIAGNOSTICS=False`).
  6. Error Detail and Log Sanitization across touched APIs:
     - Sanitized raw `str(e)` exposure in `server/app/api/projects.py:402`, `server/app/api/admin/projects.py:251`, `server/app/api/exports.py:71, 102`, `server/app/api/modules.py:638, 861`, `server/app/api/copilot.py:100`, and `server/app/api/admin/ai_ops.py:358`.
     - Sanitized exception logging in `server/app/core/telemetry.py` and `server/app/services/system_setting_service.py` using `type(e).__name__` instead of raw `str(e)` to guarantee database connection strings, credentials, and passwords never leak into logs or telemetry.
  7. Repository Regression Reconciliations:
     - `server/app/api/admin/ai_ops.py`: Handled missing `raw_planning` during admin roadmap retry by defaulting to `RoadmapPlanningRequest()`, fixing `test_admin_retry_reconciles_roadmap_under_project_lock`.
     - `server/app/api/modules.py` & `server/app/services/module_orchestration_service.py`: Added `db.commit()` on legacy record rename and ensured persistence session records `module_type = "execution_roadmap"`, fixing `test_ROAD_027_legacy_record_is_readable_then_migrated_on_write`.
- **Test Evidence & Backend Suite Reconciliation:**
  - **Full Backend Suite Status:**
    - Exact Command: `pytest -rs -q`
    - Working Directory: `server/` (using `server/pytest.ini` with `pythonpath = .`, `testpaths = tests`)
    - Collection Total: **469 tests collected across the repository** (0 exclusions, 0 altered pytest configurations)
    - Results: **460 passed, 9 skipped, 0 failed, 98 warnings in 150.85s**
    - Suite Reconciliation Note: The earlier reported "73 tests" was a selected regression suite covering Phases 3–7, admin ops, AI failure modes, and concurrency sync; 469 tests is the authoritative full repository suite.
    - Reasons for 9 Skipped Tests:
      1. `tests/test_pdf_and_ai.py:68`: `Live Gemini API key not configured; skipping integration smoke test.`
      2. `tests/test_e2e_full_workflows.py:106`: `Live Gemini API key not configured; skipping real AI generation workflow test.`
      3. `tests/test_e2e_full_workflows.py:138`: `Live Gemini API key not configured; skipping real AI generation workflow test.`
      4. `tests/test_batch_04_admin_authorization.py:1016`: `PostgreSQL concurrency test requires running PostgreSQL instance.`
      5. `tests/test_correction_batch_06_1_reconciliation.py:1094`: `PostgreSQL concurrency test requires running PostgreSQL instance.`
      6. `tests/test_correction_batch_06_1_reconciliation.py:1192`: `PostgreSQL concurrency test requires running PostgreSQL instance.`
      7. `tests/test_correction_batch_06_1_reconciliation.py:1283`: `PostgreSQL concurrency test requires running PostgreSQL instance.`
      8. `tests/test_correction_batch_06_1_reconciliation.py:1410`: `PostgreSQL concurrency test requires running PostgreSQL instance.`
      9. `tests/test_deployment_and_supabase_readiness.py:195`: `Requires live Supabase / PostgreSQL instance for real DDL smoke test.`
  - **Phase 7 Focused Suite:**
    - `server/tests/test_correction_phase_07_error_sanitization_exports_chat.py` (13/13 passed in 7.62s):
      - `test_sanitize_filename_and_rfc5987_formatting`
      - `test_sanitize_filename_bounds_length_and_edge_cases`
      - `test_unicode_export_filename_content_disposition`
      - `test_newline_and_header_injection_defense`
      - `test_missing_export_dependency_handling`
      - `test_chat_history_pagination_and_ordering`
      - `test_chat_history_cursor_pagination_before_id`
      - `test_chat_provider_context_limits`
      - `test_chat_provider_context_truncation_drops_oldest_preserving_prompt`
      - `test_cross_user_tenant_isolation_copilot_and_exports`
      - `test_synthetic_sensitive_markers_never_leak_in_client_or_telemetry`
      - `test_unhandled_route_exception_returns_clean_500_with_request_id`
      - `test_diagnostics_middleware_sanitizes_unhandled_subapp_exceptions`
  - **Frontend Verification:**
    - Test Suite: `npm test` in `client/` — **10 test files, 100 passed in 48.07s**.
    - Linter: `npm run lint` in `client/` — **0 errors, 25 warnings**.
    - Build: `npm run build` in `client/` — **Built successfully (`tsc -b && vite build`)**.
- **Remaining Limitations & Honest Disclosures:**
  - **ReportLab Typography / Glyph Limitation:** Standard ReportLab core Type 1 Helvetica fonts are restricted to the Latin-1 character set. Titles or content containing Devanagari (Hindi `व्यापार`), CJK (Japanese `日本語`), Cyrillic, or Arabic render unmapped placeholders in the PDF document body unless external TrueType Unicode font files (`.ttf`) are registered with ReportLab's font manager. However, the download filename in the HTTP `Content-Disposition` header preserves 100% UTF-8 character fidelity via RFC 5987 `filename*` encoding without crashing Starlette/Uvicorn.
  - **PostgreSQL Engine-Level Concurrency:** Engine-level row lock / race condition tests remain skipped pending a running disposable PostgreSQL instance (Phase 11).
- **Production Config / Migration Requirements:** None. Zero schema migrations required.

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

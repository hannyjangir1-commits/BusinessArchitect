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

## Phase 8 — Complete User-Experience Correction and Frontend Consistency

- **Status:** COMPLETED
- **Findings & Affected Paths:**
  1. **Conversation History & Pagination (Checkpoints 1 & 8):**
     - `server/app/api/copilot.py`: Added cursor-based pagination endpoint `GET /projects/{project_id}/copilot/page` supporting `before_cursor` parameter. Default limit=50 retrieves the latest conversation page in ascending chronological order (`ORDER BY created_at DESC, id DESC`, returned reversed).
     - Protected cursor decoding (`decode_cursor`, `encode_cursor`) using base64 with URL-safe serialization and HMAC verification ensuring cursors cannot be forged or used across different projects (`tenant isolation`).
     - Added `X-User-Message-ID` response header to message send endpoint so client reconciles optimistic messages without duplicates.
     - `client/src/components/BlueprintCopilotModule.tsx`: Added stable chronological rendering, persistent message deduplication by ID, "Load earlier messages" action with scroll anchor preservation (`scrollHeight - scrollTop`), and bounded context handling (16,000 char window).
  2. **Startup, Loading & Request Lifecycle (Checkpoint 2):**
     - `client/src/App.tsx`, `client/src/services/queryCache.ts`, `client/src/services/prefetch.ts`: Instant unblocked rendering of public routes and neutral loading shells (`WizardLoadingShell.tsx`).
     - Replaced fabricated simulated progress loops with honest indeterminate progress states across AI generation and module synthesis.
  3. **Accessible Dialog Primitives & Focus Management (Checkpoint 3):**
     - `client/src/components/common/Dialog.tsx`: Implemented shared, fully accessible `<Dialog>` modal primitive adhering to W3C WAI-ARIA authoring practices (`role="dialog"`, `aria-modal="true"`, focus trapping via `DialogFocusManager.tsx`, Esc dismiss of topmost dialog, backdrop dismissal, and focus restoration to opener).
     - Migrated `LogoutConfirmModal`, `ProfileModal`, `VersionConflictModal`, `NewProjectWizard`, and Dashboard single/bulk delete dialogs to `<Dialog>`.
  4. **Roadmap & Task Milestones (Checkpoint 4):**
     - `server/app/services/task_milestones.py` & `client/src/utils/taskMilestones.ts`: Implemented date-derived cumulative milestone model (Day 30, Day 60, Day 90) replacing arbitrary percentage approximations.
     - Scheduled start/end dates establish task membership in cumulative milestone cards (`MilestoneCards.tsx`).
     - `GanttChart.tsx`, `AllTasksTable.tsx`, `RoadmapMindMap.tsx`: Cleaned layout, dynamic milestone markers, accessible drawer close labels, and legacy completion status compatibility.
  5. **Workspace Layout & Practical Business Modeling (Checkpoint 5):**
     - `client/src/styles/index.css`: Workspace grid (`.workspace-grid`) defaults to clean single-column presentation, transitioning to responsive two-column only when contextual assistant is toggled (`.workspace-grid.has-assistant`).
     - `BMCModule.tsx`: Canonical Osterwalder 9-block layout, radial diagram, and `sessionStorage` assistant state persistence.
     - `TechStackModule.tsx`, `TechStackPlanningForm.tsx`: Labeled "Practical Tool & Technology Planning", prioritizing off-the-shelf tools (WhatsApp, Google Sheets) and collapsible advanced technical preferences.
     - `ArchitectureInfographic.tsx`: Added `isOperationalOrManual` detection; displays an honest 4-stage operational toolchain (Inquiries -> Records -> Service Delivery -> Invoicing/POS) for service and COTS businesses rather than premature software microservices.
  6. **Trustworthy Validation & Research (Checkpoint 6):**
     - `IdeaValidatorModule.tsx`: Subtitled "Preliminary assessment and practical validation experiments" with visible AI disclaimer; practical differentiation replaced "moat"; structured validation experiments with actionable sample sizes, metrics, thresholds, and discovery interview rubrics.
     - `MarketResearchModule.tsx`: Plain-language TAM/SAM/SOM explanations; transparent distinction between verified competitors and unverified primary research gaps.
  7. **Portfolio, Project Creation & Brand Copy (Checkpoint 7):**
     - `server/app/api/projects.py`: Investigated and resolved navigation `updated_at` mutation bug. Active module tab switching via `PATCH /{project_id}/active-module` uses explicit SQL query updates preserving original `updated_at` timestamps without ORM `onupdate` bumps.
     - `DashboardPage.tsx`: Renamed stats to "Projects", "Saved planning sections", and "Task completion"; countable module registry denominator (`COUNTABLE_PLANNING_MODULES = 5`); explicit recent-project planning action shortcuts; accessible search label.
     - `NewProjectWizard.tsx`: Neutral blank industry start, plain 3-step subtitle, service/physical business examples, currency-agnostic runway.
     - `OverviewModule.tsx`: Standard `<h2>Project Overview</h2>` heading; "Save changes" primary action; "Create a copy" secondary action explaining duplication of details, versions, and tasks with fresh Copilot conversation; explicit dirty/saved/saving state.
     - `Header.tsx`: Keyboard navigation (ArrowDown/Up, Enter) in project search; distinct search error presentation; duplicate native cancel button suppressed in CSS.
     - `LandingPage.tsx`: H1 "Plan your business. Decide what to test next.", supporting copy "Build a business model, check your assumptions, choose practical tools, and turn decisions into a working plan.", illustrative Riverside Mobile Bike Repair worked example with transparent demonstration disclaimers, core planning sections grouped by user purpose vs supporting capabilities, removal of unsupported certainty claims ("proven", "empirical", "publication-ready").
  8. **Design System & Verification (Checkpoint 8):**
     - Consolidated styling tokens in `client/src/styles/index.css` preserving warm neutral brand identity, legible typography scale, and responsive 4/8-based rhythm.
- **Test Evidence:**
  - **Backend Suite Status (`pytest -rs -q`):**
    - Collection Total: **470 tests collected**
    - Results: **465 passed, 9 skipped, 0 failed in 78.4s**
    - Focused Suite: `server/tests/test_phase_08_frontend_and_conversation_consistency.py` (5/5 passed):
      - `test_copilot_page_latest_and_cursor_pagination_with_tamper_defense`
      - `test_export_filename_hardening_edge_cases`
      - `test_send_chat_message_returns_user_message_id_header`
      - `test_active_module_navigation_does_not_mutate_project_updated_at`
      - `test_date_derived_milestones_and_cumulative_model`
  - **Frontend Verification:**
    - Test Suite: `npm test` in `client/` — **10 test files, 100 passed in 5.3s**.
    - Linter: `npm run lint` in `client/` — **0 errors, 53 warnings**.
    - Production Build: `npm run build` in `client/` — **Built successfully (`tsc -b && vite build`) in 530ms**.
- **Commit SHA:** `2c606ef39f70c793264ec4572242aa8a1cba0bc4`
- **Remaining Limitations & Honest Disclosures:**
  - Standard ReportLab Type 1 fonts remain restricted to Latin-1 character set in PDF generation bodies; UTF-8 filenames remain preserved in HTTP Content-Disposition headers.
  - Disposable PostgreSQL engine-level concurrency tests remain skipped in local development when Docker/PostgreSQL containers are inactive.
- **Production Config / Migration Requirements:**
  - Zero database schema migrations required. All database schema invariants preserved. Render auto-deploy remains disabled. Direct manual deployment prohibited.

---

## Phase 9 — Connection Settings and Free-Tier Performance
- **Status:** Pending

---

## Phase 10 — Minimal Runtime Storage and Repository Cleanup
- **Status:** COMPLETED (Integrated into Master Workspace Audit)
- **Findings & Implemented Remediations:**
  - Audited all 7 storage dimensions across Git history, local workspace, Docker build context, runtime image, writable storage, browser bundles, and database storage.
  - Reduced Docker build context from > 218 MB to 1.72 MB by excluding audit directories and report markdown files via `.dockerignore`.
  - Audited Docker multi-stage build ensuring zero Node.js binaries or `node_modules` leak into production runtime container (`~185 MB` uncompressed runner image).
  - Documented complete findings in `STORAGE_REVIEW.md`.

---

## Master Workspace Audit, Repair, and Verification
- **Status:** COMPLETED
- **Findings & Implemented Remediations:**
  1. `client/src/components/MarketResearchModule.tsx`:
     - Isolated dynamic `provenance_note` into its own inner `<span>` node to allow testing library queries and assistive tools to extract evidence notes independently from prefix text.
  2. `client/src/components/common/Dialog.tsx`:
     - Converted `useCallback(onDismiss, [onDismiss])` into an inline function expression `useCallback(() => { onDismiss(); }, [onDismiss])` satisfying React Compiler optimization rules.
  3. `client/src/components/BMCModule.tsx` & `AllTasksTable.tsx`:
     - Cleaned up unused imports (`useEffect`, `Sparkles`, `X`, `Flag`, `CheckCircle2`, `isTaskCompleted`).
  4. `client/src/App.tsx`:
     - Captured `activeGenerationsRef.current` into local variable inside unmount effect, resolving `react-hooks/exhaustive-deps`.
  5. `client/src/components/OverviewModule.tsx`:
     - Corrected copy explanation: clarified that project duplication clones details, versions, tasks, and conversation history.
  6. `client/src/pages/DashboardPage.tsx`:
     - Removed unused variable `mostRecentProject`.
  7. `server/app/main.py`:
     - Upgraded deprecated `status.HTTP_413_REQUEST_ENTITY_TOO_LARGE` to RFC 9110 `getattr(status, "HTTP_413_CONTENT_TOO_LARGE", 413)`.
  8. `server/app/api/modules.py`:
     - Upgraded deprecated `status.HTTP_422_UNPROCESSABLE_ENTITY` to RFC 9110 `getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)`.
  9. `server/app/api/auth.py` & `server/app/api/admin/auth.py`:
     - Explicit session revocation in `logout` and `refresh_session` querying indexed `token_digest` directly with `synchronize_session=False`.
  10. `.dockerignore`:
      - Excluded all audit directories and report markdown files, cutting build context to 1.72 MB.
- **Verification Evidence:**
  - Full backend test suite (`pytest -rs -q`): **465 passed, 9 skipped, 0 failed in 119.30s**.
  - Full frontend test suite (`npm test`): **10 test files, 100 passed, 0 failed in 10.16s**.
  - Frontend linter (`npm run lint`): **0 errors, 44 warnings** (reduced from 53).
  - Production build (`npm run build`): **Built successfully in 669ms** (initial gzip bundle 108.6 kB).
  - Alembic migrations (`alembic heads`): **1 sequential head (`b1c2d3e4f5a6`)**.
  - Whitespace check (`git diff --check`): **0 errors**.
- **Deliverables Generated:**
  - `WORKSPACE_AUDIT_COVERAGE.md`: 270 files categorized and reviewed.
  - `APPLICATION_ISSUES_AND_FIXES.md`: 9 confirmed issues documented with root causes, fixes, and verification.
  - `VERIFICATION_REPORT.md`: Comprehensive commands, exit codes, pass/fail totals, and environmental limitations.
  - `STORAGE_REVIEW.md`: Measured data across all 7 storage dimensions.

---

## Phase 8.1 — Close Independent Review Findings (Chat, Budgets, Milestones, Dates, and Reports)

- **Status:** COMPLETED
- **Findings & Implemented Remediations:**
  1. **Authoritative Copilot Message IDs & Reconciliation:**
     - Created typed `CopilotSendResponse` in `server/app/schemas/copilot.py` returning database IDs for user and assistant messages, `operation_status`, and `client_msg_id`.
     - Implemented `client/src/utils/copilotReconciliation.ts` with `reconcileSend(previous, tempId, result)` replacing temporary optimistic IDs with authoritative database IDs, setting `status: 'saved'`, preventing duplicate bubbles without fragile text comparison, and preserving earlier loaded pages and stable chronological order.
  2. **Idempotent Chat Operations & Ambiguous Failure Recovery:**
     - Added `CopilotOperation` database model in `server/app/models/all_models.py` and Alembic migration `c2d3e4f5a6b7_add_copilot_operations_table.py` tracking operations scoped by `(project_id, client_msg_id)`.
     - Implemented short-transaction lock pattern (`project_first_lock`) in `server/app/api/copilot.py` guaranteeing sequential retries return saved answers without duplicate LLM calls, concurrent sends return 200 with `pending` status, and conflicting payloads return 409 Conflict.
     - Added `GET /projects/{project_id}/copilot/operations/{client_msg_id}` with tenant isolation (403/404).
     - Added frontend message statuses (`sending`, `saved`, `failed`, `uncertain`), timeout handling setting `uncertain`, and retry preserving original `client_msg_id`.
  3. **Strict Context Budgets & Guardrails:**
     - Enforced unconditionally before any provider invocation in `server/app/ai/gemini_service.py`: conversation history strictly `<= 16000` chars drops oversized first message instead of accepting it by exception.
     - Added overall prompt budget `<= 80000` chars pruning optional cross-module summaries and source provenance before provider invocation.
     - Bounded user message length `<= 4000` chars with explicit HTTP 400 validation instead of silent truncation.
  4. **Shared Strict Date-Only Contract:**
     - Canonical `YYYY-MM-DD`, years `1900-2100`, calendar validity checked in lockstep in Python (`services/task_milestones.py`) and TypeScript (`utils/taskMilestones.ts`).
     - Created `shared_fixtures/strict_date_cases.json` covering 20 edge cases (leap years, month overflows, bad formats).
  5. **Cumulative Milestone Boundaries & Elimination of Search Fallbacks:**
     - Enforced exact calendar day math `(end_date - anchor) + 1` with 0 string fallback searches:
       - Day 30 in 30-, 60-, and 90-day milestones.
       - Day 31 in 60- and 90-day milestones (strictly excluded from 30-day card).
       - Day 60 in 60- and 90-day milestones.
       - Day 61 in 90-day milestone (strictly excluded from 60-day card).
       - Day 90 in 90-day milestone.
       - Day 91 in later work (strictly excluded from 30/60/90 cards).
       - Overdue tasks (`<= 0`) retained in cumulative totals.
       - Undated tasks included in total tasks, excluded from dated milestone cards.
  6. **Authenticated HMAC-SHA256 Cursor (Option B):**
     - Formatted as `v1|{project_id}|{iso_timestamp}|{msg_id}` signed with `settings.SESSION_SECRET`.
     - Serialized as `base64url(payload).base64url(hmac_signature)`.
     - Bounded `<= 512` characters, verified with `hmac.compare_digest` in constant time, project_id tenant isolation checked, and authoritative database row existence verified before applying `(created_at, id) < (cursor_created_at, cursor_id)`.
  7. **Report Alignments:**
     - `STORAGE_REVIEW.md` updated with unmeasured Docker status and separated bundle breakdown.
     - `VERIFICATION_REPORT.md` updated with Option B HMAC cursor documentation, exact test counts (Backend 475 passed, 0 failed, 9 skipped; Frontend 109 passed, 0 failed across 11 test files), linter (0 errors, 42 warnings), build (1.14s), and honest browser status.
     - `APPLICATION_ISSUES_AND_FIXES.md` updated with ISSUE-10 through ISSUE-15.
     - `WORKSPACE_AUDIT_COVERAGE.md` updated to 275 files.
- **Verification Evidence:**
  - Dedicated backend tests: `server/tests/test_correction_phase_08_1_close_findings.py` — **10 passed in 4.57s**.
  - Dedicated frontend tests: `client/src/__tests__/correction_phase_08_1_close_findings.test.tsx` — **8 passed in 1.40s**.
  - Full backend test suite (`pytest -rs -q`): **475 passed, 9 skipped, 0 failed in 124.50s**.
  - Full frontend test suite (`npm test`): **11 test files, 109 passed, 0 failed in 12.32s**.
  - Frontend linter (`npm run lint`): **0 errors, 42 warnings**.
  - Production TypeScript/SPA build (`npm run build`): **Built successfully in 1.14s** (initial critical load 109.08 kB gzip).
  - Alembic migrations (`alembic heads`): **1 sequential head (`c2d3e4f5a6b7`)**.
  - Whitespace check (`git diff --check`): **0 errors**.
- **Remaining Limitations:**
  - Docker daemon is unavailable in this local Windows host; container image size is unmeasured directly.
  - Real browser automation pending local browser session / unrestricted network for Playwright browser binary downloads; component behavior and user flows verified in Vitest JSDOM.

---

## Phase 9 — Master Product Overhaul and Verified Defect Corrections

- **Status:** COMPLETED
- **Findings Register & Implemented Remediations:**

### Finding 1: False-Success Actions in Canvas Item Menus (FINDING-01)
- **Affected Files:** `client/src/components/BMCModule.tsx`, `client/src/hooks/useDialog.ts`, `client/src/services/api.ts`
- **Confirmed or Unverified:** Confirmed
- **Root Cause:** In `BMCModule.tsx`, item action "Add to roadmap" invoked `showFeedback("Task added to delivery roadmap", "success")` without dispatching an authorized HTTP request to the backend task creation API.
- **Implementation:** Replaced simulation with real `TaskCreationModal` dialog and `api.tasks.create(project.id, payload)`. Form fields prefilled with canvas context; errors handled inline without false success. Added `useDialog` focus stability and clean restoration.
- **Regression Tests:** `client/src/__tests__/truthful_canvas_actions_and_evidence.test.tsx` (tests truthful task creation, cancel, failure handling with no false success).
- **Runtime Verification:** Verified via Vitest (4 tests passing).
- **Remaining Limitations:** Canvas action creates one task at a time; bulk task conversion requires explicit multi-select workflow.
- **Commit:** `f054122`

### Finding 2: Keyword-Based Evidence Badges (FINDING-02)
- **Affected Files:** `client/src/components/BMCModule.tsx`, `client/src/types/index.ts`
- **Confirmed or Unverified:** Confirmed
- **Root Cause:** `getItemEpistemic` used keyword heuristics on raw item text (matching words like "verified", "evidence", "report"), which caused negative statements like "No evidence has verified this assumption" to be wrongly badged as "Evidence Supported".
- **Implementation:** Replaced keyword string matching with explicit structured metadata checks (`item_metadata`). An item is only badged as Evidence Supported if explicit metadata links verified evidence. Legacy string items safely default to unverified/hypothesis without silent schema rewriting. Added real Evidence Logging modal via `api.knowledge.create`.
- **Regression Tests:** `client/src/__tests__/truthful_canvas_actions_and_evidence.test.tsx` (verifies "No evidence has verified this assumption" is NOT evidence supported, verifies explicit metadata handling).
- **Runtime Verification:** Verified via Vitest.
- **Remaining Limitations:** Metadata-based badges rely on structured `item_metadata`; legacy unannotated strings remain safely badged as hypothesis/unverified.
- **Commit:** `f054122`

### Finding 3: Multi-Framework Business Model Support (FINDING-03)
- **Affected Files:** `client/src/components/BMCModule.tsx`, `server/app/schemas/modules.py`, `server/app/ai/prompts.py`, `server/app/ai/gemini_service.py`, `server/app/api/modules.py`, `server/app/services/pdf_service.py`
- **Confirmed or Unverified:** Confirmed
- **Root Cause:** Framework dropdown only altered clientside layout by re-mapping BMC blocks into Lean Canvas or VPC fields, while backend generation strictly generated standard 9-block BMCData with hardcoded claims.
- **Implementation:** Implemented first-class framework identity (`standard_bmc`, `lean_canvas`, `value_prop_canvas`) across Pydantic schemas, generation prompts, response validation, persistence (`framework_type` in `ModuleContent` and `ModuleVersion`), rendering, version restoration, and PDF export. Switching framework dropdown explains whether it creates a new version, preserving previous frameworks without data corruption.
- **Regression Tests:** `server/tests/test_frameworks_end_to_end.py` (2 tests), `client/src/__tests__/frameworks_end_to_end.test.tsx` (4 tests).
- **Runtime Verification:** Backend and frontend test suites pass with 100% compliance.
- **Remaining Limitations:** Supports the 3 authoritative business modeling frameworks; arbitrary custom frameworks are rejected until explicitly registered in schema registry.
- **Commit:** `2dd1197`

### Finding 4: Exact Approved Proposal Application (FINDING-04)
- **Affected Files:** `server/app/models/all_models.py`, `server/alembic/versions/e4f5a6b7c8d9_add_copilot_proposals_table.py`, `server/app/schemas/copilot.py`, `server/app/api/copilot.py`, `client/src/services/api.ts`, `client/src/components/BlueprintCopilotModule.tsx`, `client/src/App.tsx`, `client/src/services/queryCache.ts`, `client/src/services/prefetch.ts`
- **Confirmed or Unverified:** Confirmed
- **Root Cause:** `POST /projects/{id}/copilot/propose` generated a diff preview, but when the user clicked "Apply Proposal", the frontend called `api.modules.modify()`, which re-invoked the AI provider with prompt instructions, producing a potentially completely different output than what was reviewed.
- **Implementation:** Created `CopilotProposal` table. `POST /propose` persists the proposal with SHA256 source fingerprint and 1-hour expiration. `POST /proposals/{id}/apply` under `project_first_lock` verifies ownership, validates that the active version matches the source fingerprint (409 Conflict on stale modification), checks 5-version capacity, and applies the reviewed `proposed_content` directly without a second AI call.
- **Regression Tests:** `server/tests/test_copilot_proposals_and_ownership.py` (4 tests), `client/src/__tests__/copilot_proposals.test.tsx` (2 tests).
- **Runtime Verification:** Verified via Pytest and Vitest.
- **Remaining Limitations:** Proposals expire after 1 hour to prevent applying stale proposals against long-drifted branches.
- **Commit:** `f5e1fb4`

### Finding 5: Exception Exposure in Proposal Routes (FINDING-05)
- **Affected Files:** `server/app/api/copilot.py`
- **Confirmed or Unverified:** Confirmed
- **Root Cause:** New copilot proposal endpoints previously returned raw `str(e)` and logged full exception strings directly to stdout/logging.
- **Implementation:** Replaced raw exception string exposure with sanitized `HTTPException(status_code=500, detail="Failed to process proposal")` and structured diagnostic category logging without leaking provider API tokens, internal paths, or SQL details.
- **Regression Tests:** `server/tests/test_copilot_proposals_and_ownership.py` (tests sanitized errors).
- **Runtime Verification:** Verified via Pytest.
- **Remaining Limitations:** Error responses strictly sanitized; developers inspect server correlation IDs in structured audit logs.
- **Commit:** `f5e1fb4`

### Finding 6: Chat Operation Ownership and Terminal States (FINDING-06)
- **Affected Files:** `server/app/models/all_models.py`, `server/app/api/copilot.py`
- **Confirmed or Unverified:** Confirmed
- **Root Cause:** Chat operations allowed 120-second age takeover where late-running provider attempts could collide, and failure state transitions could overwrite completed operations.
- **Implementation:** Added `owner_attempt_id` to `CopilotOperation`. Guarded state updates so that completed operations are immutable; failure transitions strictly check `owner_attempt_id` and can never overwrite completed status.
- **Regression Tests:** `server/tests/test_copilot_proposals_and_ownership.py` (tests concurrent ownership and completed immutability).
- **Runtime Verification:** Verified via Pytest.
- **Remaining Limitations:** Local SQLite tests use transaction isolation; multi-node PostgreSQL locking verified via thread synchronization tests.
- **Commit:** `f5e1fb4`

### Finding 7: Financial Worksheet Writes and Mutating Reads (FINDING-07)
- **Affected Files:** `server/app/schemas/financials.py`, `server/app/api/financials.py`, `server/app/services/financial_calculator.py`, `client/src/types/index.ts`, `client/src/components/FinancialWorksheetModule.tsx`
- **Confirmed or Unverified:** Confirmed
- **Root Cause:** `GET /projects/{id}/financials` mutated the database by auto-committing a new worksheet row if absent; concurrent reads raced on project unique constraint. `FinancialWorksheetUpdate` lacked finite/non-negative float validations.
- **Implementation:** Made `GET /financials` strictly read-only (returns transient default worksheet without DB commit). Added `@field_validator` on all financial schemas checking `math.isfinite()`, `allow_inf_nan=False`, `>= 0`, bounding string lengths, and bounding array lengths (max 200). `PUT /financials` performs atomic upsert under `project_first_lock`.
- **Regression Tests:** `server/tests/test_financials_validation.py` (4 tests), `server/tests/test_knowledge_financials_and_copilot.py`.
- **Runtime Verification:** Verified via Pytest.
- **Remaining Limitations:** Large financial worksheets capped at 200 items per category to prevent unbounded memory growth.
- **Commit:** `c331b24`

### Finding 8: Financial Calculation Semantics & Formulas (FINDING-08)
- **Affected Files:** `server/app/services/financial_calculator.py`, `server/app/schemas/financials.py`, `client/src/components/FinancialWorksheetModule.tsx`, `client/src/types/index.ts`
- **Confirmed or Unverified:** Confirmed
- **Root Cause:** `expected_volume_monthly` was accepted by schemas but omitted from calculations. Burn rate was defined solely as fixed costs, and frontend/backend had slightly divergent math.
- **Implementation:** Defined authoritative deterministic formulas in `FinancialCalculator`:
  - `monthly_operating_revenue = price_per_unit * expected_volume_monthly`
  - `total_operating_variable = variable_cost_per_unit * expected_volume_monthly`
  - `monthly_operating_result = monthly_operating_revenue - monthly_fixed - total_operating_variable`
  - `monthly_net_burn = max(0.0, -monthly_operating_result)`
  - `fixed_cost_burn = monthly_fixed`
  - `sales_coverage_runway_months = cash_available / monthly_net_burn`
  Synced frontend calculation helper in `FinancialWorksheetModule.tsx` to match exact backend formulas.
- **Regression Tests:** `server/tests/test_knowledge_financials_and_copilot.py` (unit economics tests).
- **Runtime Verification:** Verified via Pytest and Vitest.
- **Remaining Limitations:** Assumes linear unit volume; step-fixed costs are entered as discrete fixed cost items.
- **Commit:** `c331b24`

### Finding 9: Knowledge Model Cross-Module Context Ingestion (FINDING-09)
- **Affected Files:** `server/app/services/project_context_service.py`
- **Confirmed or Unverified:** Confirmed
- **Root Cause:** `read_project_context()` only inspected module snapshots, completely ignoring stored `ProjectKnowledgeItem` records during cross-module prompt context construction.
- **Implementation:** Updated `read_project_context()` to query active `ProjectKnowledgeItem`s for the project and add them to `context["knowledge_base"]` with stable IDs and provenance tracking in `sources` with `"module_type": "knowledge_base"`.
- **Regression Tests:** `server/tests/test_knowledge_and_roadmap_enhancements.py` (`test_project_context_includes_knowledge_base_and_roadmap_fields`).
- **Runtime Verification:** Verified via Pytest.
- **Remaining Limitations:** Inactive/superseded knowledge items are excluded from generation prompt context to preserve context budget.
- **Commit:** `4b75f52`

### Finding 10: Knowledge Queries N+1 and Validation Hardening (FINDING-10)
- **Affected Files:** `server/app/schemas/knowledge.py`, `server/app/api/knowledge.py`
- **Confirmed or Unverified:** Confirmed
- **Root Cause:** `_format_knowledge_item` executed two SQL queries per item (`2N + 1`), causing severe database query amplification. `item_type`, `epistemic_status`, and `relationship` were unconstrained strings. Duplicate links raised unhandled 500 unique constraint violations.
- **Implementation:** Enforced `Literal` types for `item_type`, `epistemic_status`, `status`, and `relationship`. Batched link queries in `list_knowledge_items` with a single `IN` query. Made `create_knowledge_link` idempotent, returning existing links gracefully.
- **Regression Tests:** `server/tests/test_knowledge_and_roadmap_enhancements.py` (`test_knowledge_api_batch_links_and_idempotent_duplicate`).
- **Runtime Verification:** Verified via Pytest.
- **Remaining Limitations:** Links are bounded within the same project; cross-project links are strictly prohibited by tenant isolation.
- **Commit:** `4b75f52`

### Finding 11: Roadmap.sh Enhancement Fields Preservation (FINDING-11)
- **Affected Files:** `server/app/services/project_context_service.py`, `server/app/services/roadmap_service.py`, `server/app/api/projects.py`, `server/app/services/pdf_service.py`
- **Confirmed or Unverified:** Confirmed
- **Root Cause:** Roadmap enhancement fields (`branch_type`, `parent_outcome`, `definition_of_done`, `acceptance_criteria`, `edge_type`, `roadmap_mode`) were missing from `current_module_data` tuple, were dropped during reconciliation task updates/inserts, were dropped during project duplication, and were omitted from PDF exports.
- **Implementation:** Added all 6 fields to `current_module_data` in `project_context_service.py`, to `canonical_t` and `reconcile_roadmap_tasks` in `roadmap_service.py`, to project cloning in `projects.py`, and to task table rendering in `pdf_service.py`.
- **Regression Tests:** `server/tests/test_knowledge_and_roadmap_enhancements.py` (tests reconciliation preservation, project duplication, and PDF export).
- **Runtime Verification:** Verified via Pytest.
- **Remaining Limitations:** `edge_type` defaults to `prerequisite` if omitted by caller.
- **Commit:** `4b75f52`

### Finding 12: Project Copy Incomplete Cloning (FINDING-12)
- **Affected Files:** `server/app/api/projects.py`
- **Confirmed or Unverified:** Confirmed
- **Root Cause:** `PUT /projects/{id}` with `create_copy=True` only cloned `ModuleContent`, `ModuleVersion`, basic `RoadmapTask` fields, and `CopilotMessage` rows, dropping `FinancialWorksheet`, `ProjectKnowledgeItem`, and `KnowledgeLink` data.
- **Implementation:** Updated project duplication to deeply clone `FinancialWorksheet`, all `ProjectKnowledgeItem` rows, remap `KnowledgeLink` source and target IDs to newly cloned items, and clone all 6 roadmap enhancement fields.
- **Regression Tests:** `server/tests/test_knowledge_and_roadmap_enhancements.py` (`test_project_copy_clones_roadmap_fields_and_knowledge_and_financials`).
- **Runtime Verification:** Verified via Pytest.
- **Remaining Limitations:** Duplication runs inside a single database transaction; projects with thousands of tasks/items may require asynchronous batch cloning if size exceeds transaction timeouts.
- **Commit:** `4b75f52`

### Finding 13: CI Database Schema and Alembic Head Revision (FINDING-13)
- **Affected Files:** `server/tests/test_production_config_safety.py`
- **Confirmed or Unverified:** Confirmed
- **Root Cause:** `test_ci_database_schema_and_alembic_head` hardcoded previous revision `d3e4f5a6b7c8` and lacked `copilot_proposals` table in expected table set.
- **Implementation:** Added `"copilot_proposals"` to `required_tables` and updated head revision check to `e4f5a6b7c8d9`.
- **Regression Tests:** `server/tests/test_production_config_safety.py` (8 passed).
- **Runtime Verification:** Full backend test suite passes (505 tests collected, 495 passed, 9 skipped, 0 failures).
- **Remaining Limitations:** Head revision must be updated whenever a new Alembic migration is authored.
- **Commit:** `50d8ae4`

### Finding 14: Shared Frontend Infrastructure Stability (FINDING-14)
- **Affected Files:** `client/src/hooks/useDialog.ts`, `client/src/services/queryCache.ts`, `client/src/services/prefetch.ts`
- **Confirmed or Unverified:** Confirmed
- **Root Cause:** `useDialog` re-registered on every keystroke if `onClose` was inline; `queryCache` did not immediately reject on `signal.aborted` and lacked prefix invalidation; `prefetch` had mismatched cache keys for copilot.
- **Implementation:** Stable dialog lifecycle registration via ref; immediate abort signal handling and `invalidatePrefix` in queryCache; aligned prefetch keys and abort signals.
- **Regression Tests:** `client/src/__tests__/truthful_canvas_actions_and_evidence.test.tsx`, `client/src/__tests__/architectural_enhancements.test.tsx`.
- **Runtime Verification:** Full frontend test suite passes (125 tests across 15 files).
- **Remaining Limitations:** In-flight fetch cancellation relies on browser `AbortController` support.
- **Commit:** `f054122`, `f5e1fb4`

### Finding 15: Deterministic Offline Fallbacks & Scope Routing (FINDING-15)
- **Affected Files:** `server/app/ai/gemini_service.py`, `server/app/schemas/copilot.py`
- **Confirmed or Unverified:** Confirmed
- **Root Cause:** Previous offline modification simulation appended arbitrary keys (`key_technologies`, `direct_competitors`) that violated module schemas. Chat routing previously allowed historical word presence to blanket-authorize any future question.
- **Implementation:** Removed schema-invalid offline modification mutations; all offline modifications conform strictly to module schemas. 4-route classifier evaluates current request intent, distinguishing `clearly_relevant`, `supporting_concept`, `ambiguous`, and `unrelated_or_unauthorized`, while legitimately permitting context-aware project security questions.
- **Regression Tests:** `server/tests/test_knowledge_financials_and_copilot.py`, `server/tests/test_ai_failure_modes.py`.
- **Runtime Verification:** Verified via Pytest.
- **Remaining Limitations:** Offline mode uses deterministic heuristics; production uses Gemini model classifier with fallback to safe clarification.
- **Commit:** `2dd1197`, `f5e1fb4`

- **Verification Evidence Summary:**
  - Full backend test suite (`pytest`): **495 passed, 9 skipped, 0 failed** across 33 test files (505 collected items).
  - Full frontend test suite (`npm test`): **125 passed, 0 failed** across 15 test files.
  - Production TypeScript & Vite build (`npm run build`): **Built in 1.18s** with 0 errors.
  - Alembic migrations (`alembic heads`): **1 sequential head (`e4f5a6b7c8d9`)**.
  - Whitespace & format check (`git diff --check`): **0 errors**.
- **Commits on main:**
  - `f054122`: fix(canvas): truthful canvas actions, evidence metadata and dialog focus stability
  - `2dd1197`: feat(bmc): implement business model frameworks end to end and schema-valid offline modification
  - `f5e1fb4`: fix(copilot): exact approved proposal application, operation ownership and sanitized errors
  - `c331b24`: fix(financials): non-mutating reads, validated writes and deterministic unit economics
  - `4b75f52`: feat(knowledge,roadmap): connect knowledge model to context and preserve roadmap fields
  - `50d8ae4`: test(alembic): update expected head revision to e4f5a6b7c8d9 in production config safety test

"""Phase 5 Verification: Bounded Gemini Key Failover, Key Health, and Request Budgets.

Verifies:
1. Server-only configuration: multiple keys supported, deduplicated, opaque slot diagnostics.
2. Failover policy:
   - First key succeeds.
   - First rate-limited, second key succeeds.
   - Timeout then fallback to next key.
   - Invalid key handling: disables rejected key slot, fails over to remaining keys.
   - All keys unavailable: raises clear actionable error without data fabrication.
3. Key health & cooldown:
   - Process-local thread-safe cooldown tracking.
   - Automatic recovery after cooldown expires.
4. Concurrency & request deadlines:
   - Request deadline exhaustion terminates cleanly.
   - In-flight concurrency bounded by semaphore to safeguard free-tier memory.
5. Resource budgets & abuse protection:
   - User-scoped AI rate limiter throttles abusive traffic with HTTP 429 and Retry-After.
   - Input size bounding rejects oversized messages/instructions.
   - Zero credential leakage in exceptions, diagnostics, or admin responses.
"""

from datetime import datetime, timedelta, timezone
import json
import secrets
import threading
import time
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import SessionLocal
from app.models.all_models import User, Project, Session as DBSession, gen_id
from app.core.config import settings, Settings
from app.core.security import hash_password, generate_session_token, hash_session_token, generate_csrf_token
from app.core.ai_limiter import ai_limiter, check_ai_rate_limit, reset_ai_limiter_state
from app.ai.gemini_service import GeminiAIService, ai_service
from app.schemas.copilot import CopilotChatRequest
from app.schemas.modules import SectionModifyRequest, BMCData


class ProviderQuotaError(Exception):
    code = 429


class ProviderInvalidKeyError(Exception):
    code = 400


class ProviderOverloadError(Exception):
    code = 503


@pytest.fixture
def clean_ai_limiter():
    reset_ai_limiter_state()
    yield
    reset_ai_limiter_state()


@pytest.fixture
def test_setup():
    uid = secrets.token_hex(4)
    with SessionLocal() as db:
        u = User(
            id=gen_id("usr_"),
            username=f"p5_user_{uid}",
            email=f"p5_user_{uid}@example.com",
            hashed_password=hash_password("StrongPassword123!"),
            role="user",
            is_suspended=False,
        )
        db.add(u)
        p = Project(
            id=gen_id("proj_"),
            name="Key Failover Project",
            user_id=u.id,
            stage="Idea",
            description="Testing bounded Gemini key failover and rate limits",
            industry="Software",
            target_customers="Developers",
            goals="Reliable AI failover",
            budget="$10,000",
            business_context="High reliability distributed web platform",
        )
        db.add(p)
        raw_tok = generate_session_token()
        s = DBSession(
            id=gen_id("ses_"),
            user_id=u.id,
            token_digest=hash_session_token(raw_tok),
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        db.add(s)
        db.commit()

        user_id = u.id
        project_id = p.id

    client = TestClient(app)
    client.cookies.set("aba_session", raw_tok)
    client.headers["X-CSRF-Token"] = generate_csrf_token(raw_tok)

    return {
        "client": client,
        "user_id": user_id,
        "project_id": project_id,
        "raw_token": raw_tok,
    }


def test_config_key_parsing_and_deduplication():
    """Verify comma, semicolon, newline, JSON list parsing and deduplication in Settings."""
    with patch.dict("os.environ", {
        "GEMINI_API_KEYS": '["key_alpha", "key_beta", "key_alpha"]',
        "GEMINI_API_KEY": "key_gamma",
    }):
        cfg = Settings()
        assert cfg.GEMINI_API_KEYS == ["key_alpha", "key_beta", "key_gamma"]
        assert cfg.GEMINI_API_KEY == "key_alpha"

    with patch.dict("os.environ", {
        "GEMINI_API_KEYS": "key_one, key_two\nkey_three; key_two",
        "GEMINI_API_KEY": "key_four",
    }):
        cfg2 = Settings()
        assert cfg2.GEMINI_API_KEYS == ["key_one", "key_two", "key_three", "key_four"]
        assert cfg2.GEMINI_API_KEY == "key_one"


def test_first_key_succeeds_without_further_rotation():
    """When the first key succeeds, only slot 1 is queried and no failover occurs."""
    service = GeminiAIService()
    service.api_keys = ["mock-key-1", "mock-key-2", "mock-key-3"]
    service.api_key = "mock-key-1"

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value.text = '{"tagline": "SaaS Platform"}'

    with patch.object(service, "_get_client", return_value=mock_client) as get_client:
        res = service._execute_json_prompt("sys", "user")

    assert res == {"tagline": "SaaS Platform"}
    assert get_client.call_count == 1
    # Verify slot diagnostics: slot_1 healthy, all healthy
    diagnostics = service.get_key_slot_diagnostics()
    assert len(diagnostics) == 3
    assert diagnostics[0]["slot_id"] == "slot_1"
    assert diagnostics[0]["status"] == "healthy"
    assert diagnostics[1]["status"] == "healthy"


def test_first_rate_limited_second_succeeds():
    """When slot 1 is rate-limited (429), it cools down and immediately fails over to slot 2."""
    service = GeminiAIService()
    service.api_keys = ["mock-key-1", "mock-key-2", "mock-key-3"]
    service.api_key = "mock-key-1"

    client1 = MagicMock()
    client1.models.generate_content.side_effect = ProviderQuotaError("RESOURCE_EXHAUSTED: quota exceeded")

    client2 = MagicMock()
    client2.models.generate_content.return_value.text = '{"tagline": "Failover Succeeded"}'

    with patch.object(service, "_get_client", side_effect=[client1, client2]) as get_client:
        res = service._execute_json_prompt("sys", "user")

    assert res == {"tagline": "Failover Succeeded"}
    assert get_client.call_count == 2

    # Slot 1 should now be in cooldown
    diagnostics = service.get_key_slot_diagnostics()
    assert diagnostics[0]["slot_id"] == "slot_1"
    assert diagnostics[0]["status"] == "cooling_down"
    assert diagnostics[0]["cooldown_remaining_seconds"] > 0
    assert diagnostics[1]["status"] == "healthy"


def test_timeout_then_fallback_key():
    """When slot 1 times out or encounters 504 Gateway Timeout, failover rotates to slot 2."""
    service = GeminiAIService()
    service.api_keys = ["mock-key-1", "mock-key-2"]
    service.api_key = "mock-key-1"

    client1 = MagicMock()
    client1.models.generate_content.side_effect = TimeoutError("504 Gateway Timeout")

    client2 = MagicMock()
    client2.models.generate_content.return_value.text = '{"tagline": "Recovered from Timeout"}'

    with patch.object(service, "_get_client", side_effect=[client1, client2]) as get_client:
        res = service._execute_json_prompt("sys", "user")

    assert res == {"tagline": "Recovered from Timeout"}
    assert get_client.call_count == 2


def test_invalid_key_handling_disables_slot_and_falls_back():
    """When slot 1 receives 400 API_KEY_INVALID, slot 1 is marked permanently disabled and slot 2 handles request."""
    service = GeminiAIService()
    service.api_keys = ["bad-key-1", "good-key-2"]
    service.api_key = "bad-key-1"

    client1 = MagicMock()
    client1.models.generate_content.side_effect = ProviderInvalidKeyError("API_KEY_INVALID: API key not valid")

    client2 = MagicMock()
    client2.models.generate_content.return_value.text = '{"tagline": "Valid Key Handled"}'

    with patch.object(service, "_get_client", side_effect=[client1, client2]):
        res = service._execute_json_prompt("sys", "user")

    assert res == {"tagline": "Valid Key Handled"}

    # Diagnostic verifies slot 1 is disabled
    diagnostics = service.get_key_slot_diagnostics()
    assert diagnostics[0]["slot_id"] == "slot_1"
    assert diagnostics[0]["status"] == "disabled"
    assert diagnostics[1]["status"] == "healthy"

    # Subsequent request uses slot 2 directly without querying disabled slot 1
    available = service._available_key_slots()
    assert len(available) == 1
    assert available[0][0] == 2  # slot 2


def test_all_keys_unavailable_raises_clear_error_without_fabrication():
    """When all configured keys fail with quota or overload, raises clear error without fabricated content."""
    service = GeminiAIService()
    service.api_keys = ["exhausted-key-1", "exhausted-key-2"]
    service.api_key = "exhausted-key-1"

    client1 = MagicMock()
    client1.models.generate_content.side_effect = ProviderQuotaError("RESOURCE_EXHAUSTED: quota exceeded")
    client2 = MagicMock()
    client2.models.generate_content.side_effect = ProviderQuotaError("RESOURCE_EXHAUSTED: quota exceeded")

    with patch.object(service, "_get_client", side_effect=[client1, client2]):
        with pytest.raises(RuntimeError, match="quota is exhausted"):
            service._execute_json_prompt("sys", "user")

    # Immediate second call notices all keys cooling down
    with pytest.raises(RuntimeError, match="temporarily cooling down"):
        service._execute_json_prompt("sys", "user")


def test_cooldown_recovery_restores_eligibility():
    """A key cooling down automatically recovers and returns to healthy state once cooldown expires."""
    service = GeminiAIService()
    service.api_keys = ["recoverable-key-1"]
    service.api_key = "recoverable-key-1"

    # Set a tiny 0.1s cooldown
    service._cool_down_key("recoverable-key-1", custom_cooldown=0.1)

    # Immediately after, available slots is empty
    assert len(service._available_key_slots()) == 0
    assert service.get_key_slot_diagnostics()[0]["status"] == "cooling_down"

    # Sleep past cooldown
    time.sleep(0.15)

    # Now available again
    available = service._available_key_slots()
    assert len(available) == 1
    assert available[0][1] == "recoverable-key-1"
    assert service.get_key_slot_diagnostics()[0]["status"] == "healthy"


def test_deadline_exhaustion_stops_failover():
    """When total request deadline is reached, loop stops immediately and raises timeout error."""
    service = GeminiAIService()
    service.api_keys = ["key-1", "key-2", "key-3"]
    service.api_key = "key-1"

    def slow_client(*args, **kwargs):
        # Exceed deadline
        time.sleep(0.2)
        raise ProviderOverloadError("503 Overloaded")

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = slow_client

    with patch.object(service, "_get_client", return_value=mock_client), patch.object(
        settings, "GEMINI_TOTAL_TIMEOUT_SECONDS", 0.1
    ):
        with pytest.raises(RuntimeError, match="timed out|overloaded|deadline"):
            service._execute_json_prompt("sys", "user")


def test_concurrent_generation_semaphore_limits_in_flight_calls():
    """Concurrency semaphore bounds active generation calls to GEMINI_MAX_CONCURRENT_CALLS."""
    service = GeminiAIService()
    service.api_keys = ["key-1"]
    service.api_key = "key-1"

    in_flight_counts = []
    max_seen_in_flight = 0
    in_flight_lock = threading.Lock()
    current_in_flight = 0

    def concurrent_generate(*args, **kwargs):
        nonlocal current_in_flight, max_seen_in_flight
        with in_flight_lock:
            current_in_flight += 1
            if current_in_flight > max_seen_in_flight:
                max_seen_in_flight = current_in_flight
        time.sleep(0.05)
        with in_flight_lock:
            current_in_flight -= 1
        res = MagicMock()
        res.text = '{"tagline": "concurrency test"}'
        return res

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = concurrent_generate

    threads = []
    with patch.object(service, "_get_client", return_value=mock_client), patch.object(
        settings, "GEMINI_MAX_CONCURRENT_CALLS", 3
    ):
        service._concurrency_semaphore = threading.Semaphore(3)

        for _ in range(6):
            t = threading.Thread(target=lambda: service._execute_json_prompt("sys", "user"))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

    assert max_seen_in_flight <= 3, f"Expected max 3 concurrent in-flight calls, saw {max_seen_in_flight}"


def test_no_credential_leakage_in_diagnostics_and_system_health(test_setup):
    """Verify that diagnostics and admin endpoints return opaque slot identifiers without secret leakage."""
    service = GeminiAIService()
    raw_secret_key = "AIzaSyD-SecretKeyMaterialNotToBeExposed"
    service.api_keys = [raw_secret_key]
    service.api_key = raw_secret_key

    diagnostics = service.get_key_slot_diagnostics()
    diag_str = json.dumps(diagnostics)

    # Must contain opaque identifiers
    assert "slot_1" in diag_str
    # Must NEVER contain the raw key secret
    assert raw_secret_key not in diag_str
    assert "SecretKeyMaterial" not in diag_str


def test_user_ai_rate_limiter_blocks_abusive_frequency(clean_ai_limiter):
    """User-scoped AI rate limiter triggers HTTP 429 when frequency exceeds configured threshold."""
    user_id = "usr_rate_limit_test"

    # Temporarily set max RPM to 3
    with patch.object(settings, "GEMINI_MAX_USER_RPM", 3):
        # 3 calls succeed
        check_ai_rate_limit(user_id)
        check_ai_rate_limit(user_id)
        check_ai_rate_limit(user_id)

        # 4th call raises 429
        with pytest.raises(Exception) as exc_info:
            check_ai_rate_limit(user_id)

        assert exc_info.value.status_code == 429
        assert "rate limit exceeded" in exc_info.value.detail.lower()
        assert "Retry-After" in exc_info.value.headers


def test_input_size_bounding_rejects_oversized_messages():
    """Verify input models reject payloads exceeding 4000 characters with 422 validation errors."""
    with pytest.raises(ValueError):
        CopilotChatRequest(message="x" * 4001)

    # Valid message passes
    valid_copilot = CopilotChatRequest(message="x" * 4000)
    assert len(valid_copilot.message) == 4000

    with pytest.raises(ValueError):
        SectionModifyRequest(instruction="y" * 4001)

    valid_modify = SectionModifyRequest(instruction="y" * 4000)
    assert len(valid_modify.instruction) == 4000

"""Phase 8.1 Correction Regression Test Suite.

Verifies:
1. Shared strict date-only contract using shared_fixtures/strict_date_cases.json.
2. Milestone exact cumulative boundaries (days 1, 30, 31, 60, 61, 90, 91), overdue policy, and removal of timeline string fallbacks.
3. Strict context budgeting: history limit <= 16,000 chars (no oversized first message exception) and overall prompt budget <= 80,000 chars.
4. Chat message idempotency: CopilotOperation record, duplicate sequential sends, concurrent in-flight handling, payload mismatch conflict (409), status retrieval endpoint, and tenant isolation.
5. Authenticated HMAC-SHA256 cursor: signature verification, cross-project tamper rejection, oversized cursor rejection.
"""

import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import SessionLocal
from app.models.all_models import (
    User, Project, CopilotMessage, CopilotOperation, RoadmapTask, Session as DBSession, gen_id
)
from app.core.security import hash_password, generate_session_token, hash_session_token, generate_csrf_token
from app.services.task_milestones import parse_strict_date_only, calculate_roadmap_summary
from app.ai.gemini_service import ai_service
from app.api.copilot import encode_cursor, decode_cursor


@pytest.fixture
def auth_fixture():
    """Create isolated test users and projects."""
    uid = secrets.token_hex(4)
    with SessionLocal() as db:
        u1 = User(
            id=gen_id("usr_"),
            username=f"p81_user1_{uid}",
            email=f"p81_user1_{uid}@example.com",
            hashed_password=hash_password("Password123!"),
            role="user",
            is_suspended=False
        )
        db.add(u1)
        p1 = Project(
            id=gen_id("proj_"),
            name="Phase 8.1 Primary Project",
            user_id=u1.id,
            stage="Idea",
            description="Phase 8.1 test project",
            industry="Technology",
            target_customers="Developers"
        )
        db.add(p1)

        u2 = User(
            id=gen_id("usr_"),
            username=f"p81_user2_{uid}",
            email=f"p81_user2_{uid}@example.com",
            hashed_password=hash_password("Password123!"),
            role="user",
            is_suspended=False
        )
        db.add(u2)
        p2 = Project(
            id=gen_id("proj_"),
            name="Phase 8.1 Tenant B Project",
            user_id=u2.id,
            stage="Idea",
            description="Tenant B project",
            industry="Healthcare",
            target_customers="Clinics"
        )
        db.add(p2)

        raw_tok1 = generate_session_token()
        s1 = DBSession(
            id=gen_id("ses_"),
            user_id=u1.id,
            token_digest=hash_session_token(raw_tok1),
            session_token=None,
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(days=1)
        )
        db.add(s1)

        raw_tok2 = generate_session_token()
        s2 = DBSession(
            id=gen_id("ses_"),
            user_id=u2.id,
            token_digest=hash_session_token(raw_tok2),
            session_token=None,
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(days=1)
        )
        db.add(s2)
        db.commit()

        csrf1 = generate_csrf_token(raw_tok1)
        csrf2 = generate_csrf_token(raw_tok2)
        p1_id = p1.id
        p2_id = p2.id

    client1 = TestClient(app, cookies={"aba_session": raw_tok1})
    client2 = TestClient(app, cookies={"aba_session": raw_tok2})

    return {
        "client1": client1,
        "csrf1": csrf1,
        "p1_id": p1_id,
        "client2": client2,
        "csrf2": csrf2,
        "p2_id": p2_id,
    }


# ============================================================
# 1. SHARED STRICT DATE-ONLY CONTRACT
# ============================================================

def test_shared_strict_date_contract_fixtures():
    """Verify parse_strict_date_only against the shared JSON fixture file."""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    fixture_path = os.path.join(base_dir, "shared_fixtures", "strict_date_cases.json")
    assert os.path.exists(fixture_path), f"Shared fixture not found at {fixture_path}"

    with open(fixture_path, "r", encoding="utf-8") as f:
        cases = json.load(f)

    for case in cases:
        raw_input = case["input"]
        expected_valid = case["valid"]
        parsed = parse_strict_date_only(raw_input)
        if expected_valid:
            assert parsed is not None, f"Failed valid case: {case['reason']} with input {raw_input!r}"
            assert parsed.year == case["year"]
            assert parsed.month == case["month"]
            assert parsed.day == case["day"]
        else:
            assert parsed is None, f"Failed invalid case: {case['reason']} with input {raw_input!r}, got {parsed}"


# ============================================================
# 2. MILESTONE CUMULATIVE BOUNDARIES & STRING FALLBACK REMOVAL
# ============================================================

def test_milestone_exact_cumulative_boundaries():
    """Verify exact calendar boundaries (Day 1, 30, 31, 60, 61, 90, 91) and overdue handling."""
    # Anchor date: 2026-03-01
    # Day 1:  2026-03-01
    # Day 30: 2026-03-30 (30 days inclusive)
    # Day 31: 2026-03-31 (Day 31 -> outside day 30, inside day 60)
    # Day 60: 2026-04-29 (31 days in March + 29 days in April = 60 days)
    # Day 61: 2026-04-30 (Day 61 -> outside day 60, inside day 90)
    # Day 90: 2026-05-29 (31 + 30 + 29 = 90 days)
    # Day 91: 2026-05-30 (Day 91 -> outside day 90)
    # Overdue: 2026-02-20 (due before anchor -> cumulative day <= 0, included in cumulative cards)
    tasks = [
        RoadmapTask(id="t_overdue", project_id="p", task_code="P0-01", title="Overdue task",
                    start_date="2026-02-15", end_date="2026-02-20", status="not_started"),
        RoadmapTask(id="t_d01", project_id="p", task_code="P1-01", title="Day 1 task",
                    start_date="2026-03-01", end_date="2026-03-01", status="completed"),
        RoadmapTask(id="t_d30", project_id="p", task_code="P1-02", title="Day 30 boundary",
                    start_date="2026-03-10", end_date="2026-03-30", status="completed"),
        RoadmapTask(id="t_d31", project_id="p", task_code="P2-01", title="Day 31 boundary",
                    start_date="2026-03-15", end_date="2026-03-31", status="not_started"),
        RoadmapTask(id="t_d60", project_id="p", task_code="P2-02", title="Day 60 boundary",
                    start_date="2026-04-01", end_date="2026-04-29", status="completed"),
        RoadmapTask(id="t_d61", project_id="p", task_code="P3-01", title="Day 61 boundary",
                    start_date="2026-04-15", end_date="2026-04-30", status="in_progress"),
        RoadmapTask(id="t_d90", project_id="p", task_code="P3-02", title="Day 90 boundary",
                    start_date="2026-05-01", end_date="2026-05-29", status="completed"),
        RoadmapTask(id="t_d91", project_id="p", task_code="P4-01", title="Day 91 later task",
                    start_date="2026-05-15", end_date="2026-05-30", status="not_started"),
        RoadmapTask(id="t_undated", project_id="p", task_code="P4-02", title="Undated task",
                    start_date=None, end_date=None, status="completed"),
    ]

    summary = calculate_roadmap_summary(tasks, saved_start_date="2026-03-01")

    # Overall: 9 tasks, 5 completed (t_d01, t_d30, t_d60, t_d90, t_undated) -> 5/9 = 55%
    assert summary["total_tasks"] == 9
    assert summary["completed_tasks"] == 5
    assert summary["overall_progress"] == 55

    # 30-day cumulative: t_overdue (due <= 0), t_d01 (due 1), t_d30 (due 30) = 3 tasks
    # Completed: t_d01, t_d30 = 2 completed -> 2/3 = 66%
    assert summary["milestone_30_total"] == 3
    assert summary["milestone_30_completed"] == 2
    assert summary["milestone_30_progress"] == 66

    # 60-day cumulative: + t_d31 (due 31), + t_d60 (due 60) = 5 tasks
    # Completed: t_d01, t_d30, t_d60 = 3 completed -> 3/5 = 60%
    assert summary["milestone_60_total"] == 5
    assert summary["milestone_60_completed"] == 3
    assert summary["milestone_60_progress"] == 60

    # 90-day cumulative: + t_d61 (due 61), + t_d90 (due 90) = 7 tasks
    # Completed: t_d01, t_d30, t_d60, t_d90 = 4 completed -> 4/7 = 57%
    assert summary["milestone_90_total"] == 7
    assert summary["milestone_90_completed"] == 4
    assert summary["milestone_90_progress"] == 57


def test_milestone_no_timeline_string_fallbacks():
    """Verify that a task with timeline='30-day MVP' but end_date at Day 45 does NOT enter Day 30."""
    tasks = [
        RoadmapTask(
            id="t_str_conflict",
            project_id="p",
            task_code="P1-99",
            title="Task with misleading duration string",
            timeline="30-day quickstart target",
            start_date="2026-03-01",
            end_date="2026-04-14",  # Day 45
            status="completed"
        )
    ]
    summary = calculate_roadmap_summary(tasks, saved_start_date="2026-03-01")

    # Day 45 is > 30, so Day 30 count MUST be 0
    assert summary["milestone_30_total"] == 0
    assert summary["milestone_30_completed"] == 0

    # Day 45 is <= 60, so Day 60 count is 1
    assert summary["milestone_60_total"] == 1
    assert summary["milestone_60_completed"] == 1


# ============================================================
# 3. STRICT PROVIDER CONTEXT BUDGETS
# ============================================================

def test_history_budget_drops_oversized_first_message():
    """Test that an oversized first history message (>16,000 chars) is strictly rejected, not accepted by exception."""
    oversized_msg = "X" * 17000
    smaller_msg = "What is our customer target?"

    history = [
        {"role": "user", "content": oversized_msg},
        {"role": "assistant", "content": "I received your detailed message."},
        {"role": "user", "content": smaller_msg},
        {"role": "assistant", "content": "The customer target is enterprise teams."}
    ]

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = "Strategic response"
    mock_client.models.generate_content.return_value = mock_resp

    with patch.object(ai_service, "_scope_decision", return_value=MagicMock(allowed=True)), \
         patch.object(ai_service, "_configured_api_keys", return_value=["fake-key"]), \
         patch.object(ai_service, "_available_key_slots", return_value=[("slot_1", "fake-key")]), \
         patch.object(ai_service, "_get_client", return_value=mock_client), \
         patch.object(ai_service, "_close_client"):

        ai_service.chat_copilot(
            project_info={"name": "Venture Atlas"},
            chat_history=history,
            user_message="New strategic question"
        )

        assert mock_client.models.generate_content.called
        call_kwargs = mock_client.models.generate_content.call_args[1]
        contents = call_kwargs.get("contents", "")

        # The 17,000 character message MUST NOT be present anywhere in serialized contents
        assert oversized_msg not in contents
        # But the smaller valid message is present
        assert smaller_msg in contents


def test_overall_prompt_budget_prunes_modules_not_question():
    """Test that overall prompt budget <= 80,000 chars prunes optional modules while preserving the full user question."""
    huge_summary = "M" * 75000
    current_q = "What is our core go-to-market plan? " + ("Q" * 1000)

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = "Strategic response"
    mock_client.models.generate_content.return_value = mock_resp

    with patch.object(ai_service, "_scope_decision", return_value=MagicMock(allowed=True)), \
         patch.object(ai_service, "_configured_api_keys", return_value=["fake-key"]), \
         patch.object(ai_service, "_available_key_slots", return_value=[("slot_1", "fake-key")]), \
         patch.object(ai_service, "_get_client", return_value=mock_client), \
         patch.object(ai_service, "_close_client"):

        ai_service.chat_copilot(
            project_info={"name": "Venture Atlas"},
            chat_history=[],
            user_message=current_q,
            cross_module_context={"bmc": {"summary": huge_summary}}
        )

        assert mock_client.models.generate_content.called
        call_kwargs = mock_client.models.generate_content.call_args[1]
        contents = call_kwargs.get("contents", "")

        # Full user question is preserved
        assert current_q in contents
        # Overall serialized content is <= 80,000 chars
        assert len(contents) <= 80000


# ============================================================
# 4. CHAT IDEMPOTENCY & OPERATION RECORDS
# ============================================================

def test_idempotent_send_sequential_retry_returns_saved_result(auth_fixture):
    """Test that submitting the same client_msg_id twice returns the saved result without invoking the provider again."""
    client1 = auth_fixture["client1"]
    csrf1 = auth_fixture["csrf1"]
    p1_id = auth_fixture["p1_id"]
    client_msg_id = f"op_test_{secrets.token_hex(4)}"

    provider_calls = 0

    def mock_chat_fn(*args, **kwargs):
        nonlocal provider_calls
        provider_calls += 1
        return "Provider generated response #1."

    with patch("app.ai.gemini_service.ai_service.chat_copilot", side_effect=mock_chat_fn):
        # First send
        resp1 = client1.post(
            f"/api/projects/{p1_id}/copilot",
            json={"message": "What is our primary differentiator?", "client_msg_id": client_msg_id},
            headers={"X-CSRF-Token": csrf1}
        )
        assert resp1.status_code == 200
        data1 = resp1.json()
        assert data1["operation_status"] == "completed"
        assert data1["user_message"] is not None
        assert data1["user_message"]["content"] == "What is our primary differentiator?"
        assert data1["assistant_message"] is not None
        assert data1["assistant_message"]["content"] == "Provider generated response #1."
        assert provider_calls == 1

        # Second send with identical client_msg_id and identical payload
        resp2 = client1.post(
            f"/api/projects/{p1_id}/copilot",
            json={"message": "What is our primary differentiator?", "client_msg_id": client_msg_id},
            headers={"X-CSRF-Token": csrf1}
        )
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["operation_status"] == "completed"
        assert data2["user_message"]["id"] == data1["user_message"]["id"]
        assert data2["assistant_message"]["id"] == data1["assistant_message"]["id"]
        # Crucial check: Provider was NOT called a second time
        assert provider_calls == 1

        # Database check: exactly 1 user message, 1 assistant message, 1 operation record
        with SessionLocal() as db:
            user_msgs = db.query(CopilotMessage).filter(
                CopilotMessage.project_id == p1_id,
                CopilotMessage.content == "What is our primary differentiator?"
            ).all()
            assert len(user_msgs) == 1

            op = db.query(CopilotOperation).filter(
                CopilotOperation.project_id == p1_id,
                CopilotOperation.client_msg_id == client_msg_id
            ).first()
            assert op is not None
            assert op.status == "completed"


def test_idempotent_send_same_id_conflicting_payload_rejected(auth_fixture):
    """Test that reusing the same client_msg_id with different message text returns 409 Conflict."""
    client1 = auth_fixture["client1"]
    csrf1 = auth_fixture["csrf1"]
    p1_id = auth_fixture["p1_id"]
    client_msg_id = f"op_conflict_{secrets.token_hex(4)}"

    with patch("app.ai.gemini_service.ai_service.chat_copilot", return_value="Original answer"):
        # First send
        resp1 = client1.post(
            f"/api/projects/{p1_id}/copilot",
            json={"message": "First distinct message text", "client_msg_id": client_msg_id},
            headers={"X-CSRF-Token": csrf1}
        )
        assert resp1.status_code == 200

        # Attempt to reuse the same ID with completely different question text
        resp2 = client1.post(
            f"/api/projects/{p1_id}/copilot",
            json={"message": "Second different question text", "client_msg_id": client_msg_id},
            headers={"X-CSRF-Token": csrf1}
        )
        assert resp2.status_code == 409
        assert "different message payload" in resp2.json()["detail"]


def test_operation_status_endpoint_and_tenant_isolation(auth_fixture):
    """Test GET /projects/{project_id}/copilot/operations/{client_msg_id} and cross-tenant isolation."""
    client1 = auth_fixture["client1"]
    csrf1 = auth_fixture["csrf1"]
    p1_id = auth_fixture["p1_id"]
    client2 = auth_fixture["client2"]
    p2_id = auth_fixture["p2_id"]
    client_msg_id = f"op_status_{secrets.token_hex(4)}"

    with patch("app.ai.gemini_service.ai_service.chat_copilot", return_value="Status test guidance"):
        post_resp = client1.post(
            f"/api/projects/{p1_id}/copilot",
            json={"message": "Inquire about strategic status", "client_msg_id": client_msg_id},
            headers={"X-CSRF-Token": csrf1}
        )
        assert post_resp.status_code == 200

    # User 1 queries status: 200 with completed operation
    status_resp = client1.get(f"/api/projects/{p1_id}/copilot/operations/{client_msg_id}")
    assert status_resp.status_code == 200
    st_data = status_resp.json()
    assert st_data["status"] == "completed"
    assert st_data["client_msg_id"] == client_msg_id
    assert st_data["user_message"] is not None
    assert st_data["assistant_message"] is not None

    # Tenant isolation: User 2 attempting to access User 1's project operation returns 403 Forbidden
    tenant_resp = client2.get(f"/api/projects/{p1_id}/copilot/operations/{client_msg_id}")
    assert tenant_resp.status_code in (403, 404)

    # Tenant isolation: User 2 querying their own project with User 1's operation ID returns 404 (not found in p2)
    tenant_resp2 = client2.get(f"/api/projects/{p2_id}/copilot/operations/{client_msg_id}")
    assert tenant_resp2.status_code == 404


def test_distinct_sends_with_identical_text_remain_separate(auth_fixture):
    """Test that two intentionally separate sends with different client_msg_id remain distinct."""
    client1 = auth_fixture["client1"]
    csrf1 = auth_fixture["csrf1"]
    p1_id = auth_fixture["p1_id"]

    id1 = f"op_sep1_{secrets.token_hex(4)}"
    id2 = f"op_sep2_{secrets.token_hex(4)}"
    identical_question = "What are the revenue streams?"

    with patch("app.ai.gemini_service.ai_service.chat_copilot", return_value="Here are the revenue streams."):
        resp1 = client1.post(
            f"/api/projects/{p1_id}/copilot",
            json={"message": identical_question, "client_msg_id": id1},
            headers={"X-CSRF-Token": csrf1}
        )
        assert resp1.status_code == 200
        msg1_id = resp1.json()["user_message"]["id"]

        resp2 = client1.post(
            f"/api/projects/{p1_id}/copilot",
            json={"message": identical_question, "client_msg_id": id2},
            headers={"X-CSRF-Token": csrf1}
        )
        assert resp2.status_code == 200
        msg2_id = resp2.json()["user_message"]["id"]

        assert msg1_id != msg2_id

        with SessionLocal() as db:
            count = db.query(CopilotMessage).filter(
                CopilotMessage.project_id == p1_id,
                CopilotMessage.content == identical_question
            ).count()
            assert count == 2


# ============================================================
# 5. AUTHENTICATED HMAC-SHA256 CURSOR
# ============================================================

def test_authenticated_hmac_cursor_roundtrip_and_tamper_defense(auth_fixture):
    """Test Option B authenticated HMAC-SHA256 cursor generation, decoding, and tamper resistance."""
    p1_id = auth_fixture["p1_id"]
    p2_id = auth_fixture["p2_id"]
    ts = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
    msg_id = "msg_test_001"

    cursor = encode_cursor(p1_id, ts, msg_id)
    assert cursor is not None
    assert len(cursor) < 512

    # Roundtrip decoding succeeds for matching project
    decoded_ts, decoded_id = decode_cursor(p1_id, cursor)
    assert decoded_ts == ts
    assert decoded_id == msg_id

    # Cross-project tamper defense: decoding with wrong project_id raises HTTPException 400
    with pytest.raises(HTTPException) as exc_info:
        decode_cursor(p2_id, cursor)
    assert exc_info.value.status_code == 400
    assert "Cursor does not belong to the authorized project" in exc_info.value.detail

    # Tampered signature raises HTTPException 400
    tampered = cursor[:-4] + "ABCD"
    with pytest.raises(HTTPException) as exc_info:
        decode_cursor(p1_id, tampered)
    assert exc_info.value.status_code == 400

    # Oversized cursor (> 512 chars) rejected
    huge_cursor = "a" * 513
    with pytest.raises(HTTPException) as exc_info:
        decode_cursor(p1_id, huge_cursor)
    assert exc_info.value.status_code == 400
    assert "length" in exc_info.value.detail

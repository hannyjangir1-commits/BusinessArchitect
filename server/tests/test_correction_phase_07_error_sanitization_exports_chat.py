"""Phase 7 Verification: Error Sanitization, Exports, and Chat History.

Covers:
1. Standards-compatible Content-Disposition headers (RFC 5987 / RFC 6266) with safe ASCII fallback for Unicode titles.
2. HTTP header injection defense (CR/LF control character neutralization).
3. Optional export dependency graceful handling (controlled 503 instead of 500 / crash).
4. Chat history bounded retrieval, pagination (limit, offset, order), and boundaries.
5. Provider context bounding (prompt context bounded independently of stored DB history).
6. Cross-user tenant isolation across copilot history, chat messaging, and document exports.
7. Error sanitization ensuring synthetic sensitive markers (passwords, connection strings, secrets) never leak in client responses, logs, or telemetry.
8. Request correlation IDs (X-Request-ID and body request_id) attached to error responses.
"""

from datetime import datetime, timedelta, timezone
import secrets
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import SessionLocal
from app.models.all_models import (
    User, Project, ModuleContent, ModuleVersion, RoadmapTask,
    CopilotMessage, AuditLog, AIOperation, Session as DBSession, gen_id
)
from app.core.config import settings
from app.core.security import hash_password, generate_session_token, hash_session_token, generate_csrf_token
from app.core.exports import sanitize_filename, format_content_disposition
from app.services.pdf_service import PDFService


@pytest.fixture
def auth_fixture():
    """Create isolated test users and projects."""
    uid = secrets.token_hex(4)
    with SessionLocal() as db:
        # User A
        u1 = User(
            id=gen_id("usr_"),
            username=f"p7_user1_{uid}",
            email=f"p7_user1_{uid}@example.com",
            hashed_password=hash_password("Password123!"),
            role="user",
            is_suspended=False
        )
        db.add(u1)
        p1 = Project(
            id=gen_id("proj_"),
            name="व्यापार योजना - Venture Atlas",  # Unicode Hindi title
            user_id=u1.id,
            stage="Idea / MVP",
            description="Testing RFC 5987 Unicode exports and chat pagination",
            industry="Software & AI",
            target_customers="Enterprise users"
        )
        db.add(p1)

        # Overview module for P1 so export succeeds
        m1 = ModuleContent(
            id=gen_id("mod_"),
            project_id=p1.id,
            module_type="overview",
            created_at=datetime.now(timezone.utc)
        )
        db.add(m1)
        v1 = ModuleVersion(
            id=gen_id("ver_"),
            module_content_id=m1.id,
            version_number=1,
            version_name="V1",
            data={"description": p1.description, "goals": "Enterprise validation", "stage": "Idea / MVP"},
            is_active=True,
            created_at=datetime.now(timezone.utc)
        )
        db.add(v1)
        m1.active_version_id = v1.id

        # User B (for cross-user tenant isolation tests)
        u2 = User(
            id=gen_id("usr_"),
            username=f"p7_user2_{uid}",
            email=f"p7_user2_{uid}@example.com",
            hashed_password=hash_password("Password123!"),
            role="user",
            is_suspended=False
        )
        db.add(u2)
        p2 = Project(
            id=gen_id("proj_"),
            name="User B Project",
            user_id=u2.id,
            stage="Growth",
            description="Tenant isolation check project"
        )
        db.add(p2)

        # Create session tokens
        raw_token1 = generate_session_token()
        sess1 = DBSession(
            id=gen_id("ses_"),
            user_id=u1.id,
            token_digest=hash_session_token(raw_token1),
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(days=1)
        )
        db.add(sess1)

        raw_token2 = generate_session_token()
        sess2 = DBSession(
            id=gen_id("ses_"),
            user_id=u2.id,
            token_digest=hash_session_token(raw_token2),
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(days=1)
        )
        db.add(sess2)

        db.commit()

        csrf1 = generate_csrf_token(raw_token1)
        csrf2 = generate_csrf_token(raw_token2)

        p1_id = p1.id
        p2_id = p2.id
        u1_id = u1.id
        u2_id = u2.id

    client1 = TestClient(app, cookies={settings.COOKIE_NAME: raw_token1}, headers={"X-CSRF-Token": csrf1})
    client2 = TestClient(app, cookies={settings.COOKIE_NAME: raw_token2}, headers={"X-CSRF-Token": csrf2})

    return {
        "p1_id": p1_id,
        "p2_id": p2_id,
        "u1_id": u1_id,
        "u2_id": u2_id,
        "client1": client1,
        "client2": client2,
        "raw_token1": raw_token1,
        "csrf1": csrf1,
    }


def test_sanitize_filename_and_rfc5987_formatting():
    """Unit test RFC 5987 / RFC 6266 filename sanitization and formatting."""
    # 1. ASCII name
    safe_ascii, utf8_fn = sanitize_filename("Enterprise Blueprint", fallback="blueprint")
    assert safe_ascii == "Enterprise_Blueprint.pdf"
    assert utf8_fn == "Enterprise Blueprint.pdf"

    # 2. Pure Unicode non-ASCII (Hindi)
    safe_ascii, utf8_fn = sanitize_filename("व्यापार योजना", fallback="blueprint")
    assert safe_ascii == "blueprint.pdf"
    assert utf8_fn == "व्यापार योजना.pdf"

    header = format_content_disposition("व्यापार योजना", fallback="blueprint")
    assert 'filename="blueprint.pdf"' in header
    assert "filename*=UTF-8''" in header
    # Header must be strictly ASCII-encodable (no Latin-1/Unicode header crash)
    header.encode("latin-1")

    # 3. CR/LF and control character injection neutralization
    safe_ascii, utf8_fn = sanitize_filename("Project\r\nInjected: True\n\x00Name", fallback="blueprint")
    assert "\r" not in safe_ascii and "\n" not in safe_ascii and "\x00" not in safe_ascii
    assert "\r" not in utf8_fn and "\n" not in utf8_fn and "\x00" not in utf8_fn


def test_unicode_export_filename_content_disposition(auth_fixture):
    """Test PDF exports with non-ASCII Unicode project titles produce valid RFC 5987 headers without Latin-1 errors."""
    client = auth_fixture["client1"]
    p_id = auth_fixture["p1_id"]

    # 1. Full project PDF export
    resp = client.get(f"/api/projects/{p_id}/export/pdf")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    assert resp.headers["Content-Type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF-")

    disp = resp.headers.get("Content-Disposition", "")
    assert disp.startswith("attachment; ")
    assert 'filename="' in disp
    assert "filename*=UTF-8''" in disp
    # Ensure header is strictly safe ASCII
    disp.encode("latin-1")

    # 2. Module PDF export
    resp_mod = client.get(f"/api/projects/{p_id}/export/modules/overview/pdf")
    assert resp_mod.status_code == 200
    assert resp_mod.headers["Content-Type"] == "application/pdf"
    disp_mod = resp_mod.headers.get("Content-Disposition", "")
    assert disp_mod.startswith("attachment; ")
    assert "filename*=UTF-8''" in disp_mod
    disp_mod.encode("latin-1")


def test_newline_and_header_injection_defense(auth_fixture):
    """Test that project titles containing newlines or control characters cannot perform HTTP header injection."""
    client = auth_fixture["client1"]
    p_id = auth_fixture["p1_id"]

    # Update project name to contain CR/LF header injection payload
    with SessionLocal() as db:
        proj = db.query(Project).filter(Project.id == p_id).first()
        proj.name = "Malicious Project\r\nInjected-Header: evil\r\n\r\nPayload"
        db.commit()

    resp = client.get(f"/api/projects/{p_id}/export/pdf")
    assert resp.status_code == 200

    disp = resp.headers.get("Content-Disposition", "")
    # Neither carriage returns nor newlines may exist in the header value
    assert "\r" not in disp
    assert "\n" not in disp
    # Injected-Header must not be recognized as a separate header
    assert "Injected-Header" not in resp.headers


def test_missing_export_dependency_handling(auth_fixture):
    """Test that missing optional export dependency (reportlab) returns controlled 503 instead of 500 crash."""
    client = auth_fixture["client1"]
    p_id = auth_fixture["p1_id"]

    with patch.object(PDFService, "is_available", return_value=False):
        # Full project export
        resp = client.get(f"/api/projects/{p_id}/export/pdf")
        assert resp.status_code == 503
        assert "temporarily unavailable" in resp.json()["detail"]

        # Single module export via exports router
        resp_mod = client.get(f"/api/projects/{p_id}/export/modules/overview/pdf")
        assert resp_mod.status_code == 503
        assert "temporarily unavailable" in resp_mod.json()["detail"]

        # Single module export via modules router
        resp_mod2 = client.get(f"/api/projects/{p_id}/modules/overview/export/pdf")
        assert resp_mod2.status_code == 503
        assert "temporarily unavailable" in resp_mod2.json()["detail"]


def test_chat_history_pagination_and_ordering(auth_fixture):
    """Test that copilot chat history supports pagination (limit, offset, order) with bounded queries."""
    client = auth_fixture["client1"]
    p_id = auth_fixture["p1_id"]

    # Seed 65 sequenced messages
    base_time = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    with SessionLocal() as db:
        for i in range(65):
            msg = CopilotMessage(
                id=gen_id("cmsg_"),
                project_id=p_id,
                role="user" if i % 2 == 0 else "assistant",
                content=f"Message sequence {i:03d}",
                created_at=base_time + timedelta(minutes=i)
            )
            db.add(msg)
        db.commit()

    # Default query (limit 50, offset 0, asc)
    resp = client.get(f"/api/projects/{p_id}/copilot")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 50
    assert data[0]["content"] == "Message sequence 000"
    assert data[-1]["content"] == "Message sequence 049"

    # Page 1: limit 25, offset 0
    resp_p1 = client.get(f"/api/projects/{p_id}/copilot?limit=25&offset=0")
    assert resp_p1.status_code == 200
    p1_data = resp_p1.json()
    assert len(p1_data) == 25
    assert p1_data[0]["content"] == "Message sequence 000"
    assert p1_data[-1]["content"] == "Message sequence 024"

    # Page 2: limit 25, offset 25
    resp_p2 = client.get(f"/api/projects/{p_id}/copilot?limit=25&offset=25")
    assert resp_p2.status_code == 200
    p2_data = resp_p2.json()
    assert len(p2_data) == 25
    assert p2_data[0]["content"] == "Message sequence 025"
    assert p2_data[-1]["content"] == "Message sequence 049"

    # Page 3: limit 25, offset 50 (remaining 15)
    resp_p3 = client.get(f"/api/projects/{p_id}/copilot?limit=25&offset=50")
    assert resp_p3.status_code == 200
    p3_data = resp_p3.json()
    assert len(p3_data) == 15
    assert p3_data[0]["content"] == "Message sequence 050"
    assert p3_data[-1]["content"] == "Message sequence 064"

    # Page 4: offset beyond total count
    resp_p4 = client.get(f"/api/projects/{p_id}/copilot?limit=25&offset=100")
    assert resp_p4.status_code == 200
    assert resp_p4.json() == []

    # Reverse ordering (descending)
    resp_desc = client.get(f"/api/projects/{p_id}/copilot?limit=10&offset=0&order=desc")
    assert resp_desc.status_code == 200
    desc_data = resp_desc.json()
    assert len(desc_data) == 10
    assert desc_data[0]["content"] == "Message sequence 064"

    # Parameter boundaries validation
    assert client.get(f"/api/projects/{p_id}/copilot?limit=0").status_code == 422
    assert client.get(f"/api/projects/{p_id}/copilot?limit=201").status_code == 422
    assert client.get(f"/api/projects/{p_id}/copilot?offset=-1").status_code == 422
    assert client.get(f"/api/projects/{p_id}/copilot?order=unsupported").status_code == 422


def test_chat_provider_context_limits(auth_fixture):
    """Test that provider context is strictly bounded to recent messages without leaking or destroying saved history."""
    client = auth_fixture["client1"]
    p_id = auth_fixture["p1_id"]

    # Seed 35 existing messages
    base_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    with SessionLocal() as db:
        for i in range(35):
            db.add(CopilotMessage(
                id=gen_id("cmsg_"),
                project_id=p_id,
                role="user" if i % 2 == 0 else "assistant",
                content=f"Historical message {i:02d}",
                created_at=base_time + timedelta(minutes=i)
            ))
        db.commit()

    captured_history = []

    def mock_chat_copilot(project_info, chat_history, user_message, cross_module_context=None):
        nonlocal captured_history
        captured_history = list(chat_history)
        return "Provider response respecting bounded context."

    with patch("app.ai.gemini_service.ai_service.chat_copilot", side_effect=mock_chat_copilot):
        resp = client.post(
            f"/api/projects/{p_id}/copilot",
            json={"message": "What is our customer acquisition strategy?"}
        )
        assert resp.status_code == 200
        assert resp.json()["content"] == "Provider response respecting bounded context."

    # Context passed to provider must be bounded to at most 20 messages
    assert len(captured_history) <= 20
    # Captured history must be in chronological order
    if len(captured_history) > 1:
        assert captured_history[-1]["content"] == "Historical message 34"

    # Verify that all messages in database are preserved (35 initial + 1 user + 1 assistant = 37)
    with SessionLocal() as db:
        total_in_db = db.query(CopilotMessage).filter(CopilotMessage.project_id == p_id).count()
        assert total_in_db == 37


def test_cross_user_tenant_isolation_copilot_and_exports(auth_fixture):
    """Test that User B cannot read copilot history, send messages, or export documents for User A's project."""
    client_b = auth_fixture["client2"]
    user_a_project_id = auth_fixture["p1_id"]

    # 1. Copilot history
    resp_hist = client_b.get(f"/api/projects/{user_a_project_id}/copilot")
    assert resp_hist.status_code == 403

    # 2. Copilot message post
    resp_post = client_b.post(
        f"/api/projects/{user_a_project_id}/copilot",
        json={"message": "Attempting cross-tenant access"}
    )
    assert resp_post.status_code == 403

    # 3. Project PDF export
    resp_exp = client_b.get(f"/api/projects/{user_a_project_id}/export/pdf")
    assert resp_exp.status_code == 403

    # 4. Module PDF export
    resp_mod_exp = client_b.get(f"/api/projects/{user_a_project_id}/export/modules/overview/pdf")
    assert resp_mod_exp.status_code == 403


def test_synthetic_sensitive_markers_never_leak_in_client_or_telemetry(auth_fixture):
    """Test that internal database errors containing synthetic credentials/passwords never leak to client responses or telemetry."""
    client = auth_fixture["client1"]
    p_id = auth_fixture["p1_id"]

    synthetic_secret = "SYNTHETIC_SUPABASE_PASSWORD_SECRET_889922"
    synthetic_operational_error = (
        f'OperationalError: connection to server at "db.xyz.supabase.co" failed: '
        f'password authentication failed for user "postgres" with password "{synthetic_secret}"'
    )

    # Trigger failure in bulk delete projects with the synthetic secret
    with patch("sqlalchemy.orm.Session.delete", side_effect=RuntimeError(synthetic_operational_error)):
        resp = client.post(
            "/api/projects/bulk-delete",
            json={"project_ids": [p_id]}
        )
        assert resp.status_code == 500
        # Synthetic secret must NEVER appear in response body
        assert synthetic_secret not in resp.text
        # Detail must be generic and useful
        data = resp.json()
        assert "internal error" in data["detail"].lower()
        # Request correlation ID must be present in response
        assert "X-Request-ID" in resp.headers

    # Check telemetry / audit logs to verify synthetic secret was not written to database
    with SessionLocal() as db:
        audits = db.query(AuditLog).all()
        for audit in audits:
            assert synthetic_secret not in str(audit.details)
            assert synthetic_secret not in str(audit.reason)

        ai_ops = db.query(AIOperation).all()
        for op in ai_ops:
            assert synthetic_secret not in str(op.error_message)


def test_unhandled_route_exception_returns_clean_500_with_request_id(auth_fixture):
    """Test that an unhandled exception in an API endpoint returns a sanitized 500 JSON response with request_id."""
    raw_token = auth_fixture["raw_token1"]
    csrf = auth_fixture["csrf1"]
    client = TestClient(
        app,
        cookies={settings.COOKIE_NAME: raw_token},
        headers={"X-CSRF-Token": csrf},
        raise_server_exceptions=False
    )
    p_id = auth_fixture["p1_id"]

    # Simulate an unexpected unhandled exception in an endpoint
    with patch("app.api.exports.read_project_context", side_effect=KeyError("unexpected_missing_internal_key")):
        resp = client.get(f"/api/projects/{p_id}/export/pdf")
        assert resp.status_code == 500
        data = resp.json()
        assert "request_id" in data
        assert resp.headers.get("X-Request-ID") == data["request_id"]
        assert "internal" in data["detail"].lower()
        # Raw internal python KeyError details must not leak
        assert "unexpected_missing_internal_key" not in data["detail"]


# ==============================================================================
# Comprehensive Regression Tests for Verification Closeout
# ==============================================================================

def test_chat_pagination_over_50_messages_equal_timestamps_and_cursor(auth_fixture):
    """Test pagination with 65 messages, equal timestamps, cursor paging, and stable secondary key ordering."""
    client = auth_fixture["client1"]
    p_id = auth_fixture["p1_id"]
    fixed_time = datetime(2026, 10, 25, 12, 0, 0, tzinfo=timezone.utc)

    # Insert 65 messages with predictable IDs
    with SessionLocal() as db:
        # Clear existing messages for clean test
        db.query(CopilotMessage).filter(CopilotMessage.project_id == p_id).delete()
        db.commit()

        for i in range(65):
            # Messages 20 to 30 share identical created_at timestamp
            t = fixed_time if (20 <= i <= 30) else (fixed_time + timedelta(seconds=i))
            msg = CopilotMessage(
                id=f"msg_{i:04d}",
                project_id=p_id,
                role="user" if i % 2 == 0 else "assistant",
                content=f"Message {i:04d}",
                created_at=t
            )
            db.add(msg)
        db.commit()

    # 1. Fetch latest page with limit=25, order=desc
    r1 = client.get(f"/api/projects/{p_id}/copilot?limit=25&order=desc")
    assert r1.status_code == 200
    p1_data = r1.json()
    assert len(p1_data) == 25
    assert r1.headers.get("X-Total-Count") == "65"
    assert r1.headers.get("X-Has-More") == "true"
    assert p1_data[0]["id"] == "msg_0064"

    # 2. Fetch second page using cursor before_id
    cursor = p1_data[-1]["id"]  # msg_0040
    r2 = client.get(f"/api/projects/{p_id}/copilot?limit=25&order=desc&before_id={cursor}")
    assert r2.status_code == 200
    p2_data = r2.json()
    assert len(p2_data) == 25
    assert p2_data[0]["id"] == "msg_0039"

    # Verify no overlap between p1 and p2
    p1_ids = {m["id"] for m in p1_data}
    p2_ids = {m["id"] for m in p2_data}
    assert p1_ids.isdisjoint(p2_ids)

    # 3. Fetch third page (remaining 15 messages) which crosses the equal-timestamp boundary
    cursor2 = p2_data[-1]["id"]  # msg_0015
    r3 = client.get(f"/api/projects/{p_id}/copilot?limit=25&order=desc&before_id={cursor2}")
    assert r3.status_code == 200
    p3_data = r3.json()
    assert len(p3_data) == 15
    assert p3_data[-1]["id"] == "msg_0000"

    # Combined messages must equal exactly 65 unique IDs
    all_paged_ids = [m["id"] for m in p1_data + p2_data + p3_data]
    assert len(all_paged_ids) == 65
    assert len(set(all_paged_ids)) == 65


def test_provider_context_character_budget_and_prompt_preservation(auth_fixture):
    """Test that recent history passed to provider respects 16,000 char budget while preserving user question in full."""
    client = auth_fixture["client1"]
    p_id = auth_fixture["p1_id"]

    # Seed 10 large messages in history: each 3,000 chars = 30,000 total chars
    with SessionLocal() as db:
        db.query(CopilotMessage).filter(CopilotMessage.project_id == p_id).delete()
        for i in range(10):
            msg = CopilotMessage(
                id=f"large_msg_{i}",
                project_id=p_id,
                role="user" if i % 2 == 0 else "assistant",
                content=f"History message {i}: " + ("x" * 2980),
                created_at=datetime.now(timezone.utc) + timedelta(seconds=i)
            )
            db.add(msg)
        db.commit()

    captured_history = None
    captured_request = None

    def mock_chat_copilot(proj_info, history_dicts, user_message, cross_module_context=None):
        nonlocal captured_history, captured_request
        captured_history = history_dicts
        captured_request = user_message
        return "Simulated budget test reply"

    long_user_question = "Explain technical scalability: " + ("y" * 2000)

    with patch("app.ai.gemini_service.ai_service.chat_copilot", side_effect=mock_chat_copilot):
        resp = client.post(
            f"/api/projects/{p_id}/copilot",
            json={"message": long_user_question}
        )
        assert resp.status_code == 200

    # User question must be preserved completely (not truncated)
    assert captured_request == long_user_question
    assert len(captured_request) > 2000

    # Total characters in history passed to provider must not exceed 16,000 chars
    total_history_chars = sum(len(m["content"]) for m in captured_history)
    assert total_history_chars <= 16000
    # Must preserve the most recent history messages
    assert captured_history[-1]["content"].startswith("History message 9")


def test_export_filename_comprehensive_edge_cases():
    """Verify filename handling across Unicode-only, control characters, slashes, punctuation-only, and long titles."""
    from app.core.exports import sanitize_filename, format_content_disposition

    # 1. Unicode-only title (Hindi)
    ascii_f, utf8_f = sanitize_filename("व्यापार", fallback="project")
    assert ascii_f == "project.pdf"
    assert utf8_f == "व्यापार.pdf"
    disp = format_content_disposition("व्यापार", fallback="project")
    assert 'filename="project.pdf"' in disp
    assert "filename*=UTF-8''" in disp

    # 2. Mixed-language title with quotes, slashes, percent, and semicolons
    ascii_f, utf8_f = sanitize_filename('Project "Alpha" / Beta \\ Gamma; 100%', fallback="project")
    assert "/" not in ascii_f and "\\" not in ascii_f and ";" not in ascii_f and '"' not in ascii_f
    assert "/" not in utf8_f and "\\" not in utf8_f and ";" not in utf8_f and '"' not in utf8_f
    assert ascii_f.endswith(".pdf")
    assert utf8_f.endswith(".pdf")

    # 3. CR/LF, null bytes, and DEL control character
    ascii_f, utf8_f = sanitize_filename("Injected\r\nHeader\x00Name\x7fTest", fallback="safe")
    assert "\r" not in ascii_f and "\n" not in ascii_f and "\x00" not in ascii_f and "\x7f" not in ascii_f
    assert "\r" not in utf8_f and "\n" not in utf8_f and "\x00" not in utf8_f and "\x7f" not in utf8_f

    # 4. Empty or punctuation-only title
    ascii_f, utf8_f = sanitize_filename("???///:::;;;***", fallback="fallback_doc")
    assert ascii_f == "fallback_doc.pdf"
    assert utf8_f == "fallback_doc.pdf"

    # 5. Very long title (500 chars)
    long_title = "A" * 500
    ascii_f, utf8_f = sanitize_filename(long_title, fallback="doc")
    # Base must be bounded to <= 100 chars, so total <= 104 chars
    assert len(ascii_f) <= 104
    assert len(utf8_f) <= 104
    assert ascii_f.count(".pdf") == 1


def test_exception_sanitization_across_main_and_mounted_routes(auth_fixture):
    """Test unexpected failures in main app, mounted API, with diagnostics enabled and disabled."""
    raw_token = auth_fixture["raw_token1"]
    csrf = auth_fixture["csrf1"]
    client = TestClient(
        app,
        cookies={settings.COOKIE_NAME: raw_token},
        headers={"X-CSRF-Token": csrf},
        raise_server_exceptions=False
    )
    p_id = auth_fixture["p1_id"]

    # 1. Diagnostics enabled: unhandled exception returns generic 500 with correlation ID
    def broken_dep_div():
        raise ZeroDivisionError("secret_database_division_error")

    def broken_dep_val():
        raise ValueError("connection_string=postgres://usr:secret_pwd@db/app")

    from app.main import api_v1
    from app.api.deps import get_user_project

    try:
        api_v1.dependency_overrides[get_user_project] = broken_dep_div
        with patch("app.core.config.settings.PERF_DIAGNOSTICS", True):
            resp = client.get(f"/api/projects/{p_id}")
            assert resp.status_code == 500
            data = resp.json()
            assert "internal server error" in data["detail"].lower()
            assert "secret_database_division_error" not in resp.text
            assert "request_id" in data
            assert resp.headers.get("X-Request-ID") == data["request_id"]

        # 2. Diagnostics disabled: unhandled exception returns generic 500 with correlation ID
        api_v1.dependency_overrides[get_user_project] = broken_dep_val
        with patch("app.core.config.settings.PERF_DIAGNOSTICS", False):
            resp = client.get(f"/api/projects/{p_id}")
            assert resp.status_code == 500
            data = resp.json()
            assert "secret_pwd" not in resp.text
            assert "connection_string" not in resp.text
            assert "request_id" in data
            assert resp.headers.get("X-Request-ID") == data["request_id"]
    finally:
        api_v1.dependency_overrides.clear()

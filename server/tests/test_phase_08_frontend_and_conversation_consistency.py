"""Phase 8 Verification: Frontend and Conversation Consistency.

Covers:
1. Chat cursor pagination (/copilot/page), latest-page opening, older retrieval, and cross-project cursor tamper rejection.
2. Hardened export filenames and RFC 5987 filename* encoding (safe="", path separators, repeated extensions, bounds).
3. Send chat message returns X-User-Message-ID correlation header for optimistic client reconciliation.
"""

import secrets
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import SessionLocal
from app.models.all_models import (
    User, Project, CopilotMessage, Session as DBSession, gen_id
)
from app.core.security import hash_password, generate_session_token, hash_session_token, generate_csrf_token
from app.core.exports import sanitize_filename, format_content_disposition


@pytest.fixture
def auth_fixture():
    """Create isolated test users and projects."""
    uid = secrets.token_hex(4)
    with SessionLocal() as db:
        # User 1
        u1 = User(
            id=gen_id("usr_"),
            username=f"p8_user1_{uid}",
            email=f"p8_user1_{uid}@example.com",
            hashed_password=hash_password("Password123!"),
            role="user",
            is_suspended=False
        )
        db.add(u1)
        p1 = Project(
            id=gen_id("proj_"),
            name="Venture Atlas Cycle Plan",
            user_id=u1.id,
            stage="Idea",
            description="Phase 8 test project",
            industry="Physical Services",
            target_customers="Local cyclists"
        )
        db.add(p1)

        # User 2 (tenant isolation check)
        u2 = User(
            id=gen_id("usr_"),
            username=f"p8_user2_{uid}",
            email=f"p8_user2_{uid}@example.com",
            hashed_password=hash_password("Password123!"),
            role="user",
            is_suspended=False
        )
        db.add(u2)
        p2 = Project(
            id=gen_id("proj_"),
            name="Tenant B Bakery",
            user_id=u2.id,
            stage="Idea",
            description="Tenant B project",
            industry="Food",
            target_customers="Neighborhood shoppers"
        )
        db.add(p2)

        # Sessions
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


def test_copilot_page_latest_and_cursor_pagination_with_tamper_defense(auth_fixture):
    """Test /copilot/page returns latest messages chronologically ascending, paginates older messages, and rejects cross-tenant cursors."""
    client1 = auth_fixture["client1"]
    p1_id = auth_fixture["p1_id"]
    client2 = auth_fixture["client2"]
    p2_id = auth_fixture["p2_id"]

    # Seed 65 messages for project 1
    base_time = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    with SessionLocal() as db:
        for i in range(65):
            t = base_time + timedelta(minutes=i)
            msg = CopilotMessage(
                id=f"p8_msg_{i:04d}",
                project_id=p1_id,
                role="user" if i % 2 == 0 else "assistant",
                content=f"Planning query step {i:03d}",
                created_at=t
            )
            db.add(msg)
        db.commit()

    # 1. Opening conversation loads the latest page (50 items) ordered chronologically
    resp1 = client1.get(f"/api/projects/{p1_id}/copilot/page?limit=50")
    assert resp1.status_code == 200
    page1 = resp1.json()
    assert page1["total_count"] == 65
    assert page1["has_more"] is True
    assert len(page1["messages"]) == 50
    # Oldest in this 50-item page is message 15, newest is message 64
    assert page1["messages"][0]["id"] == "p8_msg_0015"
    assert page1["messages"][-1]["id"] == "p8_msg_0064"
    assert page1["before_cursor"] is not None

    # 2. Paginate older messages using before_cursor
    cursor = page1["before_cursor"]
    resp2 = client1.get(f"/api/projects/{p1_id}/copilot/page?limit=50&before_cursor={cursor}")
    assert resp2.status_code == 200
    page2 = resp2.json()
    assert page2["has_more"] is False
    assert len(page2["messages"]) == 15
    # Oldest is message 0, newest is message 14
    assert page2["messages"][0]["id"] == "p8_msg_0000"
    assert page2["messages"][-1]["id"] == "p8_msg_0014"
    assert page2["before_cursor"] is None

    # No overlapping IDs between pages
    p1_ids = {m["id"] for m in page1["messages"]}
    p2_ids = {m["id"] for m in page2["messages"]}
    assert p1_ids.isdisjoint(p2_ids)
    assert len(p1_ids.union(p2_ids)) == 65

    # 3. Cross-project cursor tamper defense: user 2 attempting to use project 1's cursor on project 2
    tamper_resp = client2.get(f"/api/projects/{p2_id}/copilot/page?before_cursor={cursor}")
    assert tamper_resp.status_code == 400
    assert "Cursor does not belong to the authorized project" in tamper_resp.json()["detail"]


def test_export_filename_hardening_edge_cases():
    """Verify that export filenames are strictly sanitized against path separators, repeated extensions, and control chars."""
    # 1. Path traversal and separators are stripped
    safe_ascii, utf8_name = sanitize_filename("../../etc/passwd/plan.pdf", fallback="export", extension="pdf")
    assert "/" not in safe_ascii
    assert "\\" not in safe_ascii
    assert ".." not in safe_ascii
    assert "/" not in utf8_name
    assert "\\" not in utf8_name
    assert utf8_name.endswith(".pdf")

    # 2. Repeated expected extension stripped
    safe_ascii, utf8_name = sanitize_filename("business_model.pdf.pdf.pdf", fallback="export", extension="pdf")
    assert safe_ascii == "business_model.pdf"
    assert utf8_name == "business_model.pdf"

    # 3. Empty or punctuation-only title safely defaults
    safe_ascii, utf8_name = sanitize_filename("!@#$%^&*()_+", fallback="default_plan", extension="pdf")
    assert safe_ascii == "default_plan.pdf"
    assert utf8_name == "default_plan.pdf"

    # 4. Content-Disposition format uses safe="" strict encoding for filename*
    header = format_content_disposition("My Plan / 2026", fallback="plan", extension="pdf", disposition_type="attachment")
    assert header.startswith('attachment; filename="')
    assert "filename*=UTF-8''" in header
    # Ensure slash is not present in quoted ASCII filename
    assert "/" not in header.split(";")[1]

    # 5. Length bounding prevents overflow
    very_long_title = "A" * 250
    safe_ascii, utf8_name = sanitize_filename(very_long_title, fallback="export", extension="pdf")
    assert len(safe_ascii) <= 105  # 100 base + .pdf
    assert len(utf8_name) <= 105


def test_send_chat_message_returns_user_message_id_header(auth_fixture):
    """Test that posting a chat message returns the persisted user message ID in X-User-Message-ID header."""
    client1 = auth_fixture["client1"]
    csrf1 = auth_fixture["csrf1"]
    p1_id = auth_fixture["p1_id"]

    with patch("app.ai.gemini_service.ai_service.chat_copilot", return_value="Here is your strategic guidance."):
        resp = client1.post(
            f"/api/projects/{p1_id}/copilot",
            json={"message": "What is our customer acquisition strategy?", "client_msg_id": "temp-user-1234"},
            headers={"X-CSRF-Token": csrf1}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "assistant"
        assert data["content"] == "Here is your strategic guidance."

        # Verify X-User-Message-ID header is present and valid
        user_msg_id = resp.headers.get("X-User-Message-ID")
        assert user_msg_id is not None

        # Verify user message in database
        with SessionLocal() as db:
            saved_user_msg = db.query(CopilotMessage).filter(CopilotMessage.id == user_msg_id).first()
            assert saved_user_msg is not None
            assert saved_user_msg.content == "What is our customer acquisition strategy?"
            assert saved_user_msg.role == "user"
            assert saved_user_msg.project_id == p1_id


def test_active_module_navigation_does_not_mutate_project_updated_at(auth_fixture):
    """Verify that changing navigation preference via PATCH /{project_id}/active-module does NOT mutate project.updated_at."""
    client1 = auth_fixture["client1"]
    csrf1 = auth_fixture["csrf1"]
    p1_id = auth_fixture["p1_id"]

    # Explicitly set updated_at in past
    past_time = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    with SessionLocal() as db:
        proj = db.query(Project).filter(Project.id == p1_id).first()
        proj.updated_at = past_time
        db.commit()

    # Issue navigation tab preference update
    resp = client1.patch(
        f"/api/projects/{p1_id}/active-module",
        json={"active_module": "tech_stack"},
        headers={"X-CSRF-Token": csrf1}
    )
    assert resp.status_code == 200
    assert resp.json()["active_module"] == "tech_stack"

    # Verify that project.updated_at was preserved and not bumped
    with SessionLocal() as db:
        proj_after = db.query(Project).filter(Project.id == p1_id).first()
        assert proj_after.active_module == "tech_stack"
        # Compare timestamp up to second precision
        assert abs((proj_after.updated_at.replace(tzinfo=timezone.utc) - past_time).total_seconds()) < 1.0


def test_date_derived_milestones_and_cumulative_model():
    """Verify calculate_roadmap_summary cumulative logic, boundary dates, missing dates, and status parsing."""
    from app.services.task_milestones import (
        calculate_roadmap_summary, parse_strict_date_only, derive_anchor_date
    )
    from app.models.all_models import RoadmapTask

    # Anchor date: 2026-03-01
    # Day 30: 2026-03-30 (30 days from March 1, inclusive: (30-1)+1 = 30)
    # Day 31: 2026-03-31 (Day 31 -> outside day 30 boundary, inside day 60)
    # Day 60: 2026-04-29 (31 in March + 29 in April = 60 days)
    # Day 90: 2026-05-29 (31 + 30 + 29 = 90 days)
    tasks = [
        RoadmapTask(
            id="t1", project_id="p", task_code="P1-01", title="Task 1",
            start_date="2026-03-01", end_date="2026-03-15", status="completed"
        ),
        RoadmapTask(
            id="t2", project_id="p", task_code="P1-02", title="Task 2 (exact 30)",
            start_date="2026-03-10", end_date="2026-03-30", status="not_started"
        ),
        RoadmapTask(
            id="t3", project_id="p", task_code="P2-01", title="Task 3 (day 31)",
            start_date="2026-03-15", end_date="2026-03-31", status="completed"
        ),
        RoadmapTask(
            id="t4", project_id="p", task_code="P2-02", title="Task 4 (day 60)",
            start_date="2026-04-01", end_date="2026-04-29", status="in_progress"
        ),
        RoadmapTask(
            id="t5", project_id="p", task_code="P3-01", title="Task 5 (day 90)",
            start_date="2026-05-01", end_date="2026-05-29", status="completed"
        ),
        RoadmapTask(
            id="t6", project_id="p", task_code="P4-01", title="Task 6 (day 120, later)",
            start_date="2026-06-01", end_date="2026-06-29", status="not_started"
        ),
        RoadmapTask(
            id="t7", project_id="p", task_code="P4-02", title="Undated Task",
            start_date=None, end_date=None, status="completed"
        ),
    ]

    summary = calculate_roadmap_summary(tasks, saved_start_date="2026-03-01")

    # Overall tasks: 7 total, 4 completed (t1, t3, t5, t7) -> 4/7 = 57%
    assert summary["total_tasks"] == 7
    assert summary["completed_tasks"] == 4
    assert summary["overall_progress"] == 57

    # 30-day cumulative: t1 and t2 (t1 is completed, t2 is not_started)
    # t3 is on day 31, so not in 30-day
    assert summary["milestone_30_total"] == 2
    assert summary["milestone_30_completed"] == 1
    assert summary["milestone_30_progress"] == 50

    # 60-day cumulative: includes t1, t2, t3, t4 -> 4 tasks.
    # Completed in 60-day: t1 (completed), t3 (completed) -> 2/4 = 50%
    assert summary["milestone_60_total"] == 4
    assert summary["milestone_60_completed"] == 2
    assert summary["milestone_60_progress"] == 50

    # 90-day cumulative: includes t1, t2, t3, t4, t5 -> 5 tasks.
    # Completed in 90-day: t1, t3, t5 -> 3/5 = 60%
    assert summary["milestone_90_total"] == 5
    assert summary["milestone_90_completed"] == 3
    assert summary["milestone_90_progress"] == 60

    # Undated task t7 is excluded from date-derived milestone cards
    # but correctly counted in overall tasks
    assert summary["total_tasks"] == 7



"""Tests for Knowledge base context integration, batch links, duplicate idempotency,
and Roadmap enhancement field preservation in context, reconciliation, project copy, and PDF export.
"""

import secrets
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import SessionLocal
from app.models.all_models import (
    User, Project, ModuleContent, ModuleVersion, RoadmapTask,
    ProjectKnowledgeItem, KnowledgeLink, FinancialWorksheet, Session as DBSession, gen_id
)
from app.core.config import settings
from app.core.security import hash_password, generate_session_token, generate_csrf_token
from app.services.project_context_service import read_project_context, current_module_data
from app.services.roadmap_service import RoadmapDomainService
from app.services.pdf_service import PDFService


@pytest.fixture
def enhanced_setup():
    uid = secrets.token_hex(4)
    with SessionLocal() as db:
        user = User(
            id=gen_id("usr_"),
            username=f"enh_user_{uid}",
            email=f"enh_{uid}@example.com",
            hashed_password=hash_password("Password123!"),
            role="user",
            is_suspended=False
        )
        db.add(user)

        project = Project(
            id=gen_id("proj_"),
            name="Quantum Logistics",
            user_id=user.id,
            stage="Seed",
            industry="Supply Chain",
            description="Autonomous routing and predictive freight distribution.",
            target_customers="Mid-market fleet operators.",
            budget=50000.0,
            goals="Achieve 15% fleet idle time reduction."
        )
        db.add(project)

        # Roadmap module content and version
        mod_roadmap = ModuleContent(
            id=gen_id("mod_"),
            project_id=project.id,
            module_type="execution_roadmap",
            framework_type="default"
        )
        db.add(mod_roadmap)

        ver_roadmap = ModuleVersion(
            id=gen_id("ver_"),
            module_content_id=mod_roadmap.id,
            version_number=1,
            version_name="Roadmap V1",
            data={
                "phases": [
                    {"name": "Phase 1: Ingestion", "start_date": "2026-01-01", "end_date": "2026-01-15"}
                ],
                "tasks": []
            },
            is_active=True
        )
        db.add(ver_roadmap)
        mod_roadmap.active_version_id = ver_roadmap.id

        # Initial roadmap task with full enhancement fields
        task1 = RoadmapTask(
            id=gen_id("tsk_"),
            project_id=project.id,
            task_code="TSK-01",
            phase="Phase 1: Ingestion",
            title="Setup GPS Telemetry Stream",
            description="Ingest live truck positions via Kafka.",
            timeline="30-day",
            start_date="2026-01-01",
            end_date="2026-01-07",
            priority="Critical",
            status="In Progress",
            dependencies=[],
            deliverables="Real-time stream broker",
            effort="1 week",
            assigned_to="Lead Data Engineer",
            assigned_role="Data Engineer",
            department="Engineering",
            steps=["Deploy Kafka", "Provision VPC"],
            is_overloaded=False,
            order_index=0,
            is_ai_generated=True,
            branch_type="core",
            parent_outcome="Telemetry Reliability",
            definition_of_done="Zero message drop during 48-hour continuous run.",
            acceptance_criteria=["p99 latency < 50ms", "Throughput >= 10k events/sec"],
            edge_type="prerequisite",
            roadmap_mode="execution"
        )
        db.add(task1)

        # Knowledge items
        k1 = ProjectKnowledgeItem(
            id=gen_id("kno_"),
            project_id=project.id,
            item_type="fact",
            title="US DOT Regulations Verified",
            content="Fleet hours of service must comply with Part 395 standards.",
            status="active",
            epistemic_status="evidence_supported",
            source_reference="49 CFR Part 395",
            linked_module="execution_roadmap",
            metadata_json={"regulation_code": "DOT-395"}
        )
        k2 = ProjectKnowledgeItem(
            id=gen_id("kno_"),
            project_id=project.id,
            item_type="assumption",
            title="Driver Adoption Hypothesis",
            content="Drivers will log fuel stops within 5 minutes if prompted via SMS.",
            status="active",
            epistemic_status="hypothesis",
            source_reference="Customer interviews",
            linked_module="bmc"
        )
        db.add(k1)
        db.add(k2)
        db.flush()

        # Link between k1 and k2
        link = KnowledgeLink(
            id=gen_id("knl_"),
            project_id=project.id,
            source_id=k1.id,
            target_id=k2.id,
            relationship="supports"
        )
        db.add(link)

        # Financial worksheet
        ws = FinancialWorksheet(
            id=gen_id("fin_"),
            project_id=project.id,
            currency="USD",
            startup_costs=[{"category": "servers", "item": "Cloud instances", "amount": 1200.0, "is_confirmed": True}],
            fixed_costs=[{"category": "subscriptions", "item": "Mapping API", "monthly_amount": 250.0}],
            variable_costs=[{"item": "Data processing per trip", "unit_cost": 0.5}],
            revenue_model={"model_type": "subscription", "price_per_unit": 100.0, "expected_volume_monthly": 50},
            cash_available=15000.0
        )
        db.add(ws)

        db.commit()

        token = generate_session_token()
        csrf = generate_csrf_token(token)
        session_rec = DBSession(
            id=gen_id("ses_"),
            user_id=user.id,
            session_token=token,
            expires_at=datetime.now(timezone.utc).replace(year=2030)
        )
        db.add(session_rec)
        db.commit()

        return {
            "user_id": user.id,
            "project_id": project.id,
            "session_token": token,
            "csrf_token": csrf,
            "task_id": task1.id,
            "k1_id": k1.id,
            "k2_id": k2.id,
            "link_id": link.id
        }


def test_project_context_includes_knowledge_base_and_roadmap_fields(enhanced_setup):
    p_id = enhanced_setup["project_id"]
    with SessionLocal() as db:
        context, sources = read_project_context(db, p_id)

        # 1. Verify knowledge_base in context
        assert "knowledge_base" in context
        kb_items = context["knowledge_base"]
        assert len(kb_items) == 2
        kb_titles = [item["title"] for item in kb_items]
        assert "US DOT Regulations Verified" in kb_titles
        assert "Driver Adoption Hypothesis" in kb_titles

        # 2. Verify sources contains knowledge_base entry
        kb_source = next((s for s in sources if s.get("module_type") == "knowledge_base"), None)
        assert kb_source is not None
        assert kb_source["origin"] == "project_knowledge_items"
        assert kb_source["count"] == 2
        assert "content_fingerprint" in kb_source

        # 3. Verify roadmap tasks contain all 6 enhancement fields
        roadmap_data = context["execution_roadmap"]
        assert "tasks" in roadmap_data
        assert len(roadmap_data["tasks"]) == 1
        t = roadmap_data["tasks"][0]
        assert t["branch_type"] == "core"
        assert t["parent_outcome"] == "Telemetry Reliability"
        assert t["definition_of_done"] == "Zero message drop during 48-hour continuous run."
        assert t["acceptance_criteria"] == ["p99 latency < 50ms", "Throughput >= 10k events/sec"]
        assert t["edge_type"] == "prerequisite"
        assert t["roadmap_mode"] == "execution"


def test_knowledge_api_batch_links_and_idempotent_duplicate(enhanced_setup):
    client = TestClient(
        app,
        cookies={settings.COOKIE_NAME: enhanced_setup["session_token"]},
        headers={"X-CSRF-Token": enhanced_setup["csrf_token"]}
    )
    p_id = enhanced_setup["project_id"]

    # 1. List knowledge items (batch query)
    res = client.get(f"/api/projects/{p_id}/knowledge")
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 2

    k1 = next(item for item in items if item["id"] == enhanced_setup["k1_id"])
    k2 = next(item for item in items if item["id"] == enhanced_setup["k2_id"])
    assert len(k1["outgoing_links"]) == 1
    assert k1["outgoing_links"][0]["relationship"] == "supports"
    assert len(k2["incoming_links"]) == 1
    assert k2["incoming_links"][0]["relationship"] == "supports"

    # 2. Attempt duplicate link creation (idempotency check)
    dup_res = client.post(
        f"/api/projects/{p_id}/knowledge/links",
        json={
            "source_id": enhanced_setup["k1_id"],
            "target_id": enhanced_setup["k2_id"],
            "relationship": "supports"
        }
    )
    assert dup_res.status_code == 201
    dup_data = dup_res.json()
    assert dup_data["id"] == enhanced_setup["link_id"]

    # 3. Invalid schema validation test (invalid relationship Literal)
    invalid_res = client.post(
        f"/api/projects/{p_id}/knowledge/links",
        json={
            "source_id": enhanced_setup["k1_id"],
            "target_id": enhanced_setup["k2_id"],
            "relationship": "invalid_relationship_type"
        }
    )
    assert invalid_res.status_code == 422


def test_roadmap_reconciliation_preserves_enhancement_fields(enhanced_setup):
    p_id = enhanced_setup["project_id"]
    with SessionLocal() as db:
        project = db.query(Project).filter(Project.id == p_id).first()

        # Update existing task TSK-01 and insert new task TSK-02 with enhancement fields
        incoming_tasks = [
            {
                "task_code": "TSK-01",
                "phase": "Phase 1: Ingestion",
                "title": "Setup GPS Telemetry Stream (Updated)",
                "description": "Updated description",
                "timeline": "30-day",
                "start_date": "2026-01-01",
                "end_date": "2026-01-08",
                "priority": "Critical",
                "status": "In Progress",
                "dependencies": [],
                "deliverables": "Enhanced stream broker",
                "effort": "1 week",
                "branch_type": "parallel",
                "parent_outcome": "Updated Telemetry Outcome",
                "definition_of_done": "99.99% uptime for 7 days",
                "acceptance_criteria": ["Latency < 25ms"],
                "edge_type": "optional_branch",
                "roadmap_mode": "execution"
            },
            {
                "task_code": "TSK-02",
                "phase": "Phase 1: Ingestion",
                "title": "Anomaly Detection Engine",
                "description": "Analyze telemetry for routing anomalies.",
                "timeline": "30-day",
                "start_date": "2026-01-09",
                "end_date": "2026-01-15",
                "priority": "High",
                "status": "Pending",
                "dependencies": ["TSK-01"],
                "deliverables": "Detection model",
                "effort": "1 week",
                "branch_type": "learning",
                "parent_outcome": "Route Safety",
                "definition_of_done": "Precision >= 90%",
                "acceptance_criteria": ["F1 score >= 0.88"],
                "edge_type": "alternative",
                "roadmap_mode": "learning"
            }
        ]

        RoadmapDomainService.reconcile_roadmap_tasks(db, project, incoming_tasks)
        db.commit()

        # Verify TSK-01 updated fields
        t1 = db.query(RoadmapTask).filter(RoadmapTask.project_id == p_id, RoadmapTask.task_code == "TSK-01").first()
        assert t1.branch_type == "parallel"
        assert t1.parent_outcome == "Updated Telemetry Outcome"
        assert t1.definition_of_done == "99.99% uptime for 7 days"
        assert t1.acceptance_criteria == ["Latency < 25ms"]
        assert t1.edge_type == "optional_branch"
        assert t1.roadmap_mode == "execution"

        # Verify TSK-02 inserted fields
        t2 = db.query(RoadmapTask).filter(RoadmapTask.project_id == p_id, RoadmapTask.task_code == "TSK-02").first()
        assert t2.branch_type == "learning"
        assert t2.parent_outcome == "Route Safety"
        assert t2.definition_of_done == "Precision >= 90%"
        assert t2.acceptance_criteria == ["F1 score >= 0.88"]
        assert t2.edge_type == "alternative"
        assert t2.roadmap_mode == "learning"


def test_project_copy_clones_roadmap_fields_and_knowledge_and_financials(enhanced_setup):
    client = TestClient(
        app,
        cookies={settings.COOKIE_NAME: enhanced_setup["session_token"]},
        headers={"X-CSRF-Token": enhanced_setup["csrf_token"]}
    )
    p_id = enhanced_setup["project_id"]

    # Clone project via PUT /projects/{id} with create_copy=True
    clone_res = client.put(
        f"/api/projects/{p_id}",
        json={"name": "Quantum Logistics (Copy)", "create_copy": True}
    )
    assert clone_res.status_code == 200
    cloned_proj = clone_res.json()
    cloned_id = cloned_proj["id"]
    assert cloned_id != p_id

    with SessionLocal() as db:
        # 1. Verify cloned roadmap tasks
        cloned_tasks = db.query(RoadmapTask).filter(RoadmapTask.project_id == cloned_id).all()
        assert len(cloned_tasks) >= 1
        ct1 = next(t for t in cloned_tasks if t.task_code == "TSK-01")
        assert ct1.parent_outcome == "Telemetry Reliability"
        assert ct1.definition_of_done == "Zero message drop during 48-hour continuous run."
        assert ct1.acceptance_criteria == ["p99 latency < 50ms", "Throughput >= 10k events/sec"]
        assert ct1.edge_type == "prerequisite"
        assert ct1.roadmap_mode == "execution"

        # 2. Verify cloned financial worksheet
        cloned_ws = db.query(FinancialWorksheet).filter(FinancialWorksheet.project_id == cloned_id).first()
        assert cloned_ws is not None
        assert cloned_ws.currency == "USD"
        assert cloned_ws.cash_available == 15000.0
        assert len(cloned_ws.startup_costs) == 1
        assert cloned_ws.startup_costs[0]["item"] == "Cloud instances"

        # 3. Verify cloned knowledge items and links
        cloned_k_items = db.query(ProjectKnowledgeItem).filter(ProjectKnowledgeItem.project_id == cloned_id).all()
        assert len(cloned_k_items) == 2
        cloned_links = db.query(KnowledgeLink).filter(KnowledgeLink.project_id == cloned_id).all()
        assert len(cloned_links) == 1
        assert cloned_links[0].relationship == "supports"


def test_pdf_export_renders_enhanced_roadmap_tasks(enhanced_setup):
    p_id = enhanced_setup["project_id"]
    with SessionLocal() as db:
        project = db.query(Project).filter(Project.id == p_id).first()
        proj_dict = {
            "name": project.name,
            "stage": project.stage,
            "description": project.description,
            "industry": project.industry,
            "target_customers": project.target_customers,
            "goals": project.goals,
            "budget": project.budget
        }
        tasks = db.query(RoadmapTask).filter(RoadmapTask.project_id == p_id).all()
        tasks_list = [
            {
                "task_code": t.task_code,
                "phase": t.phase,
                "title": t.title,
                "start_date": t.start_date,
                "end_date": t.end_date,
                "timeline": t.timeline,
                "priority": t.priority,
                "status": t.status,
                "deliverables": t.deliverables,
                "branch_type": t.branch_type,
                "parent_outcome": t.parent_outcome,
                "definition_of_done": t.definition_of_done,
            }
            for t in tasks
        ]

        pdf_bytes = PDFService.generate_full_project_pdf(proj_dict, {}, tasks_list)
        assert pdf_bytes is not None
        assert len(pdf_bytes) > 500
        assert pdf_bytes.startswith(b"%PDF")

import json
import hashlib
import uuid
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.models.all_models import CopilotProposal, CopilotOperation, ModuleContent, ModuleVersion

client = TestClient(app)

def create_user_and_project():
    uid = uuid.uuid4().hex[:8]
    user_data = {
        "username": f"user_{uid}",
        "email": f"user_{uid}@example.com",
        "password": "Password123!",
        "confirm_password": "Password123!",
        "terms_accepted": True
    }
    resp = client.post("/api/auth/register", json=user_data)
    assert resp.status_code == 201, resp.text
    csrf = resp.json()["csrf_token"]

    proj_data = {
        "name": f"Copilot Project {uid}",
        "stage": "MVP",
        "industry": "Enterprise SaaS",
        "description": "Intelligent orchestration for distributed teams",
        "target_customers": "Engineering organizations",
        "goals": "Scale pilot customers"
    }
    proj_resp = client.post("/api/projects", json=proj_data, headers={"X-CSRF-Token": csrf})
    assert proj_resp.status_code == 201, proj_resp.text
    return proj_resp.json()["id"], csrf


def test_copilot_proposal_persistence_and_exact_application():
    project_id, csrf = create_user_and_project()
    headers = {"X-CSRF-Token": csrf}

    # 1. Generate BMC module
    gen_resp = client.post(
        f"/api/projects/{project_id}/modules/bmc/generate",
        json={"framework_type": "standard_bmc"},
        headers=headers
    )
    assert gen_resp.status_code == 200, gen_resp.text
    v1_id = gen_resp.json()["active_version_id"]
    v1_data = gen_resp.json()["data"]

    # 2. Propose change to BMC
    prop_resp = client.post(
        f"/api/projects/{project_id}/copilot/propose",
        json={
            "target_module": "bmc",
            "instruction": "Expand enterprise customer segments and compliance offerings"
        },
        headers=headers
    )
    assert prop_resp.status_code == 200, prop_resp.text
    prop_body = prop_resp.json()
    proposal_id = prop_body["id"]
    assert proposal_id is not None
    assert prop_body["status"] == "pending"
    assert "proposed_content" in prop_body

    # Verify DB persistence and source content fingerprint
    with SessionLocal() as db:
        prop_rec = db.query(CopilotProposal).filter(CopilotProposal.id == proposal_id).first()
        assert prop_rec is not None
        assert prop_rec.project_id == project_id
        assert prop_rec.status == "pending"
        expected_fp = hashlib.sha256(json.dumps(v1_data, sort_keys=True).encode()).hexdigest()
        assert prop_rec.source_content_fingerprint == expected_fp

    # 3. Apply exact approved proposal
    apply_resp = client.post(
        f"/api/projects/{project_id}/copilot/proposals/{proposal_id}/apply",
        headers=headers
    )
    assert apply_resp.status_code == 200, apply_resp.text
    apply_body = apply_resp.json()
    assert apply_body["success"] is True
    assert apply_body["proposal_id"] == proposal_id
    assert apply_body["version_number"] == 2
    v2_id = apply_body["version_id"]
    assert v2_id != v1_id

    # Verify database state: proposal is applied and linked to v2
    with SessionLocal() as db:
        prop_rec = db.query(CopilotProposal).filter(CopilotProposal.id == proposal_id).first()
        assert prop_rec.status == "applied"
        assert prop_rec.result_version_id == v2_id
        assert prop_rec.applied_at is not None

        # Verify active version in module is v2 and data matches exact proposal
        v2 = db.get(ModuleVersion, v2_id)
        assert v2.is_active is True
        assert v2.data == prop_body["proposed_content"]

    # 4. Repeated apply is idempotent
    reapply_resp = client.post(
        f"/api/projects/{project_id}/copilot/proposals/{proposal_id}/apply",
        headers=headers
    )
    assert reapply_resp.status_code == 200, reapply_resp.text
    reapply_body = reapply_resp.json()
    assert reapply_body["success"] is True
    assert reapply_body["version_id"] == v2_id


def test_copilot_proposal_stale_fingerprint_rejection():
    project_id, csrf = create_user_and_project()
    headers = {"X-CSRF-Token": csrf}

    # 1. Generate BMC
    client.post(
        f"/api/projects/{project_id}/modules/bmc/generate",
        json={"framework_type": "standard_bmc"},
        headers=headers
    )

    # 2. Propose change
    prop_resp = client.post(
        f"/api/projects/{project_id}/copilot/propose",
        json={"target_module": "bmc", "instruction": "Add subscription model"},
        headers=headers
    )
    assert prop_resp.status_code == 200
    proposal_id = prop_resp.json()["id"]

    # 3. Directly modify BMC to advance its state
    mod_resp = client.post(
        f"/api/projects/{project_id}/modules/bmc/modify",
        json={"instruction": "Add direct enterprise licensing and SLA tiers"},
        headers=headers
    )
    assert mod_resp.status_code == 200

    # 4. Attempt to apply the now-stale proposal -> must return 409 Conflict
    apply_resp = client.post(
        f"/api/projects/{project_id}/copilot/proposals/{proposal_id}/apply",
        headers=headers
    )
    assert apply_resp.status_code == 409, apply_resp.text
    assert "underlying module has changed" in apply_resp.json()["detail"].lower()


def test_copilot_proposal_expired_rejection():
    project_id, csrf = create_user_and_project()
    headers = {"X-CSRF-Token": csrf}

    client.post(
        f"/api/projects/{project_id}/modules/bmc/generate",
        json={"framework_type": "standard_bmc"},
        headers=headers
    )

    prop_resp = client.post(
        f"/api/projects/{project_id}/copilot/propose",
        json={"target_module": "bmc", "instruction": "Add marketplace dynamics"},
        headers=headers
    )
    proposal_id = prop_resp.json()["id"]

    # Artificially expire the proposal in DB
    with SessionLocal() as db:
        prop = db.query(CopilotProposal).filter(CopilotProposal.id == proposal_id).first()
        prop.expires_at = datetime.now(timezone.utc) - timedelta(minutes=10)
        db.commit()

    # Attempt apply -> must return 400 Bad Request
    apply_resp = client.post(
        f"/api/projects/{project_id}/copilot/proposals/{proposal_id}/apply",
        headers=headers
    )
    assert apply_resp.status_code == 400
    assert "expired" in apply_resp.json()["detail"].lower()


def test_copilot_chat_operation_ownership_and_immutability():
    project_id, csrf = create_user_and_project()
    headers = {"X-CSRF-Token": csrf}

    client_msg_id = f"test-msg-{uuid.uuid4().hex[:8]}"

    # Send message with client_msg_id
    send_resp = client.post(
        f"/api/projects/{project_id}/copilot",
        json={"message": "What are key risks for this business?", "client_msg_id": client_msg_id},
        headers=headers
    )
    assert send_resp.status_code == 200, send_resp.text
    body = send_resp.json()
    assert body["operation_status"] == "completed"

    with SessionLocal() as db:
        op = db.query(CopilotOperation).filter(
            CopilotOperation.project_id == project_id,
            CopilotOperation.client_msg_id == client_msg_id
        ).first()
        assert op is not None
        assert op.status == "completed"
        assert op.owner_attempt_id is not None
        original_attempt_id = op.owner_attempt_id

    # Verify idempotency on same message hash
    dup_resp = client.post(
        f"/api/projects/{project_id}/copilot",
        json={"message": "What are key risks for this business?", "client_msg_id": client_msg_id},
        headers=headers
    )
    assert dup_resp.status_code == 200
    assert dup_resp.json()["operation_status"] == "completed"

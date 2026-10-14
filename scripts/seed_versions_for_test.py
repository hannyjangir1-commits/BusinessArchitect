import sys
import os

# Change working directory to server so relative sqlite database url matches the running server
server_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "server"))
os.chdir(server_dir)
sys.path.insert(0, server_dir)

from app.db.session import SessionLocal
from app.models.all_models import ModuleContent, ModuleVersion, Project

def seed_versions(project_name: str):
    db = SessionLocal()
    try:
        # Find newest project with this name
        proj = db.query(Project).filter(Project.name == project_name).order_by(Project.created_at.desc()).first()
        if not proj:
            print(f"ERROR: Project '{project_name}' not found.")
            return False

        mod = db.query(ModuleContent).filter(
            ModuleContent.project_id == proj.id,
            ModuleContent.module_type == "bmc"
        ).first()

        if not mod:
            # Create module record if not already created
            mod = ModuleContent(
                project_id=proj.id,
                module_type="bmc"
            )
            db.add(mod)
            db.commit()
            db.refresh(mod)

        existing = db.query(ModuleVersion).filter(
            ModuleVersion.module_content_id == mod.id
        ).order_by(ModuleVersion.version_number).all()

        current_count = len(existing)
        print(f"Project ID: {proj.id}, current version count: {current_count}")

        base_data = existing[0].data if existing else {
            "company_name": project_name,
            "problem": ["Complex PCB trace routing"],
            "solution": ["AI synthesis"],
            "value_propositions": ["10x faster layout"],
            "customer_segments": ["Aerospace Hardware Engineers"],
            "channels": ["Direct enterprise sales"],
            "revenue_streams": ["Enterprise SaaS licenses"],
            "cost_structure": ["Compute, GPU infrastructure"],
            "key_metrics": ["Routing turnaround time"],
            "key_activities": ["Model training, synthesis"],
            "key_resources": ["Proprietary CAD datasets"],
            "key_partners": ["Foundry partners"]
        }

        for i in range(current_count + 1, 6):
            v = ModuleVersion(
                module_content_id=mod.id,
                version_number=i,
                version_name=f"BMC Snapshot V{i}",
                data=base_data,
                change_summary=f"Automated engineering iteration V{i}",
                is_active=False
            )
            db.add(v)
            print(f"Added version V{i}")

        db.commit()
        print("SUCCESS: 5 versions ready for testing conflict modal.")
        return True
    finally:
        db.close()

if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "Quantum PCB CAD Synthesizer"
    seed_versions(name)

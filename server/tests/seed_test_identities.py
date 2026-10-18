"""
Phase 5: Idempotent local test-data seeder.
Creates 9 distinct isolated test identities and projects for local and automated testing.
Safety rules:
- Strictly refuses execution in production environments.
- Uses test-only credentials and data.
- Idempotent and rerunnable.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.security import hash_password
from app.models.all_models import User, Project, ModuleContent, ModuleVersion, RoadmapTask, gen_id

TEST_PASSWORD = "TestIdentityPassword123!"

IDENTITIES_CONFIG = {
    "standard_owner": {
        "username": "test_standard_owner",
        "email": "test_standard_owner@localtest.internal",
        "role": "user",
        "projects": [
            {"name": "Alpha Idea Venture", "stage": "Idea", "industry": "Consumer Tech", "target_customers": "College students and young professionals", "description": "Early consumer mobile habit tracking and wellness planning concept", "budget": "$10,000"},
            {"name": "Beta MVP Solution", "stage": "MVP", "industry": "B2B SaaS", "target_customers": "Small and medium accounting firms", "description": "Working prototype for small business automated invoice reconciliation and billing", "budget": "$25,000"},
            {"name": "Gamma Post-Launch Platform", "stage": "Post-launch", "industry": "E-commerce", "target_customers": "Eco-conscious retail consumers and subscribers", "description": "Active web shop with paying monthly subscription customers and direct order delivery", "budget": "$50,000"},
            {"name": "Delta Growth Engine", "stage": "Growth", "industry": "Logistics", "target_customers": "Regional delivery fleet managers and dispatchers", "description": "Rapidly scaling delivery fleet optimization, route dispatch, and fuel telematics platform", "budget": "$100,000"}
        ]
    },
    "pcb_saas_owner": {
        "username": "test_pcb_saas_owner",
        "email": "test_pcb_saas_owner@localtest.internal",
        "role": "user",
        "projects": [
            {
                "name": "CircuitCraft AI",
                "stage": "Idea",
                "industry": "Electronics & EDA Software",
                "target_customers": "Electronics engineering students, hardware startups, and PCB design companies",
                "description": "Cloud-native collaborative EDA platform with automated PCB routing, IPC DRC checks, and real-time distributor component sourcing",
                "budget": "$50,000",
                "existing_stack": {"frontend": "React", "backend": "Python / FastAPI", "database": "PostgreSQL"}
            }
        ]
    },
    "non_technical_owner": {
        "username": "test_non_technical_owner",
        "email": "test_non_technical_owner@localtest.internal",
        "role": "user",
        "projects": [
            {
                "name": "Artisan Roast & Bakery Cafe",
                "stage": "MVP",
                "industry": "Food & Beverage / Retail Hospitality",
                "target_customers": "Local neighborhood residents, daily commuters, and specialty coffee enthusiasts",
                "description": "Physical brick-and-mortar artisanal coffee roastery with weekend sourdough bakery, local cafe seating, and local whole-bean subscription pickup",
                "budget": "$25,000",
                "existing_stack": {"pos": "Square POS", "payments": "Stripe Terminal"}
            }
        ]
    },
    "solo_developer": {
        "username": "test_solo_developer",
        "email": "test_solo_developer@localtest.internal",
        "role": "user",
        "projects": [
            {
                "name": "Global Multi-Tenant ERP Mesh",
                "stage": "Idea",
                "industry": "Enterprise Software",
                "target_customers": "Fortune 500 manufacturing corporations",
                "description": "Massive global ERP with real-time IoT supply chain telemetry, AI multi-currency forecasting, automated international customs reconciliation, and blockchain audit logs",
                "budget": "$5,000",
                "existing_stack": {}
            }
        ]
    },
    "org_owner": {
        "username": "test_org_owner",
        "email": "test_org_owner@localtest.internal",
        "role": "user",
        "projects": [
            {
                "name": "RegTech Compliance Hub",
                "stage": "Growth",
                "industry": "FinTech / Regulatory Compliance",
                "target_customers": "Regional credit unions and community banks",
                "description": "Automated SOC2, AML, and regulatory audit compliance management platform",
                "budget": "$150,000",
                "existing_stack": {"frontend": "React", "backend": "FastAPI", "database": "PostgreSQL"}
            }
        ]
    },
    "sparse_owner": {
        "username": "test_sparse_owner",
        "email": "test_sparse_owner@localtest.internal",
        "role": "user",
        "projects": [
            {
                "name": "Sparse Project X",
                "stage": "Idea",
                "industry": None,
                "target_customers": None,
                "description": "Just a raw spark of an idea without any detailed documentation yet",
                "budget": None,
                "existing_stack": {}
            }
        ]
    },
    "empty_user": {
        "username": "test_empty_user",
        "email": "test_empty_user@localtest.internal",
        "role": "user",
        "projects": []
    },
    "isolated_user": {
        "username": "test_isolated_user",
        "email": "test_isolated_user@localtest.internal",
        "role": "user",
        "projects": [
            {
                "name": "Isolated Private Project",
                "stage": "Idea",
                "industry": "Cybersecurity",
                "target_customers": "Internal Security Teams",
                "description": "Top secret security research sandbox",
                "budget": "$10,000",
                "existing_stack": {}
            }
        ]
    },
    "admin_identity": {
        "username": "test_admin_identity",
        "email": "test_admin_identity@localtest.internal",
        "role": "super_admin",
        "projects": []
    }
}

def seed_test_identities(db: Session) -> dict:
    """Idempotently seed the 9 Phase 5 test profiles."""
    if getattr(settings, "IS_PROD", False) or getattr(settings, "APP_ENV", "") == "production":
        raise RuntimeError("CRITICAL: Refusing to seed test identities into production environment.")

    created = {}
    hashed_pw = hash_password(TEST_PASSWORD)

    for profile_key, conf in IDENTITIES_CONFIG.items():
        user = db.query(User).filter(User.username == conf["username"]).first()
        if not user:
            user = User(
                id=gen_id("usr_"),
                username=conf["username"],
                email=conf["email"],
                hashed_password=hashed_pw,
                role=conf["role"],
                is_suspended=False
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            user.hashed_password = hashed_pw
            user.role = conf["role"]
            user.is_suspended = False
            db.commit()
            db.refresh(user)

        # Seed or update projects for this user
        existing_projects = {p.name: p for p in user.projects}
        for proj_conf in conf["projects"]:
            if proj_conf["name"] not in existing_projects:
                project = Project(
                    id=gen_id("prj_"),
                    user_id=user.id,
                    name=proj_conf["name"],
                    stage=proj_conf["stage"],
                    industry=proj_conf.get("industry"),
                    target_customers=proj_conf.get("target_customers"),
                    description=proj_conf.get("description"),
                    budget=proj_conf.get("budget"),
                    existing_stack=proj_conf.get("existing_stack", {})
                )
                db.add(project)
            else:
                p = existing_projects[proj_conf["name"]]
                p.stage = proj_conf["stage"]
                p.industry = proj_conf.get("industry")
                p.target_customers = proj_conf.get("target_customers")
                p.description = proj_conf.get("description")
                p.budget = proj_conf.get("budget")
        db.commit()
        db.refresh(user)
        created[profile_key] = user

    return created

def cleanup_test_identities(db: Session) -> int:
    """Safely remove test identities without touching non-test data."""
    if getattr(settings, "IS_PROD", False) or getattr(settings, "APP_ENV", "") == "production":
        raise RuntimeError("CRITICAL: Refusing to clean up in production environment.")

    usernames = [conf["username"] for conf in IDENTITIES_CONFIG.values()]
    deleted_count = db.query(User).filter(User.username.in_(usernames)).delete(synchronize_session=False)
    db.commit()
    return deleted_count

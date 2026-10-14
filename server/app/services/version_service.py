import threading
from typing import Optional, Dict, Any, List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.all_models import ModuleContent, ModuleVersion

MAX_VERSIONS_LIMIT = 5
_version_lock = threading.Lock()

class VersionService:
    @staticmethod
    def get_or_create_module(db: Session, project_id: str, module_type: str) -> ModuleContent:
        module = db.query(ModuleContent).filter(
            ModuleContent.project_id == project_id,
            ModuleContent.module_type == module_type
        ).first()

        if not module:
            module = ModuleContent(project_id=project_id, module_type=module_type)
            db.add(module)
            db.commit()
            db.refresh(module)

        return module

    @staticmethod
    def get_versions(db: Session, module_content_id: str) -> List[ModuleVersion]:
        return db.query(ModuleVersion).filter(
            ModuleVersion.module_content_id == module_content_id
        ).order_by(ModuleVersion.version_number.asc()).all()

    @staticmethod
    def save_new_version(
        db: Session,
        module: ModuleContent,
        data: Dict[str, Any],
        change_summary: Optional[str] = None,
        custom_name: Optional[str] = None
    ) -> ModuleVersion:
        """
        Save a new version.
        Enforces MAX_VERSIONS_LIMIT (5). If 5 already exist, raises 409 Conflict
        so the frontend can prompt the user to replace or delete an existing version.
        Guarantees strict concurrency protection via mutex lock.
        """
        with _version_lock:
            versions = VersionService.get_versions(db, module.id)
            if len(versions) >= MAX_VERSIONS_LIMIT:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "error": "VERSION_LIMIT_EXCEEDED",
                        "message": f"This section already has the maximum of {MAX_VERSIONS_LIMIT} saved versions. Choose a version to replace or delete.",
                        "existing_versions": [
                            {
                                "id": v.id,
                                "version_number": v.version_number,
                                "version_name": v.version_name,
                                "change_summary": v.change_summary,
                                "is_active": v.is_active,
                                "created_at": v.created_at.isoformat()
                            }
                            for v in versions
                        ]
                    }
                )

            # Deactivate previous active versions
            for v in versions:
                v.is_active = False

            next_number = (max([v.version_number for v in versions]) + 1) if versions else 1
            default_prefix = {
                "bmc": "BMC",
                "tech_stack": "Tech Stack",
                "idea_validator": "Validator",
                "market_research": "Market Research",
                "execution_roadmap": "Roadmap",
                "overview": "Overview"
            }.get(module.module_type, "Version")
            version_name = custom_name or f"{default_prefix} V{next_number}"

            new_version = ModuleVersion(
                module_content_id=module.id,
                version_number=next_number,
                version_name=version_name,
                data=data,
                change_summary=change_summary or f"Created {version_name}",
                is_active=True
            )
            db.add(new_version)
            db.commit()
            db.refresh(new_version)

            # Set as active version on module
            module.active_version_id = new_version.id
            db.commit()
            return new_version


    @staticmethod
    def resolve_conflict_and_replace(
        db: Session,
        module: ModuleContent,
        replace_version_id: str,
        new_data: Dict[str, Any],
        new_name: Optional[str] = None,
        change_summary: Optional[str] = None
    ) -> ModuleVersion:
        """User explicitly chosen version to replace when 5-version limit is reached."""
        with _version_lock:
            target = db.query(ModuleVersion).filter(
                ModuleVersion.id == replace_version_id,
                ModuleVersion.module_content_id == module.id
            ).first()

            if not target:
                raise HTTPException(status_code=404, detail="Target version to replace not found")

            # Deactivate all
            versions = VersionService.get_versions(db, module.id)
            for v in versions:
                v.is_active = False

            # Update target version in-place with new data and name
            target.data = new_data
            if new_name:
                target.version_name = new_name
            target.change_summary = change_summary or "Replaced existing version"
            target.is_active = True
            module.active_version_id = target.id

            db.commit()
            db.refresh(target)
            return target

    @staticmethod
    def rename_version(db: Session, module: ModuleContent, version_id: str, new_name: str) -> ModuleVersion:
        v = db.query(ModuleVersion).filter(
            ModuleVersion.id == version_id,
            ModuleVersion.module_content_id == module.id
        ).first()
        if not v:
            raise HTTPException(status_code=404, detail="Version not found in this module")
        v.version_name = new_name.strip()
        db.commit()
        db.refresh(v)
        return v

    @staticmethod
    def delete_version(db: Session, module: ModuleContent, version_id: str) -> bool:
        v = db.query(ModuleVersion).filter(
            ModuleVersion.id == version_id,
            ModuleVersion.module_content_id == module.id
        ).first()
        if not v:
            raise HTTPException(status_code=404, detail="Version not found")

        versions = VersionService.get_versions(db, module.id)
        if len(versions) <= 1:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete the only remaining version of this module."
            )

        was_active = v.is_active or (module.active_version_id == v.id)
        db.delete(v)
        db.flush()

        if was_active:
            remaining = [rem for rem in versions if rem.id != version_id]
            fallback = remaining[-1]
            fallback.is_active = True
            module.active_version_id = fallback.id

        db.commit()
        return True

    @staticmethod
    def restore_version(db: Session, module: ModuleContent, version_id: str) -> ModuleVersion:
        """Restores an older version by creating a new version with its data."""
        target = db.query(ModuleVersion).filter(
            ModuleVersion.id == version_id,
            ModuleVersion.module_content_id == module.id
        ).first()
        if not target:
            raise HTTPException(status_code=404, detail="Version to restore not found")

        return VersionService.save_new_version(
            db=db,
            module=module,
            data=target.data,
            change_summary=f"Restored from {target.version_name}",
            custom_name=f"Restored ({target.version_name})"
        )

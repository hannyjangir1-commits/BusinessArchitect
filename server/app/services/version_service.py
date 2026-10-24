import threading
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models.all_models import ModuleContent, ModuleVersion
from app.services.transaction_service import lock_record

MAX_VERSIONS_LIMIT = 5

# Striped mutex lock pool to serialize concurrent writes to the same module in-process
# without using an unbounded dict or blocking unrelated modules globally across the process.
# Uses RLock for re-entrancy when helpers call internal validation/repair methods.
_NUM_MODULE_LOCKS = 256
_MODULE_LOCKS = [threading.RLock() for _ in range(_NUM_MODULE_LOCKS)]


def get_module_lock(module_id: str) -> threading.Lock:
    """Retrieve the striped in-process mutex for a specific module ID."""
    return _MODULE_LOCKS[hash(str(module_id)) % _NUM_MODULE_LOCKS]


class VersionService:
    @staticmethod
    def _lock_module(db: Session, module: ModuleContent) -> ModuleContent:
        locked = lock_record(db, ModuleContent, module.id)
        if locked is None:
            raise HTTPException(
                status_code=409,
                detail="This module was deleted while the operation was running. Reload the project and try again."
            )
        return locked

    @staticmethod
    def assert_version_capacity(db: Session, module: ModuleContent, limit: int = MAX_VERSIONS_LIMIT) -> None:
        """
        Version-capacity preflight check (B08).
        Ensures a module has not reached the maximum version limit before invoking
        expensive provider or AI generation work.
        Returns the compatible 409 Conflict payload if limit is reached.
        """
        versions = VersionService.get_version_metadata(db, module.id)
        if len(versions) >= limit:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "VERSION_LIMIT_EXCEEDED",
                    "message": f"This section already has the maximum of {limit} saved versions. Choose a version to replace or delete.",
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

    @staticmethod
    def get_or_create_module(db: Session, project_id: str, module_type: str) -> ModuleContent:
        module = db.query(ModuleContent).filter(
            ModuleContent.project_id == project_id,
            ModuleContent.module_type == module_type
        ).first()

        if not module:
            module = ModuleContent(project_id=project_id, module_type=module_type)
            try:
                db.add(module)
                db.commit()
                db.refresh(module)
            except IntegrityError:
                db.rollback()
                module = db.query(ModuleContent).filter(
                    ModuleContent.project_id == project_id,
                    ModuleContent.module_type == module_type
                ).first()
                if not module:
                    raise

        return module

    @staticmethod
    def get_version_metadata(db: Session, module_content_id: str) -> List[ModuleVersion]:
        """
        Load version list metadata without loading the heavy 'data' JSON column.
        Reduces memory allocation, database I/O, and payload transfer during read paths.
        """
        from sqlalchemy.orm import load_only
        return db.query(ModuleVersion).options(
            load_only(
                ModuleVersion.id,
                ModuleVersion.module_content_id,
                ModuleVersion.version_number,
                ModuleVersion.version_name,
                ModuleVersion.change_summary,
                ModuleVersion.is_active,
                ModuleVersion.created_at,
            )
        ).filter(
            ModuleVersion.module_content_id == module_content_id
        ).order_by(ModuleVersion.version_number.asc()).all()

    @staticmethod
    def get_versions(db: Session, module_content_id: str, include_data: bool = True) -> List[ModuleVersion]:
        if not include_data:
            return VersionService.get_version_metadata(db, module_content_id)
        return db.query(ModuleVersion).filter(
            ModuleVersion.module_content_id == module_content_id
        ).order_by(ModuleVersion.version_number.asc()).all()

    @staticmethod
    def save_new_version(
        db: Session,
        module: ModuleContent,
        data: Dict[str, Any],
        change_summary: Optional[str] = None,
        custom_name: Optional[str] = None,
        commit: bool = True
    ) -> ModuleVersion:
        """
        Save a new version under module row lock.
        Enforces MAX_VERSIONS_LIMIT (5). If 5 already exist, raises 409 Conflict.
        Serialized per module via striped lock pool and PostgreSQL row-level lock.
        """
        lock = get_module_lock(module.id)
        with lock:
            try:
                # Acquire database row-level lock on the parent ModuleContent to serialize concurrent multi-process writes
                VersionService._lock_module(db, module)
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
                db.flush()

                # Set as active version on module in the same atomic transaction
                module.active_version_id = new_version.id
                if commit:
                    db.commit()
                    db.refresh(new_version)
                else:
                    db.flush()
                return new_version
            except Exception:
                if commit:
                    db.rollback()
                raise

    @staticmethod
    def resolve_conflict_and_replace(
        db: Session,
        module: ModuleContent,
        replace_version_id: str,
        new_data: Dict[str, Any],
        new_name: Optional[str] = None,
        change_summary: Optional[str] = None,
        commit: bool = True
    ) -> ModuleVersion:
        """
        User explicitly chosen version to replace when 5-version limit is reached.
        Preserves historical immutability: deletes the user-selected version to vacate
        a slot, then creates a new version record without mutating historical snapshots.
        """
        lock = get_module_lock(module.id)
        with lock:
            try:
                # Row lock on module row to serialize concurrent writes
                VersionService._lock_module(db, module)
                target = db.query(ModuleVersion).filter(
                    ModuleVersion.id == replace_version_id,
                    ModuleVersion.module_content_id == module.id
                ).first()

                if not target:
                    raise HTTPException(status_code=404, detail="Target version to replace not found")

                target_name = target.version_name

                # Deactivate all existing versions
                versions = VersionService.get_versions(db, module.id)
                next_num = max((v.version_number for v in versions), default=0) + 1
                for v in versions:
                    v.is_active = False

                # Delete the selected version to vacate slot (preserving remaining snapshots untouched)
                db.delete(target)
                db.flush()

                # Create brand-new version record
                default_prefix = {
                    "bmc": "BMC",
                    "tech_stack": "Tech Stack",
                    "idea_validator": "Validator",
                    "market_research": "Market Research",
                    "execution_roadmap": "Roadmap",
                    "overview": "Overview"
                }.get(module.module_type, "Version")
                v_name = new_name or f"{default_prefix} V{next_num}"

                new_ver = ModuleVersion(
                    module_content_id=module.id,
                    version_number=next_num,
                    version_name=v_name,
                    data=new_data,
                    change_summary=change_summary or f"Created {v_name} (replaced {target_name})",
                    is_active=True
                )
                db.add(new_ver)
                db.flush()

                module.active_version_id = new_ver.id
                if commit:
                    db.commit()
                    db.refresh(new_ver)
                else:
                    db.flush()
                return new_ver
            except Exception:
                if commit:
                    db.rollback()
                raise

    @staticmethod
    def rename_version(db: Session, module: ModuleContent, version_id: str, new_name: str) -> ModuleVersion:
        lock = get_module_lock(module.id)
        with lock:
            try:
                VersionService._lock_module(db, module)
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
            except Exception:
                db.rollback()
                raise

    @staticmethod
    def delete_version(db: Session, module: ModuleContent, version_id: str, commit: bool = True) -> bool:
        lock = get_module_lock(module.id)
        with lock:
            try:
                VersionService._lock_module(db, module)
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

                if commit:
                    db.commit()
                else:
                    db.flush()
                return True
            except Exception:
                if commit:
                    db.rollback()
                raise

    @staticmethod
    def restore_version(db: Session, module: ModuleContent, version_id: str, commit: bool = True) -> ModuleVersion:
        """Restores an older version by setting it as active without creating a duplicate version."""
        lock = get_module_lock(module.id)
        with lock:
            try:
                VersionService._lock_module(db, module)
                target = db.query(ModuleVersion).filter(
                    ModuleVersion.id == version_id,
                    ModuleVersion.module_content_id == module.id
                ).first()
                if not target:
                    raise HTTPException(status_code=404, detail="Version to restore not found")

                # Deactivate all versions in this module
                all_versions = VersionService.get_versions(db, module.id)
                for v in all_versions:
                    v.is_active = (v.id == target.id)

                module.active_version_id = target.id
                if commit:
                    db.commit()
                    db.refresh(target)
                else:
                    db.flush()
                return target
            except Exception:
                if commit:
                    db.rollback()
                raise

    @staticmethod
    def repair_active_version_for_module(db: Session, module: ModuleContent) -> bool:
        """
        Transactional repair for broken active version state (Fix B06).
        Invariants:
        1. If module has versions, exactly one version is active and matches module.active_version_id.
        2. Valid restored older versions MUST BE PRESERVED.
        3. If module has 0 versions, active_version_id must be None.
        Returns True if a repair mutation was performed, False if already healthy.
        """
        lock = get_module_lock(module.id)
        with lock:
            VersionService._lock_module(db, module)
            versions = db.query(ModuleVersion).filter(
                ModuleVersion.module_content_id == module.id
            ).order_by(ModuleVersion.version_number.asc()).all()

            if not versions:
                if module.active_version_id is not None:
                    module.active_version_id = None
                    return True
                return False

            # Check if current pointer matches a valid version belonging to this module
            target = next((v for v in versions if v.id == module.active_version_id), None)

            if target is not None:
                # Valid pointer exists! PRESERVE IT (even if it's an older restored version).
                # Only repair mismatched is_active flags if any.
                flags_changed = False
                for v in versions:
                    expected_active = (v.id == target.id)
                    if v.is_active != expected_active:
                        v.is_active = expected_active
                        flags_changed = True
                return flags_changed

            # Pointer is missing (None) or invalid (points to non-existent or foreign module version).
            # Fallback selection:
            # If exactly one version has is_active == True, use it as fallback.
            # Otherwise, use the newest version (highest version_number).
            active_flags = [v for v in versions if v.is_active]
            if len(active_flags) == 1:
                chosen = active_flags[0]
            else:
                chosen = max(versions, key=lambda v: (v.version_number, v.created_at or datetime.min))

            module.active_version_id = chosen.id
            for v in versions:
                v.is_active = (v.id == chosen.id)
            return True

    @staticmethod
    def prune_excess_versions_for_module(db: Session, module: ModuleContent, limit: int = MAX_VERSIONS_LIMIT) -> int:
        """
        Prune excess versions beyond `limit` while strictly guaranteeing (Fix P07):
        - The active version is NEVER deleted (even if it is the oldest version V1).
        - Up to `limit - 1` newest other versions are preserved.
        - Deletes only unneeded older versions.
        - Returns the count of deleted versions.
        """
        lock = get_module_lock(module.id)
        with lock:
            VersionService._lock_module(db, module)
            # Ensure active version state is coherent first
            VersionService.repair_active_version_for_module(db, module)

            versions = db.query(ModuleVersion).filter(
                ModuleVersion.module_content_id == module.id
            ).order_by(ModuleVersion.version_number.asc()).all()

            if len(versions) <= limit:
                return 0

            active_id = module.active_version_id
            active_ver = next((v for v in versions if v.id == active_id), None)

            # Build keep set:
            # 1. Guarantee active version is retained
            # 2. Fill remaining slots up to limit with the newest other versions (sorted by version_number desc)
            keep_set = set()
            if active_ver:
                keep_set.add(active_ver)
                other_versions = [v for v in versions if v.id != active_id]
                other_versions.sort(key=lambda v: (v.version_number, v.created_at or datetime.min), reverse=True)
                slots_remaining = limit - 1
                keep_set.update(other_versions[:slots_remaining])
            else:
                sorted_versions = sorted(versions, key=lambda v: (v.version_number, v.created_at or datetime.min), reverse=True)
                keep_set.update(sorted_versions[:limit])
                module.active_version_id = sorted_versions[0].id
                for v in versions:
                    v.is_active = (v.id == sorted_versions[0].id)

            to_delete = [v for v in versions if v not in keep_set]
            deleted_count = 0
            for v in to_delete:
                db.delete(v)
                deleted_count += 1

            db.flush()
            return deleted_count

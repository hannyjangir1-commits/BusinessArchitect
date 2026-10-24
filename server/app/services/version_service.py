import copy
import threading
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from fastapi import HTTPException, status
from sqlalchemy import inspect
from sqlalchemy.orm import Session, load_only
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.exc import IntegrityError
from app.models.all_models import ModuleContent, ModuleVersion, Project
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
    def _get_authoritative_versions(
        db: Session,
        module_content_id: str,
        include_data: bool = False
    ) -> List[ModuleVersion]:
        """
        Query versions for module_content_id while guaranteeing authoritative database state.

        Contract:
        1. Targeted refresh: does not expire the entire session or discard pending caller changes
           on unrelated models.
        2. Inspects SQLAlchemy identity map for persistent ModuleVersion instances belonging to this module.
           - For instances with caller modifications (db.is_modified(v) is True), caller's dirty
             attributes are explicitly tracked and preserved while clean attributes are refreshed.
           - For clean instances, attributes are expired so populate_existing reloads authoritative DB state.
        3. When include_data is False, loads metadata only (deferring large 'data' JSON payload).
        """
        cached_versions = [
            obj for obj in db.identity_map.values()
            if isinstance(obj, ModuleVersion) and getattr(obj, "module_content_id", None) == module_content_id
        ]

        dirty_state_map = {}
        for obj in cached_versions:
            if db.is_modified(obj):
                ins = inspect(obj)
                dirty_attrs = {}
                for attr in ins.attrs:
                    hist = attr.history
                    if hist.has_changes():
                        dirty_attrs[attr.key] = copy.deepcopy(getattr(obj, attr.key))
                dirty_state_map[obj.id] = dirty_attrs
            else:
                db.expire(obj)

        query = db.query(ModuleVersion).filter(ModuleVersion.module_content_id == module_content_id)
        if not include_data:
            query = query.options(
                load_only(
                    ModuleVersion.id,
                    ModuleVersion.module_content_id,
                    ModuleVersion.version_number,
                    ModuleVersion.version_name,
                    ModuleVersion.change_summary,
                    ModuleVersion.is_active,
                    ModuleVersion.created_at,
                )
            )

        versions = query.populate_existing().order_by(ModuleVersion.version_number.asc()).all()

        for v in versions:
            if v.id in dirty_state_map:
                for k, val in dirty_state_map[v.id].items():
                    setattr(v, k, val)
                    flag_modified(v, k)

        return versions

    @staticmethod
    def sync_roadmap_working_tasks_to_active_version(
        db: Session,
        module: ModuleContent,
        project: Optional[Project] = None
    ) -> None:
        """
        Reconcile the relational roadmap task graph to match the active version snapshot.
        Atomically preserves retained work, canonical codes, and schedule integrity.
        Raises IncompatibleTaskGraphError / HTTPException on graph conflicts or malformed data,
        causing complete caller transaction rollback.
        """
        if module.module_type not in ("execution_roadmap", "detailed_roadmap"):
            return

        if not module.active_version_id:
            return

        if project is None:
            project = db.query(Project).filter(Project.id == module.project_id).first()
            if not project:
                return

        active_version = db.query(ModuleVersion).filter(
            ModuleVersion.id == module.active_version_id,
            ModuleVersion.module_content_id == module.id
        ).populate_existing().first()

        if not active_version:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Active roadmap version record not found."
            )

        if not isinstance(active_version.data, dict) or "tasks" not in active_version.data or not isinstance(active_version.data["tasks"], list):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Active roadmap version data must contain an explicit 'tasks' list."
            )

        from app.services.roadmap_service import RoadmapDomainService
        canonical_tasks = RoadmapDomainService.canonicalize_incoming_tasks(
            db, project, active_version.data["tasks"]
        )
        RoadmapDomainService.reconcile_roadmap_tasks(db, project, canonical_tasks)

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
                VersionService._lock_module(db, module)
                versions = VersionService._get_authoritative_versions(db, module.id, include_data=False)
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

                for v in versions:
                    v.is_active = False
                    flag_modified(v, "is_active")

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
                VersionService._lock_module(db, module)
                versions = VersionService._get_authoritative_versions(db, module.id, include_data=False)
                target = next((v for v in versions if v.id == replace_version_id), None)

                if not target:
                    raise HTTPException(status_code=404, detail="Target version to replace not found")

                target_name = target.version_name
                next_num = max((v.version_number for v in versions), default=0) + 1
                for v in versions:
                    v.is_active = False
                    flag_modified(v, "is_active")

                db.delete(target)
                db.flush()

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

                if module.module_type in ("execution_roadmap", "detailed_roadmap") and isinstance(new_data, dict) and "tasks" in new_data:
                    VersionService.sync_roadmap_working_tasks_to_active_version(db, module)

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
                ).populate_existing().first()
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
                versions = VersionService._get_authoritative_versions(db, module.id, include_data=True)
                v = next((ver for ver in versions if ver.id == version_id), None)
                if not v:
                    raise HTTPException(status_code=404, detail="Version not found")

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
                    fallback = max(remaining, key=lambda rem: (rem.version_number, rem.created_at or datetime.min, rem.id))
                    fallback.is_active = True
                    flag_modified(fallback, "is_active")
                    for rem in remaining:
                        if rem.id != fallback.id:
                            rem.is_active = False
                            flag_modified(rem, "is_active")
                    module.active_version_id = fallback.id

                    if module.module_type in ("execution_roadmap", "detailed_roadmap"):
                        VersionService.sync_roadmap_working_tasks_to_active_version(db, module)
                else:
                    active_ver = next((ver for ver in versions if ver.id == module.active_version_id and ver.id != version_id), None)
                    if active_ver:
                        active_ver.is_active = True
                        flag_modified(active_ver, "is_active")

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
                all_versions = VersionService._get_authoritative_versions(db, module.id, include_data=True)
                target = next((v for v in all_versions if v.id == version_id), None)
                if not target:
                    raise HTTPException(status_code=404, detail="Version to restore not found")

                for v in all_versions:
                    expected = (v.id == target.id)
                    v.is_active = expected
                    flag_modified(v, "is_active")

                module.active_version_id = target.id

                if module.module_type in ("execution_roadmap", "detailed_roadmap"):
                    VersionService.sync_roadmap_working_tasks_to_active_version(db, module)

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
    def repair_active_version_for_module(db: Session, module: ModuleContent, sync_tasks: bool = True) -> bool:
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
            versions = VersionService._get_authoritative_versions(db, module.id, include_data=False)

            if not versions:
                if module.active_version_id is not None:
                    module.active_version_id = None
                    db.flush()
                    return True
                return False

            target = next((v for v in versions if v.id == module.active_version_id), None)

            if target is not None:
                flags_changed = False
                for v in versions:
                    expected_active = (v.id == target.id)
                    if v.is_active != expected_active:
                        v.is_active = expected_active
                        flag_modified(v, "is_active")
                        flags_changed = True
                if flags_changed:
                    db.flush()
                return flags_changed

            active_flags = [v for v in versions if v.is_active]
            if len(active_flags) == 1:
                chosen = active_flags[0]
            else:
                chosen = max(versions, key=lambda v: (v.version_number, v.created_at or datetime.min, v.id))

            module.active_version_id = chosen.id
            for v in versions:
                v.is_active = (v.id == chosen.id)
                flag_modified(v, "is_active")
            db.flush()

            if sync_tasks and module.module_type in ("execution_roadmap", "detailed_roadmap"):
                VersionService.sync_roadmap_working_tasks_to_active_version(db, module)
            return True

    @staticmethod
    def prune_excess_versions_for_module(
        db: Session,
        module: ModuleContent,
        limit: int = MAX_VERSIONS_LIMIT,
        sync_tasks: bool = True
    ) -> int:
        """
        Prune excess versions beyond `limit` while strictly guaranteeing (Fix P07):
        - The active version is NEVER deleted (even if it is the oldest version V1).
        - Up to `limit - 1` newest other versions are preserved.
        - Deletes only unneeded older versions.
        - Validates limit is a positive integer >= 1.
        - Returns the count of deleted versions.
        """
        if not isinstance(limit, int) or limit < 1:
            raise ValueError(f"limit must be a positive integer >= 1, got {limit}")

        lock = get_module_lock(module.id)
        with lock:
            VersionService._lock_module(db, module)
            VersionService.repair_active_version_for_module(db, module, sync_tasks=sync_tasks)

            versions = VersionService._get_authoritative_versions(db, module.id, include_data=False)

            if len(versions) <= limit:
                return 0

            active_id = module.active_version_id
            active_ver = next((v for v in versions if v.id == active_id), None)

            keep_set = set()
            if active_ver:
                keep_set.add(active_ver)
                other_versions = [v for v in versions if v.id != active_id]
                other_versions.sort(key=lambda v: (v.version_number, v.created_at or datetime.min, v.id), reverse=True)
                slots_remaining = limit - 1
                keep_set.update(other_versions[:slots_remaining])
            else:
                sorted_versions = sorted(versions, key=lambda v: (v.version_number, v.created_at or datetime.min, v.id), reverse=True)
                keep_set.update(sorted_versions[:limit])
                module.active_version_id = sorted_versions[0].id
                for v in versions:
                    v.is_active = (v.id == sorted_versions[0].id)
                    flag_modified(v, "is_active")
                if sync_tasks and module.module_type in ("execution_roadmap", "detailed_roadmap"):
                    VersionService.sync_roadmap_working_tasks_to_active_version(db, module)

            to_delete = [v for v in versions if v not in keep_set]
            deleted_count = 0
            for v in to_delete:
                db.delete(v)
                deleted_count += 1

            db.flush()
            return deleted_count

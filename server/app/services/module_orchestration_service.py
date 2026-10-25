"""Application orchestration service for two-stage module generation, validation, and persistence."""
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.telemetry import record_ai_operation, record_analytics_event
from app.db.session import SessionLocal
from app.models.all_models import Project, ModuleContent, ModuleVersion, User
from app.schemas.modules import (
    BMCData, TechStackData, IdeaValidatorData, MarketResearchData,
    ExecutionRoadmapData, RoadmapPlanningRequest, TechStackPlanningRequest, GenerationBrief
)
from app.services.version_service import VersionService
from app.services.project_context_service import read_project_context, project_fingerprint
from app.services.roadmap_service import RoadmapDomainService
from app.services.task_graph_validator import project_first_lock
from app.ai.gemini_service import ai_service

VALIDATION_MODELS = {
    "bmc": BMCData,
    "tech_stack": TechStackData,
    "idea_validator": IdeaValidatorData,
    "market_research": MarketResearchData,
    "execution_roadmap": ExecutionRoadmapData,
    "detailed_roadmap": ExecutionRoadmapData,
}


class ModuleOrchestrationService:
    @staticmethod
    def validate_module_payload(module_type: str, data: Dict[str, Any]) -> None:
        if not isinstance(data, dict):
            raise ValueError("Module payload must be a structured dictionary.")
        model_cls = VALIDATION_MODELS.get(module_type)
        if not model_cls:
            raise HTTPException(status_code=404, detail=f"Unsupported module schema: {module_type}")
        model_cls.model_validate(data)

    @classmethod
    def execute_module_generation(
        cls,
        db: Session,
        project: Project,
        module: ModuleContent,
        module_type: str,
        planning_inputs: Optional[RoadmapPlanningRequest | TechStackPlanningRequest] = None,
        project_dict: Optional[Dict[str, Any]] = None,
    ) -> Tuple[ModuleVersion, Dict[str, Any]]:
        # Stage 0: Version-capacity preflight
        # Check capacity BEFORE reading context, building briefs, or invoking AI provider
        VersionService.assert_version_capacity(db, module)

        t0 = time.time()
        project_id = project.id
        user_id = project.user_id
        module_id = module.id
        project_fp = project_fingerprint(project)
        proj_info = dict(project_dict or {})
        cross_ctx, context_sources = read_project_context(db, project_id, exclude_module=module_type)
        proj_info["context_sources"] = context_sources

        planning_dict = None
        if module_type in ("execution_roadmap", "detailed_roadmap", "tech_stack"):
            planning = planning_inputs or (RoadmapPlanningRequest() if module_type != "tech_stack" else TechStackPlanningRequest())
            planning_dict = planning.model_dump(mode="json")
        else:
            planning = None

        # Release the checked-out database connection before calling the external provider
        db.close()

        # Stage 1: Private server-side generation brief
        if module_type in {"bmc", "tech_stack", "idea_validator", "market_research", "execution_roadmap", "detailed_roadmap"} and not ai_service._configured_api_keys():
            brief = ai_service.build_offline_generation_brief(proj_info, module_type)
        else:
            brief = ai_service.build_generation_brief(
                proj_info,
                module_type,
                cross_module_context=cross_ctx,
                planning_inputs=planning_dict,
            )

        retry_intent = {
            "module_type": module_type,
            "operation_type": "generate",
            "planning_inputs": planning_dict,
        }

        # Stage 2: Module synthesis dispatch (Zero checked-out connections or write locks held)
        from app.core.diagnostics import record_stage
        try:
            with record_stage("provider_call"):
                if module_type == "bmc":
                    generated = ai_service.generate_bmc(proj_info, brief, cross_module_context=cross_ctx)
                    data_dict = generated.model_dump()
                elif module_type == "tech_stack":
                    generated = ai_service.generate_tech_stack(proj_info, brief, cross_module_context=cross_ctx, planning_inputs=planning_dict)
                    data_dict = generated.model_dump()
                    data_dict["planning_inputs"] = planning_dict or {}
                elif module_type == "idea_validator":
                    generated = ai_service.generate_idea_validator(proj_info, brief, cross_module_context=cross_ctx)
                    data_dict = generated.model_dump()
                elif module_type == "market_research":
                    generated = ai_service.generate_market_research(proj_info, brief, cross_module_context=cross_ctx)
                    data_dict = generated.model_dump()
                elif module_type in ("execution_roadmap", "detailed_roadmap"):
                    roadmap_raw = ai_service.generate_roadmap(proj_info, planning_dict, brief, cross_module_context=cross_ctx)
                    data_dict = RoadmapDomainService.normalize_roadmap_schedule(roadmap_raw, planning)
                    data_dict["planning_inputs"] = planning_dict
                    if "feasibility_evaluation" in roadmap_raw and "feasibility_evaluation" not in data_dict:
                        data_dict["feasibility_evaluation"] = roadmap_raw["feasibility_evaluation"]
                else:
                    raise HTTPException(status_code=400, detail=f"Unsupported module type: {module_type}")

            # Attach provenance context metadata
            data_dict["context_metadata"] = {
                "stage": proj_info.get("stage"),
                "industry": proj_info.get("industry"),
                "budget": proj_info.get("budget"),
                "technical_depth": brief.technical_depth,
                "brief_summary": brief.venture_summary,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "cross_modules_used": list(cross_ctx),
                "project_fingerprint": project_fp,
                "source_versions": context_sources,
            }

            # Pre-persistence structural validation
            cls.validate_module_payload(module_type, data_dict)
        except HTTPException:
            raise
        except Exception as e:
            dur_ms = int((time.time() - t0) * 1000)
            terminal_provider_error = ai_service._terminal_provider_error_message(e)
            raw_err = str(e)
            err_msg = terminal_provider_error or "An unexpected internal error occurred during generation."
            err_cat = (
                "provider_error" if terminal_provider_error
                else ("timeout" if "timeout" in raw_err.lower()
                else ("parse_error" if "json" in raw_err.lower() or "validation" in raw_err.lower()
                else "api_error"))
            )
            try:
                with SessionLocal() as telemetry_db:
                    record_ai_operation(
                        telemetry_db,
                        user_id=user_id,
                        project_id=project_id,
                        module_type=module_type,
                        operation_type="generate",
                        model_name=settings.GEMINI_MODEL,
                        duration_ms=dur_ms,
                        status="timeout" if "timeout" in raw_err.lower() else "failed",
                        error_category=err_cat,
                        error_message=err_msg,
                        structured_validation_passed=False,
                        persistence_status="failed",
                        is_retryable=terminal_provider_error is None,
                        retry_context=retry_intent,
                    )
                    telemetry_db.commit()
            except Exception:
                pass
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Generation failed: {err_msg}",
            ) from e

        # Stage 3: Atomic save under short persistence transaction and project-first lock
        with SessionLocal(expire_on_commit=False) as persist_db:
            p_user = persist_db.query(User).filter(User.id == user_id).first()
            if not p_user or p_user.is_suspended:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User account is suspended or no longer active."
                )

            p_proj = persist_db.query(Project).filter(Project.id == project_id).first()
            if not p_proj:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Project was deleted while generation was in progress."
                )
            if p_proj.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Project ownership changed or access revoked."
                )

            p_mod = persist_db.query(ModuleContent).filter(
                ModuleContent.id == module_id,
                ModuleContent.project_id == project_id
            ).first()
            if not p_mod:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Module was deleted while generation was in progress."
                )

            with project_first_lock(persist_db, project_id, p_mod.id):
                if p_mod.module_type == "detailed_roadmap":
                    p_mod.module_type = "execution_roadmap"
                VersionService.assert_version_capacity(persist_db, p_mod)

                if module_type in ("execution_roadmap", "detailed_roadmap"):
                    if "tasks" not in data_dict or not isinstance(data_dict["tasks"], list):
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Roadmap payload missing 'tasks' list."
                        )
                    canonical_tasks = RoadmapDomainService.canonicalize_incoming_tasks(
                        persist_db, p_proj, data_dict["tasks"]
                    )
                    data_dict = dict(data_dict)
                    data_dict["tasks"] = canonical_tasks

                new_ver = VersionService.save_new_version(
                    db=persist_db,
                    module=p_mod,
                    data=data_dict,
                    change_summary="Initial blueprint generation",
                    commit=False,
                )

                if module_type in ("execution_roadmap", "detailed_roadmap"):
                    RoadmapDomainService.reconcile_roadmap_tasks(persist_db, p_proj, data_dict["tasks"])

                persist_db.commit()
                persist_db.refresh(new_ver)
                all_versions = VersionService.get_versions(persist_db, p_mod.id)
                setattr(new_ver, "_cached_versions", all_versions)

            dur_ms = int((time.time() - t0) * 1000)
            record_ai_operation(
                persist_db,
                user_id=user_id,
                project_id=project_id,
                module_type=module_type,
                operation_type="generate",
                model_name=settings.GEMINI_MODEL,
                duration_ms=dur_ms,
                status="success",
                structured_validation_passed=True,
                persistence_status="persisted",
                retry_context=retry_intent,
            )
            record_analytics_event(
                persist_db,
                user_id=user_id,
                project_id=project_id,
                event_name=f"{module_type}_generated",
            )
            persist_db.commit()

        return new_ver, data_dict

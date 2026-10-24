"""Application orchestration service for two-stage module generation, validation, and persistence."""
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.telemetry import record_ai_operation, record_analytics_event
from app.models.all_models import Project, ModuleContent, ModuleVersion
from app.schemas.modules import (
    BMCData, TechStackData, IdeaValidatorData, MarketResearchData,
    ExecutionRoadmapData, RoadmapPlanningRequest, TechStackPlanningRequest, GenerationBrief
)
from app.services.version_service import VersionService
from app.services.project_context_service import read_project_context, project_fingerprint
from app.services.roadmap_service import RoadmapDomainService
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
        # Stage 0: Version-capacity preflight (Fix B08)
        # Check capacity BEFORE reading context, building briefs, or invoking AI provider
        VersionService.assert_version_capacity(db, module)

        t0 = time.time()
        proj_info = dict(project_dict or {})
        cross_ctx, context_sources = read_project_context(db, project.id, exclude_module=module_type)
        proj_info["context_sources"] = context_sources

        try:
            planning_dict = None
            if module_type in ("execution_roadmap", "detailed_roadmap", "tech_stack"):
                planning = planning_inputs or (RoadmapPlanningRequest() if module_type != "tech_stack" else TechStackPlanningRequest())
                planning_dict = planning.model_dump(mode="json")

            # Stage 1: Private server-side generation brief. The planning modules
            # support explicitly labeled offline baselines when credentials are
            # absent; scoped modifications and copilot still require live generation.
            if module_type in {"bmc", "tech_stack", "idea_validator", "market_research", "execution_roadmap", "detailed_roadmap"} and not ai_service._configured_api_keys():
                brief = ai_service.build_offline_generation_brief(proj_info, module_type)
            else:
                brief = ai_service.build_generation_brief(
                    proj_info,
                    module_type,
                    cross_module_context=cross_ctx,
                    planning_inputs=planning_dict,
                )

            # Stage 2: Module synthesis dispatch
            from app.core.diagnostics import record_stage
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
                "project_fingerprint": project_fingerprint(project),
                "source_versions": context_sources,
            }

            # Pre-persistence structural validation
            cls.validate_module_payload(module_type, data_dict)

            # Atomic save under project-first lock protocol
            from app.services.task_graph_validator import project_first_lock
            with project_first_lock(db, project.id, module.id):
                new_ver = VersionService.save_new_version(
                    db=db,
                    module=module,
                    data=data_dict,
                    change_summary="Initial blueprint generation",
                    commit=False,
                )

                if module_type in ("execution_roadmap", "detailed_roadmap"):
                    tasks_data = data_dict.get("tasks", [])
                    RoadmapDomainService.reconcile_roadmap_tasks(db, project, tasks_data)

                db.commit()
                db.refresh(new_ver)

            dur_ms = int((time.time() - t0) * 1000)
            record_ai_operation(
                db,
                user_id=project.user_id,
                project_id=project.id,
                module_type=module_type,
                operation_type="generate",
                model_name=settings.GEMINI_MODEL,
                duration_ms=dur_ms,
                status="success",
                structured_validation_passed=True,
                persistence_status="persisted",
            )
            record_analytics_event(
                db,
                user_id=project.user_id,
                project_id=project.id,
                event_name=f"{module_type}_generated",
            )
            return new_ver, data_dict

        except HTTPException:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            dur_ms = int((time.time() - t0) * 1000)
            terminal_provider_error = ai_service._terminal_provider_error_message(e)
            err_msg = terminal_provider_error or str(e)
            err_cat = (
                "provider_error" if terminal_provider_error
                else ("timeout" if "timeout" in err_msg.lower()
                else ("parse_error" if "json" in err_msg.lower() or "validation" in err_msg.lower()
                else "api_error"))
            )
            record_ai_operation(
                db,
                user_id=project.user_id,
                project_id=project.id,
                module_type=module_type,
                operation_type="generate",
                model_name=settings.GEMINI_MODEL,
                duration_ms=dur_ms,
                status="timeout" if "timeout" in err_msg.lower() else "failed",
                error_category=err_cat,
                error_message=err_msg,
                structured_validation_passed=False,
                persistence_status="failed",
                is_retryable=terminal_provider_error is None,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Generation failed: {err_msg}",
            ) from e

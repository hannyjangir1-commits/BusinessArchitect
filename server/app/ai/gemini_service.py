import json
import logging
import re
from datetime import date, datetime
from typing import Dict, Any, Tuple, List, Optional
from google import genai
from google.genai import types
from app.core.config import settings
from app.schemas.modules import (
    GenerationBrief, BMCData, TechStackData, TechItem,
    IdeaValidatorData, ValidationRisk, ValidationExperiment,
    MarketResearchData, CompetitorProfile, ResearchSource,
    ExecutionRoadmapData, RoadmapPhase, RoadmapTaskItem, RoadmapFeasibilityEvaluation
)
from app.services.system_setting_service import get_setting_int
from app.ai.prompts import (
    BRIEF_SYSTEM_PROMPT, BMC_SYSTEM_PROMPT, TECH_STACK_SYSTEM_PROMPT,
    IDEA_VALIDATOR_SYSTEM_PROMPT, MARKET_RESEARCH_SYSTEM_PROMPT,
    ROADMAP_SYSTEM_PROMPT, SECTION_MODIFICATION_SYSTEM_PROMPT, COPILOT_SYSTEM_PROMPT
)

logger = logging.getLogger(__name__)

MODEL_CANDIDATES = [
    "gemini-3.5-flash-lite",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3-flash-preview",
    "gemini-3.8-flash"
]

NON_TECHNICAL_INDUSTRIES = {
    "retail", "cafe", "restaurant", "food & beverage", "hospitality",
    "beauty & wellness", "fitness & gym", "craft & handmade", "cleaning & home services",
    "consulting & coaching", "real estate", "construction", "event planning"
}

class GeminiAIService:
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY

    def _get_client(self) -> genai.Client:
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not configured in backend environment.")

        timeout_s = 60
        max_retries = 3
        try:
            from app.db.session import SessionLocal
            with SessionLocal() as s:
                timeout_s = get_setting_int(s, "ai_timeout_seconds", 60)
                max_retries = get_setting_int(s, "ai_max_retries", 3)
        except Exception as e:
            logger.debug("Could not read dynamic AI settings from DB, using defaults: %s", str(e))

        total_attempts = max(1, 1 + max_retries)
        http_options = types.HttpOptions(
            timeout=timeout_s * 1000,
            retry_options=types.HttpRetryOptions(
                attempts=total_attempts,
                initial_delay=1.0,
                max_delay=5.0,
                # A quota/rate-limit response is terminal for this request. Retrying it
                # for every candidate model multiplies provider calls without helping.
                http_status_codes=[503, 500]
            )
        )
        return genai.Client(api_key=self.api_key, http_options=http_options)

    def _get_candidate_models(self) -> List[str]:
        candidates = []
        configured = getattr(settings, "GEMINI_MODEL", "").strip()
        if configured:
            candidates.append(configured)
        for m in MODEL_CANDIDATES:
            if m not in candidates:
                candidates.append(m)
        return candidates

    @staticmethod
    def _terminal_provider_error_message(error: Exception) -> Optional[str]:
        """Return a safe, actionable message for provider errors that retries cannot fix."""
        code = getattr(error, "code", None) or getattr(error, "status_code", None)
        try:
            code = int(code)
        except (TypeError, ValueError):
            code = None

        error_text = str(error).lower()
        if code == 429 or any(marker in error_text for marker in ("resource_exhausted", "quota", "rate limit", "http 429")):
            return (
                "The configured generation provider is rate-limited or its quota is exhausted. "
                "Check the provider account's usage and billing limits, then retry after the limit resets."
            )
        if code in (401, 403) or any(marker in error_text for marker in ("unauthorized", "permission denied", "api key not valid", "http 401", "http 403")):
            return (
                "The configured generation provider rejected its credentials or access. "
                "Verify the server-side key and model permissions, then retry."
            )
        return None

    def _execute_json_prompt(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """Execute a structured generation prompt across model candidates with JSON response validation."""
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not configured")

        client = self._get_client()
        last_error = None

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            temperature=0.3
        )

        for model_name in self._get_candidate_models():
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=user_prompt,
                    config=config
                )
                if not response or not response.text:
                    raise ValueError(f"Empty response returned from model {model_name}")

                raw_text = response.text.strip()
                if raw_text.startswith("```json"):
                    raw_text = raw_text[7:]
                if raw_text.startswith("```"):
                    raw_text = raw_text[3:]
                if raw_text.endswith("```"):
                    raw_text = raw_text[:-3]
                raw_text = raw_text.strip()

                if not (raw_text.startswith("{") or raw_text.startswith("[")):
                    match = re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', raw_text)
                    if match:
                        raw_text = match.group(0).strip()

                return json.loads(raw_text)
            except Exception as e:
                logger.warning(f"Gemini call with model {model_name} failed: {e}")
                terminal_message = self._terminal_provider_error_message(e)
                if terminal_message:
                    raise RuntimeError(terminal_message) from e
                last_error = e

        raise RuntimeError(f"All Gemini generation attempts failed. Last error: {last_error}")

    def _execute_grounded_json_prompt(
        self,
        system_prompt: str,
        user_prompt: str,
        output_model: Any
    ) -> Tuple[Dict[str, Any], List[ResearchSource]]:
        """Generate schema-validated JSON with Google Search grounding and extracted citations."""
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not configured")

        client = self._get_client()
        last_error = None
        response_format = {
            "type": "text",
            "mime_type": "application/json",
            "schema": output_model.model_json_schema()
        }

        for model_name in self._get_candidate_models():
            try:
                interaction = client.interactions.create(
                    model=model_name,
                    input=user_prompt,
                    system_instruction=system_prompt,
                    tools=[{"type": "google_search"}],
                    response_format=response_format,
                    store=False
                )
                raw_text = (getattr(interaction, "output_text", None) or "").strip()
                if not raw_text:
                    raise ValueError(f"Empty grounded response returned from model {model_name}")
                if raw_text.startswith("```json"):
                    raw_text = raw_text[7:]
                elif raw_text.startswith("```"):
                    raw_text = raw_text[3:]
                if raw_text.endswith("```"):
                    raw_text = raw_text[:-3]
                parsed = json.loads(raw_text.strip())

                sources: Dict[str, ResearchSource] = {}
                for step in getattr(interaction, "steps", None) or []:
                    if getattr(step, "type", None) != "model_output":
                        continue
                    for content in getattr(step, "content", None) or []:
                        for annotation in getattr(content, "annotations", None) or []:
                            url = getattr(annotation, "url", None)
                            if getattr(annotation, "type", None) != "url_citation" or not url:
                                continue
                            if not url.startswith(("https://", "http://")):
                                continue
                            sources[url] = ResearchSource(
                                title=getattr(annotation, "title", None) or url,
                                url=url
                            )

                return parsed, list(sources.values())
            except Exception as e:
                logger.warning("Grounded Gemini call with model %s failed: %s", model_name, e)
                terminal_message = self._terminal_provider_error_message(e)
                if terminal_message:
                    raise RuntimeError(terminal_message) from e
                last_error = e

        raise RuntimeError(f"All grounded Gemini generation attempts failed. Last error: {last_error}")

    # =========================================================================
    # STAGE 1: Server-Side Generation Brief
    # =========================================================================
    def build_generation_brief(
        self,
        project_info: Dict[str, Any],
        module_type: str,
        cross_module_context: Optional[Dict[str, Any]] = None,
        planning_inputs: Optional[Dict[str, Any]] = None
    ) -> GenerationBrief:
        """Stage 1: Build a structured, server-side planning brief tailoring downstream generation."""
        industry = (project_info.get("industry") or "").lower()
        desc = (project_info.get("description") or "").lower()
        name = project_info.get("name") or "Ventures"
        stage = project_info.get("stage") or "Idea"
        budget = project_info.get("budget") or ""

        # Check technical project characteristics
        is_pcb_or_hardware = any(w in desc or w in industry for w in ["pcb", "electronics", "hardware", "circuit", "cad", "eda", "semiconductor"])
        is_deep_tech = is_pcb_or_hardware or any(w in desc or w in industry for w in ["machine learning", "ai model", "compiler", "robotics", "quantum", "biotech"])
        is_non_tech = any(ind in industry for ind in NON_TECHNICAL_INDUSTRIES) or any(w in desc for w in ["bakery", "cafe", "coffee", "restaurant", "boutique", "salon", "cleaning"])

        technical_depth = "deep_technical" if is_deep_tech else ("non_technical_business" if is_non_tech else "standard_digital")
        is_technical = technical_depth != "non_technical_business"

        # Check constraints & feasibility flags
        feasibility_flags = []
        is_solo = False
        horizon_weeks = 12
        if planning_inputs:
            is_solo = planning_inputs.get("is_solo_developer", False)
            horizon_weeks = planning_inputs.get("horizon_weeks", 12)

        # Check for unrealistic solo developer timeline
        if is_solo and horizon_weeks <= 12 and (is_technical or "enterprise" in desc or "saas" in desc):
            feasibility_flags.append("Solo developer requested full enterprise scope within 12 weeks. High risk of schedule overrun; scope reduction or phased rollout recommended.")

        # Check budget mismatch
        if budget and any(b in budget.lower() for b in ["$0", "<$1000", "$500", "bootstrap", "minimal"]) and ("enterprise" in desc or "hardware" in desc):
            feasibility_flags.append("Limited capital allocation for complex venture scope. Lean prototyping or staged milestones advised.")

        # Key assumptions and information gaps
        assumptions = []
        info_gaps = []
        if not project_info.get("target_customers"):
            assumptions.append("Target customer profile assumed based on typical industry buyers.")
            info_gaps.append("Target customer persona not explicitly detailed.")
        else:
            assumptions.append(f"Targeting specified audience: {project_info.get('target_customers')[:60]}")

        if not budget:
            assumptions.append("Standard lean bootstrap budget model assumed.")
            info_gaps.append("Budget parameters not explicitly specified.")

        applicable_focus = [
            f"Venture tailored for {stage} stage milestones",
            f"Industry alignment: {project_info.get('industry', 'Business Services')}",
            f"Depth profile: {technical_depth.replace('_', ' ').title()}"
        ]

        # Attempt LLM brief if API key is active
        if self.api_key:
            user_prompt = f"""Generate a Generation Brief for:
Project Name: {name}
Stage: {stage}
Industry: {project_info.get('industry')}
Description: {project_info.get('description')}
Target Customers: {project_info.get('target_customers')}
Budget: {budget}
Module: {module_type}
Cross-Module Context: {json.dumps(cross_module_context or {}, default=str)}
Planning Inputs: {json.dumps(planning_inputs or {}, default=str)}
"""
            try:
                raw_json = self._execute_json_prompt(BRIEF_SYSTEM_PROMPT, user_prompt)
                brief = GenerationBrief(**raw_json)
                if stage.lower() not in brief.stage_considerations.lower():
                    brief.stage_considerations = f"[{stage} stage] " + brief.stage_considerations
                return brief
            except Exception as e:
                terminal_message = self._terminal_provider_error_message(e)
                if terminal_message:
                    raise RuntimeError(terminal_message) from e
                logger.warning("LLM brief synthesis failed, utilizing deterministic domain brief: %s", e)

        # Deterministic domain brief fallback
        return GenerationBrief(
            venture_summary=f"Strategic blueprint for {name} ({stage} stage, {project_info.get('industry', 'General')})",
            applicable_focus=applicable_focus,
            is_technical_project=is_technical,
            technical_depth=technical_depth,
            stage_considerations=f"Focused on {stage}-stage priorities, rapid feedback loops, and unit economics.",
            budget_constraints=f"Budget bounded by: {budget or 'Lean Bootstrap'}",
            timeline_constraints=f"Target execution horizon: {horizon_weeks} weeks",
            team_capacity_considerations="Solo operator" if is_solo else "Multidisciplinary team capacity",
            key_assumptions=assumptions,
            information_gaps=info_gaps,
            feasibility_flags=feasibility_flags if feasibility_flags else ["Venture scope aligns with standard stage benchmarks."],
            custom_instructions=f"Synthesize {module_type} output with {technical_depth} precision."
        )

    # =========================================================================
    # STAGE 2: Module Syntheses
    # =========================================================================
    def generate_bmc(
        self,
        project_info: Dict[str, Any],
        brief: Optional[GenerationBrief] = None,
        cross_module_context: Optional[Dict[str, Any]] = None
    ) -> BMCData:
        brief = brief or self.build_generation_brief(project_info, "bmc", cross_module_context)
        if self.api_key:
            user_prompt = f"""Generate a 9-block Business Model Canvas guided by this Generation Brief:
Brief Summary: {brief.venture_summary}
Technical Depth: {brief.technical_depth}
Stage Considerations: {brief.stage_considerations}
Key Assumptions: {', '.join(brief.key_assumptions)}

Project Details:
Name: {project_info.get('name')}
Stage: {project_info.get('stage')}
Industry: {project_info.get('industry')}
Description: {project_info.get('description')}
Target Customers: {project_info.get('target_customers')}
Goals: {project_info.get('goals')}
Budget: {project_info.get('budget')}
Read-only context from other generated modules (use for consistency; do not modify those saved modules):
{json.dumps(cross_module_context or {}, ensure_ascii=False, default=str)}
"""
            raw_json = self._execute_json_prompt(BMC_SYSTEM_PROMPT, user_prompt)
            return BMCData(**raw_json)

        # High-Fidelity Deterministic Fallback tailored to project
        return self._fallback_bmc(project_info, brief)

    def generate_tech_stack(
        self,
        project_info: Dict[str, Any],
        brief: Optional[GenerationBrief] = None,
        cross_module_context: Optional[Dict[str, Any]] = None
    ) -> TechStackData:
        brief = brief or self.build_generation_brief(project_info, "tech_stack", cross_module_context)
        if self.api_key:
            user_prompt = f"""Generate a technology stack architectural blueprint guided by this Generation Brief:
Brief Summary: {brief.venture_summary}
Technical Depth: {brief.technical_depth} (CRITICAL: if non_technical_business, recommend COTS/POS/SaaS tools, NOT custom code!)
Budget & Constraints: {brief.budget_constraints}

Project Details:
Name: {project_info.get('name')}
Stage: {project_info.get('stage')}
Industry: {project_info.get('industry')}
Description: {project_info.get('description')}
Existing Stack: {json.dumps(project_info.get('existing_stack', {}), default=str)}
Budget: {project_info.get('budget')}
Cross Module Context: {json.dumps(cross_module_context or {}, default=str)}
"""
            raw_json = self._execute_json_prompt(TECH_STACK_SYSTEM_PROMPT, user_prompt)
            return TechStackData(**raw_json)

        return self._fallback_tech_stack(project_info, brief)

    def generate_idea_validator(
        self,
        project_info: Dict[str, Any],
        brief: Optional[GenerationBrief] = None,
        cross_module_context: Optional[Dict[str, Any]] = None
    ) -> IdeaValidatorData:
        brief = brief or self.build_generation_brief(project_info, "idea_validator", cross_module_context)
        if self.api_key:
            user_prompt = f"""Critique and validate this venture proposal guided by this Generation Brief:
Brief Summary: {brief.venture_summary}
Technical Depth: {brief.technical_depth}
Feasibility Flags: {', '.join(brief.feasibility_flags)}

Project Details:
Name: {project_info.get('name')}
Stage: {project_info.get('stage')}
Industry: {project_info.get('industry')}
Description: {project_info.get('description')}
Target Customers: {project_info.get('target_customers')}
Budget: {project_info.get('budget')}
Read-only context from other generated modules (use supplied facts and mark gaps; do not modify those saved modules):
{json.dumps(cross_module_context or {}, ensure_ascii=False, default=str)}
"""
            raw_json, source_references = self._execute_grounded_json_prompt(
                IDEA_VALIDATOR_SYSTEM_PROMPT, user_prompt, IdeaValidatorData
            )
            raw_json["source_references"] = [source.model_dump() for source in source_references]
            raw_json["evidence_note"] = (
                "Market claims were grounded in Google Search sources listed below. "
                "Treat projections and user-supplied information as assumptions."
                if source_references else
                "No source citations were returned. This is a preliminary hypothesis score, not independently verified market evidence."
            )
            return IdeaValidatorData(**raw_json)

        return self._fallback_idea_validator(project_info, brief)

    def generate_market_research(
        self,
        project_info: Dict[str, Any],
        brief: Optional[GenerationBrief] = None,
        cross_module_context: Optional[Dict[str, Any]] = None
    ) -> MarketResearchData:
        brief = brief or self.build_generation_brief(project_info, "market_research", cross_module_context)
        if self.api_key:
            user_prompt = f"""Perform market and competitor intelligence analysis guided by this Generation Brief:
Brief Summary: {brief.venture_summary}
Technical Depth: {brief.technical_depth}

Project Details:
Name: {project_info.get('name')}
Industry: {project_info.get('industry')}
Description: {project_info.get('description')}
Target Customers: {project_info.get('target_customers')}
Budget: {project_info.get('budget')}
Read-only context from other generated modules (use for consistency; do not modify those saved modules):
{json.dumps(cross_module_context or {}, ensure_ascii=False, default=str)}
"""
            raw_json, source_references = self._execute_grounded_json_prompt(
                MARKET_RESEARCH_SYSTEM_PROMPT, user_prompt, MarketResearchData
            )
            grounded_urls = {source.url for source in source_references}
            raw_json["source_references"] = [source.model_dump() for source in source_references]
            for competitor in raw_json.get("competitor_profiles", []):
                # Do not retain source names or URLs invented by the model.
                competitor["sources"] = [
                    source for source in competitor.get("sources", [])
                    if source in grounded_urls
                ]
            if not source_references:
                # Without returned grounding citations, model-written market
                # figures and named competitors cannot be presented as research.
                raw_json["competitor_profiles"] = []
                raw_json["target_market_size"] = (
                    "Not verified from available sources. Define a geography and customer segment, "
                    "then calculate TAM/SAM/SOM from current cited sources."
                )
                raw_json["provenance_note"] = (
                    "Google Search did not return source citations for this result. "
                    "Market size, competitor, market share, pricing, and growth claims were removed because they could not be verified."
                )
                raw_json.setdefault("research_gaps", []).append(
                    "No source citations were returned; verify market size, competitor claims, and pricing with primary sources."
                )
            return MarketResearchData(**raw_json)

        return self._fallback_market_research(project_info, brief)

    def generate_roadmap(
        self,
        project_info: Dict[str, Any],
        planning_inputs: Optional[Dict[str, Any]] = None,
        brief: Optional[GenerationBrief] = None,
        cross_module_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        planning_inputs = planning_inputs or {
            "start_date": date.today().isoformat(),
            "horizon_weeks": 12,
            "checklist": [],
            "completed_work": "",
            "in_progress_work": "",
            "team_capacity": "",
            "constraints": "",
            "target_outcome": "",
            "custom_items": [],
            "is_solo_developer": False,
            "departments": [],
            "team_members": [],
            "reduce_mvp_scope": False
        }
        brief = brief or self.build_generation_brief(project_info, "execution_roadmap", cross_module_context, planning_inputs)

        if self.api_key:
            user_prompt = f"""Develop an execution roadmap with tasks, dependencies, phases, and team assignments:
Brief Summary: {brief.venture_summary}
Technical Depth: {brief.technical_depth}
Feasibility Flags: {', '.join(brief.feasibility_flags)}

Project Details:
Name: {project_info.get('name')}
Stage: {project_info.get('stage')}
Description: {project_info.get('description')}
Industry: {project_info.get('industry')}
Target Customers: {project_info.get('target_customers')}
Existing Stack: {json.dumps(project_info.get('existing_stack', {}), default=str)}
Cross Module Context: {json.dumps(cross_module_context or {}, default=str)}

Current Date: {date.today().isoformat()}
Planning Inputs (Authoritative):
{json.dumps(planning_inputs, ensure_ascii=False, indent=2, default=str)}
"""
            raw_json = self._execute_json_prompt(ROADMAP_SYSTEM_PROMPT, user_prompt)
            return raw_json

        return self._fallback_roadmap(project_info, brief, planning_inputs)

    def modify_section(self, module_type: str, current_data: Dict[str, Any], instruction: str) -> Tuple[Dict[str, Any], str]:
        if self.api_key:
            try:
                user_prompt = f"""Module: {module_type}
Current Structured Data:
{json.dumps(current_data, indent=2)}

User Requested Modification:
{instruction}

Apply the requested changes while preserving all other fields. Return valid JSON containing 'change_summary' and 'data'.
"""
                result = self._execute_json_prompt(SECTION_MODIFICATION_SYSTEM_PROMPT, user_prompt)
                change_summary = result.get("change_summary", "Updated via AI modification")
                new_data = result.get("data", current_data)

                if module_type == "bmc":
                    new_data = BMCData(**new_data).model_dump()
                elif module_type == "tech_stack":
                    new_data = TechStackData(**new_data).model_dump()
                elif module_type == "idea_validator":
                    new_data = IdeaValidatorData(**new_data).model_dump()
                elif module_type == "market_research":
                    new_data = MarketResearchData(**new_data).model_dump()
                elif module_type in ("execution_roadmap", "detailed_roadmap"):
                    new_data = ExecutionRoadmapData(**new_data).model_dump()

                return new_data, change_summary
            except Exception as e:
                logger.warning("LLM section modify failed, using direct rule modification: %s", e)

        # Fallback modification: update or append to relevant list or text field
        modified = json.loads(json.dumps(current_data))
        summary = f"Applied instruction: '{instruction[:60]}'"
        # Simple heuristic to apply note to first list found
        for k, v in modified.items():
            if isinstance(v, list) and v and isinstance(v[0], str):
                v.append(f"[Modified] {instruction}")
                break
        return modified, summary

    def chat_copilot(self, project_info: Dict[str, Any], chat_history: List[Dict[str, str]], user_message: str) -> str:
        # Check scope boundaries first
        msg_lower = user_message.lower().strip()

        # Semantic Scope Check:
        # Completely out-of-scope triggers (e.g. biology, celebrity trivia, gaming, creative writing unrelated to venture)
        unrelated_patterns = [
            r"\bphotosynthesis\b", r"\bcelebrity\b", r"\bvideo game\b", r"\bmovie plot\b",
            r"\bwrite a poem\b", r"\btell me a joke\b", r"\bwho won the oscar\b", r"\bcapital of france\b"
        ]
        for pat in unrelated_patterns:
            if re.search(pat, msg_lower):
                return (
                    "### Out of Scope Inquiry\n\n"
                    "I am **Blueprint Copilot**, dedicated exclusively to venture planning, business model design, technical architecture, and execution roadmaps for your project. "
                    "I cannot assist with general trivia, unrelated science, or creative entertainment.\n\n"
                    "**How can I help with your project?**\n"
                    "- Critique your business model or pricing strategy\n"
                    "- Recommend scalable architecture or tools for your technology stack\n"
                    "- Draft an execution roadmap or assign tasks for your team"
                )

        # Module Routing detection
        if any(w in msg_lower for w in ["competitor", "market analysis", "industry landscape"]):
            route_advice = "*(Tip: You can view full competitor profiles and market share estimates in the **Market Research** module.)*\n\n"
        elif any(w in msg_lower for w in ["tech stack", "database choice", "architecture pattern", "microservices"]):
            route_advice = "*(Tip: Detailed architectural diagrams and component trade-offs are available in the **Tech Stack** module.)*\n\n"
        elif any(w in msg_lower for w in ["roadmap", "sprint", "milestones", "gantt", "task dependencies"]):
            route_advice = "*(Tip: Interactive phases, assignments, and dependency tracking are managed in the **Roadmap & Execution Plan** module.)*\n\n"
        else:
            route_advice = ""

        if self.api_key:
            try:
                client = self._get_client()
                context_prompt = f"""You are Blueprint Copilot assisting on this project:
Project: {project_info.get('name')} (Stage: {project_info.get('stage')})
Industry: {project_info.get('industry')}
Description: {project_info.get('description')}
Goals: {project_info.get('goals')}
Budget: {project_info.get('budget')}
"""
                contents = [
                    types.Content(role="user", parts=[types.Part.from_text(text=context_prompt)]),
                    types.Content(role="model", parts=[types.Part.from_text(text="Understood. I have loaded the full project context and I am ready to advise you.")])
                ]
                for msg in chat_history[-10:]:
                    role = "user" if msg.get("role") == "user" else "model"
                    contents.append(
                        types.Content(role=role, parts=[types.Part.from_text(text=msg.get("content", ""))])
                    )
                contents.append(
                    types.Content(role="user", parts=[types.Part.from_text(text=user_message)])
                )
                config = types.GenerateContentConfig(
                    system_instruction=COPILOT_SYSTEM_PROMPT,
                    temperature=0.7
                )
                for model_name in self._get_candidate_models():
                    try:
                        response = client.models.generate_content(
                            model=model_name,
                            contents=contents,
                            config=config
                        )
                        return route_advice + response.text.strip()
                    except Exception as e:
                        logger.warning(f"Copilot model {model_name} failed: {e}")
                        terminal_message = self._terminal_provider_error_message(e)
                        if terminal_message:
                            raise RuntimeError(terminal_message) from e
            except Exception as e:
                terminal_message = self._terminal_provider_error_message(e)
                if terminal_message:
                    raise RuntimeError(terminal_message) from e
                logger.warning("LLM Copilot failed, utilizing context-aware fallback advisor: %s", e)

        # High-Fidelity Domain Fallback Advisor
        name = project_info.get("name", "Your Venture")
        stage = project_info.get("stage", "Idea")
        ind = project_info.get("industry", "Business Services")

        # Handle general supporting concepts (e.g. "What is PostgreSQL?" or "What is CAC?")
        if "postgresql" in msg_lower or "postgres" in msg_lower:
            return (
                f"### Strategic Assessment: PostgreSQL for {name}\n\n"
                f"**PostgreSQL** is an advanced open-source object-relational database system known for reliability, ACID compliance, and rich extension ecosystem (such as `pgvector` for AI embeddings and PostGIS for geospatial queries).\n\n"
                f"**Relevance to {name} ({stage} Stage):**\n"
                f"- **Scalability:** Handles structured relational data gracefully up to millions of records on modest hosting.\n"
                f"- **Cost-Efficiency:** Zero licensing fees, available as managed services (Supabase, Neon, AWS RDS).\n"
                f"- **Recommendation:** Highly recommended as primary database for {ind} ventures requiring transactional integrity."
            )

        if "cac" in msg_lower or "customer acquisition cost" in msg_lower:
            return (
                f"### Key Metric: Customer Acquisition Cost (CAC) for {name}\n\n"
                f"**Customer Acquisition Cost (CAC)** measures total sales and marketing expenditure required to win a single paying customer: `CAC = Total Marketing Spend / New Customers Acquired`.\n\n"
                f"**Application for {name} ({stage} Stage):**\n"
                f"- At the **{stage}** stage, prioritize organic customer discovery and founder-led sales before scaling paid marketing channels.\n"
                f"- Aim for a **LTV:CAC ratio >= 3:1** before aggressive growth spending."
            )

        return (
            f"{route_advice}### Strategic Venture Analysis: {name}\n\n"
            f"Based on your active venture **{name}** operating in **{ind}** at the **{stage}** stage:\n\n"
            f"1. **Primary Focus:** Your immediate milestone at the {stage} stage is validating core customer hypotheses and securing repeat traction.\n"
            f"2. **Operational Recommendation:** Align your team assignments and architecture to maintain low burn and rapid learning cycles.\n"
            f"3. **Next Step:** You can run a detailed simulation in the **Roadmap & Execution Plan** or stress-test assumptions with the **Idea Validator**."
        )

    # =========================================================================
    # DETERMINISTIC DOMAIN FALLBACK GENERATORS
    # =========================================================================
    def _fallback_bmc(self, project_info: Dict[str, Any], brief: GenerationBrief) -> BMCData:
        name = project_info.get("name") or "Enterprise Venture"
        desc = (project_info.get("description") or "").lower()
        context_text = " ".join((
            str(project_info.get("name") or ""),
            str(project_info.get("industry") or ""),
            str(project_info.get("target_customers") or ""),
            str(project_info.get("description") or "")
        )).lower()
        is_pcb = any(token in context_text for token in ("pcb", "electronics", "hardware", "circuit", "eda", "cad"))
        is_non_tech = brief.technical_depth == "non_technical_business"

        if is_pcb:
            tagline = f"Next-Generation EDA and Cloud PCB Collaboration Platform for {name}"
            customers = [
                "Hardware engineering teams and electronics startups",
                "Electronics engineering universities and student labs",
                "Mid-market PCB manufacturing design bureaus"
            ]
            value_props = [
                "Real-time schematic and Gerber layout collaboration in browser",
                "Automated Design For Manufacturing (DFM) verification pre-fabrication",
                "Integrated component sourcing API with live distributor pricing"
            ]
            channels = ["Direct enterprise sales", "Academic site licensing", "Open-source hardware developer community"]
            cust_rel = ["Dedicated application engineer onboarding", "Community technical forum & Discord", "Comprehensive API documentation"]
            revenue = ["Tiered SaaS subscription per active designer", "Enterprise self-hosted license", "Transaction fee on fabrication order routing"]
            resources = ["Proprietary CAD rendering engine", "Component library database", "Hardware design verification IP"]
            activities = ["Browser CAD engine optimization", "DFM rule engine maintenance", "Supplier inventory API integrations"]
            partners = ["Component distributors (DigiKey, Mouser)", "PCB fabrication houses (JLCPCB, PCBWay)", "EDA standard consortiums"]
            costs = ["Cloud GPU/compute rendering clusters", "Hardware R&D engineering payroll", "Supplier API licensing fees"]
        elif is_non_tech:
            tagline = f"Premium Artisanal Experience and Local Service Excellence by {name}"
            customers = [
                "Local neighborhood residents and daily commuters",
                "Corporate catering and local office events",
                "Discerning retail lifestyle consumers seeking quality craft goods"
            ]
            value_props = [
                "Handcrafted local quality with verified organic sourcing",
                "Seamless in-person checkout and rapid mobile pickup loyalty app",
                "Curated specialty selection with exceptional customer hospitality"
            ]
            channels = ["Flagship physical retail storefront", "Curbside pickup mobile ordering", "Local hyper-targeted social media & word of mouth"]
            cust_rel = ["Personalized in-store loyalty rewards", "Community tasting workshops & events", "Direct email updates for new arrivals"]
            revenue = ["Direct in-store retail point-of-sale transactions", "Recurring monthly subscription club", "B2B office catering contracts"]
            resources = ["Prime foot-traffic retail leasehold", "Specialized commercial equipment", "Trained customer hospitality staff"]
            activities = ["Daily store operations and quality control", "Supplier inventory receiving and merchandising", "Staff hospitality training"]
            partners = ["Local regional agricultural producers", "Commercial equipment maintenance vendors", "Point-of-sale payment processor"]
            costs = ["Retail leasehold rent and commercial utilities", "Cost of goods sold (raw ingredients/merchandise)", "Storefront staff hourly wages"]
        else:
            tagline = f"Intelligent Workflow Automation and Value Acceleration for {name}"
            customers = [
                "Growth-stage technology startups and product teams",
                "Mid-market enterprise operations managers",
                "Digital transformation consultants and agency leads"
            ]
            value_props = [
                "Unified workflow orchestration eliminating manual data reconciliation",
                "Real-time analytics and predictive performance telemetry",
                "Intuitive self-service implementation reducing time-to-value to minutes"
            ]
            channels = ["Self-service product-led growth (PLG) portal", "Targeted outbound B2B sales", "Technology partner marketplaces"]
            cust_rel = ["In-app interactive guidance and self-serve documentation", "Dedicated customer success managers for enterprise tiers", "Automated customer health monitoring"]
            revenue = ["Monthly/annual tiered SaaS subscriptions", "Usage-based tier overages", "Professional onboarding packages"]
            resources = ["Proprietary automation engine and IP", "Customer operational telemetry dataset", "Core full-stack engineering team"]
            activities = ["Continuous platform feature development", "Cloud security and SOC2 compliance monitoring", "Customer acquisition funnel optimization"]
            partners = ["Cloud infrastructure providers (AWS/GCP)", "Integration ecosystem partners", "Payment processors (Stripe)"]
            costs = ["Cloud hosting and database infrastructure", "Core product engineering and customer success payroll", "Targeted customer acquisition and marketing"]

        guidance = {
            "customer_segments": "Conduct 15 structured problem-discovery interviews across target customer cohorts to validate willingness-to-pay.",
            "value_propositions": "Test landing page value proposition conversion rates against alternative messaging variants.",
            "channels": "Deploy a controlled acquisition test with a $500 budget to measure CAC on primary channel.",
            "customer_relationships": "Establish automated onboarding drip sequence and measure Day-7 / Day-30 retention.",
            "revenue_streams": "Run price sensitivity testing (Van Westendorp method) to determine optimal pricing tier thresholds.",
            "key_resources": "Audit existing technical and operational assets to identify critical staffing or IP gaps.",
            "key_activities": "Define sprint velocity targets focused exclusively on delivery of primary value proposition.",
            "key_partnerships": "Initiate discussions with at least 2 potential supply or distribution partners.",
            "cost_structure": "Build an 18-month unit economics model and establish maximum monthly burn threshold."
        }

        return BMCData(
            tagline=tagline,
            customer_segments=customers,
            value_propositions=value_props,
            channels=channels,
            customer_relationships=cust_rel,
            revenue_streams=revenue,
            key_resources=resources,
            key_activities=activities,
            key_partnerships=partners,
            cost_structure=costs,
            actionable_guidance=guidance,
            assumptions=brief.key_assumptions or ["Customer segment willingness to pay aligns with estimated pricing tiers."]
        )

    def _fallback_tech_stack(self, project_info: Dict[str, Any], brief: GenerationBrief) -> TechStackData:
        name = project_info.get("name") or "Project"
        desc = (project_info.get("description") or "").lower()
        context_text = " ".join((
            str(project_info.get("name") or ""),
            str(project_info.get("industry") or ""),
            str(project_info.get("target_customers") or ""),
            str(project_info.get("description") or "")
        )).lower()
        is_pcb = any(token in context_text for token in ("pcb", "electronics", "hardware", "circuit", "eda", "cad"))
        is_non_tech = brief.technical_depth == "non_technical_business"
        existing = project_info.get("existing_stack") or {}

        if is_non_tech:
            summary = f"Commercial off-the-shelf (COTS) operational and retail technology architecture for {name}, prioritizing zero custom code overhead and turnkey reliability."
            pattern = "Commercial Off-The-Shelf (COTS) & Cloud Services"
            recommendations = [
                TechItem(
                    technology="Square POS / Toast",
                    category="POS & Payments",
                    purpose="Omnichannel retail checkout, hardware terminal integration, and payment processing",
                    suitability="Industry standard for fast customer transactions with minimal setup costs and built-in offline mode",
                    trade_offs="2.6% + 10c per transaction processing fees",
                    migration_risk="Low / Greenfield",
                    role_description="Core point-of-sale terminal and merchant processing hub",
                    implementation_guidance="Order terminal hardware and configure item catalog with tax rates",
                    estimated_cost_tier="Low / Free Tier"
                ),
                TechItem(
                    technology="Shopify Retail & E-Commerce",
                    category="Business Operations",
                    purpose="Online storefront, local pickup catalog, and inventory synchronization",
                    suitability="Seamless integration with POS hardware to maintain unified stock levels across store and web",
                    trade_offs="Monthly subscription plus transaction fees if non-Shopify payments used",
                    migration_risk="Low / Greenfield",
                    role_description="Omnichannel inventory and order management system",
                    implementation_guidance="Set up brand domain, product listings, and link to payment processor",
                    estimated_cost_tier="Low / Free Tier"
                ),
                TechItem(
                    technology="QuickBooks Online / Xero",
                    category="Business Operations",
                    purpose="Automated bookkeeping, sales tax compliance, and cash flow accounting",
                    suitability="Direct automated synchronization with POS and bank feeds eliminating manual entry",
                    trade_offs="Requires initial chart-of-accounts setup by bookkeeper",
                    migration_risk="Low / Greenfield",
                    role_description="Central financial ledger and profit/loss tracking",
                    implementation_guidance="Connect business bank account and map POS sales accounts",
                    estimated_cost_tier="Low / Free Tier"
                ),
                TechItem(
                    technology="Klaviyo / Mailchimp",
                    category="Services",
                    purpose="Customer loyalty email/SMS marketing and automated visit follow-ups",
                    suitability="High ROI retention channel for repeat local customer foot traffic",
                    trade_offs="Pricing scales with active subscriber list size",
                    migration_risk="Low / Greenfield",
                    role_description="Customer relationship and retention marketing automation",
                    implementation_guidance="Embed loyalty signup on POS checkout and web storefront",
                    estimated_cost_tier="Low / Free Tier"
                ),
                TechItem(
                    technology="7shifts / Deputy",
                    category="Business Operations",
                    purpose="Employee shift scheduling, time clock tracking, and labor cost optimization",
                    suitability="Prevents staff over-scheduling and ensures regulatory labor compliance",
                    trade_offs="Requires staff mobile app adoption",
                    migration_risk="Low / Greenfield",
                    role_description="Workforce labor and scheduling hub",
                    implementation_guidance="Input employee availability and set weekly shift templates",
                    estimated_cost_tier="Low / Free Tier"
                ),
                TechItem(
                    technology="Google Workspace",
                    category="Services",
                    purpose="Custom domain email, document collaboration, and cloud storage",
                    suitability="Universal corporate communication and operational SOP document repository",
                    trade_offs="$6 per user monthly fee",
                    migration_risk="Low / Greenfield",
                    role_description="Operational communication and collaborative documents",
                    implementation_guidance="Provision business email addresses for managers and staff",
                    estimated_cost_tier="Low / Free Tier"
                )
            ]
        elif is_pcb:
            summary = f"High-performance cloud-native EDA software architecture for {name}, utilizing WebAssembly/WebGL for in-browser CAD rendering and event-driven backend microservices for compute-intensive DFM verification."
            pattern = "Event-Driven Microservices & WebAssembly/WebGL CAD Engine"
            recommendations = [
                TechItem(
                    technology="React 19 + TypeScript + WebGL / Three.js",
                    category="Frontend",
                    purpose="Interactive 60fps Gerber/schematic canvas rendering in client browser",
                    suitability="Hardware-accelerated client-side graphics reducing server rendering latency",
                    trade_offs="Higher client memory footprint on low-spec client machines",
                    migration_risk="Low / Greenfield",
                    role_description="Interactive browser-based PCB schematic and layout viewport",
                    implementation_guidance="Build reusable WebGL shader pipeline for multi-layer copper rendering",
                    estimated_cost_tier="Low / Free Tier"
                ),
                TechItem(
                    technology="FastAPI (Python 3.12) & Rust WebAssembly",
                    category="Backend",
                    purpose="High-throughput EDA file parsing, IPC netlist extraction, and REST API services",
                    suitability="Combines Python's rapid ML/scientific library ecosystem with Rust's raw memory safety for file parsing",
                    trade_offs="Dual-language runtime management in CI/CD pipeline",
                    migration_risk="Low / Greenfield",
                    role_description="Core engineering backend and computationally intensive parsing services",
                    implementation_guidance="Package Rust parsing engine via PyO3 for zero-copy file inspection",
                    estimated_cost_tier="Low / Free Tier"
                ),
                TechItem(
                    technology="PostgreSQL 16 + PostGIS & TimescaleDB",
                    category="Database",
                    purpose="Relational user accounts, project hierarchies, geometric netlist indexes, and version history",
                    suitability="PostGIS provides native R-tree indexing for complex PCB trace coordinates and clearance rules",
                    trade_offs="Requires database tuning for heavy multi-layer spatial query joins",
                    migration_risk="Low / Greenfield",
                    role_description="Primary transactional and spatial geometry database",
                    implementation_guidance="Configure PostGIS extension and establish spatial indexes on net nodes",
                    estimated_cost_tier="Low / Free Tier"
                ),
                TechItem(
                    technology="Redis 7 + Celery / RabbitMQ",
                    category="DevOps",
                    purpose="Asynchronous task queuing for long-running automated DFM design checks and BOM lookups",
                    suitability="Decouples user UI from 30-second fabrication rule validation jobs",
                    trade_offs="Requires persistent worker nodes and queue depth monitoring",
                    migration_risk="Low / Greenfield",
                    role_description="Asynchronous compute queue and real-time pub/sub bus",
                    implementation_guidance="Deploy Celery worker pool dedicated to file validation tasks",
                    estimated_cost_tier="Low / Free Tier"
                ),
                TechItem(
                    technology="AWS S3 / Cloudflare R2",
                    category="Storage",
                    purpose="Object storage for compressed multi-megabyte Gerber zip packages and 3D STEP models",
                    suitability="Extremely high durability with edge CDN distribution and low storage cost per GB",
                    trade_offs="Presigned URL expiration management required for security",
                    migration_risk="Low / Greenfield",
                    role_description="Immutable asset and file storage tier",
                    implementation_guidance="Set lifecycle rules to archive obsolete draft iterations to cold storage",
                    estimated_cost_tier="Low / Free Tier"
                ),
                TechItem(
                    technology="Docker + AWS ECS / Fly.io",
                    category="Cloud/Hosting",
                    purpose="Containerized application deployment with automated scaling across API and worker instances",
                    suitability="Predictable isolation of untrusted user Gerber file parsers",
                    trade_offs="Requires container vulnerability scanning",
                    migration_risk="Low / Greenfield",
                    role_description="Application hosting and container orchestration tier",
                    implementation_guidance="Configure multi-stage Docker builds and least-privilege security profiles",
                    estimated_cost_tier="Moderate"
                )
            ]
        else:
            summary = f"Modern, production-grade cloud modular architecture for {name}, balancing rapid feature velocity, low operational maintenance, and clear scaling paths."
            pattern = "Modular Monolith with Managed Cloud Services"
            recommendations = [
                TechItem(
                    technology="React 19 + TypeScript + Vite",
                    category="Frontend",
                    purpose="Responsive, type-safe single-page web client with rich component ecosystem",
                    suitability="Rapid development velocity, excellent developer tooling, and instant HMR",
                    trade_offs="Requires state management diligence as project complexity scales",
                    migration_risk="Low / Greenfield",
                    role_description="Client presentation and interactive user interface",
                    implementation_guidance="Initialize with strict TypeScript configuration and TailwindCSS",
                    estimated_cost_tier="Low / Free Tier"
                ),
                TechItem(
                    technology="FastAPI (Python 3.12)",
                    category="Backend",
                    purpose="High-performance asynchronous REST API backend with automatic OpenAPI documentation",
                    suitability="Native Pydantic v2 validation, async I/O performance, and rich AI/data ecosystem",
                    trade_offs="Requires disciplined architecture to prevent monolithic sprawl",
                    migration_risk="Low / Greenfield",
                    role_description="Core business logic and secure API gateway",
                    implementation_guidance="Structure modular domain routers with dependency injection",
                    estimated_cost_tier="Low / Free Tier"
                ),
                TechItem(
                    technology="PostgreSQL 16",
                    category="Database",
                    purpose="ACID-compliant relational database for user identities, projects, and structured data",
                    suitability="Proven reliability, JSONB flexibility, and seamless managed hosting options",
                    trade_offs="Requires connection pooling (e.g. PgBouncer) at scale",
                    migration_risk="Low / Greenfield",
                    role_description="Primary persistent relational data store",
                    implementation_guidance="Enforce Alembic schema migrations in CI/CD pipeline",
                    estimated_cost_tier="Low / Free Tier"
                ),
                TechItem(
                    technology="Redis 7",
                    category="Database",
                    purpose="In-memory cache, session store, and API rate limiting",
                    suitability="Sub-millisecond latency for hot session lookups and concurrency controls",
                    trade_offs="In-memory storage cost scales with dataset size",
                    migration_risk="Low / Greenfield",
                    role_description="Fast caching and distributed session management",
                    implementation_guidance="Enable key eviction policy (volatile-lru) for caching",
                    estimated_cost_tier="Low / Free Tier"
                ),
                TechItem(
                    technology="Docker + Cloud Hosting (AWS/Fly.io/Render)",
                    category="Cloud/Hosting",
                    purpose="Immutable containerized deployment with automated health checks and SSL termination",
                    suitability="Low operational overhead for early-stage and growth workloads",
                    trade_offs="Hosting costs rise as worker concurrency requirements expand",
                    migration_risk="Low / Greenfield",
                    role_description="Containerized hosting and infrastructure compute tier",
                    implementation_guidance="Set up GitHub Actions automated deployment on branch merge",
                    estimated_cost_tier="Moderate"
                ),
                TechItem(
                    technology="Sentry & Prometheus",
                    category="DevOps",
                    purpose="Application telemetry, distributed tracing, and real-time error reporting",
                    suitability="Immediate notification of uncaught exceptions and latency spikes",
                    trade_offs="Sampling rate must be tuned to prevent logging quota exhaustion",
                    migration_risk="Low / Greenfield",
                    role_description="Observability, monitoring, and error tracking tier",
                    implementation_guidance="Instrument FastAPI middleware with Sentry SDK",
                    estimated_cost_tier="Low / Free Tier"
                )
            ]

        existing_components = []
        for category, entries in existing.items():
            values = entries if isinstance(entries, list) else [entries]
            for entry in values:
                if isinstance(entry, str) and entry.strip():
                    existing_components.append(f"{category}: {entry.strip()}")
        existing_eval = {
            "evaluation_status": "not_verified_offline" if existing_components else "no_existing_stack",
            "existing_components": existing_components,
            "compatible_elements": [],
            "incompatible_or_redundant": [],
            "migration_trade_offs": (
                "The existing stack was captured, but offline mode cannot verify compatibility, support status, or migration risk. "
                "Preserve these components until a grounded compatibility review is available."
                if existing_components else
                "No existing stack was supplied for compatibility review."
            )
        }

        return TechStackData(
            summary=summary,
            architecture_pattern=pattern,
            recommendations=recommendations,
            existing_stack_evaluation=existing_eval,
            assumptions=(brief.key_assumptions or []) + [
                "Offline starter recommendations are a provisional outline; verify workload, budget, security, and compatibility before adoption."
            ]
        )

    def _fallback_idea_validator(self, project_info: Dict[str, Any], brief: GenerationBrief) -> IdeaValidatorData:
        name = project_info.get("name") or "Venture"
        stage = project_info.get("stage") or "Idea"
        description = (project_info.get("description") or "").strip()
        target_customers = (project_info.get("target_customers") or "").strip()
        industry = (project_info.get("industry") or "").strip()
        budget = (project_info.get("budget") or "").strip()
        context_text = " ".join((name, description, target_customers, industry)).lower()
        is_pcb = any(token in context_text for token in ("pcb", "electronics", "hardware", "circuit", "eda"))
        is_non_tech = brief.technical_depth == "non_technical_business"
        scope_tokens = ("enterprise", "hardware", "rocket", "semiconductor", "medical device", "global platform")
        large_scope = any(token in context_text for token in scope_tokens)
        limited_budget = any(token in budget.lower() for token in ("bootstrapped", "minimal", "under $", "$0", "$500", "$1,000", "$1000"))

        # This offline score measures the quality and feasibility of the supplied
        # inputs. Market demand remains conservative because no external evidence
        # is available; stage alone never increases the score.
        problem_clarity = min(
            92,
            35 + min(len(description), 150) // 5 + (12 if target_customers else 0) + (6 if project_info.get("goals") else 0)
        )
        market_demand = 45
        feasibility = 58 if description and target_customers else 42
        if large_scope and limited_budget:
            feasibility = max(20, feasibility - 22)
        defensibility = 55 if description and len(description) >= 40 else 40
        budget_alignment = 45 if not budget else (24 if large_scope and limited_budget else 55)
        factors = {
            "problem_clarity": problem_clarity,
            "market_demand": market_demand,
            "feasibility": feasibility,
            "defensibility": defensibility,
            "budget_alignment": budget_alignment
        }
        score = round(
            problem_clarity * 0.25
            + market_demand * 0.25
            + feasibility * 0.20
            + defensibility * 0.15
            + budget_alignment * 0.15
        )

        customer_label = target_customers or "a target customer group that still needs to be defined"
        problem = (
            f"{stage}-stage hypothesis based on the supplied description: {description}"
            if description else
            f"{stage}-stage assessment is limited because no specific customer problem or product description was supplied."
        )
        fit = (
            f"Target customers supplied: {target_customers}. Validate urgency, current alternatives, and willingness to pay with these buyers."
            if target_customers else
            "Target customer details are missing. Define a specific buyer, user, and purchase decision before treating demand as likely."
        )
        diff = (
            f"No defensible advantage is verified offline. Test whether the proposed offer ({description}) is meaningfully better "
            "than the customer's current alternative."
            if description else
            "No distinct advantage can be assessed until the product and customer problem are described."
        )

        if not budget:
            budget_eval = "No budget was supplied, so scope and runway fit cannot be assessed."
        elif large_scope and limited_budget:
            budget_eval = (
                f"The stated budget ({budget}) appears unlikely to support the full scope as described. "
                "Price a narrow proof-of-value slice and defer infrastructure, staffing, and secondary features."
            )
        else:
            budget_eval = (
                f"The stated budget ({budget}) has not been compared with verified supplier, staffing, hosting, "
                "regulatory, or acquisition costs. Build a bottom-up estimate before committing."
            )

        stage_guidance = {
            "Idea": "At Idea stage, prioritize problem interviews and a low-cost proof of demand before building the full product.",
            "MVP": "At MVP stage, measure activation and completion of the core workflow before expanding features.",
            "Post-launch": "At Post-launch stage, use retention, reliability, and support evidence to choose the next investment.",
            "Growth": "At Growth stage, validate channel economics, operational capacity, and reliability before scaling spend."
        }.get(stage, f"Align the next test with the current {stage} stage.")

        feasibility_text = (
            f"{stage_guidance} Technical and operational feasibility is not independently confirmed; validate scope, "
            "team capacity, dependencies, and regulatory needs."
        )
        risks = [
            ValidationRisk(
                risk="Market demand and willingness to pay are unverified.",
                severity="High",
                mitigation=f"Interview qualified {customer_label} and ask for a costly commitment such as a paid pilot, deposit, or signed trial."
            ),
            ValidationRisk(
                risk="Project scope may exceed available budget or delivery capacity." if (large_scope or limited_budget) else "Delivery and operating costs have not been estimated from actual requirements.",
                severity="High" if large_scope and limited_budget else "Medium",
                mitigation="Estimate the smallest end-to-end workflow, include ongoing operating costs, and phase work against the available budget."
            )
        ]
        if is_pcb:
            risks.append(ValidationRisk(
                risk="Representative electronics design files, rule checks, and manufacturing handoff may expose compatibility gaps.",
                severity="High",
                mitigation="Test imports, exports, design-rule checks, and fabrication handoff using customer-provided files and documented acceptance criteria."
            ))
        elif is_non_tech:
            risks.append(ValidationRisk(
                risk="Local operating requirements, supplier reliability, and customer acquisition costs are not yet verified.",
                severity="Medium",
                mitigation="Run a small paid pilot or pop-up and record actual costs, conversion, repeat purchase, and supplier performance."
            ))

        experiments = [
            ValidationExperiment(
                experiment=f"Interview qualified {customer_label} about the last time they faced this problem.",
                metric="Share of interviewees who describe a recent workaround and agree to a follow-up test",
                target_criteria="Set the decision threshold before interviews; do not treat interest alone as purchase evidence."
            ),
            ValidationExperiment(
                experiment="Test a clickable prototype, service trial, or manual concierge version of the core offer.",
                metric="Completion of the core customer outcome and willingness to make a concrete commitment",
                target_criteria="Compare observed use and commitments with a threshold chosen before the test."
            )
        ]

        return IdeaValidatorData(
            overall_viability_score=score,
            score_factors=factors,
            problem_clarity=problem,
            customer_fit=fit,
            value_proposition=(
                f"Potential value proposition for {name}: solve the stated problem for {customer_label}; "
                "the benefit and differentiation still need customer evidence."
            ),
            market_assumptions=[
                f"{customer_label} experiences the stated problem often enough to seek a solution.",
                "The buyer has authority and budget to pay for an effective alternative."
            ],
            differentiation=diff,
            feasibility=feasibility_text,
            budget_feasibility=budget_eval,
            scope_reduction_alternatives=[
                "Reduce the first release to one measurable customer outcome and one target customer group.",
                "Defer secondary workflows and use manual operations until demand and cost assumptions are tested."
            ],
            risks=risks,
            validation_experiments=experiments,
            suggested_next_actions=[
                "Specify the target buyer, user, and problem using the project's actual customer segment.",
                "Run customer interviews and record evidence separately from assumptions.",
                "Create a bottom-up scope and budget estimate, then compare it with available runway."
            ],
            evidence_note=(
                "Preliminary offline heuristic based on input completeness and scope signals. It has no live market, "
                "competitor-growth, sector-revenue, or pricing evidence; use the score as a prompt for validation, not an empirical forecast."
            ),
            source_references=[]
        )

    def _fallback_market_research(self, project_info: Dict[str, Any], brief: GenerationBrief) -> MarketResearchData:
        name = project_info.get("name") or "Venture"
        description = (project_info.get("description") or "").strip()
        industry = (project_info.get("industry") or "").strip() or "the stated industry"
        target_customers = (project_info.get("target_customers") or "").strip()
        budget = (project_info.get("budget") or "").strip()
        customer_label = target_customers or "the intended customer group"

        # Offline output is a planning hypothesis only. Do not invent sources,
        # competitors, market sizes, growth rates, shares, or competitor pricing.
        return MarketResearchData(
            provenance_note=(
                "Offline preliminary analysis. Google Search grounding was unavailable, "
                "so no current market facts or competitor claims are presented as verified."
            ),
            target_market_size=(
                "Not verified. A defensible TAM/SAM/SOM estimate needs current, cited market "
                "sources and a defined geography, segment, and pricing model."
            ),
            customer_needs=[
                f"Validate whether {customer_label} experiences the problem described for {name}.",
                "Measure how customers solve the problem today, including internal workarounds and substitute products.",
                "Test willingness to pay against the customer's current cost, time loss, or risk."
            ],
            competitor_profiles=[],
            competitive_positioning=(
                f"Positioning is not verified for {name}. Compare the proposed offer with direct "
                "competitors and substitutes after current sources are collected."
            ),
            differentiation_factors=[
                f"Test whether the proposed offer solves this stated need: {description or 'project description not supplied'}.",
                "Validate the advantage with target customers using a side-by-side comparison of current alternatives."
            ],
            late_entry_differentiation=(
                f"Start with a narrow use case for {customer_label}, remove a documented friction point "
                "from existing alternatives, and validate switching reasons before expanding scope."
            ),
            budget_fit_analysis=(
                f"Budget supplied: {budget}. Competitive costs and customer acquisition requirements "
                "were not benchmarked offline; validate a small, measurable launch scope before committing spend."
                if budget else
                "No budget was supplied. Set a spending ceiling and runway before judging whether the proposed scope is feasible."
            ),
            opportunities=[
                f"Hypothesis to validate: {industry} customers may be underserved in the specific workflow described for {name}."
            ],
            threats=[
                "Existing products, internal processes, or low-cost substitutes may already satisfy the need."
            ],
            research_gaps=[
                "Live competitor search was unavailable; identify and verify up to three relevant direct or indirect alternatives.",
                "Collect primary market-size sources with dates and a transparent TAM/SAM/SOM calculation.",
                "Verify competitor capabilities, pricing, customer segment, and recent growth from primary sources.",
                "Interview target customers to validate urgency, current alternatives, and willingness to pay."
            ],
            source_references=[]
        )

    def _fallback_roadmap(
        self,
        project_info: Dict[str, Any],
        brief: GenerationBrief,
        planning_inputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        from datetime import datetime, timedelta, date

        name = project_info.get("name") or "Project"
        stage = project_info.get("stage") or "Idea"
        desc = (project_info.get("description") or "").lower()
        is_pcb = "pcb" in desc or "electronics" in desc or "hardware" in desc
        is_non_tech = brief.technical_depth == "non_technical_business"

        start_date_str = planning_inputs.get("start_date") or date.today().isoformat()
        try:
            cur_d = date.fromisoformat(start_date_str[:10])
        except Exception:
            cur_d = date.today()

        horizon_w = int(planning_inputs.get("horizon_weeks") or 12)
        is_solo = planning_inputs.get("is_solo_developer", False)
        team_members = planning_inputs.get("team_members", [])
        reduce_mvp_scope = planning_inputs.get("reduce_mvp_scope", False)

        # Check for unrealistic solo developer constraint
        is_unrealistic = is_solo and horizon_w <= 12 and (not is_non_tech) and not reduce_mvp_scope

        feasibility = RoadmapFeasibilityEvaluation(
            is_realistic=not is_unrealistic,
            feasibility_issues=[
                "Solo developer requested full enterprise scope within 12 weeks. High risk of schedule overrun, burnout, and deferred testing."
            ] if is_unrealistic else [],
            recommended_alternatives=[
                "Alternative 1 (Recommended): Reduce MVP scope strictly to the single core workflow and prototype validation.",
                "Alternative 2: Extend delivery timeline from 12 weeks to 24-36 weeks to accommodate single developer velocity.",
                "Alternative 3: Bring on 1-2 specialized contract engineers for frontend/backend parallelization."
            ] if is_unrealistic else [
                "Plan pace is well-calibrated to available capacity and stage objectives."
            ],
            capacity_summary=f"Allocated {1 if is_solo else (len(team_members) or 3)} active contributors over {horizon_w} weeks."
        )

        # Helper to assign team member
        def get_assignee(role_pref: str, dept_pref: str) -> Tuple[str, str, str, bool]:
            if is_solo:
                name = team_members[0].get("name") if team_members else "Solo Developer"
                return (name, role_pref, dept_pref, True if is_unrealistic else False)
            if team_members:
                for tm in team_members:
                    roles = tm.get("roles", [])
                    skills = tm.get("skills", [])
                    dept = tm.get("department") or ""
                    if any(role_pref.lower() in r.lower() for r in roles) or any(role_pref.lower() in s.lower() for s in skills):
                        return (tm.get("name", "Team Member"), role_pref, dept or dept_pref, False)
                # Fallback to first member
                return (team_members[0].get("name", "Team Member"), role_pref, team_members[0].get("department") or dept_pref, False)
            return ("Unassigned", role_pref, dept_pref, False)

        p1_end = cur_d + timedelta(weeks=max(2, horizon_w // 3))
        p2_end = p1_end + timedelta(weeks=max(2, horizon_w // 3))
        p3_end = cur_d + timedelta(weeks=horizon_w)

        phases = [
            RoadmapPhase(
                name="Phase 1: Research, Architecture & Core Foundations",
                color="#78906c",
                start_date=cur_d.isoformat(),
                end_date=p1_end.isoformat(),
                description="Establish essential architecture, validate core user assumptions, and deploy initial infrastructure."
            ),
            RoadmapPhase(
                name="Phase 2: Core Feature Implementation & Testing",
                color="#10b981",
                start_date=p1_end.isoformat(),
                end_date=p2_end.isoformat(),
                description="Deliver functional MVP workflows, configure core integrations, and execute automated test suites."
            ),
            RoadmapPhase(
                name="Phase 3: Beta Launch, Feedback & Hardening",
                color="#8b5cf6",
                start_date=p2_end.isoformat(),
                end_date=p3_end.isoformat(),
                description="Onboard pilot customer cohort, monitor error telemetry, and refine unit economics."
            )
        ]

        # Build Stage-Aware & Domain-Specific Tasks
        tasks = []
        if is_non_tech:
            # Non-technical business roadmap (retail, cafe, agency, local services)
            t1_owner, t1_role, t1_dept, t1_ov = get_assignee("Store Manager", "Operations")
            t2_owner, t2_role, t2_dept, t2_ov = get_assignee("Retail Coordinator", "Merchandising")
            t3_owner, t3_role, t3_dept, t3_ov = get_assignee("Brand Specialist", "Marketing")
            t4_owner, t4_role, t4_dept, t4_ov = get_assignee("Operations Lead", "Operations")

            tasks = [
                RoadmapTaskItem(
                    task_code="TSK-01",
                    phase="Phase 1: Research, Architecture & Core Foundations",
                    title="Lease Agreement & Storefront Layout Design",
                    description="Finalize commercial lease terms and contract contractor for customer counter and workspace fit-out.",
                    timeline="30-day",
                    start_date=cur_d.isoformat(),
                    end_date=(cur_d + timedelta(days=14)).isoformat(),
                    priority="Critical",
                    status="Pending",
                    dependencies=[],
                    deliverables="Signed commercial lease and architectural floor plan.",
                    effort="2 weeks",
                    assigned_to=t1_owner,
                    assigned_role=t1_role,
                    department=t1_dept,
                    steps=["Review lease covenants", "Engage contractor", "Submit local municipal permits"],
                    is_overloaded=t1_ov
                ),
                RoadmapTaskItem(
                    task_code="TSK-02",
                    phase="Phase 1: Research, Architecture & Core Foundations",
                    title="Supplier Contracts & Ingredient Procurement",
                    description="Negotiate supplier terms with local producers for raw ingredients and packaging materials.",
                    timeline="30-day",
                    start_date=(cur_d + timedelta(days=7)).isoformat(),
                    end_date=p1_end.isoformat(),
                    priority="High",
                    status="Pending",
                    dependencies=["TSK-01"],
                    deliverables="Executed vendor contracts and initial inventory shipment schedule.",
                    effort="2 weeks",
                    assigned_to=t2_owner,
                    assigned_role=t2_role,
                    department=t2_dept,
                    steps=["Request sample batches", "Negotiate volume pricing", "Confirm delivery frequency"],
                    is_overloaded=t2_ov
                ),
                RoadmapTaskItem(
                    task_code="TSK-03",
                    phase="Phase 2: Core Feature Implementation & Testing",
                    title="POS & Inventory System Setup",
                    description="Configure Square POS hardware, enter item catalog, set up receipt branding, and connect QuickBooks.",
                    timeline="60-day",
                    start_date=p1_end.isoformat(),
                    end_date=(p1_end + timedelta(days=14)).isoformat(),
                    priority="Critical",
                    status="Pending",
                    dependencies=["TSK-02"],
                    deliverables="Fully operational POS terminal and synced inventory catalog.",
                    effort="2 weeks",
                    assigned_to=t1_owner,
                    assigned_role=t1_role,
                    department=t1_dept,
                    steps=["Import product barcodes and prices", "Perform test charge transactions", "Verify bank auto-deposits"],
                    is_overloaded=t1_ov
                ),
                RoadmapTaskItem(
                    task_code="TSK-04",
                    phase="Phase 2: Core Feature Implementation & Testing",
                    title="Staff Hiring & Hospitality Service Training",
                    description="Recruit initial customer-facing staff, conduct service standards training, and run dress rehearsals.",
                    timeline="60-day",
                    start_date=(p1_end + timedelta(days=7)).isoformat(),
                    end_date=p2_end.isoformat(),
                    priority="High",
                    status="Pending",
                    dependencies=["TSK-03"],
                    deliverables="Trained team equipped with service manual and schedule.",
                    effort="3 weeks",
                    assigned_to=t4_owner,
                    assigned_role=t4_role,
                    department=t4_dept,
                    steps=["Publish job postings", "Conduct interviews", "Run simulated rush hour drills"],
                    is_overloaded=t4_ov
                ),
                RoadmapTaskItem(
                    task_code="TSK-05",
                    phase="Phase 3: Beta Launch, Feedback & Hardening",
                    title="Soft Opening & Neighborhood Launch Event",
                    description="Execute invitation-only soft launch weekend, gather customer feedback, and celebrate Grand Opening.",
                    timeline="90-day",
                    start_date=p2_end.isoformat(),
                    end_date=p3_end.isoformat(),
                    priority="Critical",
                    status="Pending",
                    dependencies=["TSK-04"],
                    deliverables="Successful launch weekend with 150+ customers served and initial revenue.",
                    effort="2 weeks",
                    assigned_to=t3_owner,
                    assigned_role=t3_role,
                    department=t3_dept,
                    steps=["Send VIP invite postcards", "Host ribbon-cutting", "Collect customer reviews"],
                    is_overloaded=t3_ov
                )
            ]
        elif is_pcb:
            # Deep technical / PCB venture roadmap
            t1_owner, t1_role, t1_dept, t1_ov = get_assignee("Lead Architect", "Engineering")
            t2_owner, t2_role, t2_dept, t2_ov = get_assignee("Frontend Engineer", "Engineering")
            t3_owner, t3_role, t3_dept, t3_ov = get_assignee("Backend Engineer", "Engineering")
            t4_owner, t4_role, t4_dept, t4_ov = get_assignee("Product Lead", "Product")

            tasks = [
                RoadmapTaskItem(
                    task_code="TSK-01",
                    phase="Phase 1: Research, Architecture & Core Foundations",
                    title="WebGL Multi-Layer Canvas & KiCad Parser Benchmark",
                    description="Build hardware-accelerated 60fps schematic canvas and Rust-based KiCad parser engine.",
                    timeline="30-day",
                    start_date=cur_d.isoformat(),
                    end_date=(cur_d + timedelta(days=14)).isoformat(),
                    priority="Critical",
                    status="Pending",
                    dependencies=[],
                    deliverables="Working browser prototype capable of loading 4-layer Gerber files at 60fps.",
                    effort="2 weeks",
                    assigned_to=t1_owner,
                    assigned_role=t1_role,
                    department=t1_dept,
                    steps=["Implement multi-layer shader passes", "Benchmark KiCad v8 format parsing", "Validate memory usage"],
                    is_overloaded=t1_ov
                ),
                RoadmapTaskItem(
                    task_code="TSK-02",
                    phase="Phase 1: Research, Architecture & Core Foundations",
                    title="Automated DFM Rule Engine Implementation",
                    description="Implement geometric clearance verification, trace width checks, and drill aspect ratio validations.",
                    timeline="30-day",
                    start_date=(cur_d + timedelta(days=7)).isoformat(),
                    end_date=p1_end.isoformat(),
                    priority="Critical",
                    status="Pending",
                    dependencies=["TSK-01"],
                    deliverables="Passing DFM verification test suite across 15 standard reference boards.",
                    effort="2 weeks",
                    assigned_to=t3_owner,
                    assigned_role=t3_role,
                    department=t3_dept,
                    steps=["Define manufacturer clearance rule schemas", "Implement R-tree spatial collision tests", "Generate visual violation overlays"],
                    is_overloaded=t3_ov
                ),
                RoadmapTaskItem(
                    task_code="TSK-03",
                    phase="Phase 2: Core Feature Implementation & Testing",
                    title="Component Distributor API & Live BOM Sync",
                    description="Integrate DigiKey and Mouser inventory APIs for live pricing and component availability inside schematic editor.",
                    timeline="60-day",
                    start_date=p1_end.isoformat(),
                    end_date=(p1_end + timedelta(days=14)).isoformat(),
                    priority="High",
                    status="Pending",
                    dependencies=["TSK-02"],
                    deliverables="Live BOM pricing calculator reflecting distributor stock changes.",
                    effort="2 weeks",
                    assigned_to=t3_owner,
                    assigned_role=t3_role,
                    department=t3_dept,
                    steps=["Configure distributor OAuth credentials", "Build Redis caching layer for stock queries", "Implement lifecycle status warnings"],
                    is_overloaded=t3_ov
                ),
                RoadmapTaskItem(
                    task_code="TSK-04",
                    phase="Phase 2: Core Feature Implementation & Testing",
                    title="Real-Time Collaborative Multi-User Layout Sync",
                    description="Implement WebSocket synchronization with operational transformation or CRDT for multi-designer editing.",
                    timeline="60-day",
                    start_date=(p1_end + timedelta(days=7)).isoformat(),
                    end_date=p2_end.isoformat(),
                    priority="High",
                    status="Pending",
                    dependencies=["TSK-01"],
                    deliverables="Simultaneous 3-user collaborative schematic editing without state desync.",
                    effort="3 weeks",
                    assigned_to=t2_owner,
                    assigned_role=t2_role,
                    department=t2_dept,
                    steps=["Deploy WebSocket connection gateway", "Implement state delta broadcasting", "Handle network disconnect recovery"],
                    is_overloaded=t2_ov
                ),
                RoadmapTaskItem(
                    task_code="TSK-05",
                    phase="Phase 3: Beta Launch, Feedback & Hardening",
                    title="University Engineering Lab Pilot Cohort Onboarding",
                    description="Onboard 5 university robotics student clubs for end-to-end design and fabrication validation.",
                    timeline="90-day",
                    start_date=p2_end.isoformat(),
                    end_date=p3_end.isoformat(),
                    priority="Critical",
                    status="Pending",
                    dependencies=["TSK-03", "TSK-04"],
                    deliverables="5 functional manufactured boards verified without design-rule fabrication rejections.",
                    effort="3 weeks",
                    assigned_to=t4_owner,
                    assigned_role=t4_role,
                    department=t4_dept,
                    steps=["Deliver student onboarding workshops", "Collect bug telemetry in Sentry", "Measure design cycle speed vs Altium baseline"],
                    is_overloaded=t4_ov
                )
            ]
        else:
            # Standard Digital / SaaS venture roadmap
            t1_owner, t1_role, t1_dept, t1_ov = get_assignee("Lead Architect", "Engineering")
            t2_owner, t2_role, t2_dept, t2_ov = get_assignee("Frontend Engineer", "Engineering")
            t3_owner, t3_role, t3_dept, t3_ov = get_assignee("Fullstack Engineer", "Engineering")
            t4_owner, t4_role, t4_dept, t4_ov = get_assignee("Product Lead", "Product")

            tasks = [
                RoadmapTaskItem(
                    task_code="TSK-01",
                    phase="Phase 1: Research, Architecture & Core Foundations",
                    title="Customer Discovery & Prototype Architecture Setup",
                    description="Complete 15 customer discovery interviews and configure foundation database schemas and API scaffolds.",
                    timeline="30-day",
                    start_date=cur_d.isoformat(),
                    end_date=(cur_d + timedelta(days=14)).isoformat(),
                    priority="Critical",
                    status="Pending",
                    dependencies=[],
                    deliverables="Validated problem architecture and deployed dev environment.",
                    effort="2 weeks",
                    assigned_to=t1_owner,
                    assigned_role=t1_role,
                    department=t1_dept,
                    steps=["Synthesize customer interview insights", "Set up PostgreSQL and Alembic migrations", "Configure CI/CD automated test pipeline"],
                    is_overloaded=t1_ov
                ),
                RoadmapTaskItem(
                    task_code="TSK-02",
                    phase="Phase 1: Research, Architecture & Core Foundations",
                    title="Authentication & Multi-Tenant Role Isolation",
                    description="Implement secure session management, CSRF protection, and project ownership authorization gates.",
                    timeline="30-day",
                    start_date=(cur_d + timedelta(days=7)).isoformat(),
                    end_date=p1_end.isoformat(),
                    priority="Critical",
                    status="Pending",
                    dependencies=["TSK-01"],
                    deliverables="Passing security and tenant isolation test suite.",
                    effort="2 weeks",
                    assigned_to=t3_owner,
                    assigned_role=t3_role,
                    department=t3_dept,
                    steps=["Implement bcrypt password hashing", "Configure secure HTTPOnly session cookies", "Enforce tenant boundary checks"],
                    is_overloaded=t3_ov
                ),
                RoadmapTaskItem(
                    task_code="TSK-03",
                    phase="Phase 2: Core Feature Implementation & Testing",
                    title="Core Workflow Engine & Interactive UI Dashboard",
                    description="Develop the primary user workflow modules with interactive diagramming and real-time state feedback.",
                    timeline="60-day",
                    start_date=p1_end.isoformat(),
                    end_date=(p1_end + timedelta(days=14)).isoformat(),
                    priority="High",
                    status="Pending",
                    dependencies=["TSK-02"],
                    deliverables="Interactive client UI with complete end-to-end data persistence.",
                    effort="2 weeks",
                    assigned_to=t2_owner,
                    assigned_role=t2_role,
                    department=t2_dept,
                    steps=["Build responsive UI components", "Connect frontend mutations to REST API", "Implement accessible keyboard and touch controls"],
                    is_overloaded=t2_ov
                ),
                RoadmapTaskItem(
                    task_code="TSK-04",
                    phase="Phase 2: Core Feature Implementation & Testing",
                    title="Cross-Module Synchronization & Export Engine",
                    description="Wire module snapshot reading, staleness alerts, and multi-format PDF/SVG exports.",
                    timeline="60-day",
                    start_date=(p1_end + timedelta(days=7)).isoformat(),
                    end_date=p2_end.isoformat(),
                    priority="High",
                    status="Pending",
                    dependencies=["TSK-03"],
                    deliverables="Complete export engine and cross-module freshness detection.",
                    effort="3 weeks",
                    assigned_to=t3_owner,
                    assigned_role=t3_role,
                    department=t3_dept,
                    steps=["Build cross-module context aggregation", "Implement staleness detection flags", "Validate complete PDF/SVG generation"],
                    is_overloaded=t3_ov
                ),
                RoadmapTaskItem(
                    task_code="TSK-05",
                    phase="Phase 3: Beta Launch, Feedback & Hardening",
                    title="Closed Beta Rollout & Production Telemetry",
                    description="Invite initial 20 beta users, monitor error logging via Sentry, and measure Day-7 retention.",
                    timeline="90-day",
                    start_date=p2_end.isoformat(),
                    end_date=p3_end.isoformat(),
                    priority="Critical",
                    status="Pending",
                    dependencies=["TSK-03", "TSK-04"],
                    deliverables="20 onboarded users with zero unhandled exceptions and verified retention metrics.",
                    effort="3 weeks",
                    assigned_to=t4_owner,
                    assigned_role=t4_role,
                    department=t4_dept,
                    steps=["Conduct beta user walkthroughs", "Review error telemetry daily", "Prioritize customer bug fixes for release"],
                    is_overloaded=t4_ov
                )
            ]

        # Add custom items if supplied by user
        custom_items = planning_inputs.get("custom_items", [])
        for c_idx, c_item in enumerate(custom_items):
            if isinstance(c_item, str) and c_item.strip():
                t_owner, t_role, t_dept, t_ov = get_assignee("Lead Specialist", "Operations")
                tasks.append(
                    RoadmapTaskItem(
                        task_code=f"TSK-C{c_idx+1}",
                        phase=phases[0].name,
                        title=f"Custom: {c_item.strip()}",
                        description=f"User-specified deliverable: {c_item.strip()}",
                        timeline="30-day",
                        start_date=cur_d.isoformat(),
                        end_date=(cur_d + timedelta(days=10)).isoformat(),
                        priority="Medium",
                        status="Pending",
                        dependencies=[],
                        deliverables=f"Completed {c_item.strip()}",
                        effort="1 week",
                        assigned_to=t_owner,
                        assigned_role=t_role,
                        department=t_dept,
                        steps=[f"Execute {c_item.strip()}"],
                        is_overloaded=t_ov
                    )
                )

        return {
            "phases": [p.model_dump() for p in phases],
            "tasks": [t.model_dump() for t in tasks],
            "feasibility_evaluation": feasibility.model_dump(),
            "assumptions": brief.key_assumptions or ["Standard 40 hours per week available per full-time contributor."]
        }

ai_service = GeminiAIService()

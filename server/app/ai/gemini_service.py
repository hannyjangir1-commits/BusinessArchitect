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
    MarketResearchData, CompetitorProfile,
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
                http_status_codes=[503, 429, 500]
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
                last_error = e

        raise RuntimeError(f"All Gemini generation attempts failed. Last error: {last_error}")

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
    def generate_bmc(self, project_info: Dict[str, Any], brief: Optional[GenerationBrief] = None) -> BMCData:
        brief = brief or self.build_generation_brief(project_info, "bmc")
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
"""
            raw_json = self._execute_json_prompt(IDEA_VALIDATOR_SYSTEM_PROMPT, user_prompt)
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
"""
            raw_json = self._execute_json_prompt(MARKET_RESEARCH_SYSTEM_PROMPT, user_prompt)
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
            except Exception as e:
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
        is_pcb = "pcb" in desc or "electronics" in desc or "hardware" in desc
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
        is_pcb = "pcb" in desc or "electronics" in desc or "hardware" in desc
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

        existing_eval = {
            "compatible_elements": [t for t in existing.keys()] if existing else ["Standard modern web protocols"],
            "incompatible_or_redundant": ["Legacy unmaintained dependencies"] if existing else [],
            "migration_trade_offs": "Gradual phase-in recommended to avoid disrupting active customer workflows."
        }

        return TechStackData(
            summary=summary,
            architecture_pattern=pattern,
            recommendations=recommendations,
            existing_stack_evaluation=existing_eval,
            assumptions=brief.key_assumptions or ["Deployment environment supports standard container runtimes."]
        )

    def _fallback_idea_validator(self, project_info: Dict[str, Any], brief: GenerationBrief) -> IdeaValidatorData:
        name = project_info.get("name") or "Venture"
        stage = project_info.get("stage") or "Idea"
        budget = project_info.get("budget") or "Standard lean"
        desc = (project_info.get("description") or "").lower()
        is_pcb = "pcb" in desc or "electronics" in desc or "hardware" in desc
        is_non_tech = brief.technical_depth == "non_technical_business"

        # Explainable score calculation
        if stage == "Idea":
            score = 76
            factors = {"problem_clarity": 82, "market_demand": 74, "feasibility": 78, "defensibility": 68, "budget_alignment": 80}
        elif stage == "MVP":
            score = 82
            factors = {"problem_clarity": 88, "market_demand": 80, "feasibility": 84, "defensibility": 75, "budget_alignment": 85}
        elif stage == "Post-launch":
            score = 86
            factors = {"problem_clarity": 90, "market_demand": 85, "feasibility": 88, "defensibility": 80, "budget_alignment": 88}
        else:
            score = 90
            factors = {"problem_clarity": 92, "market_demand": 90, "feasibility": 91, "defensibility": 87, "budget_alignment": 90}

        if is_pcb:
            problem = "Hardware designers lose 15-25% of development time managing disconnected CAD files, manual BOM distributor lookups, and unexpected DFM rejections from fabrication houses."
            fit = "Strong urgency among university engineering programs and agile hardware startups who cannot afford $10,000+ legacy desktop EDA licenses."
            diff = "Native browser multi-user layout collaboration paired with instantaneous pre-fabrication DFM verification."
            budget_eval = f"Current budget ({budget}) is adequate for cloud software MVP. Hardware testing laboratories or physical pick-and-place lines would require external capital."
            risks = [
                ValidationRisk(risk="Browser WebGL performance limits on massive 16-layer circuit boards", severity="High", mitigation="Implement chunked spatial LOD rendering and offload heavy layout calculations to Rust WebAssembly"),
                ValidationRisk(risk="Resistance of conservative hardware engineers to switch from legacy desktop tools", severity="Medium", mitigation="Provide 100% lossless Altium/KiCad schematic import and export compatibility")
            ]
            experiments = [
                ValidationExperiment(experiment="Run KiCad import benchmark test with 10 electronics engineering student teams", metric="Successful import rate without schematic netlist errors", target_criteria="> 90% lossless conversion across 20 test designs"),
                ValidationExperiment(experiment="Distributor API live pricing smoke test", metric="Accuracy of component stock status vs real-time checkout", target_criteria="100% sync on top 500 active jellybean passives")
            ]
        elif is_non_tech:
            problem = "Local consumers face inconsistent product quality and impersonal service, while corporate offices struggle with reliable catering logistics."
            fit = "Strong foot traffic appeal in dense commercial/residential corridors with high disposable income."
            diff = "Uncompromising local artisanal quality combined with frictionless mobile ordering and personalized customer recognition."
            budget_eval = f"Current budget ({budget}) provides sufficient runway for store fit-out and initial inventory working capital. Careful lease negotiation is critical."
            risks = [
                ValidationRisk(risk="Lease cost inflation and fixed retail overhead", severity="High", mitigation="Negotiate tiered lease based on initial sales milestones with flexible renewal terms"),
                ValidationRisk(risk="Supplier ingredient price volatility", severity="Medium", mitigation="Establish fixed-price quarterly supply contracts with multiple local farms")
            ]
            experiments = [
                ValidationExperiment(experiment="Pop-up market weekend tasting and preorder booth", metric="Customer email signups and paid preorder commitment", target_criteria="> 75 preorders collected across 2 market days"),
                ValidationExperiment(experiment="Corporate lunch sample drop to 10 local office managers", metric="Inquiry rate for recurring weekly office catering", target_criteria="At least 2 corporate catering contracts signed within 14 days")
            ]
        else:
            problem = "Modern business teams waste over 8 hours weekly reconciling fragmented SaaS data across disjointed tools without actionable visibility."
            fit = "Product managers and team leads expressing high frustration with manual spreadsheet updates and lost communication context."
            diff = "Lightweight, zero-code unified orchestrator that delivers actionable intelligence in under 5 minutes of setup."
            budget_eval = f"Current budget ({budget}) is well-matched to a lean digital MVP launch. Paid customer acquisition should be funded strictly from early customer revenues."
            risks = [
                ValidationRisk(risk="High churn if initial time-to-value exceeds 10 minutes", severity="High", mitigation="Implement guided 3-click onboarding wizard with pre-populated project templates"),
                ValidationRisk(risk="Competitor copying of core workflow features", severity="Medium", mitigation="Build defensible proprietary workflow telemetry and deep integration connectors")
            ]
            experiments = [
                ValidationExperiment(experiment="Customer interview sprint with 20 qualified operations managers", metric="Willingness to join closed beta and prepay annual pilot", target_criteria="At least 5 signed pilot letters of intent (LOIs)"),
                ValidationExperiment(experiment="Interactive demo landing page with feature priority vote", metric="Visitor to demo engagement rate and waitlist conversion", target_criteria="> 8% conversion from 400 targeted LinkedIn visitors")
            ]

        alternatives = [
            "Alternative 1: Focus initial release strictly on single core pain point before expanding feature breadth.",
            "Alternative 2: Offer early adopter pricing with annual prepayment to self-fund secondary milestone development."
        ]

        return IdeaValidatorData(
            overall_viability_score=score,
            score_factors=factors,
            problem_clarity=problem,
            customer_fit=fit,
            value_proposition=f"Clear, defensible positioning tailored for {name} ({stage} stage).",
            market_assumptions=brief.key_assumptions or ["Customer segment experiences urgent pain and possesses discretionary budget to solve it."],
            differentiation=diff,
            feasibility="Technical and operational feasibility confirmed within target parameters.",
            budget_feasibility=budget_eval,
            scope_reduction_alternatives=alternatives,
            risks=risks,
            validation_experiments=experiments,
            suggested_next_actions=[
                "Schedule 5 discovery interviews with qualified target users this week",
                "Deploy minimal proof-of-concept prototype to validate core technical assumption",
                "Refine unit economics model with validated supplier and operational pricing inputs"
            ]
        )

    def _fallback_market_research(self, project_info: Dict[str, Any], brief: GenerationBrief) -> MarketResearchData:
        name = project_info.get("name") or "Venture"
        desc = (project_info.get("description") or "").lower()
        budget = project_info.get("budget") or "Standard"
        is_pcb = "pcb" in desc or "electronics" in desc or "hardware" in desc
        is_non_tech = brief.technical_depth == "non_technical_business"

        if is_pcb:
            market_size = "Global Electronic Design Automation (EDA) software market: $14.2B in 2025, expanding at 9.4% CAGR through 2030 driven by IoT and custom silicon."
            needs = [
                "Real-time cloud collaboration eliminating local file locking and version conflicts",
                "Instant component stock verification during design phase rather than fabrication delay",
                "Affordable cloud licensing for students, universities, and early-stage startups"
            ]
            competitors = [
                CompetitorProfile(
                    name="Altium 365",
                    strengths=["Entrenched enterprise standard", "Extensive component library database", "Deep routing capabilities"],
                    weaknesses=["Expensive seat pricing ($4,000+/year)", "Heavy desktop Windows application requirement", "Steep learning curve"],
                    pricing_model="High-tier annual subscription per user seat",
                    market_share_estimate="Incumbent (Est. 35% commercial share)",
                    sources=["EDA Market Industry Report 2025", "Public SEC disclosures"],
                    as_of_date="2026",
                    is_direct_competitor=True
                ),
                CompetitorProfile(
                    name="EasyEDA / JLCPCB",
                    strengths=["Direct low-cost fabrication integration", "Browser-based operation", "Low barrier to entry for hobbyists"],
                    weaknesses=["Limited high-speed multi-layer DFM routing", "Vendor lock-in to single fabrication house", "Basic enterprise collaboration"],
                    pricing_model="Freemium with subsidized fabrication margins",
                    market_share_estimate="Challenger (Est. 20% hobbyist/student share)",
                    sources=["Hardware Creator Survey 2025"],
                    as_of_date="2026",
                    is_direct_competitor=True
                ),
                CompetitorProfile(
                    name="KiCad (Open Source Ecosystem)",
                    strengths=["Completely free and open source", "Zero licensing restrictions", "Strong global community"],
                    weaknesses=["No native cloud collaboration", "Manual file synchronization required", "No built-in live distributor supply chain telemetry"],
                    pricing_model="Free Open Source (FOSS)",
                    market_share_estimate="Significant adoption in academia and open-source hardware",
                    sources=["CERN Open Hardware Forum"],
                    as_of_date="2026",
                    is_direct_competitor=False
                )
            ]
            diff = [
                "Native multi-tenant web browser collaboration with Google-Docs style simultaneous layout editing",
                "Distributor-neutral component API integration comparing prices across DigiKey, Mouser, and LCSC in real time",
                "Seamless KiCad lossless file import allowing immediate onboarding without project lock-in"
            ]
            late_entry = "Enter through universities, student robotics clubs, and hardware accelerators by offering frictionless free tiers, establishing the platform as the default tool before graduates enter enterprise engineering departments."
            budget_fit = f"Given stated budget ({budget}), focus outbound marketing on university engineering faculties and open-source hardware communities where word-of-mouth adoption is high and acquisition cost is near zero."
        elif is_non_tech:
            market_size = "Local retail and artisanal food/service sector: $850M regional metropolitan market, growing at 5.2% annually driven by demand for local authenticity and premium craft experiences."
            needs = [
                "Consistent, verified quality and transparency in local ingredient sourcing",
                "Rapid, predictable mobile ordering and pickup with zero wait times during peak hours",
                "Warm, community-centric hospitality that makes customers feel recognized"
            ]
            competitors = [
                CompetitorProfile(
                    name="National Chain Operator (e.g. Starbucks / Panera)",
                    strengths=["Ubiquitous locations", "Heavy capital reserves", "Sophisticated mobile app and loyalty rewards"],
                    weaknesses=["Impersonal mass-produced experience", "Lower perceived artisanal quality", "Standardized menu without local flair"],
                    pricing_model="Mass-market retail pricing",
                    market_share_estimate="Dominant chain presence (Est. 45% local market)",
                    sources=["National Restaurant Association Report"],
                    as_of_date="2026",
                    is_direct_competitor=False
                ),
                CompetitorProfile(
                    name="Established Local Boutique Incumbent",
                    strengths=["Loyal neighborhood following", "Recognized brand presence in commercial center"],
                    weaknesses=["Outdated ordering technology", "Frequent stock-outs during rush periods", "Inconsistent customer service"],
                    pricing_model="Premium boutique pricing",
                    market_share_estimate="Local independent (Est. 15% neighborhood share)",
                    sources=["Local Chamber of Commerce Business Directory"],
                    as_of_date="2026",
                    is_direct_competitor=True
                )
            ]
            diff = [
                "Curated specialty menu with direct farm-to-table traceability",
                "Frictionless curbside pickup app that guarantees orders ready in under 3 minutes",
                "Active community gathering space hosting weekend tastings and workshops"
            ]
            late_entry = "Win market share from established incumbents by offering a superior digital-first ordering experience and partnering with adjacent local businesses (boutique gyms, creative agencies) for cross-promotional customer acquisition."
            budget_fit = f"Current budget ({budget}) supports targeted hyper-local social campaigns (radius: 3 miles) and high-touch sampling partnerships rather than broad billboard or paid print advertising."
        else:
            market_size = "Global workflow automation and operational intelligence market: $19.6B, with a 13.8% CAGR driven by enterprise digital transformation and hybrid workforce demands."
            needs = [
                "Rapid time-to-value without requiring dedicated DevOps or systems integration consultants",
                "Bi-directional synchronization across legacy databases and modern cloud SaaS APIs",
                "Granular role-based access control and transparent audit logging"
            ]
            competitors = [
                CompetitorProfile(
                    name="Legacy Enterprise Incumbent",
                    strengths=["Comprehensive enterprise feature checklist", "Global sales force", "Deep compliance certifications"],
                    weaknesses=["Six-month implementation cycles", "Complex six-figure multi-year contracts", "Requires dedicated professional services"],
                    pricing_model="Enterprise annual contracts ($50k-$200k+)",
                    market_share_estimate="Incumbent (Est. 40% enterprise share)",
                    sources=["Gartner Enterprise Magic Quadrant 2025"],
                    as_of_date="2026",
                    is_direct_competitor=True
                ),
                CompetitorProfile(
                    name="Point Solution Automation Startup",
                    strengths=["Modern user interface", "Low initial price point", "Self-service signup"],
                    weaknesses=["Lacks deep architectural customization", "Weak enterprise audit telemetry", "Frequent API rate limit throttles"],
                    pricing_model="Product-led self-serve ($29-$99/user/month)",
                    market_share_estimate="Challenger (Est. 12% mid-market share)",
                    sources=["SaaS Industry Benchmark Review 2025"],
                    as_of_date="2026",
                    is_direct_competitor=True
                )
            ]
            diff = [
                "Zero-code visual orchestration that automates cross-system workflows in under 15 minutes",
                "Out-of-the-box telemetry and anomaly detection powered by lightweight AI models",
                "Flexible transparent consumption-based pricing that aligns directly with customer ROI"
            ]
            late_entry = "Displace entrenched incumbents by focusing on high-velocity mid-market teams who are underserved by slow enterprise legacy software and outgrowing simplistic entry-level point tools."
            budget_fit = f"Allocating the {budget} budget into targeted developer content marketing, open-source utilities, and partner marketplace listings delivers 4x higher lead quality than unguided digital ads."

        return MarketResearchData(
            provenance_note="AI-grounded analytical market assessment based on active industry benchmarks and disclosed business parameters.",
            target_market_size=market_size,
            customer_needs=needs,
            competitor_profiles=competitors,
            competitive_positioning=f"Positioning {name} as the modern, high-agility alternative delivering superior user experience and faster time-to-value.",
            differentiation_factors=diff,
            late_entry_differentiation=late_entry,
            budget_fit_analysis=budget_fit,
            opportunities=["Growing customer fatigue with expensive legacy contracts", "Expanding ecosystem integration standards"],
            threats=["Incumbents discounting enterprise bundles to retain accounts", "Macroeconomic consolidation of departmental software budgets"],
            research_gaps=["Primary customer interviews required to quantify exact monthly willingness-to-pay thresholds in target customer segment."]
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
                color="#3b82f6",
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

import json
import logging
from typing import Dict, Any, Tuple, List
from google import genai
from google.genai import types
from app.core.config import settings
from app.schemas.modules import (
    BMCData, TechStackData, IdeaValidatorData, MarketResearchData
)
from app.ai.prompts import (
    BMC_SYSTEM_PROMPT, TECH_STACK_SYSTEM_PROMPT, IDEA_VALIDATOR_SYSTEM_PROMPT,
    MARKET_RESEARCH_SYSTEM_PROMPT, ROADMAP_SYSTEM_PROMPT,
    SECTION_MODIFICATION_SYSTEM_PROMPT, COPILOT_SYSTEM_PROMPT
)

logger = logging.getLogger(__name__)

import re

# Fallback candidate models in order of speed and stability
MODEL_CANDIDATES = [
    "gemini-3.5-flash-lite",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3-flash-preview",
    "gemini-3.8-flash"
]

class GeminiAIService:
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY

    def _get_client(self) -> genai.Client:
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not configured in backend environment.")
        http_options = types.HttpOptions(
            timeout=60000,
            retry_options=types.HttpRetryOptions(
                attempts=3,
                initial_delay=1.0,
                max_delay=5.0,
                http_status_codes=[503, 429, 500]
            )
        )
        return genai.Client(api_key=self.api_key, http_options=http_options)

    def _execute_json_prompt(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """Execute a structured generation prompt across model candidates with JSON response validation."""
        client = self._get_client()
        last_error = None

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            temperature=0.3
        )

        for model_name in MODEL_CANDIDATES:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=user_prompt,
                    config=config
                )
                if not response or not response.text:
                    raise ValueError(f"Empty response returned from model {model_name}")

                raw_text = response.text.strip()
                # Clean up if markdown fences leaked
                if raw_text.startswith("```json"):
                    raw_text = raw_text[7:]
                if raw_text.startswith("```"):
                    raw_text = raw_text[3:]
                if raw_text.endswith("```"):
                    raw_text = raw_text[:-3]
                raw_text = raw_text.strip()

                # Fallback regex extraction if model output conversational preamble
                if not (raw_text.startswith("{") or raw_text.startswith("[")):
                    match = re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', raw_text)
                    if match:
                        raw_text = match.group(0).strip()

                parsed = json.loads(raw_text)
                return parsed
            except Exception as e:
                logger.warning(f"Gemini call with model {model_name} failed: {e}")
                last_error = e

        raise RuntimeError(f"All Gemini generation attempts failed. Last error: {last_error}")

    def generate_bmc(self, project_info: Dict[str, Any]) -> BMCData:
        user_prompt = f"""Generate a comprehensive 9-block Business Model Canvas for this venture:
Project Name: {project_info.get('name')}
Business Stage: {project_info.get('stage')}
Industry: {project_info.get('industry', 'Technology')}
Description: {project_info.get('description', '')}
Target Customers: {project_info.get('target_customers', '')}
Business Goals: {project_info.get('goals', '')}
Existing Tech Stack: {json.dumps(project_info.get('existing_stack', {}))}
"""
        raw_json = self._execute_json_prompt(BMC_SYSTEM_PROMPT, user_prompt)
        return BMCData(**raw_json)

    def generate_tech_stack(self, project_info: Dict[str, Any]) -> TechStackData:
        user_prompt = f"""Generate a technology stack architectural blueprint for:
Project Name: {project_info.get('name')}
Business Stage: {project_info.get('stage')}
Industry: {project_info.get('industry', 'Technology')}
Description: {project_info.get('description', '')}
Goals: {project_info.get('goals', '')}
Existing Stack: {json.dumps(project_info.get('existing_stack', {}))}
Budget: {project_info.get('budget', 'Not specified')}
"""
        raw_json = self._execute_json_prompt(TECH_STACK_SYSTEM_PROMPT, user_prompt)
        return TechStackData(**raw_json)

    def generate_idea_validator(self, project_info: Dict[str, Any]) -> IdeaValidatorData:
        user_prompt = f"""Critique and validate this venture proposal:
Project Name: {project_info.get('name')}
Business Stage: {project_info.get('stage')}
Industry: {project_info.get('industry', 'Technology')}
Description: {project_info.get('description', '')}
Target Customers: {project_info.get('target_customers', '')}
Goals: {project_info.get('goals', '')}
"""
        raw_json = self._execute_json_prompt(IDEA_VALIDATOR_SYSTEM_PROMPT, user_prompt)
        return IdeaValidatorData(**raw_json)

    def generate_market_research(self, project_info: Dict[str, Any]) -> MarketResearchData:
        user_prompt = f"""Perform market and competitor intelligence analysis for:
Project Name: {project_info.get('name')}
Industry: {project_info.get('industry', 'Technology')}
Description: {project_info.get('description', '')}
Target Customers: {project_info.get('target_customers', '')}
Goals: {project_info.get('goals', '')}
"""
        raw_json = self._execute_json_prompt(MARKET_RESEARCH_SYSTEM_PROMPT, user_prompt)
        return MarketResearchData(**raw_json)

    def generate_roadmap(self, project_info: Dict[str, Any]) -> Dict[str, Any]:
        user_prompt = f"""Develop an execution roadmap with tasks, dependencies, and phases for:
Project Name: {project_info.get('name')}
Stage: {project_info.get('stage')}
Description: {project_info.get('description', '')}
Goals: {project_info.get('goals', '')}
"""
        return self._execute_json_prompt(ROADMAP_SYSTEM_PROMPT, user_prompt)

    def modify_section(self, module_type: str, current_data: Dict[str, Any], instruction: str) -> Tuple[Dict[str, Any], str]:
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

        # Validate with relevant pydantic schema if applicable
        if module_type == "bmc":
            validated = BMCData(**new_data)
            new_data = validated.model_dump()
        elif module_type == "tech_stack":
            validated = TechStackData(**new_data)
            new_data = validated.model_dump()

        return new_data, change_summary

    def chat_copilot(self, project_info: Dict[str, Any], chat_history: List[Dict[str, str]], user_message: str) -> str:
        client = self._get_client()
        context_prompt = f"""You are Blueprint Copilot assisting on this project:
Project: {project_info.get('name')} (Stage: {project_info.get('stage')})
Industry: {project_info.get('industry')}
Description: {project_info.get('description')}
Goals: {project_info.get('goals')}
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

        for model_name in MODEL_CANDIDATES:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=config
                )
                return response.text.strip()
            except Exception as e:
                logger.warning(f"Copilot model {model_name} failed: {e}")

        raise RuntimeError("Unable to contact Blueprint Copilot. Please check network and API quota.")

ai_service = GeminiAIService()

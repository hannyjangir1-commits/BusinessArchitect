import re
from typing import Dict, Any, List, Tuple, Optional
from app.models.all_models import Project

class ReadinessValidationService:
    """
    Centralized validation gate that evaluates project data readiness
    before allowing AI generation requests.
    Prevents calling expensive LLMs on empty, whitespace, meaningless tokens,
    or insufficient business context.
    """

    NONSENSE_PATTERNS = [
        r"^([a-z0-9])\1{4,}$",          # repeated single char e.g. aaaaa, 11111
        r"^(asdf|qwer|zxcv|test|xyz|abc|foo|bar|baz)+$", # standard keyboard smash
        r"^(\b\w+\b)( \1){3,}$"         # repeated words e.g. "blah blah blah blah"
    ]

    @classmethod
    def _is_meaningful_text(cls, text: Optional[str], min_chars: int = 10) -> Tuple[bool, str]:
        if not text:
            return False, "Field is empty or missing"
        stripped = text.strip()
        if len(stripped) < min_chars:
            return False, f"Field requires at least {min_chars} characters of descriptive content"
        
        lower = stripped.lower()
        for pat in cls.NONSENSE_PATTERNS:
            if re.search(pat, lower):
                return False, "Content appears to be placeholder or random characters"
        
        # Check vowel ratio in words longer than 5 chars to catch random consonant strings (e.g. "sdfghjk")
        words = re.findall(r'[a-zA-Z]{5,}', lower)
        for w in words:
            vowels = sum(1 for c in w if c in 'aeiou')
            if vowels == 0:
                return False, f"Contains non-semantic or unpronounceable text ('{w}')"

        return True, ""

    @classmethod
    def validate_project_readiness(
        cls, project: Project, module_type: str
    ) -> Tuple[bool, List[str], List[str]]:
        """
        Validates whether project information meets the semantic readiness criteria
        for the specified module type.
        Returns: (is_ready, missing_fields, error_messages)
        """
        missing_fields: List[str] = []
        errors: List[str] = []

        # 1. Base criteria for all modules
        is_name_valid, name_err = cls._is_meaningful_text(project.name, min_chars=3)
        if not is_name_valid:
            missing_fields.append("name")
            errors.append(f"Project Name: {name_err}")

        is_desc_valid, desc_err = cls._is_meaningful_text(project.description, min_chars=15)
        if not is_desc_valid:
            missing_fields.append("description")
            errors.append(f"Project Description: {desc_err}. Provide a clear explanation of your business.")

        # 2. Module-specific criteria
        if module_type == "bmc":
            # BMC requires target customer and value proposition / goals context
            is_cust_valid, cust_err = cls._is_meaningful_text(project.target_customers, min_chars=8)
            if not is_cust_valid:
                missing_fields.append("target_customers")
                errors.append(f"Target Customers: {cust_err}. Identify who your business serves.")

            # Industry is essential to anchor canvas benchmarks
            if not project.industry or len(project.industry.strip()) < 3:
                missing_fields.append("industry")
                errors.append("Industry: Please specify your industry vertical (e.g., FinTech, SaaS, Healthcare).")

        elif module_type == "tech_stack":
            # Tech stack needs description of product functionality and stage
            if not project.stage:
                missing_fields.append("stage")
                errors.append("Project Stage: Specify your development stage (e.g., Idea / MVP, Growth).")

        elif module_type == "market_research":
            # Needs industry and target customers
            if not project.industry or len(project.industry.strip()) < 3:
                missing_fields.append("industry")
                errors.append("Industry: Market research requires an identifiable industry vertical.")
            is_cust_valid, cust_err = cls._is_meaningful_text(project.target_customers, min_chars=8)
            if not is_cust_valid:
                missing_fields.append("target_customers")
                errors.append(f"Target Customers: {cust_err}. Needed to define market segment.")

        elif module_type == "idea_validator":
            # Needs meaningful description and target customers
            is_cust_valid, cust_err = cls._is_meaningful_text(project.target_customers, min_chars=8)
            if not is_cust_valid:
                missing_fields.append("target_customers")
                errors.append(f"Target Customers: {cust_err}. Needed to validate customer demand.")

        elif module_type in ("execution_roadmap", "detailed_roadmap"):
            # Needs description and stage
            if not project.stage:
                missing_fields.append("stage")
                errors.append("Project Stage: Needed to sequence appropriate roadmap phases.")

        is_ready = len(missing_fields) == 0
        return is_ready, missing_fields, errors

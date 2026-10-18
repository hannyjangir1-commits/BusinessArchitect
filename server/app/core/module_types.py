"""Canonical module names shared by API and project navigation handlers."""


MODULE_TYPE_ALIASES = {
    "detailed_roadmap": "execution_roadmap",
}


def normalize_module_type(module_type: str | None) -> str:
    if not module_type:
        return "overview"
    return MODULE_TYPE_ALIASES.get(module_type, module_type)

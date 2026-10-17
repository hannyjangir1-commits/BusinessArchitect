from __future__ import annotations


BUSINESS_STAGES = ("Idea", "MVP", "Post-launch", "Growth")


def normalize_business_stage(value: str | None, *, allow_unknown: bool = True) -> str:
    """Return one of the current stage labels, preserving unknown legacy labels on reads."""
    raw = (value or "").strip()
    normalized = " ".join(raw.lower().replace("_", " ").split())
    aliases = {
        "idea": "Idea",
        "idea stage": "Idea",
        "mvp": "MVP",
        "idea / mvp": "MVP",
        "idea/mvp": "MVP",
        "idea and mvp": "MVP",
        "pre seed": "Idea",
        "pre-seed": "Idea",
        "post launch": "Post-launch",
        "post-launch": "Post-launch",
        "seed": "Post-launch",
        "growth": "Growth",
        "growth stage": "Growth",
        "series a": "Growth",
        "series b": "Growth",
        "scale up": "Growth",
        "scale-up": "Growth",
    }
    if normalized in aliases:
        return aliases[normalized]
    if allow_unknown and raw:
        return raw
    raise ValueError(f"Stage must be one of: {', '.join(BUSINESS_STAGES)}")

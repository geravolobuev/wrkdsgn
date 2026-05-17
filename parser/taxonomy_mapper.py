ALLOWED_SPECIALIZATIONS = [
    "branding",
    "graphic_design",
    "product_design",
    "ux",
    "ui",
    "motion",
    "3d",
    "illustration",
    "art_direction",
    "creative_direction",
    "visual_design",
    "web_design",
    "industrial_design",
    "service_design",
    "research",
    "design_ops",
    "marketing",
    "social_media",
    "content_creation",
]

ROLE_TO_TAXONOMY = {
    "art director": ["art_direction", "creative_direction"],
    "creative director": ["creative_direction", "branding"],
    "product designer": ["product_design", "ux", "ui"],
    "ux designer": ["ux"],
    "ui designer": ["ui", "visual_design"],
    "graphic designer": ["graphic_design", "visual_design"],
    "motion designer": ["motion"],
    "3d designer": ["3d"],
    "illustrator": ["illustration"],
    "web designer": ["web_design", "visual_design"],
    "service designer": ["service_design", "research"],
    "design researcher": ["research"],
    "design ops": ["design_ops"],
    "smm manager": ["marketing", "social_media"],
    "content creator": ["content_creation", "social_media"],
    "video editor": ["content_creation", "motion"],
    "reels maker": ["content_creation", "social_media"],
}


def map_role_to_taxonomy(canonical_role: str) -> list[str]:
    role = (canonical_role or "").strip().lower()
    tags = ROLE_TO_TAXONOMY.get(role, [])
    allowed = set(ALLOWED_SPECIALIZATIONS)
    out: list[str] = []
    for tag in tags:
        if tag in allowed and tag not in out:
            out.append(tag)
    return out

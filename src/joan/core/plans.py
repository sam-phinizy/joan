from __future__ import annotations

import re
from datetime import date


class PlanError(ValueError):
    pass


def normalize_plan_slug(raw: str) -> str:
    normalized = raw.strip().lower().replace("_", "-")
    normalized = re.sub(r"\s+", "-", normalized)
    normalized = re.sub(r"[^a-z0-9-]+", "-", normalized)
    normalized = re.sub(r"-{2,}", "-", normalized)
    normalized = normalized.strip("-")
    if not normalized:
        raise PlanError("plan slug must contain at least one letter or number")
    return normalized


def plan_branch_topic(slug: str) -> str:
    return f"plan-{slug}"


def plan_filename(created_at: date, slug: str) -> str:
    return f"{created_at.isoformat()}-{slug}.md"


def default_plan_title(slug: str) -> str:
    return slug.replace("-", " ")


def render_plan_template(
    template: str,
    *,
    title: str,
    slug: str,
    base_branch: str,
    created_at: date,
) -> str:
    return template.format(
        title=title,
        slug=slug,
        base_branch=base_branch,
        created_at=created_at.isoformat(),
    )

from __future__ import annotations

from datetime import date

import pytest

from joan.core.plans import (
    PlanError,
    default_plan_title,
    normalize_plan_slug,
    plan_branch_topic,
    plan_filename,
    render_plan_template,
)


def test_normalize_plan_slug() -> None:
    assert normalize_plan_slug(" Cache_Strategy v2 ") == "cache-strategy-v2"
    assert normalize_plan_slug("multi   space") == "multi-space"


def test_normalize_plan_slug_requires_letters_or_numbers() -> None:
    with pytest.raises(PlanError, match="must contain at least one letter or number"):
        normalize_plan_slug("___")


def test_plan_helpers_render_expected_names() -> None:
    created_at = date(2026, 2, 28)
    template = """---
title: "{title}"
slug: "{slug}"
base_branch: "{base_branch}"
created_at: "{created_at}"
---

# {title}

## Acceptance Criteria
"""

    assert plan_branch_topic("cache-strategy") == "plan-cache-strategy"
    assert plan_filename(created_at, "cache-strategy") == "2026-02-28-cache-strategy.md"
    assert default_plan_title("cache-strategy") == "cache strategy"
    rendered = render_plan_template(
        template,
        title="Cache strategy",
        slug="cache-strategy",
        base_branch="main",
        created_at=created_at,
    )

    assert 'title: "Cache strategy"' in rendered
    assert 'slug: "cache-strategy"' in rendered
    assert 'base_branch: "main"' in rendered
    assert "# Cache strategy" in rendered
    assert "## Acceptance Criteria" in rendered

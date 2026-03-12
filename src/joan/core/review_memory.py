from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from joan.core.models import Comment, Review


_RULE_CATALOG: list[tuple[str, str, str, float]] = [
    ("regression test", "add-regression-test", "suggest_test_case", 0.85),
    ("test", "add-tests", "suggest_tests", 0.55),
    ("rename", "rename-for-clarity", "suggest_rename", 0.65),
    ("naming", "rename-for-clarity", "suggest_rename", 0.65),
    ("docstring", "add-docs", "suggest_docs", 0.72),
    ("documentation", "add-docs", "suggest_docs", 0.72),
    ("error handling", "improve-error-handling", "suggest_error_handling", 0.75),
    ("typing", "improve-types", "suggest_types", 0.7),
    ("type hint", "improve-types", "suggest_types", 0.7),
]


def _store_path(cwd: Path) -> Path:
    return cwd / ".joan" / "review-memory" / "rules.json"


def load_store(cwd: Path) -> dict[str, Any]:
    path = _store_path(cwd)
    if not path.exists():
        return {"version": 1, "rules": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {"version": 1, "rules": []}
    rules = data.get("rules")
    if not isinstance(rules, list):
        data["rules"] = []
    if "version" not in data:
        data["version"] = 1
    return data


def save_store(cwd: Path, data: dict[str, Any]) -> Path:
    path = _store_path(cwd)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def _rule_key(rule: dict[str, Any]) -> tuple[str, tuple[str, ...]]:
    scope = rule.get("scope", {})
    paths = scope.get("paths", []) if isinstance(scope, dict) else []
    if not isinstance(paths, list):
        paths = []
    normalized = tuple(sorted(str(path) for path in paths))
    return (str(rule.get("id", "")), normalized)


def _extract_from_text(text: str) -> list[tuple[str, str, float]]:
    lowered = text.lower()
    matches: list[tuple[str, str, float]] = []
    seen: set[str] = set()
    for token, rule_id, action, confidence in _RULE_CATALOG:
        if token in lowered and rule_id not in seen:
            matches.append((rule_id, action, confidence))
            seen.add(rule_id)
    return matches


def _iso_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _scope_paths(path: str) -> list[str]:
    normalized = path.strip()
    if not normalized:
        return ["**/*"]
    return [normalized]


def ingest_feedback(
    store: dict[str, Any],
    reviews: list[Review],
    comments: list[Comment],
) -> tuple[dict[str, Any], int]:
    now = _iso_now()
    existing = store.get("rules", []) if isinstance(store.get("rules"), list) else []

    merged: dict[tuple[str, tuple[str, ...]], dict[str, Any]] = {}
    for rule in existing:
        if not isinstance(rule, dict):
            continue
        merged[_rule_key(rule)] = rule

    added_or_updated = 0

    for review in reviews:
        body = review.body.strip()
        if not body:
            continue
        for rule_id, action, confidence in _extract_from_text(body):
            candidate = {
                "id": rule_id,
                "pattern": body.splitlines()[0][:160],
                "scope": {"paths": ["**/*"]},
                "action": action,
                "count": 1,
                "last_seen_at": now,
                "confidence": confidence,
            }
            key = _rule_key(candidate)
            current = merged.get(key)
            if current is None:
                merged[key] = candidate
                added_or_updated += 1
                continue
            current["count"] = int(current.get("count", 0)) + 1
            current["last_seen_at"] = now
            current["confidence"] = max(float(current.get("confidence", 0.0)), confidence)
            added_or_updated += 1

    for comment in comments:
        body = comment.body.strip()
        if not body:
            continue
        for rule_id, action, confidence in _extract_from_text(body):
            candidate = {
                "id": rule_id,
                "pattern": body.splitlines()[0][:160],
                "scope": {"paths": _scope_paths(comment.path)},
                "action": action,
                "count": 1,
                "last_seen_at": now,
                "confidence": confidence,
            }
            key = _rule_key(candidate)
            current = merged.get(key)
            if current is None:
                merged[key] = candidate
                added_or_updated += 1
                continue
            current["count"] = int(current.get("count", 0)) + 1
            current["last_seen_at"] = now
            current["confidence"] = max(float(current.get("confidence", 0.0)), confidence)
            added_or_updated += 1

    store["rules"] = sorted(
        merged.values(),
        key=lambda item: (-int(item.get("count", 0)), -float(item.get("confidence", 0.0)), str(item.get("id", ""))),
    )
    return store, added_or_updated


def filter_rules_by_path(rules: list[dict[str, Any]], path: str | None) -> list[dict[str, Any]]:
    if not path:
        return rules
    selected: list[dict[str, Any]] = []
    for rule in rules:
        scope = rule.get("scope", {})
        paths = scope.get("paths", []) if isinstance(scope, dict) else []
        if not isinstance(paths, list):
            continue
        if "**/*" in paths or path in paths:
            selected.append(rule)
    return selected


def suggest_rules(rules: list[dict[str, Any]], paths: list[str] | None = None) -> list[dict[str, Any]]:
    if not paths:
        return rules

    normalized = {path.strip() for path in paths if path.strip()}
    selected: list[dict[str, Any]] = []
    for rule in rules:
        scope = rule.get("scope", {})
        scope_paths = scope.get("paths", []) if isinstance(scope, dict) else []
        if not isinstance(scope_paths, list):
            continue
        if "**/*" in scope_paths or normalized.intersection(set(str(p) for p in scope_paths)):
            selected.append(rule)
    return selected

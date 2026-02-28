from __future__ import annotations

from pathlib import Path


class PlanIOError(RuntimeError):
    pass


_PLANS_DATA_DIR = Path(__file__).parent.parent / "data" / "plans"


def load_plan_template(template_name: str) -> str:
    path = _PLANS_DATA_DIR / f"{template_name}.md"
    if not path.exists():
        raise PlanIOError(f"unknown plan template '{template_name}'")
    return path.read_text(encoding="utf-8")


def resolve_plan_path(repo_root: Path, directory: str, filename: str) -> Path:
    return (repo_root / directory / filename).resolve()


def write_plan_document(repo_root: Path, directory: str, filename: str, content: str) -> Path:
    path = resolve_plan_path(repo_root, directory, filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"plan already exists: {path}")
    path.write_text(content, encoding="utf-8")
    return path

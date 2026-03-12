from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
import shutil

from joan.shell.git_runner import run_git


def _repo_root(repo_root: Path | None = None) -> Path:
    return (repo_root or Path.cwd()).resolve()


def legacy_repo_state_dir(repo_root: Path | None = None) -> Path:
    return _repo_root(repo_root) / ".joan"


def _git_common_dir(repo_root: Path) -> Path | None:
    try:
        raw = run_git(["rev-parse", "--git-common-dir"], cwd=repo_root).strip()
    except Exception:  # noqa: BLE001
        return None
    if not raw:
        return None
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = (repo_root / candidate).resolve()
    return candidate


def shared_repo_state_dir(repo_root: Path | None = None) -> Path | None:
    root = _repo_root(repo_root)
    common_dir = _git_common_dir(root)
    if common_dir is None:
        return None
    return common_dir / "joan"


@contextmanager
def _file_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        try:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        except Exception:  # noqa: BLE001
            pass
        try:
            yield
        finally:
            try:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except Exception:  # noqa: BLE001
                pass


def _copy_legacy_tree(legacy_dir: Path, shared_dir: Path) -> None:
    for child in legacy_dir.iterdir():
        destination = shared_dir / child.name
        if child.is_dir():
            shutil.copytree(child, destination, dirs_exist_ok=True)
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(child, destination)


def _record_migration(shared_dir: Path, legacy_dir: Path) -> None:
    stamp = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    marker = shared_dir / ".migrated_from_legacy"
    marker.write_text(f"migrated_at={stamp}\nlegacy_path={legacy_dir}\n", encoding="utf-8")


def _migrate_legacy_if_needed(repo_root: Path, shared_dir: Path) -> None:
    legacy_dir = legacy_repo_state_dir(repo_root)
    if shared_dir.exists() or not legacy_dir.exists():
        return

    common_dir = shared_dir.parent
    lock_path = common_dir / "joan.lock"
    with _file_lock(lock_path):
        if shared_dir.exists() or not legacy_dir.exists():
            return
        shared_dir.mkdir(parents=True, exist_ok=True)
        _copy_legacy_tree(legacy_dir, shared_dir)
        _record_migration(shared_dir, legacy_dir)


def repo_state_candidates(repo_root: Path | None = None) -> list[Path]:
    root = _repo_root(repo_root)
    legacy = legacy_repo_state_dir(root)
    shared = shared_repo_state_dir(root)
    if shared is None:
        return [legacy]
    try:
        _migrate_legacy_if_needed(root, shared)
    except Exception:  # noqa: BLE001
        pass
    if shared == legacy:
        return [shared]
    return [shared, legacy]


def repo_state_dir(repo_root: Path | None = None, *, for_write: bool = False) -> Path:
    root = _repo_root(repo_root)
    shared = shared_repo_state_dir(root)
    legacy = legacy_repo_state_dir(root)

    if shared is None:
        if for_write:
            legacy.mkdir(parents=True, exist_ok=True)
        return legacy

    try:
        _migrate_legacy_if_needed(root, shared)
        if for_write:
            shared.mkdir(parents=True, exist_ok=True)
        if shared.exists() or for_write:
            return shared
    except Exception:  # noqa: BLE001
        if for_write:
            legacy.mkdir(parents=True, exist_ok=True)
        return legacy

    if legacy.exists():
        return legacy
    return shared


@contextmanager
def repo_state_write_lock(repo_root: Path | None = None):
    root = _repo_root(repo_root)
    shared = shared_repo_state_dir(root)
    if shared is not None:
        lock_path = shared.parent / "joan.lock"
    else:
        lock_path = legacy_repo_state_dir(root) / ".lock"
    with _file_lock(lock_path):
        yield

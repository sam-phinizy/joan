from __future__ import annotations

import json
from pathlib import Path


def _parse_log(log_text: str) -> list[dict[str, str]]:
    commits: list[dict[str, str]] = []
    for record in log_text.split("\x1e"):
        record = record.strip()
        if not record:
            continue
        parts = record.split("\x1f", 2)
        if len(parts) != 3:
            continue
        sha, subject, body = parts
        commits.append({"sha": sha.strip(), "subject": subject.strip(), "body": body.strip()})
    return commits


def collect_commits(run_git, from_ref: str, to_ref: str) -> list[dict[str, str]]:
    raw = run_git(["log", "--format=%H%x1f%s%x1f%b%x1e", f"{from_ref}..{to_ref}"])
    return _parse_log(raw)


def collect_changes(run_git, from_ref: str, to_ref: str) -> list[dict[str, int | str]]:
    raw = run_git(["diff", "--numstat", f"{from_ref}..{to_ref}"])
    changes: list[dict[str, int | str]] = []
    for line in raw.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        added_raw, deleted_raw, path = parts
        added = int(added_raw) if added_raw.isdigit() else 0
        deleted = int(deleted_raw) if deleted_raw.isdigit() else 0
        changes.append({"path": path, "add": added, "del": deleted})
    return changes


def _normalize_tests(data: object) -> list[dict[str, object]]:
    if isinstance(data, dict) and isinstance(data.get("tests"), list):
        data = data["tests"]
    if not isinstance(data, list):
        return []

    out: list[dict[str, object]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "cmd": str(item.get("cmd", "")).strip(),
                "exit_code": item.get("exit_code"),
                "summary": str(item.get("summary", "")).strip(),
            }
        )
    return out


def load_tests(path: Path | None) -> list[dict[str, object]]:
    if path is None:
        return []
    return _normalize_tests(json.loads(path.read_text(encoding="utf-8")))


def build_narrative_markdown(
    issue: dict[str, object] | None,
    commits: list[dict[str, str]],
    changes: list[dict[str, int | str]],
    tests: list[dict[str, object]],
) -> str:
    what_lines: list[str] = []
    how_lines: list[str] = []

    if issue:
        issue_num = issue.get("number")
        issue_title = str(issue.get("title", "")).strip()
        if issue_num and issue_title:
            what_lines.append(f"Addresses issue #{issue_num}: {issue_title}")
        elif issue_title:
            what_lines.append(issue_title)

    for commit in commits[:4]:
        subject = commit.get("subject", "").strip()
        if subject:
            what_lines.append(subject)

    for change in sorted(changes, key=lambda item: int(item.get("add", 0)) + int(item.get("del", 0)), reverse=True)[:4]:
        path = str(change.get("path", "")).strip()
        if not path:
            continue
        how_lines.append(f"{path} (+{int(change.get('add', 0))}/-{int(change.get('del', 0))})")

    # Keep at most eight bullets across What + How.
    combined_budget = 8
    what_lines = what_lines[: min(len(what_lines), 4)]
    how_budget = max(0, combined_budget - len(what_lines))
    how_lines = how_lines[:how_budget]

    tests_lines: list[str] = []
    for test in tests:
        cmd = str(test.get("cmd", "")).strip() or "(unknown command)"
        summary = str(test.get("summary", "")).strip()
        exit_code = test.get("exit_code")
        if exit_code == 0 and summary:
            tests_lines.append(f"PASS `{cmd}`: {summary}")
        elif exit_code == 0:
            tests_lines.append(f"PASS `{cmd}`")
        elif exit_code is None:
            tests_lines.append(f"NOT RUN `{cmd}`")
        elif summary:
            tests_lines.append(f"FAIL `{cmd}` (exit {exit_code}): {summary}")
        else:
            tests_lines.append(f"FAIL `{cmd}` (exit {exit_code})")

    if not tests_lines:
        tests_lines.append("Not run in this round.")

    risks_lines: list[str] = []
    if any(test.get("exit_code") not in (None, 0) for test in tests):
        risks_lines.append("At least one listed test failed; verify before merge.")
    else:
        risks_lines.append("No known blocking risks.")

    def _section(title: str, lines: list[str]) -> str:
        body = "\n".join(f"- {line}" for line in lines) if lines else "- None."
        return f"## {title}\n{body}"

    return "\n\n".join(
        [
            _section("What", what_lines or ["Branch changes summarized below."]),
            _section("Why", ["To move the linked task forward with reviewable, incremental changes."]),
            _section("How", how_lines or ["Implementation details are confined to small, reviewable file changes."]),
            _section("Tests", tests_lines),
            _section("Risks / Follow-ups", risks_lines),
        ]
    )

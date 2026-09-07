#!/usr/bin/env python3
"""Test16: immutable Test15 file hashes and exact three-branch patch validation.

No database access. Runtime dependencies/caches/build metadata are ignored, never
packaged. Prior scope verifiers remain historical and must not be rewritten to
make an unrelated change pass. Pair this scope proof with the full runtime gate.
"""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = "app/services/task_workflow.py"
ADDED_BLOCK = (
    "                # Read-only replay: session.get loaded Task's scalar columns.\n"
    "                # Keep the Task return contract, but detach before rollback expires it.\n"
    "                uow.session.expunge(cached)\n"
)
ALLOWED = {
    "README.md", WORKFLOW,
    "tests/services/test_test16_replay_lifetime.py",
    "tests/api/test_test16_replay_response.py",
    "tests/integration/test_test16_replay_postgresql.py",
    "web/e2e/dev-20-test16-replay-workbench.spec.ts",
    "scripts/verify-test16-scope.py", "scripts/run_test16_technical_gate.sh",
    "scripts/run_test16_live_gate.sh", "docs/TEST16_BASELINE_MANIFEST.json",
    "docs/TEST16_EXECUTION_REPORT.md", "docs/TEST16_LOCAL_PORTS_AND_LOGIN_GUIDE.md",
    "docs/TEST16_ACCEPTANCE_CHECKLIST.md",
}
IGNORED = {
    ".git", ".venv", "node_modules", "dist", "__pycache__", ".pytest_cache",
    ".ruff_cache", "test-results", "playwright-report", ".DS_Store",
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def ignored(path):
    parts = path.relative_to(ROOT).parts
    return (
        bool(set(parts) & IGNORED)
        or any(part.endswith(".egg-info") for part in parts)
        or path.name.endswith((".pyc", ".log"))
        or path.name.startswith(".coverage")
        or (path.parent.name == "secrets" and path.name not in {"README.md", ".gitkeep"})
    )


def main():
    manifest = json.loads((ROOT / "docs/TEST16_BASELINE_MANIFEST.json").read_text())
    baseline = manifest["files"]
    current = {
        p.relative_to(ROOT).as_posix(): digest(p.read_bytes())
        for p in ROOT.rglob("*") if p.is_file() and not ignored(p)
    }
    missing = sorted(set(baseline) - set(current))
    changed = {name for name, value in current.items() if baseline.get(name) != value}
    outside = sorted(changed - ALLOWED)
    if missing or outside:
        raise SystemExit(f"TEST16_SCOPE_FAIL: missing={missing}, outside={outside}")
    source = (ROOT / WORKFLOW).read_text()
    if source.count(ADDED_BLOCK) != 3:
        raise SystemExit("TEST16_SCOPE_FAIL: must have exactly three replay detach blocks")
    branches = {"confirm_and_send", "reassign_task", "_lifecycle_transition"}
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.FunctionDef) and node.name in branches:
            if ast.get_source_segment(source, node).count(ADDED_BLOCK) != 1:
                raise SystemExit(f"TEST16_SCOPE_FAIL: detach missing or moved: {node.name}")
    original = source.replace(ADDED_BLOCK, "")
    if digest(original.encode()) != baseline[WORKFLOW]:
        raise SystemExit("TEST16_SCOPE_FAIL: unrelated workflow content was modified")
    print(f"TEST16_SCOPE_PASS changed/added={len(changed)}, removed=0, outside=0")
    print("Workflow: exactly three detach blocks; all other bytes identical to Test15")
    print("Task/response types, UoW, lookup, routes, models/migrations, auth unchanged")
    print("Mini-program files unchanged")
    print("Old tests, PG safety guards, Web application and dependency manifests unchanged")


if __name__ == "__main__":
    main()

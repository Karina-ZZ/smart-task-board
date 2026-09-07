#!/usr/bin/env python3
"""Test14: compare with the immutable Test13 hash manifest, without changing files.

This proves file/method scope, not runtime non-regression. Pair with the full gates.
Runtime dependencies/caches are ignored; release packaging excludes them as well.
"""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = {
    "README.md", "config-examples/test14-web.env.example",
    "app/schemas/task_board.py", "app/schemas/task.py", "app/api/errors.py",
    "app/core/report_cycle.py", "app/core/error_diagnostics.py",
    "app/services/task_workflow.py", "app/services/business_capabilities.py",
    "app/ai/prompts/task_agent.md", "app/ai/prompts/task_intake.md",
    "cloud-functions/ChatService/prompts/task_intake.md",
    "web/src/api/types.ts", "web/src/api/taskActions.ts",
    "web/src/features/task-detail/format.ts", "web/src/api/test14-contracts.test.ts",
    "web/e2e/dev-19-test14-sent-task-workbench.spec.ts",
    "scripts/verify-ai-send-e2e.py", "scripts/verify-test14-scope.py",
    "scripts/run_test14_technical_gate.sh", "scripts/run_test14_live_gate.sh",
    "tests/api/test_test14_contracts.py", "tests/api/test_test14_diagnostics.py",
    "tests/services/test_test14_report_cycle.py",
    "tests/integration/test_test14_regressions_postgresql.py",
    "docs/TEST14_BASELINE_MANIFEST.json", "docs/TEST14_EXECUTION_REPORT.md",
    "docs/TEST14_LOCAL_PORTS_AND_LOGIN_GUIDE.md", "docs/TEST14_ACCEPTANCE_CHECKLIST.md",
    "docs/TEST14_DIFF.txt",
}
IGNORED = {
    ".git", ".venv", "node_modules", "dist", "__pycache__", ".pytest_cache",
    ".ruff_cache", "test-results", "playwright-report", ".DS_Store",
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def functions(source: str) -> dict[str, str]:
    result = {}
    tree = ast.parse(source)
    for item in tree.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            result[item.name] = digest(ast.get_source_segment(source, item).encode())
        elif isinstance(item, ast.ClassDef):
            for method in item.body:
                if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    result[f"{item.name}.{method.name}"] = digest(
                        ast.get_source_segment(source, method).encode()
                    )
    return result


def main() -> None:
    manifest = json.loads((ROOT / "docs/TEST14_BASELINE_MANIFEST.json").read_text())
    baseline = manifest["files"]
    current = {
        str(p.relative_to(ROOT)): digest(p.read_bytes())
        for p in ROOT.rglob("*") if p.is_file()
        and not (set(p.relative_to(ROOT).parts) & IGNORED)
        and not p.name.endswith((".pyc", ".log"))
        and not (p.parent.name == "secrets" and p.name not in {"README.md", ".gitkeep"})
    }
    missing = set(baseline) - set(current)
    changed = {name for name in current if current[name] != baseline.get(name)}
    unexpected = changed - ALLOWED
    if missing or unexpected:
        raise SystemExit(f"SCOPE FAIL missing={sorted(missing)} outside={sorted(unexpected)}")
    for name, methods in manifest["protected_functions"].items():
        actual = functions((ROOT / name).read_text())
        for symbol, expected in methods.items():
            if actual.get(symbol) != expected:
                raise SystemExit(f"SCOPE FAIL unrelated function changed: {name}:{symbol}")
    print(f"TEST14_SCOPE_PASS: changed/added={len(changed)}, removed=0, outside=0")
    print("Models/migrations/mini-program/action projection/auth/dependencies: unchanged")


if __name__ == "__main__":
    main()

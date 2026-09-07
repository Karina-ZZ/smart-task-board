#!/usr/bin/env python3
"""Test16 modal hotfix scope: immutable previous Test16 hashes; two page methods only.

No database, network, deletion or business mutation. The old replay-only scope
checker remains byte-identical and historical. Current gates call this checker.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE_SHA = "1ef44ee2c48d5562d86c0721710734bcd6d5d3123464ea3054f3eaf2ee0b5d5a"
METHODS = {
    "wechat-miniprogram/pages/task-detail/index.js": ("  acceptTask() {", "\n  returnTask() {"),
    "wechat-miniprogram/pages/review/index.js": ("  approve() {", "\n  reject() {"),
}
GATES = {"scripts/run_test16_technical_gate.sh", "scripts/run_test16_live_gate.sh"}
ALLOWED = {
    *METHODS, *GATES, "README.md",
    "scripts/verify-test16-modal-scope.py",
    "wechat-miniprogram/tests/helpers/modal-page-harness.js",
    "wechat-miniprogram/tests/modal-confirmation.test.js",
    "wechat-miniprogram/tests/modal-confirmation-mock-flow.test.js",
    "docs/TEST16_MODAL_BASELINE_MANIFEST.json",
    "docs/TEST16_MODAL_HOTFIX_REPORT.md",
    "docs/TEST16_MODAL_ACCEPTANCE_CHECKLIST.md",
    "docs/TEST16_MODAL_LOCAL_PORTS_AND_LOGIN_GUIDE.md",
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


def fail(message):
    raise SystemExit(f"TEST16_MODAL_SCOPE_FAIL: {message}")


def main():
    manifest = json.loads((ROOT / "docs/TEST16_MODAL_BASELINE_MANIFEST.json").read_text())
    if manifest["baseline_zip_sha256"] != BASELINE_SHA or len(manifest["files"]) != 551:
        fail("wrong baseline identity")
    baseline = manifest["files"]
    current = {
        p.relative_to(ROOT).as_posix(): digest(p.read_bytes())
        for p in ROOT.rglob("*") if p.is_file() and not ignored(p)
    }
    missing = sorted(set(baseline) - set(current))
    changed = {name for name, value in current.items() if baseline.get(name) != value}
    outside = sorted(changed - ALLOWED)
    if missing or outside:
        fail(f"missing={missing}, outside={outside}")
    for name, (start, end) in METHODS.items():
        source = (ROOT / name).read_text()
        if source.count(start) != 1 or source.count(end) != 1:
            fail(f"ambiguous method boundary: {name}")
        first = source.index(start)
        last = source.index(end, first)
        normalized = source[:first] + "<APPROVED_METHOD>" + source[last:]
        if digest(normalized.encode()) != manifest["outside_method_hashes"][name]:
            fail(f"unrelated page code changed: {name}")
    for name in GATES:
        source = (ROOT / name).read_text()
        marker = "scripts/verify-test16-modal-scope.py"
        if source.count(marker) != 1:
            fail(f"missing current scope check: {name}")
        restored = source.replace(marker, "scripts/verify-test16-scope.py")
        if digest(restored.encode()) != baseline[name]:
            fail(f"gate changed beyond scope checker path: {name}")
    print(f"TEST16_MODAL_SCOPE_PASS changed/added={len(changed)}, removed=0, outside=0")
    print("Only acceptTask() and approve() changed within the two production pages")
    print("Backend replay repair, app/, alembic/, cloud-functions/, web/ unchanged")
    print("API/store/auth/config, WXML/WXSS, prior tests and PG safety guards unchanged")
    print("Current gates only switch scope-checker path; no runtime gate was removed")


if __name__ == "__main__":
    main()

# SmartTaskBoard Delivery Plan

> Historical / Pre-V1.1 evidence: this file records the pre-V1.1 delivery plan and must not be
> read as proof that SmartTaskBoard V1.1 requirements are complete. The active V1.1 source of truth
> is `docs/DEVELOPMENT_PLAN_V1.1.md` plus the PRD/reference materials under `docs/reference/`.

This plan tracks execution of `提示词文件.md`. The master specification and verified repository
state take precedence if this summary becomes stale.

## Completed foundation

- [x] Protect and audit the inherited worktree, migration history and baseline tags.
- [x] Restore the project-local Python 3.12 environment and install development dependencies.
- [x] Validate Batch 2B against an isolated PostgreSQL 16 database.
- [x] Close Batch 2B authorization regressions and stale response assertions.
- [x] Pass backend, frontend, migration, OpenAPI, dependency, secret and residual-data gates.

## Remaining delivery waves

- [ ] Wave 1 — immutable completion-review rounds, rejection, explicit rework and resubmission.
- [ ] Wave 2 — immutable task-change requests and complete cancel/withdraw/merge/close lifecycle.
- [ ] Wave 3 — employee profiles, authorized scopes, system parameters and production auth/RBAC.
- [ ] Wave 4 — performance metrics, matching snapshots and explainable recommendations.
- [ ] Wave 5 — workload snapshots, priority scoring and conflict detection.
- [ ] Wave 6 — reminder rules, idempotent notification outbox and provider adapters.
- [ ] Wave 7 — archives, operation logs, structured search and safe task reuse.
- [ ] Wave 8 — AI/voice input workflow with deterministic fake providers and human confirmation.
- [ ] Wave 9 — complete `/api/v1` and responsive frontend closure for all implemented capabilities.
- [ ] Wave 10 — production hardening, production-equivalent deployment, backup/restore and CI.
- [ ] Final acceptance — 25 logical tables or verified equivalents, clean worktree and release tag.

Every wave includes design review, additive migration, model, service, API, necessary UI, tests,
documentation, real PostgreSQL acceptance and the complete quality gate before checkpointing.


## Feature 15 P0 override (2026-09-03)

DEV-17 no longer implements historical workload-snapshot task details. The approved flow is: executive workload breakdown -> “查看该员工任务” -> existing task overview with employee-name display / `employeeNo` backend filter -> existing task detail. No new business table, field, or Alembic migration is part of Feature 15. See `docs/FEATURE_15_EXECUTIVE_EMPLOYEE_TASK_FILTER_RULES.md`.

## DEV-18 Test10 release-gate finalization (2026-09-04)

- Product scope: unchanged from Feature16/Test9.
- Fixed deterministic `task_status_logs` ordering: `task_version` is the authoritative timeline key before timestamp/UUID tiebreakers.
- Test10 candidate PostgreSQL gate requests 3 consecutive same-database passes; normal PG gate requires at least 2.
- Explicit Web test dependency: `@testing-library/dom`.
- Remaining formal gates: real Ruff 0 errors, PostgreSQL 28/28 consecutive passes under Python 3.12, clean `npm ci`, and real WeCom E2E when credentials/environment are available.
- Status: release candidate; do not mark V1.1 final release until the formal gates pass.

## DEV-18 / Feature16 Test11 final technical gate

- No product feature or schema change.
- Close the six remaining Ruff findings reported by the user's Test10 local run.
- Freeze task-status-log version-first ordering; do not modify the state machine.
- Require PostgreSQL 28/28 for three consecutive same-database passes plus 5 x 20 concurrency stress.
- Require Python 3.12 and check-only Ruff in the formal technical gate.
- Keep real WeCom production E2E as a separate environment gate.

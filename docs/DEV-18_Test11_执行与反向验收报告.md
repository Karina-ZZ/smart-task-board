# DEV-18 / Feature16 Test11 执行与反向验收报告

## 结论

Test11 已完成代码收口、门禁固化、打包与 ZIP 反向验收。当前执行容器可运行的测试全部通过；正式 Python 3.12 + Ruff + PostgreSQL/Docker 门禁必须继续由具备对应环境的本地/CI 执行，未在本报告中伪装为通过。

## 本轮代码改动

仅处理 Test10 本地报告中的 6 个 Ruff 问题：

- `app/integrations/wecom/client.py`: `Callable` 改从 `collections.abc` 导入；
- `app/services/features/performance_matching/scoring.py`: `Iterable/Mapping/Sequence` 改从 `collections.abc` 导入；
- `app/services/business_capabilities.py`: planning analytics import block 按 Ruff/isort 规则整理；
- `app/services/task_workflow.py`: 两个 aliased idempotency imports 拆分；
- `cloud-functions/ChatService/services/task_intake.py`: import section 分组整理；
- `tests/migrations/test_alembic_metadata.py`: Alembic / SQLAlchemy / first-party import 顺序整理。

对上述 6 个文件执行了 AST 语义对比：去除 import 节点后，Test10 与 Test11 的 AST 全部一致；没有函数体或业务规则变化。

## Test11 新增门禁

- `scripts/run_test11_release_gate.sh`
  - 强制 Python 3.12；
  - `pip check`；
  - `ruff check .`，CI/gate 不自动 `--fix`；
  - PostgreSQL 同库连续 3 轮；
  - 复用 `run_postgresql_gate.sh` 的 5 个并发用例 x 20 轮 = 100 次压力验证；
  - 非 PG、Mini Program、Web、ChatService 全量门禁；
  - 技术门禁与真实 WeCom E2E 分离。
- `tests/test_test11_release_candidate_contract.py`：冻结 Ruff 6 项修复和 Test11 门禁合同。

## 当前容器实际执行结果

- compileall: PASS
- 受影响模块定点测试: `84 passed`
- ChatService: `3/3 PASS`
- Test8/Test9/Test10/Test11/dev-dependency 合同: `19 passed`
- 后端非 PostgreSQL 全量: `508 passed / 28 deselected`
- 微信小程序累计: `21/21 PASS`
- 微信 JS syntax: PASS
- Python >100 字符行: `0`
- Alembic heads: 单 head `c2d3e4f5a6b7`
- Alembic migration 文件: `10`
- Test11 shell syntax: PASS
- Test11 正式 gate 在当前容器按设计 fail-closed: `[TEST11 BLOCKED] Python 3.12 is required`

## 当前容器无法正式执行的门禁

- Python 3.12：当前为 Python 3.13.5；
- Ruff：当前没有 Ruff binary；
- PostgreSQL/Docker：当前容器没有 Docker/PostgreSQL；
- Web clean `npm ci`：当前环境安装超时并留下不完整依赖树，已清理后再打包；
- 真实 WeCom E2E：无真实凭据/HTTPS部署/fresh login code。

因此以下目标仍需用户本地/CI真实复验：

- Ruff `0 errors`；
- PostgreSQL `28/28 x 3`；
- 并发压力 `100/100`；
- Python 3.12 正式门禁；
- Web clean `npm ci -> lint -> 109/109+ -> build`；
- 真实 WeCom E2E 单独执行。

## ZIP 反向验收

最终 ZIP 生成后，从 ZIP 解压至全新目录，不复用工作树，再次执行：

- release contracts: `19 passed`；
- non-PG: `508 passed / 28 deselected`；
- Mini Program: `21/21 PASS`；
- Mini Program JS syntax: PASS；
- ChatService: `3/3 PASS`；
- compileall: PASS。

ZIP 内确认不包含 `__pycache__`、`.pyc`、`node_modules`、`.pytest_cache`。

## 最终状态

`Test11 RELEASE CANDIDATE / WAITING FOR FORMAL LOCAL GATES`

在正式 Python 3.12 环境中取得 Ruff 0、PG 28/28 x3、stress 100/100、Web clean gate 全绿后，才可升级为 `V1.1 TECHNICAL RELEASE READY`。真实 WeCom E2E 仍作为独立环境门禁。

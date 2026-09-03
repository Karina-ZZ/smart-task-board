# 功能16 / DEV-18 Test4 修复与执行记录

> 日期：2026-09-03
> 输入证据：用户本地 `DEV-18_测试失败详情与报错.md`。
> 基线说明：该本地报告测试的是较早的 `smart-task-board-feature16-wecom-auth-baseline.zip`；Test4 在后续 Test3 基线上修复，不将旧包的 19/28 直接当作 Test4 结果。
> 当前状态：待真实 PostgreSQL 16 + Python 3.12 + Ruff + 企业微信环境复验。

## 1. 本轮修复映射

### F1-F7 PostgreSQL V1.1 测试夹具过期

已修复，原则是不放宽产品 API：

- 创建 payload / `CreateTaskDraftCommand` 补齐发送前必填任务字段；
- 创建阶段不再提交 `nodes`、`dependencies`、`node_participants`；
- 不再提交/回填 `estimated_hours`、`actual_hours`；
- 主承办人接受后断言 `decomposing`；
- 通过测试专用确定性拆解 helper 调用真实 `TaskDecompositionService.complete_result()`，由服务端落节点后进入 `in_progress`；
- 自建自办仍必须接受任务；
- 移除旧 `confirm_task_plan()` 流程。

涉及：

- `tests/integration/test_business_capabilities_postgresql.py`
- `tests/integration/test_core_workflow_postgresql.py`
- `tests/integration/test_core_workflow_api_postgresql.py`
- `tests/integration/test_completion_review_api_postgresql.py`
- `tests/integration/test_task_board_api_postgresql.py`
- `tests/integration/v11_postgresql_helpers.py`
- `tests/test_postgresql_v11_fixture_contract.py`

静态 V1.1 fixture 门禁已纳入普通 pytest，防止旧流程回流。

### F8 Outbox 并发测试标记 failed

本地报告已经证明产品行锁的核心断言通过：`provider.send_count == 1`。

旧测试 `_BarrierProvider` 却在 `provider.send()` 内执行 `Barrier(2).wait()`。正确的 `FOR UPDATE SKIP LOCKED` 实现下第二个 worker 本来就不会进入 provider，因此旧测试会因为等不到第二个 provider caller 自己超时并抛异常，随后产品异常分支把通知正确标记为 `failed`。

Test4 修改为 `_BlockingProvider`：

- 第一个 provider call 用 Event 暂停；
- 第二 worker 在第一行仍锁定时并发执行 SELECT；
- 正确实现应 `SKIP LOCKED` 并返回，不调用 provider；
- 释放第一发送后断言 `send_count == 1` 且最终 `send_status == sent`。

产品 `ReminderNotificationService.send_pending()` 的 `FOR UPDATE SKIP LOCKED` 逻辑没有为了测试而放宽或重写。

### F9 `/api/v1/me` 旧响应断言

已更新 PostgreSQL 集成测试：保留并验证当前正式的 `roles`、`permissions`、`scopes` 权限投影，不删除产品字段迁就旧测试。

### 开发依赖 `httpx2`

`pyproject.toml` 已从：

```text
httpx2>=2.9,<3.0
```

修正为官方包：

```text
httpx>=0.27,<1.0
```

新增 `tests/test_dev_dependency_contract.py` 防止错误包名回流。

## 2. Ruff 本轮低风险处理

依据用户本地报告，已人工清理非纯格式类问题：

- F401 未使用导入：报告列出的 10 类位置；
- F841 未使用局部变量：权限校验调用保留副作用，仅去掉无用赋值；
- B033 重复 set 项：两处重复 `task_decomposition_records`；
- E701 / E702：任务 schema 测试中的单行复合语句拆开。

当前执行环境无法安装 Ruff，因此 **E501 / I001 不在本环境宣称 PASS**。为避免在没有 Ruff 反馈时制造大范围无意义格式 diff，Test4 需要在用户本地 Ruff 0.9.x 再跑一次，以实际剩余诊断继续 Test5（如有）。

## 3. 当前可执行结果

```text
Python compileall: PASS
后端非 PostgreSQL: 482 passed, 28 deselected
PostgreSQL V1.1 fixture 静态合同: PASS（包含于上述 482）
微信小程序累计: 20/20 PASS
微信 JS node --check: PASS
```

本执行容器没有 PostgreSQL 16 / Python 3.12 / Ruff，也没有用户真实企业微信配置，因此以下项目不伪造 PASS：

- 真实 PostgreSQL 28 项；
- 5 项 × 20 轮 PostgreSQL 并发 stress；
- Python 3.12 正式依赖安装；
- `ruff check .`；
- 真实 CorpId / AgentId / Secret / AppID 企业微信 E2E。

## 4. Test4 正式门禁脚本

新增：

```text
scripts/run_test4_release_gate.sh
```

脚本强制：

1. Python 必须为 3.12；
2. 必须处在项目虚拟环境；
3. `pip install -e ".[dev]"` 与 `pip check` 必须成功；
4. `ruff check .` 必须成功；
5. 使用空的隔离 PostgreSQL 16，升级到 `c2d3e4f5a6b7`；
6. 真实 PG 全部专项 + 5 项×20轮 stress；
7. 企业微信真实配置必须存在，且小程序不能使用 `touristappid`；
8. 微信累计测试/JS语法；
9. React Web lint/test/build。

缺任一正式条件即 BLOCKED，不静默 skip。

## 5. 用户本地下一次复验重点

优先重新执行 Test4，而不是旧 `wecom-auth-baseline`：

1. 使用 Python 3.12 venv；
2. 创建/重建空库 `smarttaskboard_core_test`（127.0.0.1:46479）；
3. 执行 `scripts/run_test4_release_gate.sh`；
4. 重点回报：PG 28项结果、Outbox 20轮结果、Ruff剩余规则和行号。

如果 F1-F7/F9 再失败，应按新的 Test4 堆栈判断，不再引用旧包的 422/旧 `/me` 断言；如果 F8 仍失败，则需要读取新的异常原因和最终 `fail_reason`，而不是继续假定 Barrier 超时。

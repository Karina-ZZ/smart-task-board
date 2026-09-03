# 功能16 / DEV-18 Test3 发布门禁执行报告

> 日期：2026-09-03
> 输入包：Test2-smart-task-board-feature16-release-gate.zip
> 结论：BLOCKED。没有用 mock/SQLite 代替真实 PostgreSQL 或企业微信环境。

## 1. 本轮目标

1. Python 3.12 + PostgreSQL 16真实门禁。
2. 真实企业微信 CorpId / AgentId / Secret + 真实小程序 AppID。
3. 全链路E2E发布验收。

## 2. 当前执行环境硬阻塞

- 当前只有 Python 3.13.5。
- `uv python install 3.12.12` 已实际执行，但 DNS 无法访问下载源，安装失败。
- 当前容器无 Docker、postgres、initdb、psql，无法创建 PostgreSQL 16 隔离测试库。
- `secrets/` 只有 `.gitkeep`，没有用户真实 CorpId / AgentId / Secret / Qwen Key。
- `wechat-miniprogram/project.config.json` 仍为 `touristappid`，符合源码包安全默认值，但不能用于真实企微验收。

以上任何一项都不能用 SQLite/mock 冒充真实 PASS。

## 3. Test3 实际执行结果

### 3.1 后端非 PostgreSQL

执行：

```bash
DATABASE_URL=sqlite+pysqlite:///:memory: \
AUTH_MODE=test_header \
ALLOW_TEST_EMPLOYEE_HEADER=true \
python3 -m pytest -q -m 'not postgresql'
```

结果：

```text
477 passed
2 failed
28 deselected
```

两个失败均来自 `tests/test_postgresql_v11_fixture_contract.py`：

1. API PostgreSQL fixtures 仍在创建请求中提交 `nodes/dependencies/node_participants`。
2. `test_business_capabilities_postgresql.py` / `test_core_workflow_postgresql.py` 仍含旧 `confirm_task_plan()` 流程。

这说明 Test2 中旧 PostgreSQL fixture 债务已经被自动化门禁真实拦截。正确修复是把集成测试改成：

```text
创建任务（无nodes/hours）
→ submit-for-confirmation
→ confirm-and-send
→ pending_accept
→ assignee accept
→ decomposing
→ deterministic test AI provider
→ decomposition execute
→ 5~10个正式节点落库
→ in_progress
→ 后续节点/汇报/验收流程
```

禁止为了让旧测试通过而重新开放创建人提交 nodes 或恢复 `confirm_task_plan()`。

### 3.2 微信小程序

```text
20 / 20 PASS
```

### 3.3 Test3真实门禁脚本

新增：`scripts/run_test3_release_gate.sh`

脚本硬性要求：

- Python 必须是 3.12；
- 必须提供 PostgreSQL 测试库；
- `RUN_POSTGRESQL_INTEGRATION=1`；
- 必须提供 `WANGXU_BACKEND_ENV_FILE`；
- `AUTH_MODE=wecom`；
- CorpId / AgentId / Secret 不得为空；
- 小程序 AppID 不得为 `touristappid`；
- Ruff / pip check / Alembic / PG / 非PG / 微信 / React 全部执行。

当前环境执行脚本会立即：

```text
[TEST3 BLOCKED] Python 3.12 is required
```

这是预期行为：正式发布门禁不允许静默 skip。

## 4. PostgreSQL 真实门禁下一步

当前不能在无 PostgreSQL 环境下盲改复杂 PG fixture 后宣称通过。
在有 Docker 的本机，下一轮必须：

1. Python 3.12 建独立 venv。
2. PostgreSQL 16 启动 `smarttaskboard_core_test`，端口 46479。
3. 空库 `alembic upgrade head` 到 `c2d3e4f5a6b7`。
4. 逐个迁移上述旧 fixture 到 V1.1 accept→decompose 流程。
5. 每改一组即跑真实 PG；最终要求 PostgreSQL 专项 0 fail / 0 skip。
6. 再跑通知 Outbox 多 worker 并发 stress，验证 provider 单次发送。

## 5. 企业微信真实环境下一步

必须由部署者提供真实：

- WECOM_CORP_ID
- WECOM_AGENT_ID
- WECOM_APP_SECRET
- 小程序真实 AppID
- 企业微信测试成员与应用可见范围

真实环境验收至少覆盖：普通员工、高管、disabled 用户、未绑定用户；并验证 `/auth/wecom -> /me` 与原业务权限一致。

## 6. Test3状态

```text
BLOCKED
```

原因不是新增业务回归，而是：

- 缺 Python 3.12；
- 缺 PostgreSQL 16；
- 缺真实企业微信配置；
- PostgreSQL integration fixtures 仍有 V1.1 前流程债务，并已被非PG静态门禁拦截。

在以上问题完成前，不得宣称 DEV-18 发布成功。

# 功能16 / DEV-18 Test2 发布门禁执行报告

> 日期：2026-09-03  
> 测试基线：`Test1-smart-task-board-feature16-secure-config.zip`  
> 结论：`IN_PROGRESS / BLOCKED_BY_REAL_ENV_AND_PG_TEST_DEBT`  
> 原则：真实 PostgreSQL、真实企业微信未执行即不记 PASS；SQLite/mock 不能替代真实门禁。

## 1. 本轮实际执行环境

- Python：3.13.5（当前容器）；项目正式门禁要求 Python 3.12。
- `uv`：0.10.0，但容器 DNS/网络不可用，无法下载 Python 3.12 standalone。
- Docker：当前容器未安装。
- PostgreSQL server/client：当前容器未安装。
- Node.js：22.16.0；npm 10.9.2。
- 企业微信真实配置：未提供；`secrets/` 只有 `.gitkeep`。
- `WECOM_CORP_ID / WECOM_AGENT_ID / WECOM_APP_SECRET / DASHSCOPE_API_KEY / POSTGRES_TEST_DATABASE_URL` 均未设置。

因此本轮不能宣称完成“Python 3.12 + PostgreSQL 16真实门禁”或“真实企业微信 CorpId/AppID”验收。

## 2. 已执行且通过的门禁

### 2.1 后端非 PostgreSQL 累计

在 SQLite 隔离库、`AUTH_MODE=test_header` 下执行：

```text
477 passed
28 deselected (postgresql marker)
```

Test1 基线为 476；本轮新增 1 个启动脚本安全配置合同测试。

### 2.2 微信小程序累计

```text
20 / 20 test files PASS
```

全部小程序 JS `node --check` 通过。

### 2.3 ChatService

以下纯逻辑测试通过：

```text
test_auth.py        PASS
test_config_file.py PASS
test_task_intake.py PASS
```

### 2.4 企业微信生产模式启动 smoke

使用临时占位 CorpId/AgentId/Secret、SQLite，仅验证应用能在 `AUTH_MODE=wecom` 配置形态下启动：

```text
GET /health/live  200
GET /openapi.json 200
GET /docs         200
```

这不是企业微信真实认证通过，只证明生产认证模式的配置/路由可启动。

### 2.5 PostgreSQL 测试收集合同

真实 PG 测试仍为：

```text
28 tests collected
476/477 ordinary tests deselected by marker
```

正式 `scripts/run_postgresql_gate.sh` 已硬要求：

- Python 3.12；
- `RUN_POSTGRESQL_INTEGRATION=1`；
- 固定隔离库 `smarttaskboard_core_test@127.0.0.1:46479`；
- 空库；
- Alembic head `c2d3e4f5a6b7`；
- 28 项 PostgreSQL；
- 5 个并发测试 × 20 轮；
- 尾部非 PG 回归。

该脚本不会把 skip 当 PASS。

## 3. 本轮发现并已修复的问题

### P1：安全配置已经改用 `secrets/backend.env`，但旧 `scripts/start-dev.sh` 仍生成根 `.env`

风险：形成两套配置入口，用户可能修改错误文件；脚本还会自动写入 JWT Secret，与最新安全配置规范冲突。

本轮修复：

- `scripts/start-dev.sh` 默认读取 `secrets/backend.env`；
- 支持 `WANGXU_BACKEND_ENV_FILE=/etc/wangxu/backend.env` 覆盖；
- `docker compose` 显式使用同一 `--env-file`；
- 不再创建、修改项目根 `.env`；
- 不再自动写 JWT Secret；
- 不再要求旧 `AI_API_KEY`；
- 缺配置时只报字段名，不打印真实值；
- 新增 `tests/test_start_dev_secret_contract.py`。

本轮业务源码无修改。

## 4. 真实 PostgreSQL 当前的重大开放问题

静态检查发现，多份 PostgreSQL 集成测试仍保留 V1.1 之前的创建/规划测试夹具。

典型情况：

- `test_core_workflow_api_postgresql.py` 在 `POST /api/v1/tasks` 中提交 `nodes / dependencies / node_participants`；
- `test_completion_review_api_postgresql.py` 创建任务时直接提交 `nodes`；
- `test_task_board_api_postgresql.py` 的 `_task_payload()` 仍提交 `nodes / dependencies / node_participants`；
- `test_core_workflow_postgresql.py` 仍用 `CreateTaskDraftCommand(nodes=..., dependencies=...)` 并走旧人工 planning/confirm；
- `test_business_capabilities_postgresql.py` 仍包含 `hours:` 输入和 `confirm_task_plan()` 人工节点确认链路；
- `test_task_board_api_postgresql.py` 对 `/api/v1/me` 仍执行旧 5 字段“完全相等”断言。

而当前正式 `CreateTaskRequest` 明确：

```text
creator draft transport; nodes/hours are not client-writable
```

因此这些测试不能通过“放宽生产 API”修复。正式处理方式必须是把 PostgreSQL 测试夹具迁移到 V1.1：

```text
完整任务级字段
→ POST /tasks（无 nodes）
→ submit-for-confirmation
→ confirm-and-send
→ pending_accept
→ assignee accept
→ decomposing
→ 确定性 fake decomposition provider
→ 5~10 nodes/dependencies 落真实 PostgreSQL
→ in_progress
→ 后续执行/汇报/验收测试
```

这与用户此前本地 19/28 的失败根因一致。当前容器没有 PostgreSQL，不能安全宣称这些迁移已经修好，因此 Test2 不盲改这组复杂 PG 测试。

## 5. 企业微信真实环境门禁当前状态

当前源码实现已具备：

```text
wx.qy.login
→ POST /api/v1/auth/wecom
→ WeCom gettoken
→ jscode2session
→ corpid 校验
→ users.wecom_user_id
→ employee_no
→ 现有 access/refresh token
```

但真实门禁缺少：

- 真实 `WECOM_CORP_ID`；
- 真实 `WECOM_AGENT_ID`；
- 真实 `WECOM_APP_SECRET`；
- 登录企业微信开发者工具的真实账号；
- 真实小程序 AppID；
- 可见范围内的企业微信测试成员；
- 数据库中对应 `users.wecom_user_id` 绑定；
- `wx.qy.login()` 当次的一次性 code。

另外当前交付源仍故意保留：

```text
wechat-miniprogram/project.config.json -> appid = touristappid
wechat-miniprogram/config.js -> mode = mock, apiBaseUrl = ""
```

所以交付包本身不会误连真实生产服务。真实验收必须在本地测试副本中配置真实 AppID、`mode=api` 和测试 API 地址后执行，不能把真实 CorpSecret/Qwen Key 写进小程序。

## 6. React Web

当前容器没有 `web/node_modules`；`npm ci` 因当前容器网络/工具超时未完成，所以本轮无法重新执行 latest Test2 的 Web lint/test/build。

用户上一轮本地报告对更早基线实测为：

```text
lint PASS
109 tests PASS
build PASS
```

该结果只能作为历史证据，不能替代 Test2 最新包重新验收。

## 7. Test2 与 Test1 的源码差异

业务功能代码没有修改。

仅：

```text
CHANGED README.md
CHANGED scripts/start-dev.sh
ADDED   tests/test_start_dev_secret_contract.py
ADDED   docs/FEATURE_16_TEST2_RELEASE_GATE_REPORT.md
```

任务、看板、通知、AI拆解、状态机、权限、绩效、负荷、高管功能均未修改。

## 8. Test2 总结

已证明：

- Test1 的普通后端回归仍稳定；
- 微信累计 20/20 稳定；
- ChatService 鉴权和 Qwen intake 纯逻辑稳定；
- 企业微信生产认证模式可以启动；
- LoginService 无运行时依赖；
- 新安全配置方案现在连 `start-dev.sh` 也统一到 `secrets/backend.env`；
- 正式 PG gate 不会把缺环境的 skip 当 PASS。

仍未证明：

- Python 3.12 正式依赖安装；
- PostgreSQL 16 28/28；
- 5×20 并发 stress；
- Ruff 0；
- Test2 React Web 109+；
- 真实 CorpId/AppID 企业微信登录；
- 真实 Qwen Key 网络调用；
- 企业微信身份开始的全任务生命周期 E2E；
- 375/390/430 真机与企业微信模式验收。

因此：

```text
DEV-18 / 功能16 = IN_PROGRESS
Test2 = PARTIAL PASS, NOT RELEASE PASS
```

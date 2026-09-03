# 更新日志 (Changelog)

本仓库所有显著变更都记录在此文件中。格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

## [功能 16] - 2026-09-03 — 企业微信登录 + 安全配置 + 发布门禁

### 新增

#### 后端

- **企业微信自建应用登录**：后端 `auth_mode` 增加 `wecom`；新增 `POST /api/v1/auth/wecom/login` 换票接口（`app/services/wecom_authentication.py` + `app/integrations/wecom`），用企业微信 code 换 `userid`，经 `User.wecom_user_id` 映射 `employee_no` 后签发 JWT。
- **删除 LoginService 云函数**：仅服务内部员工，企业微信接管身份，短信登录不再部署。
- **密钥安全配置**：后端配置改从 `secrets/backend.env` 读取（可经 `WANGXU_BACKEND_ENV_FILE` 覆盖）；ChatService 改从 `secrets/chatservice.env` 读取（可经 `WANGXU_CHAT_ENV_FILE` 覆盖）。`.gitignore` 屏蔽 `secrets/*`，仅提交 `secrets/.gitkeep`。变量名规范化：`WECOM_APP_SECRET`、`DASHSCOPE_API_KEY`、`CHAT_SERVICE_JWT_SECRET_KEY`。新增空模板 `config-examples/backend.env.example`、`config-examples/chatservice.env.example`。

#### 测试

- 新增 `tests/integrations/test_wecom_client.py`、`tests/services/test_wecom_authentication.py`、`tests/test_start_dev_secret_contract.py`（发布门禁：密钥契约校验）。
- **Test3 发布门禁（2026-09-03）**：新增 `scripts/run_test3_release_gate.sh`（硬门禁：必须 Python 3.12 + 真实 PostgreSQL 16 + `RUN_POSTGRESQL_INTEGRATION=1` + `WANGXU_BACKEND_ENV_FILE` + `AUTH_MODE=wecom` + 真实企微 CorpId/AgentId/Secret + 非 `touristappid` 小程序 AppID，任一缺失即 `BLOCKED`）；新增 `tests/integration/v11_postgresql_helpers.py`、`tests/test_postgresql_v11_fixture_contract.py`（旧 PG fixture V1.1 前流程债务契约，已被门禁正确拦截）。Test3 结论 **BLOCKED（预期）**：当前环境缺 Python 3.12 / PostgreSQL 16 / 真实企微配置，非PG 实测 `477 passed, 2 failed`、微信 `20/20 PASS`；**非代码回归**，详见 `docs/FEATURE_16_TEST3_EXECUTION_REPORT.md`。
- **Test4 修复与门禁（2026-09-03）**：修复 Test3 门禁拦出的旧 PG V1.1 fixture 债务（F1-F7：创建阶段不再提交 nodes/dependencies/estimated_hours，接受后断言 decomposing，移除旧 `confirm_task_plan()`）；Outbox 并发测试 `_BarrierProvider`→`_BlockingProvider` 正确验证 `FOR UPDATE SKIP LOCKED`（F8）；`/me` 权限投影断言更新（F9）。`pyproject.toml` 依赖包名 `httpx2`→`httpx` 修正（错误包名会致 pip 安装失败），新增 `tests/test_dev_dependency_contract.py` 防回流。ruff 清理 F401/F841/B033/E701/E702。新增 `scripts/run_test4_release_gate.sh`（强制 Py3.12+venv+`pip check`+`ruff`+真实 PG 28 项+5×20 并发 stress+企微配置，缺一即 BLOCKED）。Test4 本环境：`compileall PASS`、非PG `482 passed, 28 deselected`、微信 `20/20 PASS`；真实 PG/Py3.12/Ruff/企微仍待复验（不伪造 PASS），详见 `docs/FEATURE_16_TEST4_EXECUTION_REPORT.md`。
- **Test5 并行完善（2026-09-03）**：仅完善发布门禁，不新增产品功能、`app/` 业务源码无修改。收敛 PostgreSQL V1.1 集成测试夹具（`tests/integration/v11_postgresql_helpers.py` 统一 `send_accept_and_decompose_v11()` + `tests/test_postgresql_v11_fixture_contract.py` 防回流，禁止旧 creator-owned 前流程）；加固 Outbox 并发防回流断言（provider 只调一次、`send_status==sent`、`retry_count==0`、`fail_reason is None`、第二轮 `send_pending()` 返回空、已 sent 不再调用 provider）。新增 `scripts/run_test5_release_gate.sh`（硬门禁：Py3.12+venv+`pip install -e ".[dev]"`+`pip check`+`ruff`+compileall+PG16 空库+Alembic 单 head+28 项 PG 集成+5×20 并发+非 PG 累计+真实企微 backend env+真实 Qwen ChatService env+小程序真实 AppID/apiBaseUrl+小程序累计/JS 语法+React lint/test/build，缺一即 `BLOCKED`）。新增真实企业微信身份 smoke/E2E 脚本 `scripts/run_wecom_real_e2e.py` 与 `docs/FEATURE_16_REAL_WECOM_E2E.md`（自动验证 `/health`、`/auth/wecom`、`wecom_user_id→employee_no`、`auth_mode=wecom`、`/me` 权限投影、`/ai-token`、refresh 轮换与登出失效，绝不打印 Secret/Token）。Test5 本环境：compileall PASS、非PG `485 passed, 28 deselected`、Test5+V1.1 发布合同 `8 passed`、微信 `20/20 PASS`、JS `node --check` `48 文件 PASS`、Test5 shell gate 语法 PASS；真实 PG 28/28 / 5×20 并发 / Ruff 0 error / 真实企微与 Qwen E2E 仍待真实环境复验（不伪造 PASS），详见 `docs/FEATURE_16_TEST5_PARALLEL_IMPROVEMENT_REPORT.md`。
- **Test6 定点修复（2026-09-03）**：吸收本地 Test4 真实执行证据（PG16 空库迁移成功、28 项 PG 19 passed/9 failed、Outbox 5×20 共 100 次全过、Ruff 仅余 E501/I001 与一个 F821）。关闭 Outbox 并发项（以本地真实 PG 100/100 为准，不改产品发送逻辑）；修复 PG `_command()` 解包（测试改收单个 `CreateTaskDraftCommand`）；补 `from dataclasses import replace` 修 F821；新增 V1.1 client hours 静态门禁（`tests/test_postgresql_v11_fixture_contract.py`，business-capability PG fixture 禁止 `hours/estimated_hours/actual_hours`）。**两个真实产品缺陷修复**：① `app/services/features/task_decomposition/service.py` 的 `TaskDecompositionService.get_latest()` 在只读 UoW 退出前 `session.expunge(record)`，修复路由在 session 关闭后序列化触发 `DetachedInstanceError`；② `app/schemas/task_board.py` 的 `AvailableActionsResponse` 补 `priority_quadrant / importance_score / urgency_score / remaining_hours / sort_rank`，修复 `/api/v1/tasks/{task_id}/available-actions` 合法服务结果被响应模型校验转成 500（新增 API/Schema 回归覆盖）。新增 `scripts/run_test6_release_gate.sh`（硬门禁：Py3.12+venv+`pip check`+`ruff`+compileall+PG16 空库+Alembic 单 head+28 项 PG 集成+5×20 并发+非 PG 累计+真实企微/Qwen env+小程序真实 AppID/apiBaseUrl+React lint/test/build，缺一即 BLOCKED）。Test6 本环境：定点回归 `46 passed`、非PG `488 passed, 28 deselected`、微信 `20/20 PASS`、JS `node --check` PASS、compileall PASS；真实 PG 28/28 / Ruff 0 error / 真实企微与 Qwen E2E 仍以本地 Test6 实跑结果为准（不伪造 PASS），详见 `docs/FEATURE_16_TEST6_EXECUTION_REPORT.md`。
- 后端测试保持 **488 passed（非 PostgreSQL，含 28 项 deselected PG opt-in）**；`ruff` 仅风格类告警，F821 已清零。

#### 文档

- 新增 `docs/FEATURE_16_WECOM_AUTH_ACCEPTANCE.md`、`docs/WECOM_IDENTITY_ORG_MAPPING.md`、`docs/SECRETS_CONFIGURATION_GUIDE.md`、`docs/FEATURE_16_SECRET_CONFIG_ACCEPTANCE.md`、`docs/FEATURE_16_TEST2_RELEASE_GATE_REPORT.md`、`docs/FEATURE_16_TEST3_EXECUTION_REPORT.md`、`docs/FEATURE_16_TEST4_EXECUTION_REPORT.md`、`docs/FEATURE_16_TEST5_PARALLEL_IMPROVEMENT_REPORT.md`、`docs/FEATURE_16_TEST6_EXECUTION_REPORT.md`、`docs/FEATURE_16_REAL_WECOM_E2E.md`。

### 移除

- 删除 `cloud-functions/LoginService`（短信验证码登录云函数）。

---

## [功能 15] - 2026-09-03 — 高管员工任务筛选

> 本次交付实际包含功能 14（高管任务看板）与功能 15（员工任务筛选）两个功能。

### 新增

#### 后端

- **高管成员只读接口**
  - 新增 `GET /api/v1/executive/members`，只返回当前高管有效部门授权范围内的 active 员工，候选范围受显式部门授权限制。
- **任务查询扩展**
  - 扩展 `GET /api/v1/executive/tasks`，支持 `employeeNo`、状态、四象限、日期过滤，各条件按 AND 叠加。
  - 员工筛选在 Repository 层使用 `Task.main_assignee_employee_no == employee_no`；查询前先校验高管显式授权部门，再校验目标员工所属部门，授权外员工在任务查询前拒绝并审计。
  - 任务结果仍以授权部门集合为第一范围边界。
  - 新增 `app/services/features/executive_dashboard/task_list.py`。

#### 微信小程序

- 高管看板负荷构成抽屉新增「查看该员工任务」真实按钮，携带 `source=executive`、`departmentId`、`employeeNo`、`employeeName`、`period`、`datePreset` 跳转现有任务概览页。
- `employeeName` 仅用于展示，不作为后端数据库过滤条件。
- 复用 `pages/tasks/index`（未创建第四个业务页）；任务详情复用 `pages/task-detail/index`，不新增高管专用详情页，不扩大高管业务写权限。
- 高管上下文错误态区分无权限，403 时不展示员工/任务业务数据；清除员工筛选时保留高管部门授权上下文。
- 返回时 `navigateBack` 保留完整任务页实例状态；无历史栈时按高管/员工上下文回退。

#### 功能 14 高管任务看板（随本次交付）

- 授权部门与本周/本月筛选、进行中/按期率/KPI 关联/总体进度、团队四象限、员工工作日负荷热力图、单快照五维负荷构成。
- P0 规则：KPI 只认用户确认关系，不要求 strong；不区分核心 KPI；停用绩效指标不进入当前 KPI 卡；总体进度包含 `pending_review`。

#### 测试

- 新增 `tests/repositories/test_executive_dashboard_queries.py`。
- 新增小程序测试 `executive-employee-tasks.test.js`、`executive-employee-tasks-flow.test.js`（功能 15）与 `executive-dashboard.test.js`（功能 14）。
- 后端测试由 436 增至 **460 passed**；小程序测试由 16 组增至 **19 组**。

#### 文档

- 新增 `docs/FEATURE_14_ACCEPTANCE.md`、`docs/FEATURE_14_EXECUTIVE_DASHBOARD_RULES.md`。
- 新增 `docs/FEATURE_15_ACCEPTANCE.md`、`docs/FEATURE_15_EXECUTIVE_EMPLOYEE_TASK_FILTER_RULES.md`。

### 移除

- 删除占位页面 `pages/workload-tasks/`（该页按 `employeeNo` 查询后在前端拼装假负荷压力，不符合 P0 三页流程）。小程序 `app.json` 注册页面数为 13。

### 修复

- 修复 `app/services/task_board_query.py` 中 `available_actions()` 引用未定义变量 `priority` 导致 `GET /api/v1/tasks/{task_id}/available-actions` 返回 500 的缺陷（ruff F821 已清零）。
- 修复 `wechat-miniprogram/package.json` 与 `wechat-miniprogram-standalone/package.json` 的 `test` 脚本遗漏串联功能 14/15 新增的 3 个测试文件，导致 `npm test` 只跑 16 组而非 19 组。

### 说明

- 功能 15 无新增业务表、无新增数据库字段、无新增 Alembic 迁移，`alembic/versions` 文件集合与功能 14 基线一致，Alembic head 仍为 `b1c2d3e4f5a6`。
- 明确不实现：`workload_snapshot_task_details`、snapshot task detail 字段、按 snapshotId 查询历史任务集合、独立员工负荷任务业务页、新负荷公式。
- 功能 14 的 `period`-only 兼容保持不变；功能 15 显式 `datePreset=all` 时不会被 `period` 隐式覆盖。

---

## [功能 13] - 2026-09-03 — 通知、提醒与协办节点承接

### 新增

#### 后端

- **协办节点承接机制**
  - `task_nodes` 新增 `assignment_status`（`pending / accepted / rejected`）、`assignment_responded_at`、`assignment_reject_reason` 字段；历史节点迁移时默认回填 `accepted`，升级不锁死既有任务。
  - 新增动作接口：`POST /api/v1/tasks/{taskId}/nodes/{nodeId}/actions/accept-assignment`（接受承接）与 `reject-assignment`（拒绝承接，原因必填）。
  - AI 拆解出的主承办人本人节点直接进入可执行状态；协办人节点服务端写 `assignment_status=pending`，只向该节点负责人发送「节点待承接」通知。
  - 拒绝承接后自动通知主承办人处理责任问题。
- **节点执行提醒体系**
  - `reminder_rules.reminder_type` 约束新增 `node_start`、`node_due`；节点临期/逾期继续复用 `due_soon` / `overdue`。
  - 临期提前量按工作跨度动态计算：`≤1` 工作日提前 2 个工作小时；`>1 且 ≤3` 提前 4 个工作小时；`>3` 提前 1 个工作日；复用统一工作时间能力，不读取 `estimated_hours`。
  - 新增调度接口：`POST /api/v1/reminders/scan`、`POST /api/v1/notifications/send-pending`（仅 active admin scheduler 可调用）。
  - 企业微信 provider 失败按 5/10/20 分钟退避重试，同一 `notification_id` 不重复创建业务通知。
- **通知中心**
  - `GET /api/v1/notifications` 仅返回当前用户自己的站内通知；高管/管理员不能读取他人私人通知。
  - 通知按后端派生 `notificationType / targetType / actionRequired / canOpen / unavailableReason` 提供上下文与跳转目标，不授予权限，动作接口再次鉴权。
- **数据库迁移**
  - 新增 Alembic 迁移 `b1c2d3e4f5a6`（`fa1b2c3d4e5_feature13_node_assignment_and_reminders.py`），自 `a9c4e7f1b2d3` 升级。
- **测试与脚本**
  - 新增 `tests/integration/test_feature13_postgresql.py` 功能 13 集成测试。
  - 新增 `scripts/provision_postgresql_gate_docker.sh`、`scripts/run_postgresql_gate.sh` PostgreSQL 门禁脚本。

#### 微信小程序（生产版本与独立版同步）

- 「节点待承接」通知点击进入任务详情并定位节点；待承接节点提供「接受承接 / 无法承接」操作，拒绝需填写原因。
- 通知中心按后端派生字段展示与跳转；旧通知在任务已处理、关系失效或任务不可见时不再保留过期写动作。
- 红点改为「待处理事项」语义（`actionRequired`），不因已读而消失。
- 移除生产页面的「全部已读」假语义、身份切换与重置演示数据；这些状态不再落入 localStorage。
- 新增 `tests/notifications-node-assignment.test.js` 小程序测试。

#### 文档

- 新增 `docs/FEATURE_13_NOTIFICATION_RULES.md`：功能 13 P0 通知与节点承接规则基线。
- 新增 `docs/FEATURE_13_ACCEPTANCE.md`：功能 13 验收记录（口径、数据模型、接口、微信端交互、门禁证据）。
- 新增 `docs/POSTGRESQL_GATE_EXECUTION_REPORT.md`：PostgreSQL 门禁执行报告。
- 更新 `docs/DEVELOPMENT_PLAN_V1.1.md`、`FEATURE_COVERAGE.md`、根 README 的累计交付状态。

### 修复 / 强化

- 协办节点未接受前，节点开始、临期、到期、逾期提醒与开始/完成动作全部由服务端拒绝。
- 已完成、已取消、任务未生效/终止、负责人不匹配或未接受的节点，历史 reminder rule 到点时在创建通知前再次校验并停用。
- 节点逾期扫描只纳入 `assignment_status=accepted` 的有效节点。
- AI 拆解成功不再向创建人/主承办人发送纯知悉通知。

### 不兼容变更

- 无（迁移对历史数据安全回填，接口只增不改）。

## [功能 12] - 2026-09-03 — 全量源码首次入库

- 完整项目源码（FastAPI 后端 + React Web 前端 + 微信小程序 + 云函数）首次上传。
- 功能 01～12 累计交付：任务创建与状态机、AI 结构化拆解、节点执行、进度汇报与卡点闭环、完成验收与返工、企业绩效口径（25%+25%+25%+20%+5%，阈值 70）、五维负荷等。
- 小程序独立版置于 `wechat-miniprogram-standalone/`。
- 新增 `docs/ACCEPTANCE_STANDARDS.md` 单功能验收标准（10 + 1 条硬性条件）。
- 整理 `docs/` 与 `docs/reference/` 中文文件名为可读 UTF-8。

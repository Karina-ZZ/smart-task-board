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
- **Test7 AI 字段回填优化（2026-09-04）**：可体验快照（先行交付），仅优化“AI 识别/追问 → 任务创建页字段自动回填”链路，未改任务发送/接受/拆解/执行/通知/验收/看板/企微登录等后续业务规则。`app/ai/prompts/task_intake.md` 与 `cloud-functions/ChatService/prompts/task_intake.md` 新增强制规则：人员字段只允许解析用户**明确提到**的人，禁止按岗位/部门/技能/负荷/直属关系或“更合适”判断主动推荐；未明确提到主承办人/汇报对象/验收人/协同人时保持 null/[] 并按必填规则追问；同名歧义不猜。`wechat-miniprogram/pages/create-details/index.js` 手工选人后清理对应 AI `missingFields/lowConfidenceFields/confirmQuestions` 状态；`wechat-miniprogram/utils/api.js` mock 模式新增 `explicitPeopleFromText()` 支持明确人员语句自动回填；新增 `cloud-functions/ChatService/tests/test_task_intake.py`（Prompt 契约测试）与 `wechat-miniprogram/tests/ai-field-hydration.test.js`（字段回填用例）。Test7 本环境：`compileall` PASS、ChatService `test_task_intake.py` PASS、小程序 `21/21 PASS`、新增 `ai-field-hydration.test.js` PASS、JS `node --check` PASS；后端全量 pytest 在本容器因缺 `psycopg` 于收集阶段被环境依赖阻塞（非产品失败/通过，沿用 Test6 非PG `488 passed`），真实 PG / Ruff / 真实企微与 Qwen E2E 仍待本地实跑复验（不伪造 PASS），详见 `docs/FEATURE_16_TEST7_AI_FIELD_HYDRATION_REPORT.md`。
- **Test8 发布候选（2026-09-04）**：以 Test7 为代码基线，不新增产品功能。收口 Test6 真实验收暴露的 6 项 PostgreSQL 债务：① Feature11 completed/archived 旧测试合同改为最终状态断言 `archived` 并检查 `completion_approved`/`task_archived` 日志与版本；② `test_core_workflow_postgresql.py` 等 4 个 PG 测试清理流程删除 tasks 前先删 TaskArchive（消除 teardown FK 失败与 pending notification 残留，产品 Outbox `FOR UPDATE SKIP LOCKED` 实现未改）；③ `TaskIntakeService.create_draft_from_extraction()` 显式 `estimated_hours=None`（V1.1 创建阶段客户端/AI 不可写 hours 规则未放宽）；④ pending node 可用动作旧断言按正式节点动作合同更新（未开始且依赖满足仅 `start_node`）。Ruff 历史债务（202 项）：全仓 import 规范排序、长行拆分，`app/tests/alembic/cloud-functions/scripts` 中 >100 字符 Python 行=0，新增 `tests/test_test8_release_candidate_contract.py` 持续检查 line-length 物理上限；新增 `scripts/run_test8_release_gate.sh`（顺序：Python 3.12 → pip check → Ruff → Test8 快速合同 → PG 空库迁移 → 28 项 PG → 5×20 并发 → 非 PG → WeCom/Qwen 配置 → 小程序 → Web）。Test8 本环境：compileall PASS、非PG `495 passed`、定点回归 `76 passed`、Test8+V1.1 静态合同 `16 passed`、ChatService task-intake PASS、小程序 `21/21 PASS`、Python >100 字符行 `0`、JS `node --check` PASS；真实 PG 28/28 / Outbox 5×20=100/100 / Ruff 0 error / Web 全绿 / 真实企微 E2E 仍待本地 Test8 实跑放行（不伪造 PASS），详见 `docs/FEATURE_16_TEST8_RELEASE_CANDIDATE_REPORT.md`。
- **Test9 发布候选修复（2026-09-04）**：吸收本地 Test8 真实门禁暴露的问题，只收口不改产品功能/状态机/Outbox 并发算法/普通员工权限边界。F1 归档搜索权限契约保持 `employee + department/user scope + 无直接任务关系 → 不获得额外业务任务查看权`（`PermissionScopeService.can_access_task()` 不动），PG 业务集成改由 `executive` + `department` scope 验证授权归档搜索（`test_employee_scope_does_not_expand_business_task_visibility` 继续锁定）；F2 `available-actions.nodes` 改为稀疏动作投影（只返回 `allowed_actions` 非空的节点，完整节点事实由任务详情 DTO 提供，React 现有 Map 查询兼容），新增 `test_available_node_actions_only_projects_actionable_nodes` 并同步 PG API 契约与 Test8 静态合同；F3 business 集成 fixture 改为按 `task_ids` 清理完整任务图（notifications→reminder_rules→task_issues→…→task_nodes→`Task.latest_decomposition_id=NULL`→task_decomposition_records→tasks 顺序覆盖），消除 ReminderRule 自动生成残留导致的 FK/teardown 污染与 F4/F5 顺序依赖；F4/F5 产品逻辑（`FOR UPDATE SKIP LOCKED`、notification 唯一约束、task_version 自增、task_status_logs 版本）不动，待 F3 修复后由 PG 全量连续两轮判断；F6 Ruff 统一整理 import block（125×I001、4×F401、1×E402），`datetime.UTC` 等按 Ruff/isort 排序，4 个 `import app.models` 保留并标注 `# noqa: F401 - register all ORM models in Base.metadata`，ChatService `Path` import 上移模块顶部，Python >100 字符行仍 `0`；PostgreSQL 门禁增强为同一已迁移库连续两轮全量 PG suite（第二轮专门证明无残留）+ 5×20 并发，且先跑无需真实凭据的 PG/小程序/Web/ChatService 纯逻辑门禁再检查 WeCom/Qwen。新增 `scripts/run_test9_release_gate.sh` 与 `tests/test_test9_release_candidate_contract.py`（防清理/权限/available-actions 契约回退）。Test9 本环境：compileall PASS、非PG `500 passed, 28 deselected`、Test9+Test8 静态合同 PASS、迁移/依赖定点 `40 passed`、小程序 `21/21 PASS`、JS `node --check` PASS、ChatService task_intake/auth/config PASS、shell `bash -n` PASS、Web/微信源码与 Test8 完全无差异；真实 PG 28/28×2 / Outbox 5×20=100/100 / Ruff 0 error / 真实企微 E2E 仍待本地 Test9 实跑放行（不伪造 PASS），详见 `docs/FEATURE_16_TEST9_RELEASE_CANDIDATE_REPORT.md`。
- **Test10 发布候选（2026-09-04）**：以 Test9 为代码基线，**只修复 Test9 真实门禁暴露的工程质量问题，不新增产品功能/状态机/Outbox 并发算法/权限边界**。F1 **PG 第二轮失败根因修复**：`app/repositories/task_status_log.py` 的 `list_by_task_id()` / `list_by_task_id_paginated()` / `get_latest_for_task()` 全部以 `task_version` 为第一权威排序键（同事务 `created_at` 共享时不再被随机 UUID 翻转 `completion_approved`/`task_archived` 顺序），Repository 排序合同永久化（不允许退回 `created_at + UUID` 作为权威业务顺序），新增 `tests/test_test10_release_candidate_contract.py` 持续检查同时间戳下 `12→13` 与 `latest` 取最大 `task_version`；F2 **PG 多轮门禁增强**：`scripts/run_postgresql_gate.sh` 新增 `POSTGRES_GATE_PASSES`（默认 2，必须 ≥2；同一数据库不清库连续多轮执行全量 PG suite，专门证明无残留与顺序依赖），新增 `scripts/run_test10_release_gate.sh`（Test10 候选固定 `POSTGRES_GATE_PASSES=3`，开发候选期放大顺序依赖与 teardown 污染）；F3 **Ruff 收口**：`alembic/app/tests/cloud-functions/scripts` 重新分组 import block（标准库/第三方/first-party），按 Ruff/isort 排序，alembic 中 `sqlalchemy` 与本项目 `alembic` package import 保持正确分组，不改变 revision/down_revision 或 migration `upgrade/downgrade` 或业务逻辑；F4 **Web 干净安装依赖合同**：`@testing-library/dom ^10.4.1` 显式加入 `web/package.json` `devDependencies` 与 `web/package-lock.json`，避免依赖已有 `node_modules` 或间接 peer dependency，导致首次干净 `npm ci` 缺包。Test10 本环境：compileall PASS、非PG `504 passed, 28 deselected`、Test10/Repository 定点合同 PASS、ChatService `task_intake/auth/config` PASS、小程序 `21/21 PASS`、JS `node --check` PASS、Web `package-lock` 离线一致性 PASS、`bash -n` Test10/PG gate PASS、候选 ZIP 反向验收与工作树结果一致；真实 PG 28/28×3 / Ruff 0 error / Python 3.12 正式 gate / Web 干净 `npm ci` / 真实企微 E2E 仍待本地 Test10 实跑放行（不伪造 PASS），详见 `docs/FEATURE_16_TEST10_RELEASE_CANDIDATE_REPORT.md`。
- **Test11 最终技术门禁（2026-09-04）**：发布工程收口，**零产品功能/数据库表/字段/迁移/任务状态迁移/权限扩展/Outbox 算法变化**。仅修复 Test10 本地报告的 6 个 Ruff 问题：`app/integrations/wecom/client.py` 的 `Callable` 与 `app/services/features/performance_matching/scoring.py` 的 `Iterable/Mapping/Sequence` 改从 `collections.abc` 导入（UP035）；`app/services/business_capabilities.py`、`app/services/task_workflow.py`、`cloud-functions/ChatService/services/task_intake.py`、`tests/migrations/test_alembic_metadata.py` import block 按 Ruff/isort 规则整理（I001）；AST 语义对比确认无函数体或业务规则变化。新增最终技术门禁 `scripts/run_test11_release_gate.sh`（强制 Python 3.12 + 项目 venv + `pip check` + 真实 `ruff check .` 无 auto-fix + compileall + Test8/9/10/11 合同 + 空 PostgreSQL 16 迁移单 head `c2d3e4f5a6b7` + 同库连续 3 轮 PG suite + 5×20=100 并发 + 非 PG 全量回归 + 小程序 + Web 干净 `npm ci`/lint/test/build + ChatService，技术门禁与真实 WeCom E2E 分离）与 `tests/test_test11_release_candidate_contract.py` 冻结 Ruff 修复与门禁合同。Test11 本环境：compileall PASS、受影响模块定点 `84 passed`、ChatService `3/3 PASS`、Test8/9/10/11/dev-dependency 合同 `19 passed`、非PG `508 passed, 28 deselected`、小程序 `21/21 PASS`、JS syntax PASS、Python >100 字符行 `0`、Test11 gate 按设计 fail-closed（`Python 3.12 is required`）、候选 ZIP 反向验收通过；Ruff 0 errors / PG 28/28×3 / 并发 100/100 / Python 3.12 正式 gate / Web 干净安装 / 真实企微 E2E 仍待正式环境放行（不伪造 PASS），`V1.1 TECHNICAL RELEASE READY` 仅在上述全绿后升级，详见 `docs/FEATURE_16_TEST11_TECHNICAL_GATE_REPORT.md` 与 `docs/DEV-18_Test11_执行与反向验收报告.md`。
- 后端测试保持 **508 passed（非 PostgreSQL，含 28 项 deselected PG opt-in）**；`ruff` 仅风格类告警，F821 已清零。

#### 文档

- 新增 `docs/FEATURE_16_WECOM_AUTH_ACCEPTANCE.md`、`docs/WECOM_IDENTITY_ORG_MAPPING.md`、`docs/SECRETS_CONFIGURATION_GUIDE.md`、`docs/FEATURE_16_SECRET_CONFIG_ACCEPTANCE.md`、`docs/FEATURE_16_TEST2_RELEASE_GATE_REPORT.md`、`docs/FEATURE_16_TEST3_EXECUTION_REPORT.md`、`docs/FEATURE_16_TEST4_EXECUTION_REPORT.md`、`docs/FEATURE_16_TEST5_PARALLEL_IMPROVEMENT_REPORT.md`、`docs/FEATURE_16_TEST6_EXECUTION_REPORT.md`、`docs/FEATURE_16_TEST7_AI_FIELD_HYDRATION_REPORT.md`、`docs/FEATURE_16_TEST8_RELEASE_CANDIDATE_REPORT.md`、`docs/FEATURE_16_TEST9_RELEASE_CANDIDATE_REPORT.md`、`docs/FEATURE_16_TEST10_RELEASE_CANDIDATE_REPORT.md`、`docs/FEATURE_16_TEST11_TECHNICAL_GATE_REPORT.md`、`docs/DEV-18_Test11_执行与反向验收报告.md`、`docs/FEATURE_16_REAL_WECOM_E2E.md`。

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

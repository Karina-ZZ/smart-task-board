# 更新日志 (Changelog)

本仓库所有显著变更都记录在此文件中。格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

## [H5 网页第一版] - 2026-09-07 — Test16 全功能迁移至企业微信自建应用 React H5

> 在 Test16 Performance-Link Hotfix（commit `bd7400b`）之上叠加。本轮**只新增 H5 网页代码与文档**，PostgreSQL 业务表 / 字段 / Alembic / 任务状态机 / AI 拆解业务规则 / 节点承接与提醒 / 绩效 / 优先级 / 负荷 / 冲突计算 / 高管 KPI 与总体进度公式 / Test16 微信小程序生产代码：均未改动。Test16 微信小程序仍为唯一生产前端。

### 新增

#### 后端

- **企业微信 H5 OAuth 身份**：`app/integrations/wecom/client.py` + `app/services/wecom_authentication.py` 已支持 H5 网页 OAuth code 换 `userid`，与 Test16 小程序共用同一身份流（`userid → users.wecom_user_id → employee_no → JWT`）。
- **企业微信自建应用消息 Provider**：`app/integrations/wecom/message_provider.py` 新增 `WeComApplicationMessageProvider`，`AUTH_MODE=wecom` 时调用 `/cgi-bin/message/send`，收件人继续从 `employee_no` 映射 `users.wecom_user_id`。通知 Outbox、重试、幂等、提醒业务规则未重写。
- `app/core/config.py` / `app/api/v1/auth.py` / `app/api/dependencies.py` 适配 H5 路径常量与微信回调校验。
- `config-examples/backend.env.example` 新增 `WECOM_H5_BASE_URL=https://task.example.com`。

#### 前端（H5 - `web/`）

- 新增 H5 自有页面与交互 13 个：工作台（`features/workbench`）、任务概览（`features/task-overview`）、任务详情 + 汇报 + 验收 + 完成（`features/task-detail`）、创建三页（`features/task-intake` 含 `TaskCreateDetailsPage`/`TaskCreateDetailsPanel`/`TaskCreateStartPage` + `features/task-create/TaskConfirmPage`）、AI 拆解（`features/task-decomposition`）、通知中心（`features/notifications`）、我的（`features/profile`）、高管看板与员工任务下钻（`features/executive-dashboard`）。
- 新增 `web/src/pages/WeComCallbackPage.tsx`（企业微信 OAuth 回调落地页）。
- 新增 `web/src/integrations/wecom/oauth.ts` + `web/src/integrations/chat-service.ts`（H5 端 wecom/ChatService 集成）。
- 新增 `web/.env.wecom.example`（Vite 端 wecom 与 ChatService 占位，无真实凭据）。
- 改造底部导航（工作台 / 任务 / 团队（高管）/ 消息 / 我的），移除"创建"为 Tab；工作台恢复直接 AI 文字输入、语音、发送、3 项指标、四象限；任务详情恢复节点展开、节点动作、底部主动作、更多操作 Sheet、操作记录 Sheet；通知恢复全部/任务/提醒/系统四 Tab 并按 `target_type` 深链任务、节点、AI 拆解、汇报或验收；高管恢复部门选择 Sheet、周期 Tab、四指标、四象限、负荷热力图、负荷构成和员工任务下钻。
- 移除浏览器原生 `window.prompt()` / `window.confirm()`，业务确认改为受控 Sheet。

#### 测试

- 新增 `tests/test_h5_web_v1_contract.py`（H5 静态迁移合同 + 企业微信客户端/认证定点 24 用例）。
- 新增 `tests/integrations/test_wecom_client.py`（沿用 Test3 起累计，未重写）。

### 本轮明确没有修改

- PostgreSQL 业务表 / 字段 / Alembic 迁移 / 任务状态机 / AI 拆解业务规则 / 节点承接与提醒规则 / 绩效匹配、优先级、负荷、冲突计算 / 高管 KPI 与总体进度公式 / Test16 微信小程序生产代码。

### 当前累计门禁（本环境实测）

```text
后端非 PostgreSQL 全量：617 passed / 41 deselected
H5 静态迁移合同 + 企业微信客户端/认证定点：24 passed
Test16 微信小程序累计：25 / 25 测试文件 PASS
微信小程序 JS node --check：PASS
Python compileall：PASS
React/TypeScript 源码语法转译：103 files / 0 syntax errors
tsc --noEmit（web/，含类型检查）：42 条类型层错误 → 见 docs/H5_WEB_V1_TSC_FINDINGS.txt
```

> 报告原报"语法转译 0 errors" 指 swc/esbuild parse 零错误，并非 tsc 类型零错误。tsc 报告需在用户本地 / CI 环境消除；本次未修复。

### 当前环境限制

- `npm ci` registry 访问超时，Web 完整依赖安装 + ESLint + Vitest + Vite build + Playwright E2E 仍未正式放行。
- 当前容器无真实 PostgreSQL 服务，41 个 PG 专项待正式测试库执行。
- 无真实 CorpID/AgentID/Secret/可信域名/测试员工，真实企业微信 OAuth 和应用消息 E2E 待部署执行。
- 企业微信移动 WebView、375/390/430、键盘、安全区、真机麦克风/ASR 待真机验收。

### 当前定位

```text
IMPLEMENTATION: DONE
CURRENT-ENV PAGE INTEGRATION: PASS
NON-PG REGRESSION: PASS
WECHAT-MINIPROGRAM BASELINE REGRESSION: PASS
TSC TYPECHECK (web/): 42 ERRORS / SEE docs/H5_WEB_V1_TSC_FINDINGS.txt
WEB FULL NPM GATE: BLOCKED BY NETWORK
REAL POSTGRESQL: PENDING
REAL WECOM E2E: PENDING
```

本版本可以进入真实环境门禁，但不是生产放行证明。

### 文档

- 新增 `docs/H5_WEB_V1_EXECUTION_REPORT.md`（执行报告）。
- 新增 `docs/H5_WEB_V1_MIGRATION_MATRIX.md`（Test16 → H5 逐页映射矩阵）。
- 新增 `docs/H5_WEB_V1_PAGE_INTEGRATION_REPORT.md`（页面级联调报告）。
- 新增 `docs/WECOM_H5_DEPLOYMENT.md`（企业微信 H5 部署说明）。
- 新增 `docs/H5_WEB_V1_DIFF.txt`（变更范围清单）。
- 新增 `docs/H5_WEB_V1_REVERSE_ACCEPTANCE.txt`（ZIP 反向验收记录）。
- 新增 `docs/H5_WEB_V1_TSC_FINDINGS.txt`（tsc 类型层错误快照与影响判定）。

---

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
- **Test11 Web 登录路由 Hotfix（2026-09-07）**：Web `/login` 路由收口，**零后端认证/数据库/小程序/云函数/Feature 01～16 改动**。原 `/login` 仍指向 DEV-02 占位 `RoutePlaceholders.LoginRoute`（用户实际看到开发占位文案），项目中已有真实 `LoginPage` 但未接入生产路由；本次 `web/src/app/router.tsx` 将 `/login` 改渲染 `<LoginPage />` 并移除 `LoginRoute` 导入，`LoginPage` 读取 `location.state.source`、复用 `readReturnSourceState()/resolveReturnTarget()`：直接登录默认 `/workbench`，从 `/tasks`/任务详情/带 query 内部路由跳登录则成功后恢复原路由（含 query/hash），外部或不安全返回地址回退 `/workbench`，已登录访问 `/login` 直入安全目标且不再请求演示用户列表。测试更新 `router.test.tsx`/`LoginPage.test.tsx`/e2e `dev-06`/`dev-07`（覆盖 /login 渲染真实页、匿名跳转、登录后恢复 `/tasks?status=pending_accept`、保留 query/hash、拦截不安全外部地址、已登录自动离开）。白名单差异恰 6 文件 `added 0 / removed 0 / changed 6 / WHITELIST_DIFF_PASS`；`app/`、`alembic/`、`wechat-miniprogram/`、`cloud-functions/` 与 Test11 基线完全一致。本环境：TS transpile 81 文件 0 error、Hotfix 合同 17/17 PASS、trailing whitespace 0、旧登录占位断言 0 残留、非PG `508 passed`/小程序 `21/21` 不变；ESLint/Vitest/build/Playwright DEV-06·07 正式 Web 门禁待本地 npm 环境执行（不伪造 PASS），详见 `docs/FEATURE_16_WEB_LOGIN_ROUTE_HOTFIX_REPORT.md`。
- 后端测试保持 **508 passed（非 PostgreSQL，含 28 项 deselected PG opt-in）**；`ruff` 仅风格类告警，F821 已清零。
- **功能 16 任务来源选填 + AI 追问覆盖修复 Hotfix（2026-09-07）**：在功能 16 Tech 收口 + RELEASE-01 部署工程之上叠加，**零 alembic 迁移 / 零状态机 / 零权限边界 / 零绩效/负荷/提醒算法 / 零 web 改动**，数据库结构变更 `0`、Alembic 新增迁移 `0`；`app/models/task.py` 与 `app/schemas/task.py` 原本即允许 `task_source` 为空。后端 `app/services/task_workflow.py` 的 `_validate_send_ready_task()` 把任务来源从发送必填集合（10→9）移除，其余 9 项必填 + 日期 / hours / 节点 / 依赖门禁完全不变，配套测试 `tests/services/test_task_workflow.py` 同步。微信小程序 `pages/create/index.js` 不再默认把任务来源设为 "AI 任务助手"；`pages/create-details/index.js` 删除 `needsClarification` 独立硬阻断、发送前只校验 9 项真实必填、AI 追问前传入当前草稿并在回填后保留用户已确认字段（优先级：用户最新明确填写/选择 > 本轮 AI 对未解决字段的补充 > 上一轮 AI 识别值）、用户编辑/选择字段时同步消解对应 AI 缺失/低置信提示；`pages/create-details/index.wxml` 任务来源去掉必填标记并加选填示例；`pages/create-confirm/index.wxml` 空任务来源显示 "未填写"；`utils/api.js` 创建任务 payload 允许 `taskSource=null` 并支持当前草稿 + 受保护字段合并的 clarification API；`utils/store.js` mock 草稿/发送合同同步允许任务来源为空；测试 `tests/ai-field-hydration.test.js` 同步更新 + 新增 `tests/task-creation-clarification-hotfix.test.js`；`docs/DEVELOPMENT_PLAN_V1.1.md` 增加 "功能16 P0 补充｜任务来源选填 + AI 追问覆盖修复" 段记录本次 P0 冲突裁决。专项 6 项 PASS（任务来源为空后端确认发送 / 其他真实必填缺失仍阻断 / AI 问题未回答但 9 项完整可进入确认发送 / 空来源 mock 发送 / 用户手填名称/描述/目标/来源/截止时间后再 AI 追问仍保留 / AI 仍可补充未解决汇报对象）。累计：后端非 PG `510 passed / 28 deselected`、小程序 `22 / 22 test files PASS`、JS 50 个文件 `node --check` 全过、Python compileall PASS、ChatService `test_task_intake / test_auth / test_config_file` 全部 PASS、Alembic head 仍 `c2d3e4f5a6b7`。本环境缺 `psycopg / psql / Docker / PostgreSQL server / 微信开发者工具`，28 项真实 PG 专项 + 微信开发者工具设备级验收不能在本环境声明 PASS；正式放行应在用户本地/CI 环境执行原发布门禁。详见 `docs/FEATURE_16_TASK_SOURCE_OPTIONAL_CLARIFICATION_HOTFIX_REPORT.md`。
- **Test13 Web 登录稳定启动 + AI 确认非硬门槛 Hotfix（2026-09-07）**：在功能 16 TaskSourceOptional Hotfix 之上叠加，**零 app/ / alembic/ / cloud-functions/ 改动，数据库变更 `0`、Alembic 新增迁移 `0`**；`app/services/task_workflow.py` 发送必填 9 项 + `tests/services/test_task_workflow.py` 合同保持不变。Web 登录稳定启动 4 项：① `scripts/start-web-demo.sh` 锁定当前候选包目录、默认前端 `5174` 后端 `8001`、端口已被占用直接停止（防止误连 2026-09-04 旧 5173 Vite 进程）、真实请求 FastAPI `/health/ready` 与 `/api/v1/auth/prototype-users`、不迁移不 seed 不清库、Vite 与 FastAPI 由同一终端进程管理 Ctrl+C 只结束本次启动进程；② `config-examples/web-demo.env.example`（独立 prototype 演示模板、强制 `AUTH_MODE=prototype`、禁止覆盖正式 wecom 配置、配合 `start-web-demo.sh` 使用）；③ `web/e2e/dev-18-real-login.spec.ts`（`STB_REAL_E2E=1` 对运行中的真实前后端进行登录验证、不使用 `page.route(...fulfill)`、默认 system Chrome channel）；④ `web/src/pages/LoginPage.tsx` 增加 prototype 用户接口普通网络连接失败时"登录服务不可用"专项提示与重试（`ApiError` 仍展示后端安全业务错误），同步更新 `web/src/pages/LoginPage.test.tsx`、`web/src/app/router.test.tsx`（带回异步等待修正 `getByLabelText` → `await findByLabelText`）。AI 确认非硬门槛 5 项：① `wechat-miniprogram/pages/create-details/index.wxml` AI 卡片文案明确"可回答 AI 继续整理也可直接补齐；必填信息完整后即可进入发送确认"；② `pages/create-details/index.js` `next()` 改为可读显式流程只调用现有 9 项字段 `validate()` 与真实 `saveDraft()`，不读取 `needsClarification` 作为发送门槛并增加业务注释；③ `tests/task-creation-clarification-hotfix.test.js` 新增页面级合同：`needsClarification=true` + AI 问题仍保留 + 9 项必填完整时，必须保存当前草稿并进入 `/pages/create-confirm/index`；④ `tests/integration/test_core_workflow_api_postgresql.py` 真实 PG 核心工作流的创建 payload 改为 `task_source=null`（下一次执行原 28 项 PG 门禁时同时验证选填来源贯穿真实创建→提交确认→发送主链路，未改生产数据库逻辑）；⑤ `scripts/verify-ai-send-e2e.py` 新增真实 HTTP 专项验证（prototype 登录→创建 `task_source=null` 草稿→提交确认→confirm-and-send→重新读取任务，预期最终为待接受且创建阶段无节点，不迁移不 seed 不清理数据库，必须对隔离测试库运行）。端口与登录打开方式 1 项：`docs/LOCAL_PORTS_AND_LOGIN_GUIDE.md` 正式区分 Web 本地演示 `http://127.0.0.1:5174/login`、FastAPI 本地 `http://127.0.0.1:8001`（不是登录页面，Swagger 为 `/docs`）、微信小程序 mock（无浏览器端口）、微信小程序 API 联调（测试副本 + 隔离 FastAPI）、正式企业微信（应用入口 + `wx.qy.login()` + `/api/v1/auth/wecom`），明确禁止把本地 `AUTH_MODE=prototype` 配置复制到生产环境，并写明如何用 `lsof -nP -iTCP:5173 -sTCP:LISTEN` 与 `lsof -a -p <PID> -d cwd` 核对端口对应进程的真实工作目录（防"端口=版本"误判）。白名单核对：受保护目录 `app/` / `alembic/` / `cloud-functions/` 与上一轮 `0bf5de1` 完全一致；本轮 14 文件（7 改 + 7 新）全部位于 `wechat-miniprogram/{pages,tests}/`、`web/{src,e2e}/`、`tests/integration/`、`scripts/`、`config-examples/`、`docs/`，新增 `config-examples/web-demo.env.example`、`web/e2e/dev-18-real-login.spec.ts`、`scripts/start-web-demo.sh`、`scripts/run-login-ai-hotfix-checks.sh`、`scripts/verify-ai-send-e2e.py`、`docs/FEATURE_16_LOGIN_AI_GATE_HOTFIX_EXECUTION_REPORT.md`、`docs/LOCAL_PORTS_AND_LOGIN_GUIDE.md`，修改 `web/src/app/router.test.tsx`、`web/src/pages/LoginPage.test.tsx`、`web/src/pages/LoginPage.tsx`、`wechat-miniprogram/pages/create-details/index.js`、`wechat-miniprogram/pages/create-details/index.wxml`、`wechat-miniprogram/tests/task-creation-clarification-hotfix.test.js`、`tests/integration/test_core_workflow_api_postgresql.py`（仅测试代码 payload）。本环境：py_compile PASS、JS `node --check` PASS、累计非 PG `510 passed / 28 deselected`、小程序 `22 / 22 test files` 不变、JS 50 个文件 PASS、`bash -n` `start-web-demo.sh` + `run-login-ai-hotfix-checks.sh` PASS、TS transpile 4 个 web 文件 0 error；本执行容器没有 Python 3.12 venv / Docker / PostgreSQL server / 完整 `web/node_modules` / 微信开发者工具，原 28 项 PG 专项、Web `npm ci → lint → Vitest/build`、Playwright `dev-18-real-login.spec.ts`、`verify-ai-send-e2e.py` 隔离 PG、微信开发者工具 API 模式"不回答 AI→补齐 9 项→真实发送→待接受"仍待用户本地/CI 环境执行（不伪造 PASS）。详见 `docs/FEATURE_16_LOGIN_AI_GATE_HOTFIX_EXECUTION_REPORT.md` 与 `docs/LOCAL_PORTS_AND_LOGIN_GUIDE.md`。
- **Test14 任务执行-汇报循环 Hotfix（2026-09-07）**：在 Test13 Web 登录 + AI 确认非硬门槛 Hotfix 之上叠加，**零 app/ / alembic/ / cloud-functions/ 改动，数据库变更 `0`、Alembic 新增迁移 `0`**；`app/models/` 29 文件、`alembic/` 12 文件、`wechat-miniprogram/` 118 文件、`app/services/task_board_query.py`、`app/core/config.py`、`web/src/pages/LoginPage.tsx`、`web/src/app/router.tsx`、`pyproject.toml`、`web/package.json`、`web/package-lock.json`、`scripts/run_postgresql_gate.sh` 全部 byte-identical 冻结。F1 修复创建人发送后工作台 `reassign_task` 响应契约补齐（`web/src/api/taskActions.ts` + `web/src/api/types.ts` + `app/schemas/task.py` + `app/api/errors.py` + `web/src/features/task-detail/format.ts`）；F2 可选 `report_cycle` 入库前校验（新增 `app/core/report_cycle.py` + `app/schemas/task_board.py` + `tests/services/test_test14_report_cycle.py` 拒绝 cycle 长度 ≤0 / 阶段重复 / 阶段名空白）；F3 AI 周期提示词从硬编码 `weekly` 改为 `null`，与 `cycle` 入库契约一致（`app/ai/prompts/task_agent.md` + `app/ai/prompts/task_intake.md` + `cloud-functions/ChatService/prompts/task_intake.md`）；新增脱敏诊断 `app/core/error_diagnostics.py`（异常脱敏 + 路径/类型/状态码 + 永不打印敏感负载）。范围审计 30 文件（13 改 + 17 新 + 0 删），白名单核对脚本 `scripts/verify-test14-scope.py`。本环境：py_compile 8 文件 PASS、JS `node --check` PASS、`compileall` PASS、TS transpile 84 文件 0 error、非 PG `568 passed / 32 deselected`、小程序 `22/22 PASS`、ChatService `3/3 PASS`、JS 50 文件 PASS、`bash -n` `run_test14_live_gate.sh` + `run_test14_technical_gate.sh` PASS、专项 `test_test14_contracts.py` + `test_test14_diagnostics.py` + `test_test14_report_cycle.py` + `test14-contracts.test.ts` 全部 PASS；原 28 项 PG 专项 + 微信开发者工具 API 模式"发送后 reassign_task 工作台响应契约正确 + report_cycle 拒绝非法值 + AI 周期提示词为空时不误导用户"仍待真实 PG / 微信开发者工具环境执行（不伪造 PASS），本次无数据库结构变更。详见 `docs/TEST14_EXECUTION_REPORT.md` / `docs/TEST14_ACCEPTANCE_CHECKLIST.md` / `docs/TEST14_DIFF.txt` / `docs/TEST14_BASELINE_MANIFEST.json` / `docs/TEST14_LOCAL_PORTS_AND_LOGIN_GUIDE.md`。
- **RELEASE-01 生产部署工程（2026-09-04）**：只新增部署与运维基础，**零业务代码改动**（`app/`、`alembic/versions/`、`wechat-miniprogram/pages|utils/`、`web/src/`、`tests/` 逐文件 SHA-256 保护，交付方对 Test8 基线验收 361 文件 0 差异；本仓库叠加到 Test11 最新代码后受保护目录同样零改动）。新增 `deploy/`：`Dockerfile.backend` / `Dockerfile.chatservice` / `docker-compose.production.yml`（backend、chatservice、nginx、postgres 四服务；PostgreSQL 仅内部 Docker 网络，不发布宿主机 5432）、`nginx/wangxu.conf.template`（仅 HTTP→HTTPS 跳转与 HTTPS 反代）、`env/backend|chatservice.env.production.example`（强制 `APP_ENV=production`、`AUTH_MODE=wecom`、`CHAT_REQUIRE_AUTH=true`，全部 `REPLACE_WITH_*` 占位符）、`systemd/wangxu-backend|chatservice.service`、`scripts/`（preflight 阻止测试配置上生产、deploy-compose、health-check 校验 `/health/live|ready` 与 ChatService、backup-postgres 生成 custom dump+SHA-256、restore-postgres 默认拒绝破坏性恢复、rollback-code 不自动数据库 downgrade、render-nginx、activate-release、validate-release01）；新增 `docs/deployment/` 五篇上线交接文档（部署指南、环境变量、企微部署、发布清单、运维回滚）与 `RELEASE_01_ACCEPTANCE.md` 验收记录、`docs/RELEASE_01_DEPLOYMENT_ENGINEERING_REPORT.md` 工程报告。本环境复验：9 个 deploy 脚本 `bash -n` PASS、Compose YAML 解析 PASS（四服务齐全、PG 无宿主机端口）、env 模板强制项 PASS、密钥扫描 0 命中；Docker 真实生产部署 / 企业微信真实 E2E / Qwen 公网调用 / 真实通知仍待公司预发环境执行（不伪造 PASS），真实通知 Provider、提醒 Worker、通讯录同步属后续 RELEASE 阶段。

#### 文档

- 新增 `docs/FEATURE_16_WECOM_AUTH_ACCEPTANCE.md`、`docs/WECOM_IDENTITY_ORG_MAPPING.md`、`docs/SECRETS_CONFIGURATION_GUIDE.md`、`docs/FEATURE_16_SECRET_CONFIG_ACCEPTANCE.md`、`docs/FEATURE_16_TEST2_RELEASE_GATE_REPORT.md`、`docs/FEATURE_16_TEST3_EXECUTION_REPORT.md`、`docs/FEATURE_16_TEST4_EXECUTION_REPORT.md`、`docs/FEATURE_16_TEST5_PARALLEL_IMPROVEMENT_REPORT.md`、`docs/FEATURE_16_TEST6_EXECUTION_REPORT.md`、`docs/FEATURE_16_TEST7_AI_FIELD_HYDRATION_REPORT.md`、`docs/FEATURE_16_TEST8_RELEASE_CANDIDATE_REPORT.md`、`docs/FEATURE_16_TEST9_RELEASE_CANDIDATE_REPORT.md`、`docs/FEATURE_16_TEST10_RELEASE_CANDIDATE_REPORT.md`、`docs/FEATURE_16_TEST11_TECHNICAL_GATE_REPORT.md`、`docs/DEV-18_Test11_执行与反向验收报告.md`、`docs/FEATURE_16_REAL_WECOM_E2E.md`、`docs/deployment/`（01-PRODUCTION_DEPLOYMENT_GUIDE、02-PRODUCTION_ENVIRONMENT_VARIABLES、03-WECOM_DEPLOYMENT_GUIDE、04-PRODUCTION_RELEASE_CHECKLIST、05-OPERATIONS_AND_ROLLBACK、RELEASE_01_ACCEPTANCE）、`docs/RELEASE_01_DEPLOYMENT_ENGINEERING_REPORT.md`、`docs/FEATURE_16_WEB_LOGIN_ROUTE_HOTFIX_REPORT.md`、`docs/FEATURE_16_TASK_SOURCE_OPTIONAL_CLARIFICATION_HOTFIX_REPORT.md`、`docs/reference/03-第五版-智能任务看板数据表结构-显式ID版-Test11部署交接.pdf` 与同名 .docx（与 `docs/` 根目录及 `docs/reference/` 下第四版并列保留；本版作为 Test11 部署交接唯一引用的数据表结构版本）、`docs/FEATURE_16_LOGIN_AI_GATE_HOTFIX_EXECUTION_REPORT.md`、`docs/LOCAL_PORTS_AND_LOGIN_GUIDE.md`（Test13 端口与登录打开方式文档）。

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

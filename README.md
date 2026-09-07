# Smart Task Board

## Test14 当前候选（2026-09-07）

本次仅修复创建人发送后工作台的 `reassign_task` 响应契约、可选 `report_cycle` 入库校验和AI周期提示词，并增加脱敏诊断与专项测试。数据库模型/迁移、小程序、登录认证与其他业务实现保持原样。

当前容器补充回归：非PG568项、小程序22项、JS50个和ChatService3项通过。容器只有Python3.13，未完成正式Python3.12、真实PG、完整Web与开发者工具API门禁；不能据此生产放行。下文历史进度和历史PASS不是Test14的新验收证据。

- 执行与环境限制：`docs/TEST14_EXECUTION_REPORT.md`
- 端口、各端打开及复验命令：`docs/TEST14_LOCAL_PORTS_AND_LOGIN_GUIDE.md`
- 正式验收清单：`docs/TEST14_ACCEPTANCE_CHECKLIST.md`
- 范围检查：`python scripts/verify-test14-scope.py`


智能任务看板使用 FastAPI、PostgreSQL 和 React 实现任务创建、结构化拆解、参与人协作、状态流转、节点执行、完成验收与返工。后端业务规则通过 JSON REST API 提供，前端提供适配桌面和移动设备的任务看板界面。


## Secret configuration

Real WeCom credentials, Qwen/DashScope keys, database passwords and JWT secrets are not stored in source code. New setups should copy `config-examples/backend.env.example` and `config-examples/chatservice.env.example` into the ignored local `secrets/` directory. Production servers should keep the same files under `/etc/wangxu/`.

Detailed replacement and rotation instructions: `docs/SECRETS_CONFIGURATION_GUIDE.md`.

本地 Web 演示登录、5174/8001 与旧 5173/8000 的区别、正式企业微信打开方式，以及本轮 Web 登录/AI确认发送专项验收命令，统一见：`docs/LOCAL_PORTS_AND_LOGIN_GUIDE.md`。本地 Web prototype 演示使用独立 `config-examples/web-demo.env.example`，不得覆盖正式企业微信配置。 本轮专项修改与测试证据见：`docs/FEATURE_16_LOGIN_AI_GATE_HOTFIX_EXECUTION_REPORT.md`。

## 当前进度

Phase 0～5 后端基础已经完成：

- Phase 0：工程、配置、健康检查、SQLAlchemy、Alembic、Pytest 和 Ruff。
- Phase 1：10张核心业务表的 ORM 和显式业务主键。
- Phase 2：首份 PostgreSQL 迁移及升级、降级验证。
- Phase 3：Repository 和 Unit of Work 事务边界。
- Phase 4：任务和节点状态机 Service。
- Phase 5：16条核心 REST API 业务路径，包括创建、查询、确认、发送、接受或退回、节点执行、完成提交和验收。

Batch 1 已经实现基础原型身份、任务列表、统一 Inbox、Dashboard 首页摘要、后端授权动作投影和 React 响应式前端，并已通过全部质量门。Batch 2A 已新增进度汇报和任务卡点模型及迁移，本地 checkpoint 为 `94108af17225ca9e4a2f728e47a117f1d546a0af`。Batch 2B 已完成进度汇报、问题闭环及真实 PostgreSQL 验收，本地 checkpoint 为 `7a0cf4e3c6b920d5fea10c351d4d7789f39baf90`。

Wave 1 的完成验收与返工现已实现并通过总质量门：每次提交形成不可变验收轮次；验收人按任务指定 reviewer 快照，未指定时回退创建人；支持通过、强制原因驳回、仅返工整体交付物、指定节点显式重开、多轮历史、API、Inbox、任务详情和响应式 UI。旧有 `pending_review` / `completed` 数据由迁移安全回填。本文档随 Wave 1 checkpoint 候选提交，checkpoint commit hash 尚未创建。

### Hotfix 累计进度（功能 16 / Test3 起，按 commit 时间倒序）

| 阶段 | 状态 | 范围摘要 |
| --- | --- | --- |
| **Test14 任务执行-汇报循环 Hotfix（2026-09-07）** | 🔧 已提交，待真实 PG / Web / 微信 API 复验 | 修复创建人发送后工作台 `reassign_task` 响应契约、可选 `report_cycle` 入库校验、AI 周期提示词（`weekly`→`null`），新增脱敏诊断与专项测试。**数据库变更 0 / Alembic 新增迁移 0 / 小程序/云函数改动 0**。白名单 30 文件（13 改 + 17 新）。本环境：非PG 568 passed / 32 deselected、小程序 22/22、JS 50 文件、ChatService 3/3、TS transpile 84 文件 0 error；详见 `docs/TEST14_EXECUTION_REPORT.md` / `docs/TEST14_ACCEPTANCE_CHECKLIST.md` / `docs/TEST14_DIFF.txt` |
| **Test13 Web 登录稳定启动 + AI 确认非硬门槛 Hotfix（2026-09-07）** | 🔧 已提交，待真实 PG / Web / 微信 API 复验 | 锁定候选包目录 + 5174/8001 端口、隔离 `verify-ai-send-e2e.py` 与 PG、删 `AI_GATE_REQUIRED` 硬阻断、登录成功按来源安全恢复原路由。**数据库变更 0**；详见 `docs/FEATURE_16_LOGIN_AI_GATE_HOTFIX_EXECUTION_REPORT.md` |
| **功能 16 任务来源选填 + AI 追问覆盖修复 Hotfix（2026-09-07）** | 🔧 已提交，待 PG / 微信开发者工具放行 | 发送必填从 10→9（移除 `task_source`），小程序手工选人/AI 追问/受保护字段合并契约同步。**数据库变更 0**；详见 `docs/FEATURE_16_TASK_SOURCE_OPTIONAL_CLARIFICATION_HOTFIX_REPORT.md` |
| **功能 16 Test11 最终技术门禁（2026-09-04）** | 🔧 已提交，待正式门禁放行 | 6 项 Ruff 收口（`collections.abc` 迁移 + import block 整理）；新增 `run_test11_release_gate.sh`（Py 3.12 + Ruff 0 + PG 同库 3 轮 + 100 并发 + Web 干净安装的正式技术门禁）。**零产品/表/字段/迁移/状态机/权限变化**；详见 `docs/FEATURE_16_TEST11_TECHNICAL_GATE_REPORT.md` |
| **功能 16 发布候选 Test10（2026-09-04）** | 🔧 已提交，待真实环境放行 | F1 PG 第二轮失败根因修复（`TaskStatusLogRepository` 以 `task_version` 为第一权威排序键，消除同事务 `created_at` 共享时随机 UUID 翻转顺序的缺陷）；F2 PG 多轮门禁增强（`POSTGRES_GATE_PASSES` ≥2，Test10 候选固定 3）；F3 Ruff 收口；F4 Web 干净安装依赖合同（`@testing-library/dom ^10.4.1`）；详见 `docs/FEATURE_16_TEST10_RELEASE_CANDIDATE_REPORT.md` |
| **功能 16 发布候选 Test9（2026-09-04）** | 🔧 已提交，待真实环境放行 | F1 归档搜索权限契约（employee scope 不扩大可见性）；F2 `available-actions.nodes` 改为稀疏动作投影；F3 business fixture 按 `task_id` 清理完整任务图（消 ReminderRule 残留 FK/teardown 污染）；F6 Ruff 统一整理 import block；PG 门禁增强为同库连续两轮全量 PG suite + 5×20 并发；详见 `docs/FEATURE_16_TEST9_RELEASE_CANDIDATE_REPORT.md` |
| **功能 16 发布候选 Test8（2026-09-04）** | 🔧 已提交，待真实环境放行 | 收口 Test6 真实验收暴露的 6 项 PostgreSQL 债务（completed/archived 旧合同、task_archives FK 清理、V1.1 hours 泄漏、pending node 可用动作旧断言）与 202 项 Ruff 历史债务（import 规范排序、长行清零，>100 字符行=0）；详见 `docs/FEATURE_16_TEST8_RELEASE_CANDIDATE_REPORT.md` |
| **功能 16 Test6 定点修复 / Test5 并行完善 / Test4 修复 / Test3 发布门禁（2026-09-03）** | 🔧 已提交，待真实环境放行 | Test6：修 `/available-actions` 500 + `DetachedInstanceError`；Test5：收敛 PG V1.1 集成测试夹具 + 加固 Outbox 并发防回流断言 + 真实企微 E2E 脚本；Test4：修 Test3 拦出的旧 PG V1.1 fixture 债务（F1-F7）+ Outbox 并发测试 + `/me` 旧断言 + `httpx2`→`httpx` 修正；Test3：发布门禁（硬门禁：Py 3.12 + 真实 PG 16 + 真实企微配置）；详见 `docs/FEATURE_16_TEST3/4/5/6_EXECUTION_REPORT.md` |

> 详细范围 + 本地实测结果 + 待真实环境复验项，均在各 Test 对应报告 `docs/FEATURE_16_TEST*_EXECUTION_REPORT.md` / `docs/TEST14_*_*.md` 中。下文历史 PASS 数据均非 Test14 的新验收证据。

## 微信小程序累计交付状态

当前用户侧累计交付线位于 `wechat-miniprogram/`，功能 01～04 已按第二版前端页面结构和 PRD V1.1 逐项实现：工作台、任务概览、任务详情、登录与权限。功能 04 不新增第二版原型之外的登录业务页，而是在小程序启动和 API 网关层接入服务端会话，避免破坏既有页面结构。

登录与权限当前具备：受控开发登录、`GET /me` 当前用户/部门/角色/授权范围投影、access/refresh token 保存与旋转、401 自动恢复、登出撤销、任务关系投影、员工/高管/管理员数据范围校验。生产环境不允许身份切换或重置演示数据；管理员系统身份也不自动成为任意业务任务的超级用户。真实企业微信凭证换票仍需要部署环境提供企业应用配置后接入现有 Auth/Identity Service。

## 当前已实现能力

后端和 API：

- 原型用户列表、原型登录、短期 Bearer JWT 和 `GET /api/v1/me`。
- 创建任务草稿、创建人确认、确认发送、承办人接受或退回、创建人重新发送。
- 节点开始、进度更新和完成，主承办人提交不可变完成验收轮次。
- reviewer 快照授权、验收通过、填写原因驳回、整体交付物返工和指定节点显式重开。
- 多轮验收历史与旧数据安全回填；历史轮次不会被重新提交覆盖。
- 当前用户任务列表、任务详情、节点查询和状态日志查询。
- 统一 Inbox、Dashboard 首页摘要和由后端计算的 `allowed_actions`。
- 任务级和节点级不可变进度汇报、追加式汇报更正、周期待汇报查询。
- 卡点、资源需求、协同支持和风险上报，以及 `open → processing/resolved/rejected → closed` 生命周期。
- 活动 blocker 禁止完成对应节点；任何未关闭卡点禁止提交任务验收。
- 后端在业务 Service 中继续校验身份、权限、状态和 `task_version`；前端按钮不是权限边界。

React 前端：

- 原型登录页、Dashboard 首页、任务列表、Inbox、新建任务和任务详情。
- 创建任务节点及依赖关系，执行当前后端已支持的任务和节点动作。
- 任务详情中的进度汇报、汇报历史、更正入口、卡点创建和卡点处理。
- Inbox 待汇报入口，以及 Dashboard 待汇报和待处理卡点指标。
- Inbox 待我验收动作，以及任务详情中的完成提交、通过、驳回、节点重开和验收历史面板。
- 桌面端和移动端响应式导航与布局。

## 技术栈

- Python 3.12（`>=3.12,<3.13`）
- FastAPI、Pydantic 2
- SQLAlchemy 2.x 同步 Engine/Session
- PostgreSQL 16、`psycopg[binary]`
- Alembic
- Pytest、Ruff
- React 19、TypeScript、Vite、TanStack Query
- Vitest、Testing Library、ESLint
- Docker Compose

## 数据库与迁移

当前 SQLAlchemy Metadata 精确包含13张业务表：

```text
users
departments
task_inputs
ai_extraction_records
tasks
task_participants
task_nodes
task_node_participants
task_node_dependencies
task_status_logs
task_progress_reports
task_issues
task_completion_reviews
```

当前有三份不可重写的迁移，Alembic head 为 `c31f8e7a4d02`：

```text
alembic/versions/17f69ea12754_initial_schema.py
alembic/versions/576787492bd1_add_progress_reports_and_task_issues.py
alembic/versions/c31f8e7a4d02_add_task_completion_reviews.py
```

不要手工创建或修改业务表，应通过 Alembic 管理结构变更。Docker Compose 中的 PostgreSQL 数据通过 `./data/postgres:/var/lib/postgresql/data` 绑定到项目目录，不使用默认命名卷。

Wave 1 downgrade 只允许在 `task_completion_reviews` 为空时执行；一旦存在验收历史，迁移会主动中止，避免静默删除不可变业务记录。需要回退有数据的环境时，必须先制定并验证独立的数据保全与恢复迁移。

## 核心流程

```text
创建任务草稿
→ 提交创建人确认
→ 确认并发送
→ 主承办人接受或退回
→ 节点开始、更新进度和完成
→ 进度汇报、卡点上报与闭环处理
→ 主承办人提交完成，生成新的不可变验收轮次
→ 本轮 reviewer 快照验收
   ├─ 通过：pending_review → completed
   └─ 驳回并填写原因：pending_review → in_progress
      ├─ 仅返工整体交付物，保留全部已完成节点
      └─ 指定节点后执行显式重开，保留原完成历史
→ 返工完成后重新提交，生成下一验收轮次
```

每个状态动作都由 Service 校验权限、当前状态和 `task_version`，并在一个数据库事务中更新数据和写入状态日志。只有主承办人可以提交完成；每轮验收人快照取任务指定 reviewer，未指定时才回退创建人，创建人、高管或管理员等身份本身不会自动获得验收权限。

## 环境配置

项目只正式支持 Python 3.12。`.env.example` 和 `web/.env.example` 只是开发占位模板，不能直接当作安全配置使用。

后端运行必须提供 `DATABASE_URL`。生产企业微信身份使用 `AUTH_MODE=wecom`；隔离开发仍可使用受控 prototype。企业微信生产配置至少包括：

```text
AUTH_MODE=wecom
WECOM_CORP_ID=<enterprise-corp-id>
WECOM_APP_SECRET=<self-built-app-secret>
JWT_SECRET_KEY=<locally-generated-secret-of-at-least-32-characters>
CHAT_SERVICE_JWT_SECRET_KEY=<separate-secret-of-at-least-32-characters>
ALLOW_TEST_EMPLOYEE_HEADER=false
CORS_ALLOWED_ORIGINS=<frontend-origin>
```

隔离开发如需 prototype，可继续使用 `PROTOTYPE_AUTH_ENABLED` 与 `PROTOTYPE_USER_EMPLOYEE_NOS`；生产禁止 prototype/test-header。

Docker Compose 启动 PostgreSQL 时还需要在本地环境提供 `POSTGRES_DB`、`POSTGRES_USER` 和 `POSTGRES_PASSWORD`。不要把真实数据库密码、JWT 密钥、API Key、Token 或完整数据库连接 URL 写入代码、README 或 Git。`.env`、`.venv/`、`data/` 和前端本地环境文件均已被 Git 忽略。

## 启动后端

在项目根目录执行以下 Windows PowerShell 命令：

```powershell
py -3.12 -m venv .venv
& ".\.venv\Scripts\python.exe" -m pip install -e ".[dev]"

# 首次复制安全配置模板，并仅在本机填写真实值
Copy-Item config-examples/backend.env.example secrets/backend.env

# Docker Compose 显式读取 backend.env；FastAPI/Alembic 默认读取同一文件
docker compose --env-file secrets/backend.env up -d postgres
$env:WANGXU_BACKEND_ENV_FILE = (Resolve-Path secrets/backend.env)
& ".\.venv\Scripts\python.exe" -m alembic upgrade head
& ".\.venv\Scripts\python.exe" -m uvicorn app.main:app --reload
```

使用通用 shell 时，可先激活项目内虚拟环境，再运行等价的 `python -m pip`、`python -m alembic` 和 `python -m uvicorn` 命令。

Uvicorn 未指定其他监听参数时，默认地址为 `http://127.0.0.1:8000`：

- 存活检查：`GET /health/live`
- 数据库就绪检查：`GET /health/ready`
- Swagger UI：`GET /docs`
- OpenAPI JSON：`GET /openapi.json`

## 身份边界

生产身份入口为企业微信小程序：`wx.qy.login()` 获取一次性 code，FastAPI 调用企业微信 `jscode2session` 得到 `userid/corpid`，再以 `users.wecom_user_id` 映射现有 `employee_no`。企业微信只证明身份，不改变旺序角色、授权范围或任务关系。成功后仍使用现有 HTTP Bearer JWT：

```http
Authorization: Bearer <token>
```

`X-Employee-No` 只保留给既有自动化测试。当前会话继续使用持久化哈希 refresh token、轮换刷新、撤销/登出，以及服务端角色与 `user_authorized_scopes` 权限投影。企业微信登录不会自动创建用户，也不会从企业微信部门负责人/管理员身份推导旺序 `role_type`。

不要在生产环境使用示例密钥或员工编号 Header。JWT 密钥必须由运行环境安全提供，不得提交 Git。

## 启动前端

前端位于 `web/`。`web/package.json` 当前提供 `dev`、`lint`、`test` 和 `build` 脚本：

```powershell
Set-Location web
npm.cmd ci

# 可通过未提交的 web/.env.local 设置 VITE_API_BASE_URL
npm.cmd run dev
npm.cmd run lint
npm.cmd run test -- --run
npm.cmd run build
```

`VITE_API_BASE_URL` 指向后端 API 根地址；未设置时，前端客户端默认使用 `http://localhost:8000`。如果 Windows PowerShell 执行策略阻止 `npm.ps1`，可直接使用 `npm.cmd`，不需要关闭系统安全策略。

### 微信小程序 API 联调

`wechat-miniprogram/config.js` 默认保持 `mode: "mock"`；切到真实 API 时配置 `mode: "api"`、`apiBaseUrl`，生产 `authMode` 使用 `wecom`。客户端先尝试现有 refresh token，无可用会话时调用 `wx.qy.login()`，再把 code 发送到 `/api/v1/auth/wecom`。小程序不保存企业微信 Secret/access_token。受控 `prototype` 仅保留给隔离开发，不进入生产。

## 原型登录使用流程

1. 准备并启动隔离的 PostgreSQL。
2. 通过 Alembic 将数据库迁移到当前 head。
3. 按下一节的安全要求检查并准备演示用户。
4. 配置原型身份环境变量并启动后端。
5. 配置 `VITE_API_BASE_URL` 并启动前端。
6. 在浏览器中打开 Vite 输出的本地开发地址。
7. 在登录页选择或输入允许的原型用户。
8. 前端通过原型登录获得 Bearer 身份。
9. 进入 Dashboard、任务列表、Inbox，并完成任务核心流程。

## Demo Seed安全说明

`scripts/seed_demo_data.py` 是显式启用、幂等的隔离演示数据工具。它只接受名称以 `_test` 或 `_demo` 结尾的数据库，并要求命令行确认值与当前配置中的数据库名完全一致。

先使用 dry-run 检查动作并回滚：

```powershell
& ".\.venv\Scripts\python.exe" -m scripts.seed_demo_data `
  --dry-run `
  --confirm-database-name "<isolated_test_or_demo_database_name>"
```

只有在再次核对目标后，才可以由用户明确选择持久化模式：

```powershell
& ".\.venv\Scripts\python.exe" -m scripts.seed_demo_data `
  --apply `
  --confirm-database-name "<isolated_test_or_demo_database_name>"
```

`--dry-run` 会回滚，不持久化数据；`--apply` 遇到已存在的演示员工编号时会跳过，不覆盖用户。禁止对未知、共享、开发或生产数据库运行该脚本，也不要打印或提交数据库凭据。本项目不会自动执行持久化 seed。

## 测试

默认后端质量门不连接 PostgreSQL；数据库集成测试会安全跳过：

```powershell
& ".\.venv\Scripts\python.exe" -m ruff check .
& ".\.venv\Scripts\python.exe" -m pytest
& ".\.venv\Scripts\python.exe" -m pip check
```

PostgreSQL Repository、Service 和 HTTP 集成测试只有在显式提供已批准的隔离测试数据库配置和运行开关时才会执行：

```powershell
$env:RUN_POSTGRESQL_INTEGRATION = "1"
$env:POSTGRES_TEST_DATABASE_URL = "<approved-isolated-postgresql-test-url>"
& ".\.venv\Scripts\python.exe" -m pytest tests/integration
```

前端质量门：

```powershell
Set-Location web
npm.cmd run lint
npm.cmd run test -- --run
npm.cmd run build
```

历史 Wave 1 checkpoint 当时的质量门为：后端全量 `306 passed`，其中真实 PostgreSQL 16 集成测试 `20 passed`；前端 `10 test files / 28 tests passed`。Ruff、`pip check`、`pip-audit`、SQLAlchemy mapper、Alembic check 与 downgrade/upgrade、ESLint、TypeScript（随构建执行）和 Vite build 均已通过。OpenAPI 当前包含 `35` 条 API 路径、`38` 个 operations；测试后 PostgreSQL 业务数据残留为零。当前迁移 head 为 `c31f8e7a4d02`，Metadata 为13张业务表。

上述 Wave 1 门禁只证明完成验收与返工核心闭环。完成提醒与外部通知仍延期至 Wave 6，完成对绩效关联的影响延期至 Wave 4，负荷/看板统计重算延期至 Wave 5，完成后归档快照、检索与复用延期至 Wave 7。

## Git checkpoint状态

- Phase 0～5 基线：
  - commit：`9a228cdd624339b964d21cff92e3f2533efd8275`
  - tag：`phase-5-rest-api-baseline`
- Batch 1 稳定基线：
  - commit：`637106a172d5c10d54461b2a1f910fb5fee9d0df`
  - tag：`batch-1-task-board-baseline`
- Batch 2A 本地基线：
  - commit：`94108af17225ca9e4a2f728e47a117f1d546a0af`
  - push：待 GitHub 网络恢复
- Batch 2B 本地 checkpoint：
  - commit：`7a0cf4e3c6b920d5fea10c351d4d7789f39baf90`
- Wave 1 checkpoint 候选：
  - 完成验收与返工实现及总质量门已通过
  - commit hash：尚未创建；本文档随候选提交
- 远程仓库：`https://github.com/Z-pw-36/smart-task-board.git`
- 两个稳定基线标签均已上传至 GitHub 私有仓库且不得移动；本地 `main` 当前领先 `origin/main`。

## 后续计划

Batch 1、Batch 2A、Batch 2B 和 Wave 1 功能与验收均已完成。下一步是在安全复核后创建 Wave 1 本地 checkpoint，再进入 Wave 2：不可变任务变更申请，以及取消、撤回、合并、关闭和允许场景下的恢复。不会在 Wave 1 checkpoint 中虚报 Wave 4～7 的完成下游能力。

## 历史 Wave 1 未实现清单（已过时）

以下条目只保留为早期开发记录；Feature 13～16 与企业微信认证等后续实现已覆盖其中多项，不得作为当前能力判断依据。


- 正式生产登录认证、企业统一身份或企业微信认证。
- 完整 JWT 刷新、撤销和登出机制，以及正式 RBAC 和组织范围权限。
- 任务变更申请，以及取消、撤回、合并、关闭和允许场景下的恢复。
- AI 结构化提取、真实 AI/LLM、多轮对话、语音上传和 ASR。
- 企业微信机器人、通知和 Outbox。
- 附件及交付物文件管理。
- 负荷分析、冲突分析、优先级分析和绩效关联。
- 完成提醒、完成后的绩效关联影响、负荷/看板统计重算、归档检索与复用，以及其他后续 Wave 功能。

## 有效需求文档

项目仅以 `docs/` 中以下两份文档为当前有效需求，不得修改或删除：

- `第二版-智能任务看板核心逻辑与用户使用流程节点(1).docx`
- `第四版-智能任务看板数据表结构文档-显式ID版(1).docx`

## Feature 05 cloud-function AI intake

The runtime source now contains only `cloud-functions/ChatService`; the historical SMS `LoginService` has been removed. The Mini Program authenticates through WeCom/FastAPI and obtains a short-lived `task-intake` token from `/api/v1/auth/ai-token` before calling ChatService. See `cloud-functions/README.md` and `docs/WECOM_IDENTITY_ORG_MAPPING.md`.

## Feature 13 notification and node-assignment delivery

Feature 13 is implemented against the user-confirmed rules in `docs/FEATURE_13_NOTIFICATION_RULES.md`. Collaborator-owned AI nodes require server-persisted acceptance before execution/reminder responsibility starts; dynamic node due-soon timing uses working-span bands and never estimated hours. Notification projection is recipient-scoped and action-aware, delivery retry uses the same outbox record, and production Mini Program UI uses action-required rather than read/unread as the business badge. See `docs/FEATURE_13_ACCEPTANCE.md` for the exact migration, API, tests, environment limitations, and scope boundary.

## Feature 14 executive dashboard implementation

Feature 14 is implemented against `docs/FEATURE_14_EXECUTIVE_DASHBOARD_RULES.md`: explicit authorized department scopes, week/month aggregation, four team metrics, persisted-priority quadrants, workload heatmap, and snapshot pressure breakdown. KPI dashboard aggregation uses user-confirmed relations only (`is_confirmed=true`), does not define core KPI, excludes inactive metrics from the current dashboard, and includes `pending_review` in overall progress only.

## Feature 15 executive employee task filtering

Feature 15 follows the user-confirmed P0 scope in `docs/FEATURE_15_EXECUTIVE_EMPLOYEE_TASK_FILTER_RULES.md`. The workload breakdown sheet now has a real “查看该员工任务” action that reuses the existing task overview. The task overview displays an employee-name filter but sends only `employeeNo` to the backend, combines it with status/quadrant/date filters, revalidates explicit executive department scope, and opens the existing task detail page. The old standalone `pages/workload-tasks` fake page was removed from production registration. Feature 15 adds no business table, field, or Alembic migration.

The same change also fixes the real `TaskBoardQueryService.available_actions()` undefined-`priority` 500 defect and adds direct service regression coverage. Current executable gates after Feature 15: backend non-PostgreSQL `460 passed, 28 deselected`; WeChat feature01-15 `19` groups PASS; JS syntax and Python compileall PASS. Real PostgreSQL, React dependency gates, Ruff, and WeChat Developer Tools are unavailable in this container and are not claimed as passed. See `docs/FEATURE_14_ACCEPTANCE.md`.

## Feature16 / DEV-18 Test10 release candidate

Test10 only closes Test9 release-gate debt; it does not add a product feature. The main code change makes task status-log timelines deterministic by ordering first on `task_version`, so same-timestamp `completion_approved` / `task_archived` records cannot be reversed by random UUID order. It also makes `@testing-library/dom` an explicit Web dev dependency and refreshes import ordering for the remaining Ruff I001 debt.

Automated PostgreSQL validation is now repeatable through `scripts/run_postgresql_gate.sh`; the general gate defaults to two same-database passes and the Test10 candidate gate requests three passes. See `FEATURE_16_TEST10_RELEASE_CANDIDATE_REPORT.md` for executed evidence and remaining environment gates.


## Feature16 / DEV-18 Test11 final technical gate

Test11 does not add product behavior or schema changes. It closes the six remaining Ruff findings from the user's Test10 run, keeps the Test10 task-status-log ordering fix frozen, and separates technical release readiness from real WeCom production E2E.

Current source facts: Alembic has `10` migration files with single head `c2d3e4f5a6b7`; the user's Test10 runtime inspection reported `100` OpenAPI paths / `106` operations. Test10 local evidence reached backend non-PostgreSQL `504/504`, PostgreSQL `28/28` for one real pass, Web `109/109`, and Mini Program `21/21`; Test11 requires three consecutive same-database PostgreSQL passes plus the existing `5 x 20 = 100` concurrency stress runs before technical release readiness.

Run `scripts/run_test11_release_gate.sh` in the declared Python 3.12 environment. A passing technical gate does not claim real WeCom production E2E; that remains a separate environment gate using `scripts/run_wecom_real_e2e.py` with real credentials, HTTPS deployment, mapped employee identity, and a fresh `wx.qy.login` code.

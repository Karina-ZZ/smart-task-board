# Smart Task Board

智能任务看板使用 FastAPI、PostgreSQL 和 React 实现任务创建、结构化拆解、参与人协作、状态流转、节点执行、完成验收与返工。后端业务规则通过 JSON REST API 提供，前端提供适配桌面和移动设备的任务看板界面。

> 版本历史与各功能变更明细见 [CHANGELOG.md](CHANGELOG.md)。当前版本：**功能 13（通知、提醒与协办节点承接）**。

## 功能开发进度

> **进度计划来源**：项目当前 16 项功能计划源自 `docs/reference/` 中第二版核心逻辑与数据表结构文档的对应交付清单（功能 05、12、14 为高亮的当前重点）。

**总体状态：功能 01 ～ 13 已全部完成并通过验收；功能 14、15、16 未开始。**

### 功能清单（依据用户规划第二版交付线）

| # | 功能 | 范围要点 | 当前状态 |
|---|---|---|---|
| 01 | 员工任务工作台 | 小程序工程基础、第二版应用壳、底部导航、任务指标、四象限、需要支持、AI 创建入口、最近任务 | ✅ 完成 |
| 02 | 任务概览 | 任务/节点模式、状态筛选、四象限筛选、临期筛选、自定义日期、空态、任务跳转 | ✅ 完成 |
| 03 | 任务详情 | 基础信息、责任关系、任务目标、验收标准、节点、汇报、卡点、绩效、状态轨迹、操作记录 | ✅ 完成 |
| 04 | 登录与权限 | 当前用户、任务关系、员工/高管权限、数据范围、无权访问、Token 与刷新 | ✅ 完成 |
| 05 | AI 任务输入 ⚠️ | 文字输入、录音、语音转文字、AI 字段识别、缺失字段追问、失败重试；任务创建人关联绩效指标 | ✅ 完成 |
| 06 | 创建人三步创建 | 描述任务 → 信息确认 → 确认发送；发送后进入待接受、不生成节点 | ✅ 完成 |
| 07 | 接受后 AI 拆解 | 接受/退回、拆解中、拆解失败、重新拆解、成功生效、迟到结果失效 | ✅ 完成 |
| 08 | 节点执行 | 节点展开、依赖校验、开始、更新、完成、节点负责人和协同人权限 | ✅ 完成 |
| 09 | 进度与卡点 | 当前进度、阶段成果、卡点开关、卡点说明、备注、问题处理和关闭 | ✅ 完成 |
| 10 | 任务生命周期 | 变更申请、更换承办人、撤回、取消、合并、关闭、原因弹窗和通知 | ✅ 完成 |
| 11 | 完成申请与验收 | 全部节点完成校验、多轮验收、退回修改、指定节点重开、通过后自动归档 | ✅ 完成 |
| 12 | 智能计算 ⚠️ | 绩效关联、四象限、剩余工时、负荷、冲突和服务端计算口径 | ✅ 完成 |
| 13 | 通知与我的 | 任务通知、提醒、系统消息、个人资料、任务关系统计和待办数量 | ✅ 完成 |
| 14 | 高管任务看板 ⚠️ | 团队指标、状态分布、风险、负荷热力图、卡点和绩效态势 | ⬜ 未开始 |
| 15 | 员工负荷任务下钻 | 负荷构成 → 员工任务明细 → 单任务详情，落实第二处修改 | ⬜ 未开始 |
| 16 | 全链路发布验收 | 主链路、异常链路、权限、安全、幂等、事务、性能和微信开发者工具验收 | ⬜ 未开始 |

**后端覆盖矩阵**：功能 01～13 对应的后端 Wave 1～10 在 `FEATURE_COVERAGE.md` 中全部标注 COMPLETE：完成验收与返工、任务变更与生命周期、组织档案与授权、绩效与 KPI 匹配、负荷/优先级/冲突、提醒与通知、归档与审计、AI 拆解、`/api/v1` 契约收敛、生产加固。Alembic 单一 head 为 `b1c2d3e4f5a6`，OpenAPI 共 78 条路径 / 84 个 operations。

**当前未开工的三项功能**：功能 14 / 15 / 16 是规划中已确定范围、尚未立项开发的功能。提交新功能前须执行功能 01 ～ 当前功能的全量回归（见 `docs/ACCEPTANCE_STANDARDS.md`），未开工功能不得虚报为已完成。

### 测试进度

> **以下为本机独立复核的实测结果**（复核日期 2026-09-03）：在 macOS 上用受管 Python 3.13 虚拟环境安装依赖后真实执行，非抄录交付包文档。注意项目声明 `requires-python = ">=3.12,<3.13"`，本次复核以 3.13.12 加装 `--ignore-requires-python` 执行，与官方 3.12 口径存在版本差异。

| 质量门 | 实测结果 | 说明 |
|---|---|---|
| 后端全量 pytest | ✅ `436 passed, 28 skipped` | 2.09s；28 项 skipped 均为 PostgreSQL opt-in 集成测试（文档记录为 21 skipped，实测为 28） |
| PostgreSQL 集成测试 | ⚠️ 未执行 | 需 `RUN_POSTGRESQL_INTEGRATION=1` + 隔离 PG 测试库，本次未提供，**不宣称通过** |
| Python `compileall` | ✅ PASS | `app` 包全量编译通过 |
| `ruff check` | ❌ **201 个错误** | 详见下方「静态检查发现的问题」 |
| 微信小程序功能 01～13 | ✅ `16 / 16` 组 PASS | `wechat-miniprogram/` 与 `wechat-miniprogram-standalone/` 均跑通 |
| 微信全部 JS 语法检查 | ✅ PASS | 全量 `.js` 执行 `node --check` |
| React 前端 ESLint | ✅ PASS | 无错误输出 |
| React 前端测试 | ✅ `18 test files / 109 tests passed` | vitest `--run`，3.46s |
| React 前端构建 | ✅ PASS | `tsc --noEmit && vite build`，546ms |
| 功能 14 / 15 / 16 测试 | ⬜ 未开始 | 功能尚未立项开发，无对应测试任务 |

> 交付包文档 `docs/FEATURE_13_ACCEPTANCE.md` 记录的原始口径为：后端 `436 passed`（文档中 skipped 记为 21）、迁移合同 `32 passed`、微信 `16` 组 PASS；并声明 React 未执行、Ruff 未执行。本次复核补齐了 React 与 Ruff 两项，并修正了 skipped 计数。

### 静态检查发现的问题

`ruff check .` 共 201 个错误，按类型分布：

| 类型 | 数量 | 性质 |
|---|---|---|
| E501 行超长 | 137 | 代码风格 |
| I001 import 未排序 | 31 | 代码风格 |
| **F821 未定义名称** | **11** | **⚠️ 真实缺陷** |
| F401 未使用 import | 10 | 代码风格 |
| E701 / E702 单行多语句 | 6 | 代码风格 |
| F841 未使用变量 | 3 | 代码风格 |
| B033 重复值 / UP035 弃用 import | 3 | 代码风格 |

**F821 全部集中在同一处真实缺陷**：`app/services/task_board_query.py` 第 670 ～ 674 行的 `available_actions()` 方法引用了未定义的变量 `priority`。已通过 AST 静态分析和运行时复现双重确认——调用该方法会直接抛出 `NameError: name 'priority' is not defined`。

- **影响面**：该方法是 `GET /api/v1/tasks/{task_id}/available-actions` 接口的后端实现，真实调用将返回 HTTP 500。
- **未被引爆的原因**：唯一覆盖真实实现的测试 `tests/integration/test_progress_issues_postgresql.py` 属于 PostgreSQL opt-in 测试（默认 skipped）；而 `tests/api/test_task_board_routes.py` 用 mock 替换了 service 返回值，绕过了真实代码路径。因此 436 个通过的测试全部未触及该缺陷。
- **修复方向**：同文件 `_summary()` 方法中已有正确写法 `priority = self._latest_priority(task.task_id)`，`available_actions()` 中缺少这一行赋值。

> 该缺陷属功能 12（智能计算）遗留，尚未修复——修复需按 `docs/ACCEPTANCE_STANDARDS.md` 执行全量回归后提交。

## 微信小程序累计交付状态

当前用户侧累计交付线位于 `wechat-miniprogram/`，功能 01～13 已按第二版前端页面结构和 PRD V1.1 逐项实现并开放验收：工作台、任务概览、任务详情、登录与权限、云函数 AI 配置、创建人三步创建、AI 输入与追问、AI 拆解、节点执行、进度汇报与问题闭环、任务变更与生命周期、绩效优先级负荷冲突口径、通知与节点承接。功能 04 不新增第二版原型之外的登录业务页，而是在小程序启动和 API 网关层接入服务端会话，避免破坏既有页面结构。

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

当前 SQLAlchemy Metadata 覆盖 27 张业务表（含身份、组织授权、任务全生命周期、绩效、负荷、优先级、冲突、提醒、通知、归档与审计等，完整清单见 `FEATURE_COVERAGE.md` 核心业务表覆盖矩阵）。

当前有九份不可重写的迁移，Alembic 单一 head 为 `b1c2d3e4f5a6`：

```text
alembic/versions/17f69ea12754_initial_schema.py
alembic/versions/576787492bd1_add_progress_reports_and_task_issues.py
alembic/versions/c31f8e7a4d02_add_task_completion_reviews.py
alembic/versions/d4a8e53b7c19_add_task_change_requests.py
alembic/versions/e6f1a2b3c4d5_add_remaining_business_tables.py
alembic/versions/f7b8c9d0e1f2_add_auth_refresh_tokens.py
alembic/versions/f8a1b2c3d4e5_add_task_decomposition_lifecycle.py
alembic/versions/f9a1b2c3d4e5_feature11_archive_snapshot_nullable.py
alembic/versions/fa1b2c3d4e5_feature13_node_assignment_and_reminders.py
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

后端运行必须提供 `DATABASE_URL`。使用原型身份时还需要配置：

```text
AUTH_MODE=prototype
PROTOTYPE_AUTH_ENABLED=true
PROTOTYPE_USER_EMPLOYEE_NOS=<comma-separated-demo-employee-numbers>
JWT_SECRET_KEY=<locally-generated-secret-of-at-least-32-characters>
ALLOW_TEST_EMPLOYEE_HEADER=false
CORS_ALLOWED_ORIGINS=<frontend-origin>
```

Docker Compose 启动 PostgreSQL 时还需要在本地环境提供 `POSTGRES_DB`、`POSTGRES_USER` 和 `POSTGRES_PASSWORD`。不要把真实数据库密码、JWT 密钥、API Key、Token 或完整数据库连接 URL 写入代码、README 或 Git。`.env`、`.venv/`、`data/` 和前端本地环境文件均已被 Git 忽略。

## 启动后端

在项目根目录执行以下 Windows PowerShell 命令：

```powershell
py -3.12 -m venv .venv
& ".\.venv\Scripts\python.exe" -m pip install -e ".[dev]"

# 先在当前进程或未提交的本地 .env 中安全提供所需环境变量
docker compose up -d postgres
& ".\.venv\Scripts\python.exe" -m alembic upgrade head
& ".\.venv\Scripts\python.exe" -m uvicorn app.main:app --reload
```

使用通用 shell 时，可先激活项目内虚拟环境，再运行等价的 `python -m pip`、`python -m alembic` 和 `python -m uvicorn` 命令。

Uvicorn 未指定其他监听参数时，默认地址为 `http://127.0.0.1:8000`：

- 存活检查：`GET /health/live`
- 数据库就绪检查：`GET /health/ready`
- Swagger UI：`GET /docs`
- OpenAPI JSON：`GET /openapi.json`

## 原型身份边界

当前正常原型运行使用 HTTP Bearer JWT。客户端通过原型登录接口获得短期 Token，受保护接口使用：

```http
Authorization: Bearer <token>
```

`X-Employee-No` 只保留给既有测试兼容模式或明确隔离的测试场景，不能替代正式认证。当前会话已经支持持久化哈希 refresh token、轮换刷新、撤销/登出，以及服务端角色与 `user_authorized_scopes` 权限投影；受控 `prototype` 登录仍只用于隔离开发/验收，不能替代企业统一身份或企业微信真实凭证交换。

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

`wechat-miniprogram/config.js` 默认保持 `mode: "mock"`。隔离开发环境联调真实 API 时，可本地改为 `mode: "api"` 并配置 `apiBaseUrl`。只有后端明确启用受控 `prototype` 认证时，才配置 `authMode: "prototype"` 和允许名单中的 `prototypeEmployeeNo`；代码仓库不得写入真实 Token、Secret 或企业微信凭证。客户端会自动保存 access/refresh token，并在受保护请求返回 401 时旋转 refresh token 后重试一次。生产部署应由经过验证的企业微信/统一身份登录流程取得会话并交给同一 API 网关，不允许使用员工号选择器冒充正式登录。

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

最新质量门状态（功能 13 冻结 ZIP 反向验收）见上方「测试进度」表；历史 Wave 1 门禁（后端 `306 passed`、PostgreSQL 集成 `20 passed`、前端 `10 test files / 28 tests passed`、Ruff / pip-audit / ESLint / Vite build 全通过）在当时的 OpenAPI 为 `35` 路径 / `38` operations，现已收敛至 `78` 路径 / `84` operations。

## Git 仓库状态

- 远程仓库：`https://github.com/Karina-ZZ/smart-task-board`（公开，`main` 分支）
- 累计提交线：功能 12 全量源码首次入库 → 文档整理与验收标准 → 功能 13 交付（当前 head）
- 变更明细见 [CHANGELOG.md](CHANGELOG.md)；单功能验收标准见 [docs/ACCEPTANCE_STANDARDS.md](docs/ACCEPTANCE_STANDARDS.md)
- 微信小程序独立交付版位于 `wechat-miniprogram-standalone/`，与 `wechat-miniprogram/` 内容同源

## 后续计划

下一步按用户第二版交付计划继续开发尚未立项的三项功能：

- **功能 14** 高管任务看板：团队指标、状态分布、风险、负荷热力图、卡点和绩效态势
- **功能 15** 员工负荷任务下钻：负荷构成 → 员工任务明细 → 单任务详情，落实第二处修改
- **功能 16** 全链路发布验收：主链路、异常链路、权限、安全、幂等、事务、性能和微信开发者工具验收

提交新功能前须执行功能 01 ～ 当前功能的全量回归（见 `docs/ACCEPTANCE_STANDARDS.md`）。未开工功能不得虚报为已完成。

## 当前未实现 / 环境边界

- 功能 14 高管任务看板、功能 15 员工负荷任务下钻、功能 16 全链路发布验收（按用户规划第二版尚未开发）。
- 正式生产登录认证、企业统一身份或企业微信真实凭证换票（当前为受控原型认证）。
- 功能 13 明确不提前实现：待承接再次催办间隔（未经用户确认）、协办拒绝后的完整重新分配 UI、任务级逾期升级通知创建人、用户未确认的节点逾期固定钟点。
- 企业微信 provider 当前使用确定性 fake provider，生产启用需真实凭证。
- React 前端 lint/test/build 与 PostgreSQL opt-in 集成测试需在具备相应环境时执行，当前环境未宣称通过。

## 有效需求文档

项目仅以 `docs/` 中以下两份文档为当前有效需求，不得修改或删除：

- `docs/第二版-智能任务看板核心逻辑与用户使用流程节点.docx`
- `docs/第四版-智能任务看板数据表结构文档-显式ID版.docx`

其他过程与参考文档见 `docs/`（验收记录、通知规则、开发计划、基线报告）与 `docs/reference/`（PRD V1.1、前端原型、交接文档）。

## Feature 05 cloud-function AI intake

The cumulative source now includes `cloud-functions/LoginService` and `cloud-functions/ChatService` as independently deployable Flask functions. The Mini Program reads only `loginServiceBaseUrl` and `chatServiceBaseUrl` from `wechat-miniprogram/config.js`; Qwen/API/MySQL/JWT secrets stay in cloud-function environment variables. See `cloud-functions/README.md` and `cloud-functions/mysql/schema.sql`.

## Feature 13 notification and node-assignment delivery

Feature 13 is implemented against the user-confirmed rules in `docs/FEATURE_13_NOTIFICATION_RULES.md`. Collaborator-owned AI nodes require server-persisted acceptance before execution/reminder responsibility starts; dynamic node due-soon timing uses working-span bands and never estimated hours. Notification projection is recipient-scoped and action-aware, delivery retry uses the same outbox record, and production Mini Program UI uses action-required rather than read/unread as the business badge. See `docs/FEATURE_13_ACCEPTANCE.md` for the exact migration, API, tests, environment limitations, and scope boundary.

### 协作者快速上手

第一次拿到本仓库、想在自己电脑上跑通并验证功能 13，请看 **[docs/LOCAL_TEST_GUIDE_FEATURE_13.md](docs/LOCAL_TEST_GUIDE_FEATURE_13.md)**（含完整命令、8 个验证项、已知问题，以及一段可直接交给 AI 助手执行的一键提示词）。

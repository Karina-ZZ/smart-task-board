# Smart Task Board 智能任务看板

智能任务看板（Smart Task Board）：基于 FastAPI + PostgreSQL + React + 微信小程序的任务全生命周期管理系统，覆盖任务创建、结构化拆解、参与人协作、状态流转、节点执行、进度汇报、卡点闭环、完成验收与返工等核心流程。

## 仓库结构

```text
.
├── app/                          # Python FastAPI 后端（领域模型、Service、REST API）
├── alembic/                      # 数据库迁移（head: c31f8e7a4d02）
├── tests/                        # 后端单元测试与 PostgreSQL 集成测试
├── web/                          # React 19 + TypeScript + Vite 前端
├── wechat-miniprogram/           # 微信小程序（累计交付主线版本）
├── wechat-miniprogram-standalone/ # 微信小程序独立版（Feature 01~12 验收文档齐全）
├── cloud-functions/              # 阿里云函数计算：LoginService / ChatService（Qwen AI 对话）
├── scripts/                      # 开发与演示数据脚本
├── docs/                         # 有效需求文档（第二版核心逻辑 + 第四版数据表结构）
├── docker-compose.yml            # 本地 PostgreSQL
└── pyproject.toml                # Python 3.12 项目与依赖定义
```

## 核心能力

### 后端（FastAPI + SQLAlchemy + PostgreSQL 16）

- 原型用户列表、原型登录、短期 Bearer JWT 与 `GET /api/v1/me`。
- 任务全流程状态机：创建草稿 → 创建人确认 → 确认发送 → 承办人接受/退回 → 节点执行 → 完成提交 → 验收。
- 不可变多轮验收：每轮 reviewer 快照授权、通过、填写原因驳回、整体交付物返工、指定节点显式重开。
- 任务级/节点级进度汇报与追加式更正、周期待汇报查询。
- 卡点生命周期 `open → processing/resolved/rejected → closed`；活动卡点禁止完成节点与提交验收。
- 统一 Inbox、Dashboard 摘要、后端计算的 `allowed_actions` 授权动作投影。
- 13 张业务表、3 份不可重写迁移；所有状态动作在单事务中校验权限、状态与 `task_version` 并写入状态日志。

### Web 前端（React 19 + TanStack Query）

- 登录页、Dashboard、任务列表、Inbox、新建任务、任务详情。
- 进度汇报、汇报历史、卡点创建与处理、验收面板（通过/驳回/节点重开）。
- 桌面端与移动端响应式布局。

### 微信小程序

- 累计交付线 `wechat-miniprogram/`：工作台、任务概览、任务详情、登录与权限（功能 01~04）。
- 独立版 `wechat-miniprogram-standalone/`：功能 01~12 全量交付，含各 Feature 验收文档。
- 会话管理：access/refresh token 保存与旋转、401 自动恢复、登出撤销。
- AI 对话：通过 `cloud-functions/ChatService` 接入 Qwen（密钥仅存于云函数环境变量）。

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.12、FastAPI、Pydantic 2、SQLAlchemy 2.x（同步）、Alembic |
| 数据库 | PostgreSQL 16、psycopg[binary] |
| 质量门 | Pytest、Ruff、pip check、pip-audit |
| Web 前端 | React 19、TypeScript、Vite、TanStack Query、Vitest、ESLint |
| 小程序 | 微信小程序原生框架 |
| 云函数 | Flask（阿里云 FC：LoginService / ChatService）、MySQL |
| 部署 | Docker Compose |

## 快速开始

### 1. 启动后端

```bash
python3.12 -m venv .venv
. .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# 准备环境变量（见下节），然后：
docker compose up -d postgres
alembic upgrade head
uvicorn app.main:app --reload
```

服务默认运行在 `http://127.0.0.1:8000`：

- 存活检查：`GET /health/live`
- 数据库就绪：`GET /health/ready`
- API 文档：`GET /docs`

### 2. 启动前端

```bash
cd web
npm ci
npm run dev        # lint / test / build 同样可用
```

`VITE_API_BASE_URL` 指向后端 API 根地址，未设置时默认 `http://localhost:8000`。

### 3. 环境变量

后端必须提供 `DATABASE_URL`。原型身份还需要：

```text
AUTH_MODE=prototype
PROTOTYPE_AUTH_ENABLED=true
PROTOTYPE_USER_EMPLOYEE_NOS=<演示员工编号列表>
JWT_SECRET_KEY=<至少32位随机密钥>
ALLOW_TEST_EMPLOYEE_HEADER=false
CORS_ALLOWED_ORIGINS=<前端来源>
```

Docker Compose 启动 PostgreSQL 需提供 `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD`。**不要**将真实密码、JWT 密钥、API Key 或数据库连接串写入代码或 Git；`.env`、`.venv/`、`data/` 已被 Git 忽略。

### 4. 微信小程序 API 联调

`wechat-miniprogram/config.js` 默认 `mode: "mock"`。联调真实 API 时本地改为 `mode: "api"` 并配置 `apiBaseUrl`；只有后端启用受控 `prototype` 认证时才配置 `authMode: "prototype"` 与允许名单中的 `prototypeEmployeeNo`。

## 测试

```bash
# 后端（默认不连接 PostgreSQL，集成测试安全跳过）
ruff check .
pytest
pip check

# PostgreSQL 集成测试（显式启用）
RUN_POSTGRESQL_INTEGRATION=1 POSTGRES_TEST_DATABASE_URL=<隔离测试库> pytest tests/integration

# 前端
cd web && npm run lint && npm run test -- --run && npm run build
```

质量门基线：后端 `306 passed`（含 PostgreSQL 16 集成测试 20 项）；前端 `10 test files / 28 tests passed`。OpenAPI 当前包含 35 条路径、38 个 operations。

## 核心流程

```text
创建任务草稿 → 创建人确认 → 确认发送 → 承办人接受/退回
→ 节点开始/进度更新/完成 → 进度汇报、卡点上报与闭环
→ 主承办人提交完成（生成不可变验收轮次）
→ reviewer 快照验收
   ├─ 通过：pending_review → completed
   └─ 驳回（需填原因）：pending_review → in_progress
      ├─ 仅返工整体交付物（保留已完成节点）
      └─ 指定节点显式重开（保留完成历史）
→ 返工完成后重新提交，进入下一验收轮次
```

只有主承办人可提交完成；每轮验收人取任务指定 reviewer 快照，未指定时回退创建人。创建人、高管或管理员身份不会自动获得验收权限；前端按钮不是权限边界，Service 层校验一切。

## 演示数据

`scripts/seed_demo_data.py` 为幂等的隔离演示工具，只接受以 `_test` / `_demo` 结尾的数据库，并要求 `--confirm-database-name` 与配置完全一致：

```bash
python -m scripts.seed_demo_data --dry-run --confirm-database-name "<db_name>"   # 检查并回滚
python -m scripts.seed_demo_data --apply   --confirm-database-name "<db_name>"   # 持久化
```

## 有效需求文档

`docs/` 中的两份文档为当前唯一有效需求，不得修改或删除：

- `第二版-智能任务看板核心逻辑与用户使用流程节点(1).docx`
- `第四版-智能任务看板数据表结构文档-显式ID版(1).docx`

## Roadmap

已完成：Batch 1（任务看板基础）、Batch 2A/2B（进度汇报与卡点）、Wave 1（完成验收与返工闭环）。

进行中 / 计划：

- Wave 2：不可变任务变更申请，取消、撤回、合并、关闭与恢复。
- Wave 4~7：绩效关联、负荷/看板统计重算、完成提醒与外部通知、归档快照与检索复用。
- 正式生产认证（企业统一身份 / 企业微信换票）、AI 结构化提取、附件管理。

## 当前未实现

- 正式生产登录认证与企业微信凭证换票（当前为受控原型身份）。
- 完整 RBAC 与组织范围权限。
- 任务变更申请与取消/撤回/合并/关闭流程。
- AI 结构化提取、多轮对话、语音上传与 ASR。
- 附件及交付物文件管理、绩效关联与统计分析。

## 相关文档

- [ARCHITECTURE.md](ARCHITECTURE.md) — 架构设计
- [FEATURE_COVERAGE.md](FEATURE_COVERAGE.md) — 功能覆盖情况
- [PLANS.md](PLANS.md) — 阶段计划
- [cloud-functions/README.md](cloud-functions/README.md) — 云函数部署说明

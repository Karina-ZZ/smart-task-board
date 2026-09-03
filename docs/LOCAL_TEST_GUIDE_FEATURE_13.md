# 本地跑通与功能 13 验证指南

这份文档给**第一次接触本仓库的协作者**：从零 clone 代码、启动服务、跑通测试，并逐项验证「功能 13 通知、提醒与协办节点承接」。

> 全程不需要企业内部网络。任何一台装了 Python 和 Node 的电脑都能跑通。

---

## 一、环境要求

| 依赖 | 版本 | 说明 |
|---|---|---|
| Python | **3.12**（项目声明 `>=3.12,<3.13`） | 3.13 需加 `--ignore-requires-python` 绕过，可能有细微差异 |
| Node.js | 18+ | 用于小程序测试和 React 前端 |
| Docker | 任意近期版本 | 用于起 PostgreSQL 16；也可改用本机已有的 PostgreSQL |

---

## 二、从零跑通（预计 10 分钟）

### 第 1 步：克隆仓库

```bash
git clone https://github.com/Karina-ZZ/smart-task-board.git
cd smart-task-board
```

### 第 2 步：启动数据库

```bash
# 在项目根目录创建 .env（不要提交）
cat > .env <<'EOF'
POSTGRES_DB=smart_task_board
POSTGRES_USER=stb
POSTGRES_PASSWORD=local-dev-only
POSTGRES_PORT=5432
EOF

docker compose up -d postgres
```

等健康检查通过后再继续（`docker compose ps` 看到 `healthy`）。

### 第 3 步：安装后端依赖

```bash
# macOS / Linux
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"

# Windows PowerShell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

如果本机只有 Python 3.13，把安装命令改成：

```bash
python -m pip install -e ".[dev]" --ignore-requires-python
```

### 第 4 步：配置后端环境变量

把下面内容追加到 `.env`（JWT 密钥请自己生成一个 32 位以上的随机串）：

```bash
DATABASE_URL=postgresql+psycopg://stb:local-dev-only@127.0.0.1:5432/smart_task_board
AUTH_MODE=prototype
PROTOTYPE_AUTH_ENABLED=true
PROTOTYPE_USER_EMPLOYEE_NOS=E001,E002,E003
JWT_SECRET_KEY=please-generate-a-random-string-at-least-32-chars
ALLOW_TEST_EMPLOYEE_HEADER=false
```

> `PROTOTYPE_USER_EMPLOYEE_NOS` 里的员工号就是登录白名单，测试时从这几个号里选。

### 第 5 步：执行数据库迁移

```bash
alembic upgrade head
```

成功后应停在单一 head `b1c2d3e4f5a6`（功能 13 的迁移为 `fa1b2c3d4e5`）。用 `alembic current` 确认。

### 第 6 步：启动后端

```bash
uvicorn app.main:app --reload
```

验证服务已起来：

- 存活检查：<http://127.0.0.1:8000/health/live>
- 数据库就绪：<http://127.0.0.1:8000/health/ready>
- Swagger UI：<http://127.0.0.1:8000/docs>

### 第 7 步（可选）：启动 React 前端

```bash
cd web
npm ci
npm run dev
```

前端默认连 `http://localhost:8000`，可用 `web/.env.local` 里的 `VITE_API_BASE_URL` 覆盖。

---

## 三、跑通测试套件

```bash
# 后端全量（当前基线：436 passed, 28 skipped）
python -m pytest

# 代码规范
python -m ruff check .

# 微信小程序功能 01~13（16 组测试，零依赖，不需要 npm install）
cd wechat-miniprogram && npm test

# React 前端（18 文件 / 109 测试 + 构建）
cd web && npm ci && npm run lint && npm run test -- --run && npm run build
```

> **关于 28 项 skipped**：全部是 PostgreSQL opt-in 集成测试，需显式设置 `RUN_POSTGRESQL_INTEGRATION=1` 和 `POSTGRES_TEST_DATABASE_URL` 才会执行，属预期行为，不是失败。

---

## 四、功能 13 验证清单

功能 13 的权威口径在 [`docs/FEATURE_13_ACCEPTANCE.md`](FEATURE_13_ACCEPTANCE.md) 和 [`docs/FEATURE_13_NOTIFICATION_RULES.md`](FEATURE_13_NOTIFICATION_RULES.md)。下面是可直接照做的验证步骤。

### 准备：取得身份 Token

```bash
# 用白名单里的员工号登录，取得 access token
curl -X POST http://127.0.0.1:8000/api/v1/auth/prototype-login \
  -H "Content-Type: application/json" \
  -d '{"employee_no": "E001"}'

# 后续请求带上：
#   Authorization: Bearer <access_token>
```

### 验证项 1：协办节点默认为「待承接」

创建一个任务 → AI 拆解或手工建节点 → 把某个节点负责人设为**非主承办人的协办人** → 查询节点，确认：

```
task_nodes.assignment_status == "pending"
task_nodes.assignment_responded_at == null
```

协办人（而非其他人）的 `GET /api/v1/notifications` 中应出现一条「节点待承接」通知。

### 验证项 2：未承接前禁止执行

在 `assignment_status == "pending"` 时，用协办人身份调用节点开始/完成接口：

- **预期**：被服务端拒绝（返回 4xx），不是靠前端隐藏按钮。

同时确认该节点不会产生开始/临期/到期/逾期提醒。

### 验证项 3：接受承接

```bash
curl -X POST http://127.0.0.1:8000/api/v1/tasks/{taskId}/nodes/{nodeId}/actions/accept-assignment \
  -H "Authorization: Bearer <协办人token>" \
  -H "Content-Type: application/json" \
  -d '{"expected_task_version": 1}'
```

**预期**：返回 `assignment_status: "accepted"`、`assignment_responded_at` 有值、`task_version` 递增。此后节点才进入可执行状态，执行类提醒才开始生效。

### 验证项 4：拒绝承接（原因必填）

```bash
curl -X POST http://127.0.0.1:8000/api/v1/tasks/{taskId}/nodes/{nodeId}/actions/reject-assignment \
  -H "Authorization: Bearer <协办人token>" \
  -H "Content-Type: application/json" \
  -d '{"expected_task_version": 1, "reason": "本周负荷已满，无法承接"}'
```

**预期**：`assignment_status: "rejected"`、拒绝原因入库；**主承办人**收到一条待处理通知（不是协办人自己）。

`reason` 为空时应被拒绝（该字段 `min_length=1`）。

### 验证项 5：临期提前量按工作跨度动态计算

| 节点工作跨度 | 提前量 |
|---|---|
| ≤ 1 个工作日 | 2 个工作小时 |
| > 1 且 ≤ 3 个工作日 | 4 个工作小时 |
| > 3 个工作日 | 1 个工作日 |

**关键校验**：该计算**不读取** `task_nodes.estimated_hours`，且临期时点不得早于 `planned_start_time`；与开始提醒同一时点时只保留开始提醒。

### 验证项 6：通知权限边界

- `GET /api/v1/notifications` **只返回当前登录用户自己的通知**（`recipient_employee_no == 当前用户`）。
- 用高管/管理员身份登录，也**不能**读到其他员工的私人通知。
- 通知只提供跳转目标，**不授予权限**：拿到通知后调用动作接口，服务端会再次鉴权。

### 验证项 7：扫描与发送接口仅限调度员

```bash
POST /api/v1/reminders/scan
POST /api/v1/notifications/send-pending
```

**预期**：普通员工、高管身份调用被拒绝；仅 active admin scheduler 可调用。

### 验证项 8：小程序端表现

打开 `wechat-miniprogram/`（微信开发者工具，`project.config.json` 已配 `touristappid`）：

- 「节点待承接」通知点击后进入任务详情并定位到该 `nodeId`
- 待承接节点展示「接受承接 / 无法承接」，拒绝时弹出原因输入框
- 接受成功后页面刷新任务版本与承接状态，才展示正常执行能力
- 生产页面**没有**身份切换、重置演示数据、全部已读等入口

---

## 五、已知问题（跑之前先看，免得以为是自己的错）

### ⚠️ `GET /api/v1/tasks/{task_id}/available-actions` 会返回 500

**现象**：`app/services/task_board_query.py` 第 670~674 行的 `available_actions()` 引用了未定义的变量 `priority`，运行时抛 `NameError`。

**影响**：仅影响这一个接口（后端动作投影查询），任务列表、详情、节点执行等主链路不受影响。

**为什么测试没抓到**：唯一覆盖真实实现的测试是 PostgreSQL opt-in（默认 skipped），单元测试用 mock 绕过了真实代码路径。

**修复方向**：在该方法中补一行 `priority = self._latest_priority(task.task_id)`（同文件 `_summary()` 中已有正确写法）。修复需按 `docs/ACCEPTANCE_STANDARDS.md` 执行全量回归。

### Ruff 有 201 个告警

其中 190 个是风格类（137 行超长、31 import 排序等），不影响功能；11 个 `F821` 就是上面那个真缺陷。**跑 `ruff check .` 报红属当前基线状态，不代表你环境装错了。**

### Python 版本口径

项目严格声明 3.12。若用 3.13 安装需 `--ignore-requires-python`，测试可正常通过，但与官方口径存在版本差异。

---

## 六、给 AI 助手的一键提示词

把下面这段整段复制，发给任意 AI 编程助手（Cline / Cursor / Codex / WorkBuddy 等），它会按上面的流程自动完成搭建与验证。**第一行的仓库地址已包含在内，无需再补充其他背景。**

```text
目标：在本机把 GitHub 仓库 https://github.com/Karina-ZZ/smart-task-board 跑通，并逐项验证「功能 13：通知、提醒与协办节点承接」，最后给我一份中文验证报告。

仓库里有一份专门的操作文档：docs/LOCAL_TEST_GUIDE_FEATURE_13.md。请先读它，再严格按里面的步骤执行。

执行要求：
1. 环境：Python 3.12（没有就用 3.13 加 --ignore-requires-python，并在报告里注明）、Node 18+、Docker。
2. 起 PostgreSQL 16（docker compose up -d postgres），执行 alembic upgrade head，确认停在 head b1c2d3e4f5a6。
3. 配置 prototype 认证所需环境变量（DATABASE_URL、AUTH_MODE=prototype、PROTOTYPE_AUTH_ENABLED=true、PROTOTYPE_USER_EMPLOYEE_NOS、JWT_SECRET_KEY 至少 32 位、ALLOW_TEST_EMPLOYEE_HEADER=false），启动 uvicorn，确认 /health/live 和 /health/ready 正常。
4. 跑测试：后端 pytest（基线 436 passed / 28 skipped）、ruff check、微信小程序 npm test（16 组）、React 前端 npm run lint/test/build（18 文件 / 109 测试）。
5. 按文档「四、功能 13 验证清单」的 8 个验证项逐项实测，每项都要给出：我实际执行的命令或请求、服务端真实返回、是否符合预期。不允许跳过或凭推断下结论。
6. 用 prototype-login 取得不同员工（主承办人 / 协办人 / 高管）的 token，验证权限边界。

重要提醒（已知问题，不要误判成你的环境问题）：
- GET /api/v1/tasks/{task_id}/available-actions 会返回 500，这是仓库的既有缺陷（app/services/task_board_query.py 第 670~674 行引用了未定义变量 priority）。请在报告中确认并复现它，但不要擅自修改业务代码——除非我明确要求你修。
- ruff check 会报 201 个错误，其中 190 个是风格类，属当前基线状态。
- pytest 的 28 项 skipped 是 PostgreSQL opt-in 集成测试，属预期行为。

输出要求：给我一份中文报告，包含四个部分：(a) 环境与版本信息；(b) 各项测试结果对照表（实测值 vs 文档基线）；(c) 功能 13 八个验证项的逐项结论（通过 / 不通过 / 无法验证及原因）；(d) 发现的问题清单。如实汇报，任何一项没跑通就明确说没跑通，不要粉饰。
```

---

## 七、相关文档

| 文档 | 用途 |
|---|---|
| [docs/FEATURE_13_ACCEPTANCE.md](FEATURE_13_ACCEPTANCE.md) | 功能 13 验收记录与最终口径（权威） |
| [docs/FEATURE_13_NOTIFICATION_RULES.md](FEATURE_13_NOTIFICATION_RULES.md) | 通知与提醒的 P0 规则基线 |
| [docs/ACCEPTANCE_STANDARDS.md](ACCEPTANCE_STANDARDS.md) | 单功能 10+1 条硬性验收条件 |
| [README.md](../README.md) | 项目总览、功能进度与测试进度 |
| [CHANGELOG.md](../CHANGELOG.md) | 版本变更历史 |

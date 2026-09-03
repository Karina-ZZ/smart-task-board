# 功能15高管员工任务筛选验收记录

> 日期：2026-09-03  
> 功能：功能15 / DEV-17  
> 当前结论：实现完成；当前容器可执行门禁通过。真实 PostgreSQL 与微信开发者工具门禁因环境不可用未执行，因此不宣称最终“开发成功”。

## 1. P0最终范围

用户最新确认覆盖旧 DEV-17“历史负荷快照任务明细”方案。功能15正式链路为：

```text
高管看板
→ 点击员工负荷格
→ 负荷构成抽屉
→ 查看该员工任务
→ 现有任务概览（自动带员工姓名筛选，查询使用 employeeNo）
→ 员工 + 状态 + 四象限 + 日期按AND叠加
→ 点击现有任务卡
→ 现有任务详情
→ 返回恢复任务筛选/滚动，再返回恢复高管部门/周期上下文
```

明确不实现：

- `workload_snapshot_task_details`；
- snapshot task detail字段；
- 按snapshotId查询历史任务集合；
- 独立员工负荷任务业务页；
- 新负荷公式；
- 新业务表/字段/Alembic migration。

权威规则：`docs/FEATURE_15_EXECUTIVE_EMPLOYEE_TASK_FILTER_RULES.md`。

## 2. 实现内容

### 2.1 高管看板

- 负荷构成抽屉增加真实按钮“查看该员工任务”。
- 点击携带 `source=executive`、`departmentId`、`employeeNo`、`employeeName`、`period`、`datePreset` 进入现有任务概览。
- `employeeName` 仅展示，不作为后端数据库过滤条件。

### 2.2 任务概览

- 复用 `wechat-miniprogram/pages/tasks/index`，未创建第四个业务页。
- 高管上下文增加员工姓名筛选组件。
- 默认员工任务口径：`tasks.main_assignee_employee_no = employeeNo`。
- 支持员工 + 状态 + 四象限 + 日期按 AND 叠加。
- 清除员工筛选时仍保留高管部门授权上下文。
- 员工选择列表由新的高管成员只读接口返回，候选范围受显式部门授权限制。
- 高管上下文错误态区分无权限，403时不展示员工/任务业务数据。

### 2.3 后端权限与查询

- 新增 `GET /api/v1/executive/members`，只返回当前高管有效部门范围内的 active 员工。
- 扩展 `GET /api/v1/executive/tasks` 支持 `employeeNo`、状态、四象限、日期等过滤。
- 员工筛选在 Repository 层使用 `Task.main_assignee_employee_no == employee_no`。
- 查询前先验证高管显式授权部门，再验证目标员工所属部门；授权外员工在任务查询前拒绝。
- 任务结果仍以授权部门集合为第一范围边界。
- 功能14四象限入口保持兼容：仅传 `period` 时继续按原周期语义筛选；功能15显式 `datePreset=all` 时不会被 `period` 隐式覆盖。

### 2.4 任务详情与返回

- 点击任务复用现有 `pages/task-detail/index`。
- 不新增高管专用详情，不扩大高管业务写权限。
- 普通 `navigateBack` 保留完整任务页实例状态；无历史栈时使用高管/员工上下文回退。

### 2.5 清理旧占位实现

已从生产页面清单删除旧：

```text
pages/workload-tasks/index
```

并删除其目录。该页面此前按employeeNo查询当前任务后在前端拼装假负荷压力，不符合P0三页流程。

当前 `app.json` 页面数：13；仍包含：

- `pages/executive/index`
- `pages/tasks/index`
- `pages/task-detail/index`

## 3. 数据库与迁移

功能15：

```text
新增业务表：0
新增数据库字段：0
新增Alembic migration：0
Alembic head：b1c2d3e4f5a6
```

与功能14基线比较，`alembic/versions` 文件集合无变化。

## 4. 关键修改文件

后端：

- `app/api/v1/executive.py`
- `app/repositories/executive_dashboard.py`
- `app/schemas/executive_dashboard.py`
- `app/services/features/executive_dashboard/permissions.py`
- `app/services/features/executive_dashboard/service.py`
- `app/services/features/executive_dashboard/task_list.py`（新增）

微信小程序：

- `wechat-miniprogram/pages/executive/index.js`
- `wechat-miniprogram/pages/executive/index.wxml`
- `wechat-miniprogram/pages/executive/index.wxss`
- `wechat-miniprogram/pages/tasks/index.js`
- `wechat-miniprogram/pages/tasks/index.wxml`
- `wechat-miniprogram/pages/tasks/index.wxss`
- `wechat-miniprogram/pages/task-detail/index.js`
- `wechat-miniprogram/utils/api.js`
- `wechat-miniprogram/utils/store.js`
- `wechat-miniprogram/utils/task-overview.js`
- `wechat-miniprogram/app.json`
- 删除 `wechat-miniprogram/pages/workload-tasks/`

测试/文档：

- `tests/api/test_executive_routes.py`
- `tests/api/test_task_routes.py`
- `tests/repositories/test_executive_dashboard_queries.py`（新增）
- `tests/services/test_executive_dashboard.py`
- `wechat-miniprogram/tests/executive-employee-tasks.test.js`（新增）
- `wechat-miniprogram/tests/executive-employee-tasks-flow.test.js`（新增）
- `wechat-miniprogram/tests/static-contract.test.js`
- `docs/FEATURE_15_EXECUTIVE_EMPLOYEE_TASK_FILTER_RULES.md`（新增）
- `docs/DEVELOPMENT_PLAN_V1.1.md`
- `README.md`
- `FEATURE_COVERAGE.md`
- `CODEX_EXECUTION_PROMPT.md`
- `PLANS.md`

## 5. 自动化测试证据

### 5.1 后端累计非PostgreSQL

命令：

```bash
DATABASE_URL=sqlite+pysqlite:///:memory: pytest -q -m 'not postgresql'
```

结果：

```text
460 passed
28 deselected（标记为postgresql的专项，不在此命令执行）
```

覆盖包括：

- 授权范围内员工按主承办过滤；
- 授权外员工在任务查询前拒绝并审计；
- 成员列表限制在选定授权部门范围；
- employee/status/quadrant/date参数传递；
- 功能14 period-only兼容；
- `datePreset=all`覆盖隐式period日期限制；
- Repository PostgreSQL dialect SQL合同：部门+main_assignee条件参数化；
- OpenAPI新增 `/api/v1/executive/members` 合同。

### 5.2 微信小程序累计测试

执行 `wechat-miniprogram/tests/*.test.js` 全部文件：

```text
19 / 19 test files PASS
```

功能15新增覆盖：

- 高管抽屉真实点击跳转；
- 路由带employeeNo/employeeName/departmentId/period；
- 任务页onLoad恢复员工筛选；
- API发送employeeNo，不发送employeeName做数据库过滤；
- 员工筛选summary；
- 旧`pages/workload-tasks/index`生产页面不存在。

### 5.3 语法/编译

```text
python -m compileall -q app cloud-functions   PASS
全部微信JS node --check                       PASS
```

### 5.4 云函数纯逻辑

```text
LoginService test_auth_service.py   PASS
ChatService test_task_intake.py     PASS
```

### 5.5 Alembic

```text
alembic heads
→ b1c2d3e4f5a6 (head)

功能14 vs 功能15 alembic/versions文件集合diff
→ 无变化
```

## 6. 当前环境未执行门禁

### 6.1 真实PostgreSQL

当前容器：

```text
psycopg：未安装
psql：不可用
docker：不可用
```

因此28个 PostgreSQL 专项及真实数据库联通/性能门禁未执行，不能记为PASS。

### 6.2 微信开发者工具

当前容器没有微信开发者工具，无法执行真实工具编译、设备视觉和375/390/430设备级最终验收。现有静态合同、JS语法和Node交互测试均已通过，但不等价于微信开发者工具验收。

### 6.3 Ruff / React Web门禁

`ruff` 当前不可用。功能15实际生产切片基于当前累计微信小程序代码；若仍要求架构文档中的React Web完整发布门禁，需要在具备其依赖的环境单独执行。

## 7. 最终状态

功能15业务代码和当前可执行自动化门禁已经完成；无新增数据库结构，也未提前开发功能16/DEV-18产品范围。

按项目“全部门禁通过后才报告开发成功”的规则，当前状态记录为：

```text
BLOCKED（实现完成，等待真实PostgreSQL与微信开发者工具等环境门禁）
```

## 8. 候选ZIP反向验收

在生成候选累计全源码ZIP后，将ZIP解压到全新目录，不复用开发工作树，重新执行：

```text
后端非PostgreSQL累计：460 passed, 28 deselected
Alembic head：b1c2d3e4f5a6
LoginService纯逻辑：PASS
ChatService纯逻辑：PASS
微信累计测试：19 / 19 test files PASS
全部微信JS node --check：PASS
微信结构合同：13个注册页面，executive/tasks/task-detail存在，旧workload-tasks不存在
```

反向验收结果与开发工作树一致。最终ZIP仍需在真实PostgreSQL和微信开发者工具环境执行未完成门禁后，才能按项目定义正式标记“开发成功”。

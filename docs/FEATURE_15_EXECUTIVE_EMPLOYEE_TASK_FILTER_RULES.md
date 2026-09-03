# 功能15高管员工任务筛选规则基线

> 状态：P0 用户已确认，供功能15开发直接执行。
> 日期：2026-09-03
> 优先级：用户最新确认 > 本文件 > PRD V1.1 > 既有开发计划 > 历史实现/讨论草案。
> 边界：本文件覆盖旧 DEV-17“历史负荷快照任务明细”方案。

## 1. 功能15最终定义

功能15不是“历史负荷快照任务构成追溯”。功能15只完成以下链路：

```text
高管看板
→ 点击员工负荷格
→ 打开负荷构成抽屉
→ 点击「查看该员工任务」
→ 进入现有任务概览页
→ 自动增加员工姓名筛选（业务查询使用 employee_no）
→ 在高管授权范围内查看该员工当前任务
→ 可叠加状态、四象限、日期等本功能确认的现有筛选
→ 点击任务进入现有任务详情
→ 返回恢复员工及其他筛选，再返回恢复高管看板上下文
```

## 2. 明确废止的旧方案

功能15不得：

- 新增 `workload_snapshot_task_details`；
- 新增 snapshot task detail 相关字段；
- 按 `workloadSnapshotId` 查询历史任务集合；
- 解释“某次负荷分数由哪些历史任务组成”；
- 新增独立员工负荷任务业务页；
- 重新实现负荷公式或任务列表算法。

因此功能15：新增业务表 0、数据库字段 0、Alembic migration 0。

## 3. 页面与交互节点

### 3.1 高管看板

保持功能14团队指标、四象限、热力图和负荷构成不变。负荷构成抽屉底部增加真实按钮：

```text
查看该员工任务
```

点击时带入：

```text
source=executive
departmentId=<当前高管部门筛选>
employeeNo=<被点击员工 employee_no>
employeeName=<仅展示>
period=<当前高管周期>
```

### 3.2 任务概览

复用现有 `/pages/tasks/index`。高管上下文增加“员工姓名”筛选。

- 页面显示员工姓名；
- 后端始终以 `employee_no` 过滤，不以姓名做唯一条件；
- 从高管看板进入时自动选中该员工；
- 员工筛选与状态、四象限、日期条件按 AND 叠加；本功能不额外扩大高管筛选组件范围；
- 清除员工筛选后仍保留高管部门授权上下文，显示授权范围内任务；
- 可从授权员工列表重新选择员工。

当前负荷算法以 `tasks.main_assignee_employee_no` 为员工任务口径，因此功能15员工筛选默认采用主承办人口径，不把创建人、验收人、被@人等关系混入。

### 3.3 任务详情

复用现有任务详情页，不新增高管专用详情页。高管通过授权范围获得只读访问，不因来源页面获得额外写权限。

## 4. 权限

高管员工任务筛选必须继续使用功能14的显式部门授权：

```text
users.role_type in executive/admin
AND 有有效 user_authorized_scopes department/view 授权
AND requested departmentId 属于授权部门及有效下级部门
AND employee.department_id 属于当前有效部门范围
AND task.department_id 属于当前有效部门范围
AND task.main_assignee_employee_no = employeeNo（员工筛选启用时）
```

猜测其他部门的 `employeeNo` 或 `departmentId` 必须 403，且不得泄漏员工姓名、任务数量或任务内容。

## 5. 返回恢复

任务详情返回任务概览时必须恢复：

- employeeNo / employeeName；
- status；
- quadrant；
- datePreset / startDate / endDate；
- page / sort；
- scrollTop。

任务概览再返回高管看板时必须恢复高管页已有部门、周期和页面位置。所有恢复状态只属于前端导航状态，不写业务数据库。

## 6. 数据与迁移边界

只复用现有：

- `users.employee_no/name/department_id/status`；
- `departments`；
- `user_authorized_scopes`；
- `tasks.main_assignee_employee_no/department_id/...`；
- `task_priority_scores` 等任务概览既有只读聚合。

不得新增业务表或迁移。

## 7. 最低验收

1. 负荷抽屉按钮真实可点击。
2. 点击后任务概览自动显示员工筛选。
3. 请求使用 `employeeNo`，不按姓名过滤数据库。
4. 员工 + 状态 + 四象限 + 日期等条件可叠加。
5. 清除员工筛选后仍保持高管授权范围。
6. 授权外 employeeNo / departmentId 返回 403 且不泄漏数据。
7. 任务卡进入现有详情，高管无业务关系时仍只读。
8. 详情返回恢复筛选和滚动。
9. 不存在历史快照任务明细查询和前端假算。
10. 新增 migration 为 0。

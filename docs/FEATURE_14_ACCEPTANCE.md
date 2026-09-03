# 功能14验收记录：高管基础看板

> 状态：实现完成；当前环境门禁未全部满足，因此不报告“开发成功”。
> P0规则：`docs/FEATURE_14_EXECUTIVE_DASHBOARD_RULES.md`。
> 范围：DEV-16 / 第一阶段高管基础看板；不包含DEV-17员工负荷任务明细下钻。

## 1. 本轮先修复的阻断缺陷

修复 `app/services/task_board_query.py` 中 `TaskBoardQueryService.available_actions()` 未定义 `priority` 即读取优先级字段的问题。

修复方式：在组装返回值前复用同文件权威查询：

```python
priority = self._latest_priority(task.task_id)
```

新增真实Service回归测试覆盖“无priority”和“有priority”两种情况，避免API层mock再次掩盖真实Service错误。

## 2. 高管授权范围

高管团队数据范围以 `user_authorized_scopes + departments` 为权威来源，不以 `users.department_id` 猜测负责部门。

- 当前用户必须为有效 `executive`，或为拥有显式部门授权的管理员兼容身份。
- 读取当前有效 `scope_type=department` 授权；`permission_type=view/manage/export` 均具备读取语义。
- 每个授权根部门覆盖其本身及所有启用的下级部门。
- 用户选择子部门后，指标只统计该子树；部门选择器仍保留全部授权部门选项。
- 请求授权范围外部门直接 `403 SCOPE_DENIED`，在返回任何团队数据前拒绝，并写 `operation_logs`。

## 3. 周期

统一使用 Asia/Shanghai 业务时区和半开区间 `[start, end)`：

- week：本周一00:00至下周一00:00；
- month：本月1日00:00至下月1日00:00；
- 同时计算紧邻的上一等长周期，用于环比。

## 4. 四项团队指标

### 4.1 进行中

只统计已生效且状态属于：

```text
in_progress / blocked / pending_report
```

当前值：

```text
COUNT(DISTINCT tasks.task_id)
```

历史比较通过 `task_status_logs` 重建上一周期截止时点状态，避免用今天的 `tasks.status` 冒充历史状态。上一周期为0且当前大于0时返回 `changeRate=null, changeDirection=new`，不显示无穷大。

### 4.2 按期率

周期完成集合由 `tasks.completed_at` 定义：

```text
periodStart <= completed_at < periodEnd
```

```text
onTimeRate =
COUNT(completed_at <= deadline)
/
COUNT(period completed tasks)
* 100
```

分母为0时返回 `null`，不是0%。环比使用百分点差。

### 4.3 KPI关联

严格执行P0修正规则：

- 正式关系唯一门槛：`task_performance_matches.is_confirmed = true`；
- `match_level` 不作为功能14统计门槛；strong/weak/no_clear_relation只要用户已确认均可统计；
- 当前看板排除 `performance_metrics.status = inactive`；历史确认关系不删除；
- 不定义、不展示、不计算“核心KPI”；`performance_metrics.weight`不参与KPI卡统计。

```text
kpiLinkedTaskCount = COUNT(DISTINCT task_id)
linkedMetricCount  = COUNT(DISTINCT metric_id)
```

4个正式关联任务涉及2个不同指标时必须返回 `4 / 2`。

### 4.4 总体进度

纳入：

```text
in_progress / blocked / pending_report / pending_review
```

`pending_review` 不计进行中数量、负荷和执行四象限，但继续参与总体进度。

单任务进度继续使用统一规则：当前有效拆解的非cancelled节点等权平均；历史无有效节点任务使用最新根任务进度汇报兜底。不得使用 `estimated_hours`。

团队进度：

```text
overallProgress =
SUM(taskProgress * taskWeight)
/
SUM(taskWeight)
```

`pending_review` 不在看板层硬编码100%；若权威进度小于100，保留真实结果并计入 `dataQualityIssueCount`。

## 5. 四象限

功能14不重新计算重要性/紧急性，只读取每个执行态任务最新落库的 `task_priority_scores.priority_quadrant`。

纳入状态：

```text
in_progress / blocked / pending_report
```

无最新优先级记录的任务不伪造象限，计入 `unscoredCount`。

四象限点击调用：

```text
GET /api/v1/executive/tasks
```

并重新执行部门授权校验；小程序任务概览保留 `source=executive / quadrant / departmentId / period` 上下文。

## 6. 负荷热力图与负荷构成

功能14只读取现有权威 `workload_snapshots`，不在高管Service重新实现负荷公式或写新快照。

热力图按授权部门员工和工作日组织，单元格返回：

- `workloadSnapshotId`
- `workloadScore / workloadLevel`
- 五维压力
- active/urgent/blocked/overdue任务数
- `calculatedAt`

点击有真实快照的单元格只打开本地负荷构成抽屉。功能14不开放“查看该员工任务”，不读取/新增 `workload_snapshot_task_details`。

## 7. 新增后端入口

```text
GET /api/v1/executive/overview
GET /api/v1/executive/tasks
```

核心代码按架构拆分到：

```text
app/api/v1/executive.py
app/schemas/executive_dashboard.py
app/repositories/executive_dashboard.py
app/services/features/executive_dashboard/
```

没有新增Alembic迁移。

## 8. 微信端

高管页已重建为：

```text
授权部门/周期
→ 进行中 / 按期率 / KPI关联 / 总体进度
→ 团队四象限
→ 员工工作日负荷热力图
→ 单快照五维负荷构成
```

移除功能14页面原有的直接 `/pages/workload-tasks` 下钻行为；DEV-17入口不在本功能开放。

## 9. 自动化证据

当前工作目录实际执行：

- 后端非PostgreSQL累计：`451 passed, 28 deselected`。
- `available_actions()`真实Service定向回归：PASS。
- 功能14Service/API规则测试：PASS。
- OpenAPI合同：新增2个已批准高管接口后，`95`条 `/api/v1` 路径、`101`个operations断言通过。
- Python `compileall app tests`：PASS。
- Alembic：单一head `b1c2d3e4f5a6`；功能14新增迁移 `0`。
- 微信功能01～14累计：`17`组测试 PASS。
- 微信全部 `.js` `node --check`：PASS。
- LoginService纯服务脚本：PASS。
- ChatService任务识别纯服务脚本：PASS。
- P0静态防回流检查：无 `核心KPI/coreMetric`、无功能14 `match_level=strong`门禁、无 `estimated_hours`、高管页无 `/pages/workload-tasks` 跳转。

## 10. 当前环境未通过/未执行门禁

因此本轮不能报告“功能14开发成功”：

1. **真实PostgreSQL集成测试未执行**：当前容器没有 `psycopg/psycopg2`、`psql` 或 Docker，且网络不可用于安装驱动。28个PostgreSQL专项测试未伪装为PASS。
2. **React Web test/lint/build未执行**：累计包内没有 `web/node_modules`；`npm ci --offline` 因npm缓存缺少依赖失败。功能14未修改React代码，但累计发布门禁仍不能算PASS。
3. **Ruff未执行**：当前环境没有可用 `ruff` 命令。
4. **微信开发者工具真机/编译器视觉验收未执行**：当前容器没有微信开发者工具；已完成WXML静态合同、JS语法和业务测试，但不能冒充真实工具编译/视觉验收。
5. **P95<4s真实PostgreSQL性能采样未执行**：需要批准的隔离PostgreSQL数据集。

## 11. 状态与下一步

代码实现已完成且所有当前可执行门禁通过，但完整“开发成功”仍被真实PostgreSQL、Web依赖和微信开发者工具环境阻塞。正式冻结包可用于下一环境继续执行上述门禁；在这些门禁通过前不应开始DEV-17。

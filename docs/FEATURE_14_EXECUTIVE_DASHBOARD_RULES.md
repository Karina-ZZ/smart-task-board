# 功能14高管基础看板规则基线

> 状态：P0 用户已确认，供 DEV-16 / 功能14 开发直接执行。  
> 日期：2026-09-03  
> 边界：本文件只冻结功能14已确认的高管看板业务规则，不代表功能14代码已经实现。  
> 优先级：用户最新确认 > 本文件 > PRD V1.1 > 既有开发计划 > 历史实现/讨论草案。  
> 重要说明：本文件中的“修正规则”覆盖此前讨论中与之冲突的草案表述。

## 1. 本轮确认结论

功能14关于 KPI 关联和团队总体进度，正式冻结以下规则：

1. KPI 是否属于正式关联，**只以用户最终确认结果 `task_performance_matches.is_confirmed = true` 为业务门槛**。
2. `task_performance_matches.match_level` 是系统匹配算法的解释/推荐结果，不是功能14 KPI 统计的强制条件；不得要求 `match_level = 'strong'` 才纳入统计。
3. 功能14**不定义、不展示、不计算“核心KPI/核心指标”**；不得新增 `is_core`、`core_metric`、`coreMetricCount` 或任何核心KPI阈值。
4. KPI 卡统计两个不同口径：
   - `kpiLinkedTaskCount = COUNT(DISTINCT task_id)`：有多少个不同任务已正式确认关联绩效指标；
   - `linkedMetricCount = COUNT(DISTINCT metric_id)`：这些正式确认关系一共涉及多少个不同绩效指标。
5. 同一示例中若有 4 个不同任务正式关联到 2 个不同绩效指标，则必须返回：
   - `KPI关联任务 = 4`
   - `涉及绩效指标 = 2`
   不得混入与该示例无关的其他数字。
6. 当前高管 KPI 卡**排除已停用绩效指标**：只统计 `performance_metrics.status = 'active'` 的当前有效指标。
7. 停用绩效指标不得删除历史 `task_performance_matches`；“当前看板不统计”与“历史关系删除”是两件不同的事。
8. 团队总体进度**包含 `pending_review`**；其余纳入状态为 `in_progress`、`blocked`、`pending_report`。
9. `pending_review` 不计入进行中任务数、员工执行负荷和执行四象限，但继续参与团队总体进度，直到任务归档。
10. `pending_review` 的任务进度不得在高管看板中直接硬编码为 100；必须复用项目唯一任务进度算法。若状态为 `pending_review` 但权威进度结果小于 100，应视为数据一致性异常，而不是由看板层篡改结果。

## 2. KPI 正式关联的权威字段

### 2.1 `task_performance_matches.is_confirmed`

所在表：`task_performance_matches`（任务绩效匹配表）。

字段含义：

```text
is_confirmed = false
→ 系统候选/推荐关系，尚未形成正式业务关联

is_confirmed = true
→ 用户已经最终确认，形成正式任务-KPI关系
```

功能14必须把 `is_confirmed` 作为 KPI 关联统计的唯一“是否正式关联”门槛。

当前项目源码中，绩效确认 Service 也以此字段保存创建人的最终确认事实；确认时还记录：

```text
confirmed_by_employee_no
confirmed_at
```

这些字段用于审计和追溯，但不改变功能14的去重公式。

### 2.2 `task_performance_matches.match_level`

所在表：`task_performance_matches`。

当前枚举：

```text
strong
weak
no_clear_relation
```

字段职责：保存系统绩效匹配算法的强弱判断，用于推荐解释、匹配证据及其他需要使用系统评分的业务能力。

功能14规则：

```text
match_level 不参与“是否正式关联”的门禁。
```

因此以下关系都可以进入功能14 KPI 统计，只要用户最终确认且指标当前启用：

```text
match_level = strong            + is_confirmed = true → 统计
match_level = weak              + is_confirmed = true → 统计
match_level = no_clear_relation + is_confirmed = true → 统计
```

而：

```text
match_level = strong + is_confirmed = false → 不统计
```

用户最终确认优先于系统推荐等级。

## 3. 不区分“核心KPI”

### 3.1 禁止新增未经确认的分类

功能14不得把以下任何概念作为正式业务字段或页面文案：

```text
核心KPI
核心指标
coreMetric
coreMetricCount
isCoreMetric
core_metric_threshold
```

现有 `performance_metrics.weight` 虽然表示绩效指标自身的权重/重要程度，但项目没有已确认的“多少权重以上属于核心KPI”的阈值，因此功能14不得根据 `weight` 自行划分核心与非核心。

### 3.2 页面正式文案

推荐页面展示：

```text
KPI关联任务
4

涉及绩效指标
2
```

或在空间受限时：

```text
KPI关联 4
涉及2项绩效指标
```

不得写“涉及2项核心指标”。

## 4. KPI 去重口径

“去重”不是数据库字段，而是高管 KPI 卡的聚合规则。

### 4.1 主指标：KPI关联任务数

```text
kpiLinkedTaskCount
=
COUNT(DISTINCT task_performance_matches.task_id)
```

回答的问题：

> 当前授权范围和当前统计口径下，有多少个不同任务已经由用户正式确认关联绩效指标？

### 4.2 辅助指标：涉及绩效指标数

```text
linkedMetricCount
=
COUNT(DISTINCT task_performance_matches.metric_id)
```

回答的问题：

> 上述正式确认的任务关系一共覆盖多少个不同绩效指标？

### 4.3 示例

数据：

```text
任务A → KPI001
任务B → KPI001
任务C → KPI002
任务D → KPI002
```

假设四条关系全部满足：

```text
is_confirmed = true
对应 performance_metrics.status = active
```

则：

```text
DISTINCT task_id   = 4
DISTINCT metric_id = 2
```

页面必须显示：

```text
KPI关联任务 = 4
涉及绩效指标 = 2
```

不得显示或推导为其他数字。

## 5. KPI 卡涉及的数据表和字段

### 5.1 `tasks`

用途：提供任务主体、任务所属部门以及功能14其他已确认的任务范围过滤条件。

KPI统计至少需要：

| 字段 | 用途 |
|---|---|
| `task_id` | 与 `task_performance_matches.task_id` 关联；任务去重 |
| `department_id` | 高管授权部门范围过滤 |
| `status` | 按功能14最终有效任务范围过滤 |
| `effective_at` | 判断任务是否已经正式生效（如该过滤条件适用于最终KPI统计口径） |

本文件不额外创造未确认的 KPI 周期/任务有效性规则；DEV-16 开发时必须使用开发计划和后续用户确认的最终任务范围口径。

### 5.2 `task_performance_matches`

用途：承接任务与绩效指标的匹配证据和用户最终确认关系。

功能14直接使用：

| 字段 | 用途 |
|---|---|
| `performance_match_id` | 匹配记录ID，审计/追溯 |
| `task_id` | 关联任务；用于 `DISTINCT task_id` |
| `metric_id` | 关联绩效指标；用于 `DISTINCT metric_id` |
| `match_level` | 系统推荐解释，不作为统计门槛 |
| `is_confirmed` | 正式关联唯一业务门槛 |
| `confirmed_by_employee_no` | 最终确认人审计 |
| `confirmed_at` | 最终确认时间审计 |

功能14不使用 `type_score`、`business_unit_score`、`metric_name_score`、`definition_formula_score`、`deliverable_score`、`total_score` 作为是否进入KPI卡的门槛。

### 5.3 `performance_metrics`

用途：绩效指标主数据，确认 `metric_id` 对应的指标当前是否有效，并提供名称等展示信息。

当前源码字段中，功能14直接关注：

| 字段 | 用途 |
|---|---|
| `metric_id` | 与 `task_performance_matches.metric_id` JOIN |
| `metric_name` | KPI名称展示 |
| `period` | 绩效指标周期展示/后续明确后的过滤辅助 |
| `business_unit` | 指标所属业务单元展示/辅助 |
| `status` | 当前指标是否启用；功能14只统计 `active` |
| `weight` | 指标自身权重；功能14不据此划分核心KPI |

当前 ORM 约束：

```text
performance_metrics.status IN ('active', 'inactive')
```

功能14当前 KPI 卡只统计：

```text
performance_metrics.status = 'active'
```

## 6. KPI 卡后端门禁

在其他功能14任务范围/周期条件已经满足的前提下，KPI正式关系必须满足：

```text
task 属于高管授权范围
AND task_performance_matches.is_confirmed = true
AND performance_metrics.status = 'active'
```

明确禁止增加：

```text
AND task_performance_matches.match_level = 'strong'
```

概念 SQL：

```sql
SELECT
    COUNT(DISTINCT pm.task_id)   AS linked_task_count,
    COUNT(DISTINCT pm.metric_id) AS linked_metric_count
FROM tasks t
JOIN task_performance_matches pm
  ON pm.task_id = t.task_id
JOIN performance_metrics m
  ON m.metric_id = pm.metric_id
WHERE t.department_id = ANY(:authorized_department_ids)
  AND pm.is_confirmed = TRUE
  AND m.status = 'active'
  -- 其余任务有效范围/period条件使用功能14最终冻结口径
;
```

注意：Repository实际实现必须使用项目现有枚举/常量，避免重复散落硬编码；上面的 SQL 只表达业务逻辑。

## 7. 停用绩效指标的处理

采用用户确认的“方案A”：当前 KPI 卡排除停用指标。

示例：

```text
昨天：
任务A → KPI001，已确认
任务B → KPI001，已确认
KPI001.status = active

KPI关联任务 = 2
涉及绩效指标 = 1
```

如果今天管理员把：

```text
KPI001.status = inactive
```

则当前高管 KPI 卡：

```text
KPI关联任务 = 0
涉及绩效指标 = 0
```

但是数据库中的历史：

```text
任务A → KPI001
task_performance_matches.is_confirmed = true

任务B → KPI001
task_performance_matches.is_confirmed = true
```

不得删除、不得改成未确认。停用只影响“当前看板是否统计”，不改变历史确认事实。

## 8. 当前源码的确认关系兼容事实

当前 `PerformanceMetricService.confirm_match()` 在确认某条 KPI 关系时，会取消同一任务此前其他 `is_confirmed = true` 的关系，因此当前实现事实上保持“一个任务同一时点只有一个正式确认 KPI”。

功能14聚合仍必须使用：

```text
COUNT(DISTINCT task_id)
COUNT(DISTINCT metric_id)
```

不得因为当前源码通常是一任务一确认KPI，就把 `COUNT(*)` 当成正式业务口径。这样即使以后关系模型扩展，功能14统计语义仍保持稳定。

## 9. 团队总体进度包含 `pending_review`

### 9.1 纳入状态

团队总体进度正式纳入：

```text
in_progress
blocked
pending_report
pending_review
```

排除：

```text
draft
pending_confirm
pending_accept
returned
decomposing
decomposition_failed
completed
archived
cancelled
withdrawn
merged
closed
```

其中 `completed` 为验收通过事务中的瞬时中间态，不应成为高管当前总体进度的稳定统计对象。

### 9.2 `pending_review` 在不同指标中的角色

| 状态 | 进行中任务数 | 员工执行负荷 | 执行四象限 | 团队总体进度 |
|---|---:|---:|---:|---:|
| `in_progress` | 是 | 是 | 是 | 是 |
| `blocked` | 是 | 是 | 是 | 是 |
| `pending_report` | 是 | 是 | 是 | 是 |
| `pending_review` | 否 | 否 | 否 | **是** |
| `archived` | 否 | 否 | 否 | 否 |

解释：`pending_review` 表示实际执行已经完成并提交验收，但管理闭环尚未归档；它不再产生执行负荷，也不需要执行优先级排序，但仍然应该反映在当前团队尚未归档任务的整体完成进度中。

## 10. `pending_review` 的进度计算方式

功能14不得写：

```python
if task.status == "pending_review":
    progress = 100
```

正确方式是复用项目唯一任务进度算法（现有实现/计划中的 `calculate_task_progress()` 权威逻辑）：

```text
任务有当前有效节点
→ 使用当前有效拆解的非 cancelled 节点 progress_percent 等权聚合

历史无有效节点任务
→ 使用最新有效 task_progress_reports.progress_percent 兜底
```

正常状态机要求进入 `pending_review` 前全部有效节点已经完成，因此正常情况下权威进度自然应得到 100%。

如果出现：

```text
tasks.status = pending_review
但 calculate_task_progress(task_id) < 100
```

应认定为数据一致性异常：

- 高管看板继续使用权威进度结果；
- 不得在展示层强制改成100；
- DEV-16测试应覆盖该异常并记录可观测/数据质量处理方式。

## 11. 团队总体进度公式

对授权范围内且状态属于：

```text
in_progress / blocked / pending_report / pending_review
```

的任务，逐个获得权威任务进度：

```text
progress_i = calculate_task_progress(task_i)
```

团队总体进度按 `tasks.task_weight` 加权：

```text
overall_progress
=
Σ(progress_i × task_weight_i)
/
Σ(task_weight_i)
```

任务权重只用于“任务与任务之间”的团队加权；不得用 `estimated_hours` 或节点预计工时作为权重。

## 12. 本轮废止的旧草案表述

以下内容与用户最新确认冲突，全部废止，不得进入功能14代码、测试或页面：

1. “KPI关联必须 `match_level = 'strong'` 才统计”。
2. “弱相关即使用户确认也不能进入高管KPI卡”。
3. “涉及核心指标 / 核心KPI”这一未经定义的分类。
4. 根据 `performance_metrics.weight` 自行定义核心KPI阈值。
5. 在 `DISTINCT task_id = 4`、`DISTINCT metric_id = 2` 的同一示例中展示成其他数字（例如42/8）。
6. `pending_review` 从团队总体进度中排除。
7. 在高管看板中把 `pending_review` 直接硬编码为100%，绕过统一任务进度算法。

## 13. DEV-16最低测试要求

功能14开发时至少增加以下断言：

### KPI统计

1. `strong + is_confirmed=false` → 不统计。
2. `weak + is_confirmed=true + metric active` → 统计。
3. `no_clear_relation + is_confirmed=true + metric active` → 统计。
4. `is_confirmed=true + metric inactive` → 当前KPI卡不统计，但历史关系仍存在。
5. 任务A/B关联KPI001、任务C/D关联KPI002，四条均正式确认且active → `linkedTaskCount=4`、`linkedMetricCount=2`。
6. 不存在 `coreMetricCount`、`isCoreMetric`、核心KPI阈值等功能14字段/逻辑。

### 总体进度

7. `pending_review` 任务进入总体进度分母和分子。
8. `pending_review` 不进入进行中数量、员工执行负荷和执行四象限。
9. `pending_review` 不由看板层硬编码100%，而是调用统一任务进度算法。
10. `pending_review` 但权威进度小于100时，不静默覆盖该异常。
11. `archived` 不进入当前总体进度。
12. 团队总体进度按 `task_weight` 加权，禁止使用任何 `estimated_hours`。

## 14. 开发边界

本文件只冻结规则。加入项目源时：

- 不新增功能14 Service/API/Repository/页面代码；
- 不新增数据库迁移；
- 不改变功能13已验收实现；
- 不提前实现DEV-17员工负荷任务下钻；
- DEV-16真正开发时，必须先完整读取本文件并按P0规则实现。

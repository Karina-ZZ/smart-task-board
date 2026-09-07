# Test16 绩效关联显示 Hotfix 执行报告

> 基线：Test16-Modal-Hotfix
> 目标：修复创建阶段已确认绩效指标，但任务详情在小程序 mock 模式显示“未关联已确认绩效指标”的问题。
> 边界：不修改数据库结构、不修改绩效匹配算法、不修改发送/接受/拆解/通知等其他业务状态机。

## 1. 根因

创建阶段 mock 数据层将已确认绩效指标保存为：

- `task.performanceMetricId`
- `task.performanceMetric`

任务详情组件统一读取正式 DTO 的：

- `performanceMatches[]`
- 且只展示 `isConfirmed !== false` 的关系。

此前 `store.enrichTask()` 没有把 mock 中已确认的绩效字段投影为 `performanceMatches[]`，因此页面误显示“未关联已确认绩效指标”。

## 2. 实际修改

### 小程序 mock DTO 修复

`wechat-miniprogram/utils/store.js`

- 新增 `confirmedPerformanceMatches(state, task)`。
- 对已确认 KPI 生成与正式任务详情接口一致的 `performanceMatches[]` DTO。
- 既兼容新创建任务的 `performanceMetricId`，也兼容历史演示任务仅保存 KPI 名称的情况。
- 明确选择“不关联绩效”时返回空集合。
- 任务详情页面本身不增加 mock 特判，仍只消费统一 `performanceMatches[]`。

### 新增小程序回归

`wechat-miniprogram/tests/performance-link-persistence.test.js`

覆盖：

1. 历史演示任务 KPI 正确投影。
2. 创建草稿 → 生成候选 → 创建人确认 KPI。
3. 保存并发送任务后 KPI 仍在任务 DTO 中。
4. 重新读取任务详情后 KPI 仍显示。
5. 清除正式关联后详情恢复为空。

### 新增真实 PostgreSQL 验收合同

`tests/integration/test_business_capabilities_postgresql.py`

新增：

`test_confirmed_performance_relation_survives_send_and_detail_reload_postgresql`

用于真实 PostgreSQL 环境验证：

- draft 阶段确认 `task_performance_matches.is_confirmed=true`；
- 提交确认并发送；
- 任务进入 `pending_acceptance`；
- `TaskQueryService.get_task_detail()` 仍返回同一已确认 KPI。

该测试不会新增表或字段；只使用现有 `tasks`、`performance_metrics`、`task_performance_matches`。

## 3. 当前环境实际测试

- 小程序新增专项：PASS。
- 小程序累计测试：25/25 test files PASS。
- 小程序 JS `node --check`：54 files / 0 failed。
- Python `compileall`：PASS。
- 后端非 PostgreSQL：602 passed / 41 deselected。
- 新 PostgreSQL 测试：收集成功；当前环境未执行真实 PostgreSQL。
- ChatService 原有脚本：3/3 PASS。

真实 PostgreSQL、微信开发者工具 API 模式和真机页面仍需在本地正式环境完成，不在本报告中伪报通过。

## 4. 修改范围保护

生产业务代码仅修改：

- `wechat-miniprogram/utils/store.js`

后端生产代码 `app/` 未修改。

测试新增/修改：

- `wechat-miniprogram/tests/performance-link-persistence.test.js`
- `tests/integration/test_business_capabilities_postgresql.py`

数据库：

- 新增表：0
- 新增字段：0
- 新增索引/约束：0
- Alembic migration：0

## 5. 当前结论

mock 模式中“已确认 KPI 在任务详情丢失”的已知根因已经修复并由页面 DTO 回归覆盖。

正式 API 本身原有设计通过 `task_performance_matches` 读取已确认关系，本轮未发现需要修改后端生产代码；新增真实 PostgreSQL 验收合同用于本地最终确认“确认关系跨发送流程持续存在”。

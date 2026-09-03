# 功能09验收记录｜进度汇报与卡点闭环

状态：DONE（当前环境可执行门禁）

## 本功能完成

- 仅主承办人在 `in_progress` / `blocked` / `pending_report` 可提交任务级进度汇报。
- 当前进度必填且限制 0~100；阶段成果可选；备注可选；不接受用户填写 `actual_hours`。
- 卡点开关为真时必须填写卡点说明；汇报、问题、任务状态、日志、通知在同一事务提交。
- 有卡点汇报创建 `task_issues` 并将任务置为 `blocked`，通知创建人；无卡点汇报回到 `in_progress`。
- 独立问题上报也仅允许主承办人；协同人/节点负责人不获得任务级汇报或资源诉求权限。
- 问题关闭后若已无活动 blocker，任务恢复 `in_progress`。
- 微信任务详情开放真实“汇报进度”入口；汇报页调用真实后端并带 `Idempotency-Key`。
- 功能10/11的变更、生命周期、完成、验收动作未提前开放。

## 累计门禁

- 后端非 PostgreSQL：396 passed，21 PostgreSQL 专项 deselected（当前环境缺 PostgreSQL/psycopg，未伪装通过）。
- 微信累计：12 组 PASS（含 task-decomposition、task-node-execution、progress-report）。
- Python `compileall`：PASS。
- 小程序全部 `.js` `node --check`：PASS。
- 数据库迁移：本功能无新增迁移；既有迁移合同包含在累计 pytest 中。

## 关键业务边界

- 协同人只能查看任务/完成本人授权节点，不能任务级汇报或资源申请。
- 卡点状态联动由后端决定，客户端不得直接写 task status。
- `actual_hours` 保持系统派生，进度接口不可提交。

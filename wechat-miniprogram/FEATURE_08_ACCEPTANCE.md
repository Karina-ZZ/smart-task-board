# 功能08验收记录：节点执行、依赖与节点负责人权限

## 范围
- 已生效任务在 `in_progress/blocked/pending_report` 执行态允许节点执行；拆解中、拆解失败、待验收和终态拒绝。
- AI节点必须由 `owner_employee_no` 或明确节点owner授权执行；主承办人不能因任务关系越权完成别人节点，历史owner为空节点仅保留主承办人兼容兜底。
- pending节点先开始、in_progress节点再完成；开始与完成均再次校验前置依赖，活动卡点禁止完成。
- 节点完成写 `completed_at`，`actual_hours` 由 `completed_at - planned_start_time` 系统计算；进度接口不再接受人工 actual_hours。
- 可见节点开始/完成动作携带 `taskVersion + Idempotency-Key`，后端以 operation_logs.request_id 持久化节点幂等结果。
- 微信任务详情仅本人负责节点显示“开始节点/完成节点”；任务级汇报、任务变更、完成验收仍未开放。

## 门禁
- 节点Service + API受影响专项：41 passed。
- 全量非 PostgreSQL：396 passed。
- 微信累计：11组 PASS（新增 `task-node-execution.test.js`）。
- Python compileall / 全部微信JS node --check：PASS。
- PostgreSQL专项因当前容器无 PostgreSQL/psycopg 未执行、未伪装通过。

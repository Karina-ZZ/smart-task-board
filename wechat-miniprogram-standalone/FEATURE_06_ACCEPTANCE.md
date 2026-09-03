# 功能06验收记录：创建人三步创建、真实草稿与确认发送

## 范围

- 创建流程固定为：描述任务 → 信息确认 → 确认发送；不出现创建人节点拆解。
- 信息确认展示原始AI描述、任务级字段、人员选择抽屉、绩效指标抽屉、开始/截止、权重、突发、汇报周期、验收标准。
- 保存草稿真实写后端 `tasks.status=draft`，修改携带 `taskVersion`；前端本地仅做页面恢复。
- 创建请求拒绝 `nodes/dependencies/nodeParticipants/estimatedHours/actualHours`。
- 确认发送前校验必填、日期、人员、版本；发送后为 `pending_acceptance`（客户端兼容展示 `pending_accept`），`effective_at` 为空且正式节点数为0。
- 自建自办仍进入待接受，不自动接受。
- 发送事务只创建一条主承办人待接受通知；管理员全局读取不自动成为通知订阅者或接受者。
- 绩效建议可由创建人确认或选择不关联；服务端确认动作限定创建人。
- `Idempotency-Key` 在确认发送动作通过 `operation_logs.request_id` 持久化去重，不新增业务表。

## 门禁

- 后端 Service：134 passed。
- 后端 API（SQLite导入/合同环境）：87 passed。
- 全量非 PostgreSQL：383 passed，21项 PostgreSQL 专项因当前容器无 PostgreSQL/psycopg 被测试标记排除。
- 迁移合同：31 passed；本功能无新 Alembic 迁移。
- 微信累计：9组 PASS（新增 task-creation + task-creation-api）。
- Python compileall / 全部微信JS node --check：PASS。
- 功能06未修改接受后AI拆解实现；功能07边界未提前进入。

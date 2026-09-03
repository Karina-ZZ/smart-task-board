# 功能10验收记录｜任务变更与创建人生命周期控制

状态：DONE（当前环境可执行门禁）

## 本功能完成

- 主承办人在 `in_progress` / `blocked` / `pending_report` 可提交真实变更申请；同一任务只允许一条待审批申请。
- 创建人可审批/拒绝变更；申请、审批、拒绝、取消均写审计并通知相关人员。
- 变更申请禁止夹带 `estimated_hours`、`actual_hours`，也禁止通过变更申请绕过专用“更换承办人”动作。
- 新增正式 `PUT /tasks/{taskId}/assignee`：仅创建人可更换主承办人，校验用户有效、taskVersion和Idempotency-Key。
- 更换承办人后任务回 `pending_accept`，清空 accepted/effective/decomposition 当前投影；新承办人必须重新接受并触发新的AI拆解。
- 拆解中更换承办人时当前attempt同事务 invalidated，迟到结果不能生效。
- 创建人可在白名单未完成状态撤回/取消；blocked/pending_report纳入合法状态；通知当前承办人。
- 微信“更多操作”已接真实变更申请、变更审批/拒绝、更换承办人、撤回、取消；无假成功按钮。
- 功能11完成/验收动作仍未在详情页开放。

## 累计门禁

- 后端非 PostgreSQL：401 passed，21 PostgreSQL 专项 deselected（当前环境缺 PostgreSQL/psycopg，未伪装通过）。
- 微信累计：13 组 PASS（新增 task-change-lifecycle）。
- Python `compileall`：PASS。
- 小程序全部 `.js` `node --check`：PASS。
- 数据库迁移：本功能无新增迁移。

# 功能13验收记录：通知、提醒、协办节点承接与生产演示清理

## 最终口径

- 功能13以 `docs/FEATURE_13_NOTIFICATION_RULES.md` 为P0规则基线。
- AI拆解成功本身不向创建人或主承办人发送纯知悉通知。
- AI拆解出的主承办人本人节点直接进入可执行状态；协办人节点服务端写 `assignment_status=pending`，只向该节点负责人发送“节点待承接”。
- 协办人必须由本人通过真实动作接口接受或拒绝节点承接；拒绝原因必填，并通知主承办人处理责任问题。
- 协办节点未接受前，节点开始、临期、到期和逾期等执行提醒全部禁止；节点开始/完成动作同样由服务端拒绝。
- 节点临期按工作跨度动态计算：`<=1`个工作日提前2个工作小时；`>1且<=3`个工作日提前4个工作小时；`>3`个工作日提前1个工作日。
- 临期计算复用统一工作时间能力，不读取 `task_nodes.estimated_hours`；临期时点不得早于 `planned_start_time`，与开始提醒同一时点时只保留开始提醒。
- 已完成、已取消、任务未生效、任务终止、负责人不匹配或尚未接受的节点，即使历史 reminder rule 到点，也在创建通知前再次校验并停用，不发送执行通知。
- 节点逾期扫描只纳入 `assignment_status=accepted` 的有效节点。
- 通知列表只查询 `notifications.recipient_employee_no == 当前用户`；高管和管理员身份本身不能读取其他员工私人通知。
- 通知只提供上下文和跳转目标，不授予权限；通知目标根据任务当前状态、节点承接状态和当前用户关系动态派生，真正动作接口再次鉴权。
- 生产通知中心以 `actionRequired` 表示“待处理”，不以客户端已读状态作为业务红点；历史 `read_at`/read接口仅保留兼容，不作为生产待处理语义。
- 提醒/通知扫描和发送调度仅允许 active admin scheduler 调用；普通员工、高管不能手工触发全局扫描/发送。
- 企业微信provider失败时对同一 `notification_id` 采用5/10/20分钟退避；不因重试重复创建业务通知。
- 微信生产页面移除“全部已读”假业务语义、身份切换和重置演示数据；localStorage/本地存储不再承载这些业务状态。

## 数据模型与迁移

新增Alembic迁移：`b1c2d3e4f5a6`（文件：`alembic/versions/fa1b2c3d4e5_feature13_node_assignment_and_reminders.py`），从 `a9c4e7f1b2d3` 升级。

`task_nodes` 新增：

- `assignment_status`：`pending / accepted / rejected`；历史节点迁移时默认回填 `accepted`，避免升级后锁死既有任务。
- `assignment_responded_at`：协办人接受/拒绝时间。
- `assignment_reject_reason`：协办人拒绝原因。

`reminder_rules.reminder_type` 检查约束增加：

- `node_start`
- `node_due`

既有 `due_soon` / `overdue` 在 `node_id` 非空时继续承担节点临期/逾期语义。

没有新增第二套通知表或节点提醒表；继续复用 `reminder_rules + notifications`。

## 后端动作与关键入口

- `POST /api/v1/tasks/{taskId}/nodes/{nodeId}/actions/accept-assignment`
- `POST /api/v1/tasks/{taskId}/nodes/{nodeId}/actions/reject-assignment`
- `POST /api/v1/reminders/scan`（仅active admin scheduler）
- `POST /api/v1/notifications/send-pending`（仅active admin scheduler）
- `GET /api/v1/notifications`（仅当前用户自己的站内通知）

协办节点接受后才调用统一节点执行提醒调度，拒绝后生成主承办人待处理通知。节点执行仍沿用原节点负责人、依赖、任务状态和版本/幂等校验。

## 微信端交互

- “节点待承接”通知点击后进入对应任务详情并定位 `nodeId`。
- 待承接协办节点展示“接受承接 / 无法承接”；拒绝弹出原因输入并提交真实后端动作。
- 接受成功后页面刷新任务版本和节点承接状态，之后才展示正常节点执行能力。
- 通知中心按后端派生 `notificationType / targetType / actionRequired / canOpen / unavailableReason` 展示和跳转；旧通知若任务已处理、关系已失效或任务不可见，不保留过期写动作。
- 工作台/通知入口红点使用待处理事项语义，不因“看过消息”自动消失。
- 我的页面生产态不提供角色切换或重置演示数据。

## 最终门禁（正式ZIP冻结前工作目录）

- 后端累计非PostgreSQL：`436 passed`。
- PostgreSQL opt-in：`21 skipped`；当前环境未启用 `RUN_POSTGRESQL_INTEGRATION=1` 且未提供批准的隔离 PostgreSQL 测试库，未宣称通过。
- 迁移合同：`32 passed`。
- Alembic：单一head `b1c2d3e4f5a6`。
- Python `compileall`：PASS。
- 微信功能01～13累计：`16`组 PASS。
- 微信全部 `.js` `node --check`：PASS。
- React：累计包未安装 `web/node_modules`，本环境未执行 React test/lint/build；不得计为PASS。
- Ruff：当前执行环境未安装可用ruff命令，本轮未执行；不得计为PASS。

## 范围边界

功能13未提前实现：

- DEV-16高管基础看板新增能力；
- DEV-17员工负荷快照任务下钻；
- 未经用户确认的“待承接再次催办间隔”；
- 协办拒绝后的完整重新分配UI；
- 任务级逾期升级通知创建人的新规则；
- 用户未确认的节点逾期固定钟点。

## 正式ZIP反向验收

冻结候选ZIP后，从ZIP重新解压到全新目录，不复用开发工作树，重复执行完整门禁：

- 后端累计：`436 passed, 21 skipped`。
- 迁移合同：`32 passed`。
- Alembic head：`b1c2d3e4f5a6`。
- Python compileall：PASS。
- 微信功能01～13累计：16组 PASS。
- 微信全部JS `node --check`：PASS。

候选包反向验收通过后才生成正式功能13交付包；正式包再次解压复验后方可报告交付成功。

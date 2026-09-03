# 更新日志 (Changelog)

本仓库所有显著变更都记录在此文件中。格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

## [功能 13] - 2026-09-03 — 通知、提醒与协办节点承接

### 新增

#### 后端

- **协办节点承接机制**
  - `task_nodes` 新增 `assignment_status`（`pending / accepted / rejected`）、`assignment_responded_at`、`assignment_reject_reason` 字段；历史节点迁移时默认回填 `accepted`，升级不锁死既有任务。
  - 新增动作接口：`POST /api/v1/tasks/{taskId}/nodes/{nodeId}/actions/accept-assignment`（接受承接）与 `reject-assignment`（拒绝承接，原因必填）。
  - AI 拆解出的主承办人本人节点直接进入可执行状态；协办人节点服务端写 `assignment_status=pending`，只向该节点负责人发送「节点待承接」通知。
  - 拒绝承接后自动通知主承办人处理责任问题。
- **节点执行提醒体系**
  - `reminder_rules.reminder_type` 约束新增 `node_start`、`node_due`；节点临期/逾期继续复用 `due_soon` / `overdue`。
  - 临期提前量按工作跨度动态计算：`≤1` 工作日提前 2 个工作小时；`>1 且 ≤3` 提前 4 个工作小时；`>3` 提前 1 个工作日；复用统一工作时间能力，不读取 `estimated_hours`。
  - 新增调度接口：`POST /api/v1/reminders/scan`、`POST /api/v1/notifications/send-pending`（仅 active admin scheduler 可调用）。
  - 企业微信 provider 失败按 5/10/20 分钟退避重试，同一 `notification_id` 不重复创建业务通知。
- **通知中心**
  - `GET /api/v1/notifications` 仅返回当前用户自己的站内通知；高管/管理员不能读取他人私人通知。
  - 通知按后端派生 `notificationType / targetType / actionRequired / canOpen / unavailableReason` 提供上下文与跳转目标，不授予权限，动作接口再次鉴权。
- **数据库迁移**
  - 新增 Alembic 迁移 `b1c2d3e4f5a6`（`fa1b2c3d4e5_feature13_node_assignment_and_reminders.py`），自 `a9c4e7f1b2d3` 升级。
- **测试与脚本**
  - 新增 `tests/integration/test_feature13_postgresql.py` 功能 13 集成测试。
  - 新增 `scripts/provision_postgresql_gate_docker.sh`、`scripts/run_postgresql_gate.sh` PostgreSQL 门禁脚本。

#### 微信小程序（生产版本与独立版同步）

- 「节点待承接」通知点击进入任务详情并定位节点；待承接节点提供「接受承接 / 无法承接」操作，拒绝需填写原因。
- 通知中心按后端派生字段展示与跳转；旧通知在任务已处理、关系失效或任务不可见时不再保留过期写动作。
- 红点改为「待处理事项」语义（`actionRequired`），不因已读而消失。
- 移除生产页面的「全部已读」假语义、身份切换与重置演示数据；这些状态不再落入 localStorage。
- 新增 `tests/notifications-node-assignment.test.js` 小程序测试。

#### 文档

- 新增 `docs/FEATURE_13_NOTIFICATION_RULES.md`：功能 13 P0 通知与节点承接规则基线。
- 新增 `docs/FEATURE_13_ACCEPTANCE.md`：功能 13 验收记录（口径、数据模型、接口、微信端交互、门禁证据）。
- 新增 `docs/POSTGRESQL_GATE_EXECUTION_REPORT.md`：PostgreSQL 门禁执行报告。
- 更新 `docs/DEVELOPMENT_PLAN_V1.1.md`、`FEATURE_COVERAGE.md`、根 README 的累计交付状态。

### 修复 / 强化

- 协办节点未接受前，节点开始、临期、到期、逾期提醒与开始/完成动作全部由服务端拒绝。
- 已完成、已取消、任务未生效/终止、负责人不匹配或未接受的节点，历史 reminder rule 到点时在创建通知前再次校验并停用。
- 节点逾期扫描只纳入 `assignment_status=accepted` 的有效节点。
- AI 拆解成功不再向创建人/主承办人发送纯知悉通知。

### 不兼容变更

- 无（迁移对历史数据安全回填，接口只增不改）。

## [功能 12] - 2026-09-03 — 全量源码首次入库

- 完整项目源码（FastAPI 后端 + React Web 前端 + 微信小程序 + 云函数）首次上传。
- 功能 01～12 累计交付：任务创建与状态机、AI 结构化拆解、节点执行、进度汇报与卡点闭环、完成验收与返工、企业绩效口径（25%+25%+25%+20%+5%，阈值 70）、五维负荷等。
- 小程序独立版置于 `wechat-miniprogram-standalone/`。
- 新增 `docs/ACCEPTANCE_STANDARDS.md` 单功能验收标准（10 + 1 条硬性条件）。
- 整理 `docs/` 与 `docs/reference/` 中文文件名为可读 UTF-8。

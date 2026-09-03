# 功能07验收记录：主承办人接受、AI拆解与任务生效

## 范围

- 只有主承办人可从 `pending_accept/pending_acceptance` 接受；接受后进入 `decomposing`，不直接进入 `in_progress`。
- 接受事务确认主承办关系并创建唯一有效 `task_decomposition_records`；任务保持 `effective_at` 为空且不生成正式节点。
- AI拆解使用专用 `task_decomposition.md`；服务端强制5～10个节点、负责人来自已确认人员池、时间窗合法、依赖无环，并禁止任何预计/计划/AI工时字段。
- 有效结果同一事务写 `task_nodes`、`task_node_dependencies`、节点提醒、状态日志和通知；随后写 `effective_at` 并进入 `in_progress`。
- 无节点/字段缺失/非法负责人/非法时间窗/循环依赖/预计工时等结果进入 `decomposition_failed`，且不写正式节点。
- 拆解失败可由主承办人重试；旧attempt保留。创建人在拆解中取消/撤回时运行attempt在同一事务失效，迟到结果不得落库。
- 微信任务详情的“接受任务/退回任务”已接真实API；汇报、验收等后续功能仍保持禁用。
- 微信拆解页改为真实服务端状态恢复：查询attempt、pending执行、running轮询、failed重试、succeeded返回详情；刷新/离页不使用本地假成功。

## 数据与迁移

- 新表：`task_decomposition_records`。
- `tasks` 新增：`effective_at`、`decomposition_status`、`latest_decomposition_id`。
- `task_nodes` 新增：`decomposition_id`、`source_type`、`blocked_reason`。
- 新增 Alembic：`f8a1b2c3d4e5_add_task_decomposition_lifecycle.py`。

## 门禁

- 功能07专项 + 受影响后端合同：46 passed。
- 全量非 PostgreSQL：393 passed。
- 微信累计：10组 PASS（新增 `task-decomposition.test.js`，并升级功能03阶段静态合同为“允许功能07接受/退回，继续禁止功能08～11生产动作”）。
- Python compileall / 全部微信JS `node --check`：PASS。
- 当前容器仍无 PostgreSQL/psycopg，因此 PostgreSQL 专项未执行、未伪装为通过。
- 未提前开放节点完成、进度汇报、任务变更或验收按钮。

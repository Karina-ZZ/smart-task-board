# 功能16 / DEV-18 Test9 发布候选修复与门禁报告

> 日期：2026-09-04  
> 基线：Test8 Release Candidate + 用户本地 `DEV-18_本地验收测试报告.md` / `DEV-18_测试失败详情与报错.md`  
> 范围：只收口 Test8 本地真实门禁暴露的问题，不新增产品功能17，不改变任务状态机、Outbox并发算法或普通员工权限边界。

## 1. 本轮结论

Test9 已完成以下代码收口：

1. F3 PostgreSQL 测试污染根因：business 集成 fixture 改为按 `task_id` 清理完整任务图，而不是依赖手工登记的 reminder ID。
2. F1 归档搜索权限契约：保持“employee scope 不扩大业务任务可见性”，PG 业务集成改由 executive + department scope 验证授权归档搜索。
3. F2 `available-actions.nodes`：改为稀疏动作投影，只返回 `allowed_actions` 非空的节点；完整节点事实继续由任务详情 DTO 提供。
4. F4/F5：不改 Outbox `FOR UPDATE SKIP LOCKED` 和 task_version 产品逻辑，等待 F3 修复后由 PostgreSQL 全量连续运行验证。
5. F6 Ruff：已统一整理 Python import block；4 个 `import app.models` 明确保留为 SQLAlchemy metadata 注册副作用并加 `noqa: F401`；ChatService 的 E402 已移动到模块顶部。
6. 正式 PostgreSQL 门禁增强为“同一已迁移数据库连续两轮全量 PostgreSQL suite”，第二轮专门证明测试无残留。
7. 新增 Test9 静态合同，防止上述清理、权限和 available-actions 契约回退。

## 2. F1：归档权限契约

产品代码 `PermissionScopeService.can_access_task()` 不修改：

```text
employee + department/user scope + 无直接任务关系
→ 不获得额外业务任务查看权

executive + 有效授权 scope
→ 可按授权范围只读查看
```

因此 `test_business_capabilities_postgresql.py` 中用于 archive search 的 `scoped_user` 改为 `role_type="executive"`。

原有非 PG 回归：

```text
test_employee_scope_does_not_expand_business_task_visibility
```

继续锁定 employee 不扩权。

## 3. F2：available-actions 稀疏节点合同

旧返回：

```json
{
  "nodes": [
    {"node_id": "A", "allowed_actions": ["start_node"]},
    {"node_id": "B", "allowed_actions": []},
    {"node_id": "C", "allowed_actions": []}
  ]
}
```

Test9 正式返回：

```json
{
  "nodes": [
    {"node_id": "A", "allowed_actions": ["start_node"]}
  ]
}
```

原因：`available-actions` 只投影“当前用户现在能做什么”；节点完整列表属于任务详情 DTO。React 现有调用通过 Map 查询，节点不存在时自然按无动作处理，兼容稀疏返回。

本轮新增非 PG 回归：

```text
test_available_node_actions_only_projects_actionable_nodes
```

并同步 PostgreSQL API 契约和 Test8 静态合同。

## 4. F3：PostgreSQL task graph 清理

旧 fixture 主要按 `CreatedRecords.reminder_ids` 等手工记录清理。业务过程中会自动生成未登记的 ReminderRule，造成：

```text
reminder_rules
→ task_nodes FK 残留
→ teardown rollback
→ 整个任务图污染下一用例
→ F4/F5 假失败/顺序依赖
```

Test9 改为先按 `created.task_ids` 清理任务图，顺序覆盖：

```text
notifications
reminder_rules
task_issues
task_conflicts
task_completion_reviews
task_change_requests
task_performance_matches
task_priority_scores
task_progress_reports
task_archives
task_status_logs
task_node_dependencies
task_node_participants
task_participants
ai_extraction_records
task_nodes
↓
Task.latest_decomposition_id = NULL
↓
task_decomposition_records
↓
tasks
```

然后再清理 task input、metric、scope、profile、parameter、operation log、user、department 等独立记录。

这样测试清理不再依赖“业务过程中是否记住了每一个自动生成 ID”。

## 5. F4/F5 处理原则

本轮没有修改：

- `ReminderNotificationService.send_pending()` 的 `FOR UPDATE SKIP LOCKED`；
- notification 唯一约束；
- task_version 自增；
- task_status_logs 版本逻辑。

用户本地已经证明 F4 在隔离、Feature13 整文件和 5×20 压力下通过，F5 单跑通过。因此 Test9 先消除 F3 污染，再由全量 PG 连续两轮判断是否仍存在产品问题。

## 6. Ruff 收口

针对用户本地报告：

```text
125 × I001
4   × F401
1   × E402
= 132
```

本轮执行：

- 对 `app/`、`tests/`、`alembic/`、`cloud-functions/`、`scripts/` 的 import block 做统一排序和格式整理；
- `datetime.UTC` 等 import member 按 Ruff/isort 风格排序；
- 4 个 `import app.models` 保留并明确标注：
  `# noqa: F401 - register all ORM models in Base.metadata`；
- `cloud-functions/ChatService/tests/test_task_intake.py` 的 `Path` import 移到模块顶部；
- Python >100 字符行仍为 0。

当前执行容器没有 Ruff 二进制，DNS 也无法安装 Ruff 0.16.6，因此本报告**不宣称真实 `ruff check .` 已经 0 error**。正式结论必须由用户本地 Ruff 0.16.6 / Test9 gate 复验。

为降低批量 import 整理风险，本轮额外做了 AST 语义比较：除正式需要修改的 `app/services/task_board_query.py` 外，`app/`、`alembic/`、`cloud-functions/` 的非 import AST 与 Test8 基线一致。

## 7. Test9 PostgreSQL 门禁增强

`scripts/run_postgresql_gate.sh` 现在要求：

```text
空隔离库
↓
alembic upgrade head
↓
PostgreSQL suite pass 1/2
↓
不清库
↓
PostgreSQL suite pass 2/2
↓
5 个并发用例 × 20轮
↓
非 PG 全量回归
```

目标：

```text
PG pass 1 = 28/28
PG pass 2 = 28/28
Outbox/并发压力 = 100/100
```

第二遍失败即认为测试隔离仍有缺陷，不允许发布。

新增：

```text
scripts/run_test9_release_gate.sh
tests/test_test9_release_candidate_contract.py
```

Test9 release gate 还调整了执行顺序：先跑所有不需要真实凭据的 PG / 小程序 / Web / ChatService 纯逻辑门禁，再检查 WeCom/Qwen 真实环境。这样缺真实凭据时不会掩盖普通代码回归。

## 8. 当前环境实际测试结果

### 已执行

```text
python compileall                         PASS
后端非 PostgreSQL 全量                   500 passed / 28 deselected
Test9 + Test8 静态合同                   PASS
迁移/依赖定点                            40 passed
微信小程序累计                           21/21 PASS
微信 JS node --check                     PASS
ChatService task_intake/auth/config       PASS
shell bash -n                             PASS
Python >100字符行                         0
Web源码                                  与 Test8 完全无差异
微信源码                                 与 Test8 完全无差异
```

### 当前容器无法真实执行

```text
PostgreSQL 16 / 28项PG：无 PostgreSQL、Docker、psycopg
Ruff 0.16.6：无二进制且容器 DNS 不可用
Web npm lint/test/build：web/node_modules 不存在，离线无法 npm ci
真实 WeCom E2E：仍需真实 AppID / HTTPS 后端 / env / fresh wx.qy.login code
```

因此当前 Test9 是**修复候选**，最终放行必须依赖用户本地真实环境重跑。

## 9. 用户本地正式重跑

推荐直接运行：

```bash
./scripts/run_test9_release_gate.sh
```

要求 Python 3.12 虚拟环境。脚本会安装开发依赖、执行 Ruff、空库迁移、PG 连续两轮、并发压力、非 PG、小程序、Web、ChatService，再进入真实 WeCom/Qwen 环境门禁。

如果先只验证最关键 PostgreSQL：

```bash
PYTHON_BIN=python3.12 \
POSTGRES_TEST_DATABASE_URL='postgresql+psycopg://...@127.0.0.1:46479/smarttaskboard_core_test' \
./scripts/run_postgresql_gate.sh
```

数据库必须是批准的空隔离测试库。

## 10. Test9 最终通过标准

| 门禁 | 通过标准 |
|---|---:|
| Python | 3.12.x |
| Ruff | 0 error |
| Alembic | 单 head `c2d3e4f5a6b7`，空库升级成功 |
| PostgreSQL 第一轮 | 28/28 |
| PostgreSQL 第二轮（不清库） | 28/28 |
| 5×20并发 | 100/100 |
| 非 PG | 500/500 或更高 |
| Web | ESLint 0；Vitest 109/109或更高；build PASS |
| 微信小程序 | 21/21或更高；JS syntax PASS |
| 微信开发者工具 | 编译 PASS |
| WeCom真实E2E | 真实环境到位后 PASS；否则唯一允许的 BLOCKED |

## 11. 当前判定

```text
代码修复：完成
当前容器可执行回归：通过
真实 PostgreSQL：待用户本地 Test9 连续两轮确认
真实 Ruff：待用户本地 Ruff 0.16.6确认
真实企业微信：BLOCKED，等待真实环境
```

在 PG 28/28 × 2 和 Ruff 0 之前，不宣称 V1.1 最终发布成功。

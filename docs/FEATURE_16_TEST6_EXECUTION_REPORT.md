# 功能16 / DEV-18 Test6 定点修复报告

## 输入证据

Test6 基于 Test5，并吸收本地 Test4 真实执行结果：PostgreSQL 16 空库迁移成功，28 项 PG 为 19 passed / 9 failed，Outbox 5×20 共 100 次全部通过；Ruff 仍有 E501/I001 与一个 F821；真实企业微信因 touristappid/缺真实凭证阻塞。

## 本轮关闭项

1. **Outbox 并发：关闭**。以本地真实 PostgreSQL 100/100 为准，不再修改产品发送逻辑。
2. **PG `_command()` 解包错误**：测试改为接收单个 `CreateTaskDraftCommand`。
3. **F821 `replace` 未定义**：补齐 `from dataclasses import replace`。
4. **V1.1 client hours 回流**：新增静态门禁，business-capability PG fixture 禁止 `hours/estimated_hours/actual_hours`。

## 本轮真实产品缺陷修复

### 1. TaskDecompositionRecord DetachedInstanceError

`TaskDecompositionService.get_latest()` 使用只读 UnitOfWork。UnitOfWork 在未 commit 时退出会 rollback，SQLAlchemy 会过期仍绑定的 ORM 实例；路由在 session 关闭后再用 Pydantic 序列化会触发 DetachedInstanceError。

修复：读取完成后在 UoW 退出前 `session.expunge(record)`，只脱离该已完整加载的标量记录，不改变事务或状态机。

### 2. `/available-actions` 200 变 500

服务实际返回 priority_quadrant / importance_score / urgency_score / remaining_hours / sort_rank，但严格的 `AvailableActionsResponse` 未声明这些字段。FastAPI 响应模型校验会把合法服务结果转成 500。

修复：将上述字段补进 `AvailableActionsResponse`，与 TaskBoardSummaryResponse 的既有合同一致；新增 API/Schema 回归。

## 当前本环境结果

- 定点回归：46 passed
- 后端非 PostgreSQL：488 passed / 28 deselected
- 微信小程序：20/20 PASS
- 微信 JS node --check：PASS
- Python compileall：PASS
- PostgreSQL 真实 28 项：当前容器无 PG，必须以本地 Test6 实跑结果为准
- Ruff：当前容器无 Ruff；已修唯一 F821，E501/I001 仍需本地 Ruff 给出 Test6 实际剩余数量
- 真实企业微信：仍需真实 AppID、CorpId、AgentId、Secret 与登录态

## Test6 最关键复核目标

1. `python -m pytest -m postgresql -q` → 目标 28 passed / 0 failed / 0 skipped。
2. Outbox 5×20 → 继续保持 100/100 PASS。
3. `python -m ruff check .` → F821 必须消失；继续处理剩余 E501/I001 直到 0。
4. 真实 WeCom 配置齐全后执行 `scripts/run_wecom_real_e2e.py` 与真机 E2E。

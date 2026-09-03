# 功能16 / DEV-18 Test5 并行完善记录

生成日期：2026-09-03
基线：`Test4-smart-task-board-feature16-release-gate.zip`
状态：**IN_PROGRESS / 等待真实 PostgreSQL + Ruff + 企业微信实测结果**

## 1. 本轮边界

Test5 不新增产品功能，不修改任务、权限、状态机、看板、通知业务规则。本轮只完善已知发布门禁：

1. 收敛 PostgreSQL V1.1 集成测试夹具；
2. 加固 Outbox 并发防回流断言；
3. 增加 Test5 正式发布门禁脚本；
4. 增加真实企业微信身份 smoke/E2E 脚本与执行清单；
5. 仅清理本轮改动文件中的明显 Ruff 风险，不做全仓无关格式化。

与 Test4 比较，`app/` 业务源码无修改。

## 2. PostgreSQL V1.1 测试夹具收敛

新增/强化 `tests/integration/v11_postgresql_helpers.py`：

- `send_accept_and_decompose_v11()` 统一执行：
  - `submit_for_confirmation`
  - `confirm_and_send` 或 `confirm_self_assigned`
  - `accept_task`
  - 确认进入 `decomposing`
  - `complete_v11_decomposition`
  - 真实测试节点落库后进入 `in_progress`
- 测试夹具不得恢复 creator-owned nodes / dependencies / hours 的旧流程。

相关静态合同测试已经更新，防止以后 PostgreSQL E2E 再绕过 V1.1 接受与 AI 拆解流程。

## 3. Outbox 并发测试加固

Test4 已把错误的 `Barrier(2)` provider 脚手架改为“单发送阻塞 + 第二 worker 同时抢锁”。Test5 继续增加：

- provider 只调用一次；
- 最终 `send_status == sent`；
- `retry_count == 0`；
- `fail_reason is None`；
- 第二次执行 `send_pending()` 返回空列表；
- 已 sent 通知不得被再次调用 provider。

产品 `ReminderNotificationService.send_pending()` 本轮未修改。

## 4. Test5 正式发布门禁

新增 `scripts/run_test5_release_gate.sh`，硬要求：

- Python 3.12；
- 激活独立 venv；
- `pip install -e ".[dev]"`；
- `pip check`；
- `ruff check .`；
- compileall；
- PostgreSQL 16 空隔离库；
- Alembic 升级到单一 head；
- 28 项 PostgreSQL 集成测试；
- 5 项并发场景 × 20 轮；
- 非 PostgreSQL 累计回归；
- 真实企业微信 backend env；
- 真实通义千问 ChatService env；
- 小程序真实 AppID、`mode="api"`、非空 `apiBaseUrl`；
- 小程序累计测试和全部 JS 语法；
- React lint/test/build。

缺任何正式条件时输出 `[TEST5 BLOCKED]`，不允许用 skip 作为发布成功证据。

## 5. 真实企业微信身份 E2E

新增：

- `scripts/run_wecom_real_e2e.py`
- `docs/FEATURE_16_REAL_WECOM_E2E.md`

脚本要求使用真实 `wx.qy.login()` 一次性 code，但不会读取或打印 CorpSecret、Qwen Key、access token、refresh token。

自动验证：

1. `/health/live`；
2. `/health/ready`；
3. `/api/v1/auth/wecom`；
4. `wecom_user_id -> employee_no`；
5. `auth_mode=wecom`；
6. `/api/v1/me` 的 roles / permissions / scopes；
7. `/api/v1/auth/ai-token`；
8. refresh rotation 后身份不变；
9. logout 后 refresh token 失效。

真实 disabled / 未绑定 / 错误 corpid、高管下钻和完整任务生命周期仍按文档做设备端 E2E。

## 6. 当前可执行门禁结果

当前容器可执行结果：

- Python compileall：PASS；
- 后端非 PostgreSQL：**485 passed / 28 deselected**；
- Test5 + V1.1 发布合同定点：**8 passed**；
- 微信小程序累计：**20/20 PASS**；
- 微信 JS `node --check`：**48 文件 PASS**；
- Test5 shell gate 语法：PASS；
- 本轮新增/修改 Python 文件：无 >100 字符长行。

## 7. 当前环境无法正式确认的门禁

本执行环境仍不具备：

- Python 3.12；
- PostgreSQL 16 / Docker；
- Ruff 可执行文件（网络不可用，无法安装）；
- 真实 CorpId / AgentId / Secret / AppID；
- 真实 DashScope Key；
- React `node_modules`（当前环境无法联网安装）。

因此本报告不宣称：

- PostgreSQL 28/28 PASS；
- Outbox 5×20 PASS；
- Ruff 0 error；
- 真实企业微信 E2E PASS；
- 真实 Qwen PASS；
- DEV-18 发布成功。

这些以本地 Test4/Test5 的真实环境结果为最终证据。

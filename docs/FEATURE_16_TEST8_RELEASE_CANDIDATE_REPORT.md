# 功能16 / DEV-18 Test8 发布候选执行报告

## 1. 本轮目标

Test8 以 Test7 的 AI 字段回填体验版为代码基线，同时针对本地 Test6 真实验收暴露的
6 项 PostgreSQL 债务与 202 项 Ruff 历史债务做收口。

本轮不新增产品功能。AI 人员字段继续遵守：只解析用户明确指定的人；缺失或歧义时
留空并追问/让用户选择，不根据岗位、部门、技能、负荷或直属关系推荐人员。

## 2. AI 字段回填保留项

- 明确提及主承办人、汇报对象、验收人、协同人时，唯一匹配后写入结构化草稿。
- 多轮 clarification 合并到完整草稿，前端直接 hydrate 已解析字段。
- 用户未明确提及人员时保持 null/[]，禁止主动推荐。
- reviewer 不再默认继承 report_to。
- V1.1 AI 创建草稿固定 `estimated_hours=None`，不再从 extraction/corrections 写客户端工时。
- 小程序 Test7 hydration 行为未改动。

## 3. Test6 六项 PostgreSQL 债务的代码处理

### 3.1 completed 与 archived 旧测试合同

Feature11 正式业务行为仍保持“验收通过后同一事务完成并自动归档”。
Test8 更新 PostgreSQL 测试合同：最终状态断言 `archived`，并同时检查
`completion_approved` 与 `task_archived` 日志和对应版本。

### 3.2 task_archives 外键清理与套件污染

下列 PostgreSQL 测试清理流程已在删除 tasks 前删除 TaskArchive：

- `test_core_workflow_postgresql.py`
- `test_core_workflow_api_postgresql.py`
- `test_completion_review_api_postgresql.py`
- `test_task_board_api_postgresql.py`

目的：消除 teardown FK 失败以及由失败清理导致的 pending notification 残留。
产品 Outbox 的 `FOR UPDATE SKIP LOCKED` 实现未修改。

### 3.3 V1.1 hours 泄漏

`TaskIntakeService.create_draft_from_extraction()` 现在显式使用
`estimated_hours=None`。业务规则“V1.1 创建阶段客户端/AI不可写 hours”未放宽。

### 3.4 pending node 可用动作旧断言

按当前正式节点动作合同：尚未开始且依赖已满足的节点只有 `start_node`；
任务级 `submit_progress_report` / `report_task_issue` 不属于节点动作。
对应 PostgreSQL 集成测试已更新，不修改产品节点状态机。

## 4. Ruff 历史债务处理

- 已对 Python import block 做全仓规范化排序。
- 已拆分历史长行。
- 当前静态扫描 `app/`、`tests/`、`alembic/`、`cloud-functions/`、`scripts/`
  中 **>100 字符 Python 行 = 0**。
- 新增 Test8 静态合同会持续检查 line-length 物理上限。

本执行容器没有 Ruff 二进制，且容器 DNS 无法安装 Ruff。因此这里**不宣称真实
`ruff check .` 已为 0**；正式 Test8 门禁脚本仍要求真实 Ruff 通过。

## 5. 当前环境已实际执行结果

| 检查 | 结果 |
|---|---|
| `compileall` | PASS |
| 后端非 PostgreSQL 全量 | **495 passed / 28 deselected** |
| Feature11 / task-board / business-capability 等定点回归 | **76 passed** |
| Test8 + V1.1 静态合同 | **16 passed** |
| ChatService task-intake 脚本 | PASS |
| 微信小程序累计测试 | **21/21 PASS** |
| 小程序 JS `node --check` | PASS |
| Python >100 字符行 | **0** |
| Web 源码 | 与 Test7 基线无差异 |

## 6. 当前环境无法正式声明通过的门禁

### PostgreSQL 28 项

当前执行环境没有 Docker/PostgreSQL 服务端，因此本轮无法在这里真实执行 28 项 PG。
Test8 已根据 Test6 的六个真实失败根因完成代码/测试合同修复，但正式结论仍需在用户
已有的 PostgreSQL 16 环境执行 `scripts/run_test8_release_gate.sh`。

目标：`28 passed / 0 failed / 0 skipped`。

### Outbox 5×20

产品 Outbox 代码本轮未修改。正式门禁仍会执行 5 个并发用例各 20 次，目标 100/100。

### Ruff

正式环境运行 Ruff 0.16.5，目标 `ruff check .` 为 0 error。

### Web

当前容器没有 `web/node_modules` 且无法联网重新安装，因此未重复执行 Web lint/test/build。
Web 目录相对 Test7 完全未修改。正式 Test8 门禁仍执行 `npm ci`、lint、109+ tests、build。

### 真实企业微信

仍需真实 AppID、CorpID/AgentID/Secret、部署后端、真实测试员工以及新鲜
`wx.qy.login` code。缺条件时正式门禁必须 BLOCKED，不允许假通过。

## 7. 新增正式门禁

新增：`scripts/run_test8_release_gate.sh`

顺序：Python 3.12 -> pip check -> Ruff -> Test8 快速合同 -> PostgreSQL 空库迁移 ->
28 项 PG -> 5×20 并发 -> 非 PG -> WeCom/Qwen 配置 -> 小程序 -> Web。

## 8. 当前判定

**Test8 是发布候选代码包，不是已完成真实环境放行的最终发布证明。**

当前已完成：AI 字段回填保留、Test6 六项 PG 根因定点修复、历史长行清零、import
规范化、非 PG / 小程序 /定点回归通过。

待用户真实环境确认：PG 28/28、Outbox 100/100、Ruff 0、Web 全绿、真实 WeCom E2E。

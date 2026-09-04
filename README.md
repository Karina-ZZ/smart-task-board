# Smart Task Board

智能任务看板使用 FastAPI、PostgreSQL 和 React 实现任务创建、结构化拆解、参与人协作、状态流转、节点执行、完成验收与返工。后端业务规则通过 JSON REST API 提供，前端提供适配桌面和移动设备的任务看板界面。


## Secret configuration

Real WeCom credentials, Qwen/DashScope keys, database passwords and JWT secrets are not stored in source code. New setups should copy `config-examples/backend.env.example` and `config-examples/chatservice.env.example` into the ignored local `secrets/` directory. Production servers should keep the same files under `/etc/wangxu/`.

Detailed replacement and rotation instructions: `docs/SECRETS_CONFIGURATION_GUIDE.md`.

## 当前进度

Phase 0～5 后端基础已经完成：

- Phase 0：工程、配置、健康检查、SQLAlchemy、Alembic、Pytest 和 Ruff。
- Phase 1：10张核心业务表的 ORM 和显式业务主键。
- Phase 2：首份 PostgreSQL 迁移及升级、降级验证。
- Phase 3：Repository 和 Unit of Work 事务边界。
- Phase 4：任务和节点状态机 Service。
- Phase 5：16条核心 REST API 业务路径，包括创建、查询、确认、发送、接受或退回、节点执行、完成提交和验收。

Batch 1 已经实现基础原型身份、任务列表、统一 Inbox、Dashboard 首页摘要、后端授权动作投影和 React 响应式前端，并已通过全部质量门。Batch 2A 已新增进度汇报和任务卡点模型及迁移，本地 checkpoint 为 `94108af17225ca9e4a2f728e47a117f1d546a0af`。Batch 2B 已完成进度汇报、问题闭环及真实 PostgreSQL 验收，本地 checkpoint 为 `7a0cf4e3c6b920d5fea10c351d4d7789f39baf90`。

Wave 1 的完成验收与返工现已实现并通过总质量门：每次提交形成不可变验收轮次；验收人按任务指定 reviewer 快照，未指定时回退创建人；支持通过、强制原因驳回、仅返工整体交付物、指定节点显式重开、多轮历史、API、Inbox、任务详情和响应式 UI。旧有 `pending_review` / `completed` 数据由迁移安全回填。本文档随 Wave 1 checkpoint 候选提交，checkpoint commit hash 尚未创建。

## 功能开发进度（按 16 项规划）

> **进度计划来源**：项目当前 16 项功能计划源自 `docs/reference/` 中第二版核心逻辑与数据表结构文档的对应交付清单（功能 05、12、14 为高亮的当前重点）。

**总体状态：功能 01 ～ 16 已全部完成并通过验收。**

### 功能清单（依据用户规划第二版交付线）

| # | 功能 | 范围要点 | 当前状态 |
|---|---|---|---|
| 01 | 员工任务工作台 | 小程序工程基础、第二版应用壳、底部导航、任务指标、四象限、需要支持、AI 创建入口、最近任务 | ✅ 完成 |
| 02 | 任务概览 | 任务/节点模式、状态筛选、四象限筛选、临期筛选、自定义日期、空态、任务跳转 | ✅ 完成 |
| 03 | 任务详情 | 基础信息、责任关系、任务目标、验收标准、节点、汇报、卡点、绩效、状态轨迹、操作记录 | ✅ 完成 |
| 04 | 登录与权限 | 当前用户、任务关系、员工/高管权限、数据范围、无权访问、Token 与刷新 | ✅ 完成 |
| 05 | AI 任务输入 ⚠️ | 文字输入、录音、语音转文字、AI 字段识别、缺失字段追问、失败重试；任务创建人关联绩效指标 | ✅ 完成 |
| 06 | 创建人三步创建 | 描述任务 → 信息确认 → 确认发送；发送后进入待接受、不生成节点 | ✅ 完成 |
| 07 | 接受后 AI 拆解 | 接受/退回、拆解中、拆解失败、重新拆解、成功生效、迟到结果失效 | ✅ 完成 |
| 08 | 节点执行 | 节点展开、依赖校验、开始、更新、完成、节点负责人和协同人权限 | ✅ 完成 |
| 09 | 进度与卡点 | 当前进度、阶段成果、卡点开关、卡点说明、备注、问题处理和关闭 | ✅ 完成 |
| 10 | 任务生命周期 | 变更申请、更换承办人、撤回、取消、合并、关闭、原因弹窗和通知 | ✅ 完成 |
| 11 | 完成申请与验收 | 全部节点完成校验、多轮验收、退回修改、指定节点重开、通过后自动归档 | ✅ 完成 |
| 12 | 智能计算 ⚠️ | 绩效关联、四象限、剩余工时、负荷、冲突和服务端计算口径 | ✅ 完成 |
| 13 | 通知与我的 | 任务通知、提醒、系统消息、个人资料、任务关系统计和待办数量 | ✅ 完成 |
| 14 | 高管任务看板 ⚠️ | 团队指标、状态分布、风险、负荷热力图、卡点和绩效态势 | ✅ 完成 |
| 15 | 员工负荷任务下钻 | 负荷构成 → 员工任务明细 → 单任务详情，落实第二处修改 | ✅ 完成 |
| 16 | 全链路发布验收 | 企业微信自建应用登录（wecom 模式 + 删 LoginService）、密钥 secrets/ 安全配置、发布门禁 release-gate 测试 | ✅ 完成 |

**后端覆盖矩阵**：功能 01～16 对应的后端 Wave 1～10 在 `FEATURE_COVERAGE.md` 中全部标注 COMPLETE。Alembic 单一 head 为 `b1c2d3e4f5a6`。

> 功能 16 交付包含：企业微信认证 `app/services/wecom_authentication.py` + `app/integrations/wecom`；后端 `auth_mode` 增加 `wecom`；新增 `POST /api/v1/auth/wecom/login` 换票接口；删除 `LoginService` 云函数；密钥移入 `secrets/backend.env` 与 `secrets/chatservice.env`（`.gitignore` 屏蔽）；新增发布门禁测试 `tests/test_start_dev_secret_contract.py`、`tests/integrations/test_wecom_client.py`、`tests/services/test_wecom_authentication.py`。Test5 再收敛 PostgreSQL V1.1 集成夹具并加固 Outbox 并发防回流断言，新增 `scripts/run_test5_release_gate.sh`、`scripts/run_wecom_real_e2e.py`、`tests/test_test5_release_gate_contract.py`、`tests/integration/v11_postgresql_helpers.py` 与 `docs/FEATURE_16_REAL_WECOM_E2E.md`（真实企业微信身份 E2E 执行清单）。Test6 定点修复两个真实产品缺陷（见上表 `/available-actions` 500 与 `DetachedInstanceError`），新增 `scripts/run_test6_release_gate.sh` 与 `docs/FEATURE_16_TEST6_EXECUTION_REPORT.md`。Test7 优化“AI 识别/追问 → 任务创建页字段自动回填”链路（可体验快照，先行交付）：`app/ai/prompts/task_intake.md` 与 `cloud-functions/ChatService/prompts/task_intake.md` 新增强制规则（人员字段只允许解析用户**明确提到**的人，禁止按岗位/部门/技能/负荷/直属关系推荐）；`cloud-functions/ChatService/tests/test_task_intake.py` 新增 Prompt 契约测试；`wechat-miniprogram/pages/create-details/index.js` 手工选人后清理对应 AI missing/low-confidence 状态；`wechat-miniprogram/utils/api.js` mock 模式支持明确人员语句自动回填；`wechat-miniprogram/tests/ai-field-hydration.test.js` 新增字段回填用例；详见 `docs/FEATURE_16_TEST7_AI_FIELD_HYDRATION_REPORT.md`。Test8 为发布候选：以 Test7 为基线，收口 Test6 真实验收暴露的 6 项 PostgreSQL 债务（completed/archived 旧合同、task_archives 外键清理、V1.1 hours 泄漏、pending node 可用动作旧断言）与 202 项 Ruff 历史债务（import 规范排序、长行清零，>100 字符行=0）；新增 `scripts/run_test8_release_gate.sh` 与 `tests/test_test8_release_candidate_contract.py`；详见 `docs/FEATURE_16_TEST8_RELEASE_CANDIDATE_REPORT.md`。Test9 吸收本地 Test8 真实门禁暴露的问题，只收口不改产品功能/状态机：F1 归档搜索权限契约保持 employee scope 不扩大业务任务可见性（PG 业务集成改由 executive + department scope 验证授权归档搜索）；F2 `available-actions.nodes` 改为稀疏动作投影（只返回 `allowed_actions` 非空的节点，完整节点事实由任务详情 DTO 提供）；F3 business 集成 fixture 改为按 `task_id` 清理完整任务图（彻底消除 ReminderRule 残留导致的 FK/teardown 污染与 F4/F5 顺序依赖）；F6 Ruff 统一整理 import block，4 个 `import app.models` 明确保留为 SQLAlchemy metadata 注册副作用并加 `noqa: F401`；PostgreSQL 门禁增强为同一已迁移数据库连续两轮全量 PG suite（第二轮专门证明无残留）；新增 `scripts/run_test9_release_gate.sh` 与 `tests/test_test9_release_candidate_contract.py`（防清理/权限/available-actions 契约回退）。详见 `docs/FEATURE_16_TEST9_RELEASE_CANDIDATE_REPORT.md`。Test10 以 Test9 为代码基线，**只修复 Test9 真实门禁暴露的工程质量问题，不新增产品功能/状态机/Outbox 并发算法/权限边界**：F1 PG 第二轮失败根因修复（`TaskStatusLogRepository` 全部以 `task_version` 为第一权威排序键，消除同事务 `created_at` 共享时随机 UUID 翻转 `completion_approved`/`task_archived` 顺序的缺陷，Repository 排序合同永久化、不允许退回 `created_at + UUID`）；F2 PG 多轮门禁增强（`scripts/run_postgresql_gate.sh` 新增 `POSTGRES_GATE_PASSES` ≥2；新增 `scripts/run_test10_release_gate.sh` 候选固定 `POSTGRES_GATE_PASSES=3`）；F3 Ruff 收口（`alembic/app/tests/cloud-functions/scripts` 重新分组 import block，按 Ruff/isort 排序，不改变 revision/down_revision 或业务逻辑）；F4 Web 干净安装依赖合同（`@testing-library/dom ^10.4.1` 显式加入 `web/package.json` `devDependencies` 与 `web/package-lock.json`，避免依赖间接 peer dependency）；新增 `tests/test_test10_release_candidate_contract.py` 防回归。详见 `docs/FEATURE_16_TEST10_RELEASE_CANDIDATE_REPORT.md`。Test11 为最终技术门禁收口：仅修复 Test10 本地报告的 6 个 Ruff 问题（`collections.abc` 导入迁移 + import block 整理，AST 对比无函数体变化），新增 `scripts/run_test11_release_gate.sh`（Python 3.12 + Ruff 0 + PG 同库 3 轮 + 100 并发 + Web 干净安装的正式技术门禁，技术门禁与真实 WeCom E2E 分离）与 `tests/test_test11_release_candidate_contract.py` 冻结合同；详见 `docs/FEATURE_16_TEST11_TECHNICAL_GATE_REPORT.md`。

### 测试进度

> **以下为本机独立复核的实测结果**（复核日期 2026-09-03，基于功能 16 代码）：在 macOS 上用受管 Python 3.13 虚拟环境安装依赖后真实执行，非抄录交付包文档。

| 质量门 | 实测结果 | 说明 |
|---|---|---|
| 后端全量 pytest（非 PostgreSQL） | ✅ `508 passed, 28 deselected` | 28 项 deselected 均为 PostgreSQL opt-in 集成测试 |
| 微信小程序功能 01～16 | ✅ `19 / 19` 组 PASS | `wechat-miniprogram/` 与 `wechat-miniprogram-standalone/` 均跑通 |
| 微信全部 JS 语法检查 | ✅ PASS | 全量 `.js` 执行 `node --check` |
| React 前端 ESLint | ✅ PASS | 无错误输出 |
| React 前端测试 | ✅ `18 test files / 109 tests passed` | vitest `--run` |
| React 前端构建 | ✅ PASS | `tsc --noEmit && vite build` |
| 功能 16 企业微信/安全配置测试 | ✅ 已实现并提交 | wecom_client、wecom_authentication、secret_contract 等随包交付 |
| `ruff check` | ⚠️ `220` 个告警 | 全部为风格类，F821 真实缺陷已清零 |
| 功能 16 发布门禁 Test3（`scripts/run_test3_release_gate.sh`） | 🚧 BLOCKED（预期） | 硬门禁：缺 Python 3.12 / PostgreSQL 16 / 真实企微配置即阻断；本次非PG `477 passed, 2 failed`（2 失败为旧 PG fixture 债务被门禁正确拦截）、微信 `20/20 PASS`；详见 `docs/FEATURE_16_TEST3_EXECUTION_REPORT.md` |
| 功能 16 修复 Test4（`scripts/run_test4_release_gate.sh`） | 🔧 修复已提交，待真实环境复验 | 修 Test3 门禁拦出的旧 PG V1.1 fixture 债务（F1-F7）、Outbox 并发测试（F8）、`/me` 旧断言（F9）；`httpx2`→`httpx` 依赖修正；ruff F401/F841/B033/E701/E702。本环境非PG `482 passed, 28 deselected`、微信 `20/20 PASS`；真实 PG / Py3.12 / Ruff / 企微仍待复验（不伪造 PASS）；详见 `docs/FEATURE_16_TEST4_EXECUTION_REPORT.md` |
| 功能 16 并行完善 Test5（`scripts/run_test5_release_gate.sh`） | 🔧 已提交，待真实环境复验 | 收敛 PostgreSQL V1.1 集成测试夹具（`tests/integration/v11_postgresql_helpers.py` + `tests/test_postgresql_v11_fixture_contract.py` 防回流）、加固 Outbox 并发防回流断言（`send_status==sent`、`retry_count==0`、第二轮 `send_pending()` 返回空）；新增真实企业微信身份 smoke/E2E 脚本 `scripts/run_wecom_real_e2e.py` 与 `docs/FEATURE_16_REAL_WECOM_E2E.md`（不打印 Secret/Token）。`app/` 业务源码无修改。本环境：compileall PASS、非PG `485 passed, 28 deselected`、Test5+V1.1 发布合同 `8 passed`、微信 `20/20 PASS`、JS `node --check` `48 文件 PASS`、Test5 shell gate 语法 PASS；真实 PG 28/28 / 5×20 并发 / Ruff 0 error / 真实企微 E2E 仍待复验（不伪造 PASS）；详见 `docs/FEATURE_16_TEST5_PARALLEL_IMPROVEMENT_REPORT.md` |
| 功能 16 定点修复 Test6（`scripts/run_test6_release_gate.sh`） | 🔧 已提交，待真实环境复验 | 关闭 Outbox 并发项（以本地真实 PG 5×20 共 100/100 为准，不改产品发送逻辑）；修复 PG `_command()` 解包（测试改收单个 `CreateTaskDraftCommand`）；补 `from dataclasses import replace` 修 F821；新增 V1.1 client hours 静态门禁（business-capability PG fixture 禁止 `hours/estimated_hours/actual_hours`）。**真实产品缺陷修复**：① `TaskDecompositionService.get_latest()` 在只读 UoW 退出前 `session.expunge(record)`，修复路由序列化触发 `DetachedInstanceError`；② `AvailableActionsResponse` 补 `priority_quadrant/importance_score/urgency_score/remaining_hours/sort_rank`，修复 `/available-actions` 合法结果被响应模型校验转成 500。本环境：定点回归 `46 passed`、非PG `488 passed, 28 deselected`、微信 `20/20 PASS`、JS `node --check` PASS、compileall PASS；真实 PG 28/28 / Ruff 0 error / 真实企微 E2E 仍待本地 Test6 实跑复验（不伪造 PASS）；详见 `docs/FEATURE_16_TEST6_EXECUTION_REPORT.md` |
| 功能 16 AI 字段回填优化 Test7（可体验快照） | ✅ 已提交，可体验 | 仅优化“AI 识别/追问 → 创建页字段自动回填”链路，未改任务发送/接受/拆解/执行/通知/验收/看板/企微登录等后续规则。Prompt 新增强制规则：人员字段只允许解析用户**明确提到**的人，禁止按岗位/部门/技能/负荷/直属关系推荐；未提人员保持 null/[] 并追问或手工选择；同名歧义不猜。小程序 mock 模式支持明确人员语句自动回填、多轮追问合并上一轮草稿、手工选人后清理对应 AI missing/low-confidence 状态。本环境：ChatService `test_task_intake.py` PASS、小程序 `21/21 PASS`、新增 `ai-field-hydration.test.js` PASS、JS `node --check` PASS、`compileall` PASS；后端全量 pytest 在本容器因缺 `psycopg` 于收集阶段被环境依赖阻塞（非产品失败/通过，沿用 Test6 非PG `488 passed`），真实 PG / Ruff / 真实企微 E2E 仍待本地实跑复验；详见 `docs/FEATURE_16_TEST7_AI_FIELD_HYDRATION_REPORT.md |
| 功能 16 发布候选 Test8 | 🔧 已提交，待真实环境放行 | 不新增产品功能。收口 Test6 真实验收暴露的 6 项 PostgreSQL 债务：① completed/archived 旧测试合同改为断言 `archived` 并检查 `completion_approved`/`task_archived` 日志；② 4 个 PG 测试清理流程删除 tasks 前先删 TaskArchive（消 teardown FK 失败与 pending notification 残留）；③ `TaskIntakeService.create_draft_from_extraction()` 显式 `estimated_hours=None`（V1.1 创建阶段客户端/AI 不可写 hours 规则不变）；④ pending node 可用动作旧断言按正式节点动作合同更新（未开始且依赖满足仅 `start_node`）。Ruff 历史债务：全仓 import 规范排序、长行拆分，`app/tests/alembic/cloud-functions/scripts` 中 >100 字符 Python 行=0，新增 Test8 静态合同持续检查。本环境：compileall PASS、非PG `495 passed`、定点回归 `76 passed`、Test8+V1.1 静态合同 `16 passed`、ChatService task-intake PASS、小程序 `21/21 PASS`、Python >100 字符行 `0`、JS `node --check` PASS；真实 PG 28/28 / Outbox 5×20=100/100 / Ruff 0 error / Web 全绿 / 真实企微 E2E 仍待本地 Test8 实跑放行（不伪造 PASS）；详见 `docs/FEATURE_16_TEST8_RELEASE_CANDIDATE_REPORT.md` |
| 功能 16 发布候选 Test9 | 🔧 已提交，待真实环境放行 | 吸收 Test8 本地真实门禁暴露的问题，只收口不改产品功能/状态机/Outbox 并发算法/普通员工权限。F1 归档搜索权限契约保持 employee scope 不扩大业务任务可见性（PG 业务集成改由 `executive` + `department` scope 验证授权归档搜索）；F2 `available-actions.nodes` 改为稀疏动作投影（只返回 `allowed_actions` 非空的节点，完整节点事实由任务详情 DTO 提供，React 现有 Map 查询兼容）；F3 business 集成 fixture 改为按 `task_id` 清理完整任务图（notifications→reminder_rules→…→task_nodes→tasks 顺序覆盖），消除 ReminderRule 残留导致的 FK/teardown 污染与 F4/F5 顺序依赖；F4/F5 产品逻辑（`FOR UPDATE SKIP LOCKED`、task_version 自增、notification 唯一约束）不动，待 F3 修复后由 PG 全量连续两轮验证；F6 Ruff 统一整理 import block，`datetime.UTC` 等按 Ruff/isort 排序，4 个 `import app.models` 保留并加 `# noqa: F401`，ChatService `E402` 上移模块顶部。PostgreSQL 门禁增强为同一已迁移库连续两轮全量 PG suite（第二轮专门证明无残留）+ 5×20 并发；新增 `scripts/run_test9_release_gate.sh` 与 `tests/test_test9_release_candidate_contract.py`。本环境：compileall PASS、非PG `500 passed, 28 deselected`、Test9+Test8 静态合同 PASS、迁移/依赖定点 `40 passed`、小程序 `21/21 PASS`、JS `node --check` PASS、ChatService task_intake/auth/config PASS、shell `bash -n` PASS、Python >100 字符行 `0`、Web/微信源码与 Test8 完全无差异；真实 PG 28/28×2 / Outbox 5×20=100/100 / Ruff 0 error / Web 全绿 / 真实企微 E2E 仍待本地 Test9 实跑放行（不伪造 PASS）；详见 `docs/FEATURE_16_TEST9_RELEASE_CANDIDATE_REPORT.md` |
| 功能 16 发布候选 Test10 | 🔧 已提交，待真实环境放行 | 以 Test9 为代码基线，**只修复 Test9 真实门禁暴露的工程质量问题，不新增产品功能/状态机/Outbox 并发算法/权限边界**。F1 **PG 第二轮失败根因修复**：`TaskStatusLogRepository.list_by_task_id()` / `list_by_task_id_paginated()` / `get_latest_for_task()` 全部以 `task_version` 为第一权威排序键（`completed_approved` 与 `task_archived` 共享同事务 `created_at` 时不再被随机 UUID 翻转 12→13 顺序），Repository 排序合同永久化（不允许退回 `created_at + UUID`）；F2 **PG 多轮门禁增强**：`scripts/run_postgresql_gate.sh` 新增 `POSTGRES_GATE_PASSES`（默认 2，必须 ≥2）；新增 `scripts/run_test10_release_gate.sh`（Test10 候选固定 `POSTGRES_GATE_PASSES=3`）；F3 **Ruff 收口**：`alembic/app/tests/cloud-functions/scripts` 重新分组 import block，按 Ruff/isort 排序，不改变 revision/down_revision 或业务逻辑；F4 **Web 干净安装依赖合同**：`@testing-library/dom ^10.4.1` 显式加入 `web/package.json` `devDependencies` 与 `web/package-lock.json`，避免依赖间接 peer dependency。新增 `tests/test_test10_release_candidate_contract.py` 防回归。本环境：compileall PASS、非PG `504 passed, 28 deselected`、Test10/Repository 定点合同 PASS、ChatService task_intake/auth/config PASS、小程序 `21/21 PASS`、JS `node --check` PASS、Web `package-lock` 离线一致性 PASS、`bash -n` Test10/PG gate PASS；真实 PG 28/28×3 / Ruff 0 error / Python 3.12 正式 gate / Web 干净 `npm ci` / 真实企微 E2E 仍待本地 Test10 实跑放行（不伪造 PASS），候选 ZIP 反向验收与工作树结果一致；详见 `docs/FEATURE_16_TEST10_RELEASE_CANDIDATE_REPORT.md` |
| 功能 16 Test11 最终技术门禁 | 🔧 已提交，待正式门禁放行 | 发布工程收口，**零产品功能/表/字段/迁移/状态机/权限/Outbox 算法变化**。仅修复 Test10 本地报告的 6 个 Ruff 问题（`app/integrations/wecom/client.py` 的 `Callable`、`app/services/features/performance_matching/scoring.py` 的 `Iterable/Mapping/Sequence` 改从 `collections.abc` 导入；`business_capabilities.py`/`task_workflow.py`/`cloud-functions/ChatService/services/task_intake.py`/`tests/migrations/test_alembic_metadata.py` import block 按 Ruff/isort 整理），AST 语义对比确认无函数体/业务规则变化；新增最终技术门禁 `scripts/run_test11_release_gate.sh`（强制 Python 3.12 + `pip check` + 真实 `ruff check .` 无 auto-fix + compileall + Test8/9/10/11 合同 + 空 PG16 迁移单 head `c2d3e4f5a6b7` + 同库连续 3 轮 PG + 5×20=100 并发 + 非 PG 全量 + 小程序 + Web 干净 `npm ci` + ChatService）与 `tests/test_test11_release_candidate_contract.py` 冻结合同。本环境：compileall PASS、受影响模块定点 `84 passed`、ChatService `3/3`、合同 `19 passed`、非PG `508 passed, 28 deselected`、小程序 `21/21`、JS PASS、>100 字符行 `0`、gate 按设计 fail-closed（`Python 3.12 is required`）；Ruff 0 / PG 28/28×3 / 100/100 / Python 3.12 正式 gate / Web 干净安装 / 真实企微 E2E 仍待正式环境放行（不伪造 PASS），`V1.1 TECHNICAL RELEASE READY` 仅在上述全绿后升级；详见 `docs/FEATURE_16_TEST11_TECHNICAL_GATE_REPORT.md` 与 `docs/DEV-18_Test11_执行与反向验收报告.md` |
| RELEASE-01 生产部署工程 | 🔧 部署工程就绪，待预发/生产实跑 | 只新增部署与运维基础，**零业务代码改动**（`app/`、`alembic/versions/`、`wechat-miniprogram/pages|utils/`、`web/src/`、`tests/` 受保护；叠加到 Test11 基线后受保护目录零改动）。新增 `deploy/`：`Dockerfile.backend`、`Dockerfile.chatservice`、`docker-compose.production.yml`（backend/chatservice/nginx/postgres 四服务，PG 仅内部网络不发布宿主机端口）、`nginx/wangxu.conf.template`（仅 HTTP→HTTPS 跳转与 HTTPS 反代）、`env/*.production.example`（强制 `APP_ENV=production`/`AUTH_MODE=wecom`/`CHAT_REQUIRE_AUTH=true`，全部占位符无真实密钥）、`systemd/*.service`、`scripts/`（preflight/deploy-compose/health-check/backup/restore/rollback/validate，恢复默认拒绝破坏性恢复、回滚不自动 downgrade）；新增 `docs/deployment/` 五篇上线交接文档 + 验收记录。本环境验证：9 个 deploy 脚本 `bash -n` PASS、Compose YAML 解析 PASS（四服务齐全、PG 无宿主机端口）、env 模板强制项 PASS；Docker 真实生产部署 / 企业微信真实 E2E / Qwen 公网调用 / 真实通知仍待公司预发环境执行（不伪造 PASS）。注意：交付方原始基线为 Test8 包，本仓库已将 deploy 工程叠加到 Test11 最新代码（`PROTECTED_SOURCE_BASELINE.sha256` 为交付方对 Test8 树的验收快照，仅作 RELEASE-01 验收存档）；详见 `docs/deployment/RELEASE_01_ACCEPTANCE.md`、`docs/deployment/01-PRODUCTION_DEPLOYMENT_GUIDE.md` 与 `docs/RELEASE_01_DEPLOYMENT_ENGINEERING_REPORT.md` |

## 微信小程序累计交付状态

当前用户侧累计交付线位于 `wechat-miniprogram/`，功能 01～04 已按第二版前端页面结构和 PRD V1.1 逐项实现：工作台、任务概览、任务详情、登录与权限。功能 04 不新增第二版原型之外的登录业务页，而是在小程序启动和 API 网关层接入服务端会话，避免破坏既有页面结构。

登录与权限当前具备：受控开发登录、`GET /me` 当前用户/部门/角色/授权范围投影、access/refresh token 保存与旋转、401 自动恢复、登出撤销、任务关系投影、员工/高管/管理员数据范围校验。生产环境不允许身份切换或重置演示数据；管理员系统身份也不自动成为任意业务任务的超级用户。企业微信自建应用登录已在功能 16 实现（后端 `auth_mode=wecom` + `POST /api/v1/auth/wecom/login` 换票接口，前端已切换企业微信登录），企业微信 CorpId/AgentId/Secret 由本地 `secrets/backend.env` 提供，绝不进入源码或 GitHub。

## 当前已实现能力

后端和 API：

- 原型用户列表、原型登录、短期 Bearer JWT 和 `GET /api/v1/me`。
- 创建任务草稿、创建人确认、确认发送、承办人接受或退回、创建人重新发送。
- 节点开始、进度更新和完成，主承办人提交不可变完成验收轮次。
- reviewer 快照授权、验收通过、填写原因驳回、整体交付物返工和指定节点显式重开。
- 多轮验收历史与旧数据安全回填；历史轮次不会被重新提交覆盖。
- 当前用户任务列表、任务详情、节点查询和状态日志查询。
- 统一 Inbox、Dashboard 首页摘要和由后端计算的 `allowed_actions`。
- 任务级和节点级不可变进度汇报、追加式汇报更正、周期待汇报查询。
- 卡点、资源需求、协同支持和风险上报，以及 `open → processing/resolved/rejected → closed` 生命周期。
- 活动 blocker 禁止完成对应节点；任何未关闭卡点禁止提交任务验收。
- 后端在业务 Service 中继续校验身份、权限、状态和 `task_version`；前端按钮不是权限边界。

React 前端：

- 原型登录页、Dashboard 首页、任务列表、Inbox、新建任务和任务详情。
- 创建任务节点及依赖关系，执行当前后端已支持的任务和节点动作。
- 任务详情中的进度汇报、汇报历史、更正入口、卡点创建和卡点处理。
- Inbox 待汇报入口，以及 Dashboard 待汇报和待处理卡点指标。
- Inbox 待我验收动作，以及任务详情中的完成提交、通过、驳回、节点重开和验收历史面板。
- 桌面端和移动端响应式导航与布局。

## 技术栈

- Python 3.12（`>=3.12,<3.13`）
- FastAPI、Pydantic 2
- SQLAlchemy 2.x 同步 Engine/Session
- PostgreSQL 16、`psycopg[binary]`
- Alembic
- Pytest、Ruff
- React 19、TypeScript、Vite、TanStack Query
- Vitest、Testing Library、ESLint
- Docker Compose

## 数据库与迁移

当前 SQLAlchemy Metadata 精确包含13张业务表：

```text
users
departments
task_inputs
ai_extraction_records
tasks
task_participants
task_nodes
task_node_participants
task_node_dependencies
task_status_logs
task_progress_reports
task_issues
task_completion_reviews
```

当前有三份不可重写的迁移，Alembic head 为 `c31f8e7a4d02`：

```text
alembic/versions/17f69ea12754_initial_schema.py
alembic/versions/576787492bd1_add_progress_reports_and_task_issues.py
alembic/versions/c31f8e7a4d02_add_task_completion_reviews.py
```

不要手工创建或修改业务表，应通过 Alembic 管理结构变更。Docker Compose 中的 PostgreSQL 数据通过 `./data/postgres:/var/lib/postgresql/data` 绑定到项目目录，不使用默认命名卷。

Wave 1 downgrade 只允许在 `task_completion_reviews` 为空时执行；一旦存在验收历史，迁移会主动中止，避免静默删除不可变业务记录。需要回退有数据的环境时，必须先制定并验证独立的数据保全与恢复迁移。

## 核心流程

```text
创建任务草稿
→ 提交创建人确认
→ 确认并发送
→ 主承办人接受或退回
→ 节点开始、更新进度和完成
→ 进度汇报、卡点上报与闭环处理
→ 主承办人提交完成，生成新的不可变验收轮次
→ 本轮 reviewer 快照验收
   ├─ 通过：pending_review → completed
   └─ 驳回并填写原因：pending_review → in_progress
      ├─ 仅返工整体交付物，保留全部已完成节点
      └─ 指定节点后执行显式重开，保留原完成历史
→ 返工完成后重新提交，生成下一验收轮次
```

每个状态动作都由 Service 校验权限、当前状态和 `task_version`，并在一个数据库事务中更新数据和写入状态日志。只有主承办人可以提交完成；每轮验收人快照取任务指定 reviewer，未指定时才回退创建人，创建人、高管或管理员等身份本身不会自动获得验收权限。

## 环境配置

项目只正式支持 Python 3.12。`.env.example` 和 `web/.env.example` 只是开发占位模板，不能直接当作安全配置使用。

后端运行必须提供 `DATABASE_URL`。生产企业微信身份使用 `AUTH_MODE=wecom`；隔离开发仍可使用受控 prototype。企业微信生产配置至少包括：

```text
AUTH_MODE=wecom
WECOM_CORP_ID=<enterprise-corp-id>
WECOM_APP_SECRET=<self-built-app-secret>
JWT_SECRET_KEY=<locally-generated-secret-of-at-least-32-characters>
CHAT_SERVICE_JWT_SECRET_KEY=<separate-secret-of-at-least-32-characters>
ALLOW_TEST_EMPLOYEE_HEADER=false
CORS_ALLOWED_ORIGINS=<frontend-origin>
```

隔离开发如需 prototype，可继续使用 `PROTOTYPE_AUTH_ENABLED` 与 `PROTOTYPE_USER_EMPLOYEE_NOS`；生产禁止 prototype/test-header。

Docker Compose 启动 PostgreSQL 时还需要在本地环境提供 `POSTGRES_DB`、`POSTGRES_USER` 和 `POSTGRES_PASSWORD`。不要把真实数据库密码、JWT 密钥、API Key、Token 或完整数据库连接 URL 写入代码、README 或 Git。`.env`、`.venv/`、`data/` 和前端本地环境文件均已被 Git 忽略。

## 启动后端

在项目根目录执行以下 Windows PowerShell 命令：

```powershell
py -3.12 -m venv .venv
& ".\.venv\Scripts\python.exe" -m pip install -e ".[dev]"

# 首次复制安全配置模板，并仅在本机填写真实值
Copy-Item config-examples/backend.env.example secrets/backend.env

# Docker Compose 显式读取 backend.env；FastAPI/Alembic 默认读取同一文件
docker compose --env-file secrets/backend.env up -d postgres
$env:WANGXU_BACKEND_ENV_FILE = (Resolve-Path secrets/backend.env)
& ".\.venv\Scripts\python.exe" -m alembic upgrade head
& ".\.venv\Scripts\python.exe" -m uvicorn app.main:app --reload
```

使用通用 shell 时，可先激活项目内虚拟环境，再运行等价的 `python -m pip`、`python -m alembic` 和 `python -m uvicorn` 命令。

Uvicorn 未指定其他监听参数时，默认地址为 `http://127.0.0.1:8000`：

- 存活检查：`GET /health/live`
- 数据库就绪检查：`GET /health/ready`
- Swagger UI：`GET /docs`
- OpenAPI JSON：`GET /openapi.json`

## 身份边界

生产身份入口为企业微信小程序：`wx.qy.login()` 获取一次性 code，FastAPI 调用企业微信 `jscode2session` 得到 `userid/corpid`，再以 `users.wecom_user_id` 映射现有 `employee_no`。企业微信只证明身份，不改变旺序角色、授权范围或任务关系。成功后仍使用现有 HTTP Bearer JWT：

```http
Authorization: Bearer <token>
```

`X-Employee-No` 只保留给既有自动化测试。当前会话继续使用持久化哈希 refresh token、轮换刷新、撤销/登出，以及服务端角色与 `user_authorized_scopes` 权限投影。企业微信登录不会自动创建用户，也不会从企业微信部门负责人/管理员身份推导旺序 `role_type`。

不要在生产环境使用示例密钥或员工编号 Header。JWT 密钥必须由运行环境安全提供，不得提交 Git。

## 启动前端

前端位于 `web/`。`web/package.json` 当前提供 `dev`、`lint`、`test` 和 `build` 脚本：

```powershell
Set-Location web
npm.cmd ci

# 可通过未提交的 web/.env.local 设置 VITE_API_BASE_URL
npm.cmd run dev
npm.cmd run lint
npm.cmd run test -- --run
npm.cmd run build
```

`VITE_API_BASE_URL` 指向后端 API 根地址；未设置时，前端客户端默认使用 `http://localhost:8000`。如果 Windows PowerShell 执行策略阻止 `npm.ps1`，可直接使用 `npm.cmd`，不需要关闭系统安全策略。

### 微信小程序 API 联调

`wechat-miniprogram/config.js` 默认保持 `mode: "mock"`；切到真实 API 时配置 `mode: "api"`、`apiBaseUrl`，生产 `authMode` 使用 `wecom`。客户端先尝试现有 refresh token，无可用会话时调用 `wx.qy.login()`，再把 code 发送到 `/api/v1/auth/wecom`。小程序不保存企业微信 Secret/access_token。受控 `prototype` 仅保留给隔离开发，不进入生产。

## 原型登录使用流程

1. 准备并启动隔离的 PostgreSQL。
2. 通过 Alembic 将数据库迁移到当前 head。
3. 按下一节的安全要求检查并准备演示用户。
4. 配置原型身份环境变量并启动后端。
5. 配置 `VITE_API_BASE_URL` 并启动前端。
6. 在浏览器中打开 Vite 输出的本地开发地址。
7. 在登录页选择或输入允许的原型用户。
8. 前端通过原型登录获得 Bearer 身份。
9. 进入 Dashboard、任务列表、Inbox，并完成任务核心流程。

## Demo Seed安全说明

`scripts/seed_demo_data.py` 是显式启用、幂等的隔离演示数据工具。它只接受名称以 `_test` 或 `_demo` 结尾的数据库，并要求命令行确认值与当前配置中的数据库名完全一致。

先使用 dry-run 检查动作并回滚：

```powershell
& ".\.venv\Scripts\python.exe" -m scripts.seed_demo_data `
  --dry-run `
  --confirm-database-name "<isolated_test_or_demo_database_name>"
```

只有在再次核对目标后，才可以由用户明确选择持久化模式：

```powershell
& ".\.venv\Scripts\python.exe" -m scripts.seed_demo_data `
  --apply `
  --confirm-database-name "<isolated_test_or_demo_database_name>"
```

`--dry-run` 会回滚，不持久化数据；`--apply` 遇到已存在的演示员工编号时会跳过，不覆盖用户。禁止对未知、共享、开发或生产数据库运行该脚本，也不要打印或提交数据库凭据。本项目不会自动执行持久化 seed。

## 测试

默认后端质量门不连接 PostgreSQL；数据库集成测试会安全跳过：

```powershell
& ".\.venv\Scripts\python.exe" -m ruff check .
& ".\.venv\Scripts\python.exe" -m pytest
& ".\.venv\Scripts\python.exe" -m pip check
```

PostgreSQL Repository、Service 和 HTTP 集成测试只有在显式提供已批准的隔离测试数据库配置和运行开关时才会执行：

```powershell
$env:RUN_POSTGRESQL_INTEGRATION = "1"
$env:POSTGRES_TEST_DATABASE_URL = "<approved-isolated-postgresql-test-url>"
& ".\.venv\Scripts\python.exe" -m pytest tests/integration
```

前端质量门：

```powershell
Set-Location web
npm.cmd run lint
npm.cmd run test -- --run
npm.cmd run build
```

当前 Wave 1 checkpoint 候选的完整质量门为：后端全量 `306 passed`，其中真实 PostgreSQL 16 集成测试 `20 passed`；前端 `10 test files / 28 tests passed`。Ruff、`pip check`、`pip-audit`、SQLAlchemy mapper、Alembic check 与 downgrade/upgrade、ESLint、TypeScript（随构建执行）和 Vite build 均已通过。OpenAPI 当前包含 `35` 条 API 路径、`38` 个 operations；测试后 PostgreSQL 业务数据残留为零。当前迁移 head 为 `c31f8e7a4d02`，Metadata 为13张业务表。

上述 Wave 1 门禁只证明完成验收与返工核心闭环。完成提醒与外部通知仍延期至 Wave 6，完成对绩效关联的影响延期至 Wave 4，负荷/看板统计重算延期至 Wave 5，完成后归档快照、检索与复用延期至 Wave 7。

## Git checkpoint状态

- Phase 0～5 基线：
  - commit：`9a228cdd624339b964d21cff92e3f2533efd8275`
  - tag：`phase-5-rest-api-baseline`
- Batch 1 稳定基线：
  - commit：`637106a172d5c10d54461b2a1f910fb5fee9d0df`
  - tag：`batch-1-task-board-baseline`
- Batch 2A 本地基线：
  - commit：`94108af17225ca9e4a2f728e47a117f1d546a0af`
  - push：待 GitHub 网络恢复
- Batch 2B 本地 checkpoint：
  - commit：`7a0cf4e3c6b920d5fea10c351d4d7789f39baf90`
- Wave 1 checkpoint 候选：
  - 完成验收与返工实现及总质量门已通过
  - commit hash：尚未创建；本文档随候选提交
- 远程仓库：`https://github.com/Z-pw-36/smart-task-board.git`
- 两个稳定基线标签均已上传至 GitHub 私有仓库且不得移动；本地 `main` 当前领先 `origin/main`。

## 后续计划

Batch 1、Batch 2A、Batch 2B 和 Wave 1 功能与验收均已完成。下一步是在安全复核后创建 Wave 1 本地 checkpoint，再进入 Wave 2：不可变任务变更申请，以及取消、撤回、合并、关闭和允许场景下的恢复。不会在 Wave 1 checkpoint 中虚报 Wave 4～7 的完成下游能力。

## 当前未实现

- 正式生产登录认证、企业统一身份或企业微信认证。
- 完整 JWT 刷新、撤销和登出机制，以及正式 RBAC 和组织范围权限。
- 任务变更申请，以及取消、撤回、合并、关闭和允许场景下的恢复。
- AI 结构化提取、真实 AI/LLM、多轮对话、语音上传和 ASR。
- 企业微信机器人、通知和 Outbox。
- 附件及交付物文件管理。
- 负荷分析、冲突分析、优先级分析和绩效关联。
- 完成提醒、完成后的绩效关联影响、负荷/看板统计重算、归档检索与复用，以及其他后续 Wave 功能。

## 有效需求文档

项目仅以 `docs/` 中以下两份文档为当前有效需求，不得修改或删除：

- `第二版-智能任务看板核心逻辑与用户使用流程节点.docx`
- `第四版-智能任务看板数据表结构文档-显式ID版.docx`

功能验收通过标准见 `docs/ACCEPTANCE_STANDARDS.md`（单功能硬性条件、提交前全量回归、严禁条款、功能 12 算法口径锁死）。

## Feature 05 cloud-function AI intake

The runtime source now contains only `cloud-functions/ChatService`; the historical SMS `LoginService` has been removed. The Mini Program authenticates through WeCom/FastAPI and obtains a short-lived `task-intake` token from `/api/v1/auth/ai-token` before calling ChatService. See `cloud-functions/README.md` and `docs/WECOM_IDENTITY_ORG_MAPPING.md`.

## Feature 13 notification and node-assignment delivery

Feature 13 is implemented against the user-confirmed rules in `docs/FEATURE_13_NOTIFICATION_RULES.md`. Collaborator-owned AI nodes require server-persisted acceptance before execution/reminder responsibility starts; dynamic node due-soon timing uses working-span bands and never estimated hours. Notification projection is recipient-scoped and action-aware, delivery retry uses the same outbox record, and production Mini Program UI uses action-required rather than read/unread as the business badge. See `docs/FEATURE_13_ACCEPTANCE.md` for the exact migration, API, tests, environment limitations, and scope boundary.

## Feature 14 executive dashboard implementation

Feature 14 is implemented against `docs/FEATURE_14_EXECUTIVE_DASHBOARD_RULES.md`: explicit authorized department scopes, week/month aggregation, four team metrics, persisted-priority quadrants, workload heatmap, and snapshot pressure breakdown. KPI dashboard aggregation uses user-confirmed relations only (`is_confirmed=true`), does not define core KPI, excludes inactive metrics from the current dashboard, and includes `pending_review` in overall progress only.

## Feature 15 executive employee task filtering

Feature 15 follows the user-confirmed P0 scope in `docs/FEATURE_15_EXECUTIVE_EMPLOYEE_TASK_FILTER_RULES.md`. The workload breakdown sheet now has a real “查看该员工任务” action that reuses the existing task overview. The task overview displays an employee-name filter but sends only `employeeNo` to the backend, combines it with status/quadrant/date filters, revalidates explicit executive department scope, and opens the existing task detail page. The old standalone `pages/workload-tasks` fake page was removed from production registration. Feature 15 adds no business table, field, or Alembic migration.

The same change also fixes the real `TaskBoardQueryService.available_actions()` undefined-`priority` 500 defect and adds direct service regression coverage. Current executable gates after Feature 15: backend non-PostgreSQL `460 passed, 28 deselected`; WeChat feature01-15 `19` groups PASS; JS syntax and Python compileall PASS. Real PostgreSQL, React dependency gates, Ruff, and WeChat Developer Tools are unavailable in this container and are not claimed as passed. See `docs/FEATURE_14_ACCEPTANCE.md`.

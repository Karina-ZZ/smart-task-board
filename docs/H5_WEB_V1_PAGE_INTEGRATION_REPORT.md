# 旺序AI任务中枢｜H5网页第一版逐页前后端联调报告

> 基线：Test16 Performance-Link Hotfix 累计源码  
> 目标：Test16 13个生产页面按“前端组件等价 + 真实 FastAPI + 现有 Service/Repository/PostgreSQL 契约”逐页迁移。  
> 判定原则：页面未完成前后端联调不得进入下一页；当前容器无法替代真实 PostgreSQL、完整 npm/Web build 与企业微信真机 WebView 门禁。

## 1. 页面执行结果

| 顺序 | 页面 | H5入口 | 前端结果 | 后端承接 | 当前判定 |
|---:|---|---|---|---|---|
| 00 | 全局框架 | 全局 | Test16底部导航、Sheet/Dialog/Toast体系、移动安全区 | 无业务状态修改 | PASS |
| 01 | 工作台 | `/workbench` | AI直接输入/语音/发送、3项指标、四象限、具体支持事项、任务卡 | `/dashboard/summary`、`/tasks`、`/tasks/inbox` → `TaskBoardQueryService` | PASS |
| 02 | 创建·描述任务 | `/create` | 独立描述页、文字/语音、识别与失败重试 | task-input/extract → `TaskIntakeService` / AI Provider | PASS |
| 03 | 创建·信息确认 | `/create/details` | 人员搜索Sheet、绩效Sheet、任务来源选填、AI不覆盖人工字段 | users/task draft/performance → `TaskCreationPeopleService`、`TaskIntakeService`、`PerformanceMetricService` | PASS |
| 04 | 创建·确认发送 | `/create/confirm` | 摘要、绩效确认、返回修改、发送成功状态页 | confirmation/send actions → `TaskWorkflowService` | PASS |
| 05 | 任务概览 | `/tasks` | 任务/节点模式、筛选、任务卡进度、高管员工筛选、返回恢复 | `/tasks`、`/executive/tasks`、`/executive/members` → Query/Executive Services | PASS |
| 06 | 任务详情 | `/task/:taskId` | 五模块、节点展开、节点动作、底部主动作、更多Sheet、操作记录Sheet | detail/available-actions/node/change/action APIs → Workflow/Node/Query Services | PASS |
| 07 | AI拆解 | `/task/:taskId/decomposition` | 处理中/失败/成功三态、重试、成功回任务 | decomposition APIs → `TaskDecompositionService` | PASS |
| 08 | 进度汇报 | `/task/:taskId/report` | 当前进度必填、阶段成果选填、卡点条件必填、备注选填 | progress/issues → `ProgressReportService` / `TaskIssueService` | PASS |
| 09 | 提交完成 | `/task/:taskId/completion` | 独立完成页、完成说明、交付摘要、提交确认 | submit-completion → `TaskWorkflowService` | PASS |
| 10 | 任务验收 | `/task/:taskId/review` | 完成申请、验收依据、通过/退回、验收历史 | approve/reject/reopen → Workflow/Node Services | PASS |
| 11 | 通知中心 | `/notifications` | 全部/任务/提醒/系统四Tab、targetType深链、返回恢复 | notification list/read → `ReminderNotificationService` | PASS |
| 12 | 我的 | `/profile` | 员工信息、身份、关联任务、待我处理、已归档、任务关系说明 | `/me` + tasks + notifications → `IdentityService` / Query Services | PASS |
| 13 | 高管看板 | `/executive` | 部门Sheet、周期Tab、4指标、四象限、热力图、构成Sheet、员工任务下钻 | `/executive/overview`/members/tasks → `ExecutiveDashboardService` + Repository | PASS |

## 2. 本轮累计回归证据

当前工作树实际执行：

```text
后端非 PostgreSQL累计：617 passed / 41 deselected
H5迁移静态合同 + 企业微信客户端/认证定点：24 passed
高管 API / Service / Repository 定点：22 passed
“我的”相关 Service 定点：4 passed
“我的”相关 API 定点：14 passed
Python compileall：PASS
Test16 微信小程序累计：25 / 25 测试文件 PASS
微信小程序 JS node --check：PASS
React/TS 源码语法转译：103 files / 0 syntax errors
```

其中 `41 deselected` 为标记为 PostgreSQL 的真实数据库专项，本轮当前容器未执行，不记为 PASS。

## 3. 页面级强制不变量

- H5 前端不自行复制服务端权限或状态机；任务动作继续由 `/available-actions` 驱动。
- 创建发送仍为 `draft -> pending_confirm -> pending_accept`，发送时不生成 nodes。
- 接受任务仍为 `pending_accept -> decomposing`，AI拆解成功后才进入 `in_progress`。
- `task_source` 继续选填；创建阶段不写/不展示 `estimated_hours`。
- AI多轮追问不得覆盖用户已经手工修改的字段。
- 协办节点未承接前不得进入执行提醒/执行动作。
- 任务级汇报只有主承办人在合法执行态可提交。
- 验收通过后同事务自动归档，不写新的 archive snapshot。
- 绩效正式关联以已确认关系为准；Test16 Performance-Link Hotfix 必须保持。
- 高管 KPI、总体进度、负荷、四象限均读取服务端结果，不在浏览器重算。
- 高管员工任务下钻以 `employeeNo` 查询，`employeeName` 仅显示，筛选条件按 AND 叠加。
- 通知只提供入口，不授予权限；打开目标页面后仍重新执行服务端鉴权。

## 4. 仍未放行的真实环境门禁

1. **Web完整 npm 门禁**：当前环境 `npm ci` 访问 registry 超时，因此 ESLint/Vitest/Vite build/Playwright 不能声明通过。
2. **真实 PostgreSQL**：41项 PostgreSQL 专项及最新迁移/事务/锁/幂等回归需在正式 PG 测试库执行。
3. **企业微信真实 OAuth**：需真实 CorpID、AgentID、Secret、可信域名、可信IP和测试员工。
4. **企业微信应用消息**：需真实员工收件、H5深链及权限二次校验 E2E。
5. **企业微信移动 WebView**：375/390/430宽度、键盘、安全区、返回、刷新、麦克风/ASR需真机验收。

## 5. 当前结论

当前代码层已完成 Test16 13个生产页面的 H5逐页组件/交互迁移，并完成当前环境可执行的前后端联调与累计回归。当前状态应记录为：

```text
IMPLEMENTATION: DONE
CURRENT-ENV PAGE INTEGRATION: PASS
NON-PG CUMULATIVE REGRESSION: PASS
REAL POSTGRESQL: PENDING
WEB FULL NPM GATE: BLOCKED BY NETWORK
REAL WECOM WEBVIEW/OAUTH/MESSAGE: PENDING
```

因此本版本可以进入真实环境门禁，但尚不能宣称生产放行。

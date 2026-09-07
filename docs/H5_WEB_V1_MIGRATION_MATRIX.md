# 旺序AI任务中枢｜H5网页第一版全功能迁移矩阵

> 基线：Test16 Performance-Link Hotfix 最新累计源码  
> 迁移目标：企业微信自建应用 + React H5  
> 原则：不重新设计；前端小组件、信息结构、业务文案和主要交互基本保持；Test16 已有功能全部保留。  
> 业务边界：任务状态机、权限、绩效、负荷、通知规则和 PostgreSQL 业务事实继续由现有 FastAPI 服务端权威实现。

## 1. 13个小程序生产页面到 H5 的映射

| Test16 小程序页面 | H5正式入口 | H5实现 | 后端复用 | 第一版状态 |
|---|---|---|---|---|
| `pages/workbench/index` | `/workbench` | `features/workbench` | dashboard/tasks/notifications | 已接真实页面 |
| `pages/tasks/index` | `/tasks` | `features/task-overview` | tasks + executive/tasks | 已接真实页面；支持高管员工筛选 |
| `pages/task-detail/index` | `/task/:taskId` | `features/task-detail` | task detail/actions/logs | 已接真实页面和服务端授权动作 |
| `pages/create/index` | `/create` | `TaskCreateStartPage` | task-inputs | 已恢复独立任务描述页 |
| `pages/create-details/index` | `/create/details` | `TaskCreateDetailsPanel` | users/task draft | 已接真实任务级字段确认 |
| `pages/create-confirm/index` | `/create/confirm` | `features/task-create` | performance + task actions | 已接真实绩效确认与确认发送 |
| `pages/decomposition/index` | `/task/:taskId/decomposition` | `features/task-decomposition` | decomposition API | 已接自动执行/轮询/失败重试 |
| `pages/report/index` | `/task/:taskId/report` | `TaskReportPage` | progress/issues | 已按Test16字段口径独立实现 |
| `pages/completion/index` | `/task/:taskId/completion` | `TaskCompletionPage` | completion reviews | 已独立实现完成说明/交付摘要/提交验收 |
| `pages/review/index` | `/task/:taskId/review` | `TaskReviewPage` | completion reviews | 已独立实现通过/退回/验收历史 |
| `pages/notifications/index` | `/notifications` | `features/notifications` | notifications | 已接列表、未读、已读、任务跳转 |
| `pages/profile/index` | `/profile` | `features/profile` | current user/tasks/notifications | 已接正式身份资料；无角色切换 |
| `pages/executive/index` | `/executive` | `features/executive-dashboard` | executive overview/members/tasks | 已接指标、四象限、负荷、员工下钻 |

## 2. 关键组件等价迁移

| 小程序能力/组件 | H5对应 | 迁移原则 |
|---|---|---|
| 顶栏/返回 | `TopBar` / 页面返回按钮 | 保持移动端层级与返回语义 |
| 底部导航 | `AppShell` BottomNavigation | 保持工作台/任务/高管/通知/我的入口 |
| 卡片 | shared `Card` | 继续第二版 HTML 蓝白移动端视觉 |
| 状态徽标 | `Badge` + server status | 中文标签只展示，不作为数据事实 |
| 任务卡 | task overview card | 点击进入现有任务详情 |
| 四象限 | Workbench/Executive quadrants | 后端计算，不在浏览器复制算法 |
| 筛选器/抽屉 | FilterSheet/Sheet | 状态、四象限、日期、员工按 AND 叠加 |
| AI输入 | `TaskIntakePage` | 文字 + 语音，AI结果只作为草稿 |
| 语音按钮 | MediaRecorder → ChatService ASR | 与 Test16 同一短时 AI token/ASR 链路；失败不假成功 |
| 人员选择 | real `/api/v1/users` | 使用 `employee_no`，不以姓名作主键 |
| 确认发送 | `TaskConfirmPage` | 不生成创建人节点；发送进入 `pending_accept` |
| 任务动作 | `TaskExecutionControls` | 只显示服务端 `available-actions` |
| 节点承接 | Task detail node actions | 协办节点未承接不得进入执行动作 |
| 汇报/卡点 | `ProgressIssuesPanel` | 主承办人任务级动作，复用后端权限 |
| 变更 | `ChangeRequestsPanel` | 复用现有变更审批合同 |
| 完成/验收 | `CompletionReviewsPanel` | 提交、通过、退回、多轮验收、自动归档 |
| 绩效 | `TaskConfirmPage` + task detail | Test16 绩效关联持久化 Hotfix 必须保留 |
| 高管热力图 | `ExecutiveDashboardPage` | 复用后端负荷结果，不重算 |
| 通知 | `NotificationsPage` | 四Tab + targetType深链；通知只提供入口，不授予任务权限 |

## 3. Test16 Hotfix 防回归清单

- `task_source` 继续选填。
- AI 追问只补充未人工修改字段，不能覆盖用户已填内容。
- AI 是否仍有追问，不单独阻断已经完整的真实必填字段继续创建。
- 接受任务使用真实服务端动作，接受后进入 `decomposing`。
- 自建自办仍必须接受。
- 创建阶段不写 `estimated_hours`。
- 创建阶段已确认 KPI 在发送后和任务详情中仍保持正式关联。
- 完成申请要求完成说明与交付摘要；实际工时由系统计算。
- 高管员工任务筛选使用 `employeeNo`，与其他筛选条件为 AND。
- 生产 H5 登录不展示 prototype 角色选择。

## 4. H5 专属变更

只允许以下运行层差异：

1. `wx.qy.login()`/小程序 code2session → 企业微信网页 OAuth `auth/getuserinfo`。
2. 小程序路由 → React Router。
3. `wx.request` → 现有 H5 API client / React Query。
4. 小程序录音文件 → H5 MediaRecorder；仍调用同一 ChatService ASR。
5. 企业微信应用消息的链接指向 H5；打开后重新执行身份与业务权限校验。
6. 企业微信 OAuth loading/failure、浏览器刷新和 WebView 安全区属于 H5 特有状态。

## 5. 逐页联调状态

13个Test16生产页面当前均已完成当前环境可执行的前后端联调。完整记录见 `docs/H5_WEB_V1_PAGE_INTEGRATION_REPORT.md`。

## 6. 第一版仍需在真实环境完成的门禁

- Web `npm ci`、ESLint、Vitest、Vite build、Playwright（当前执行容器 DNS 无法安装依赖）。
- 真实 PostgreSQL 专项与最新 Test16 PG 回归。
- 企业微信自建应用真实 CorpID/AgentID/Secret、可信域名、可信 IP、OAuth E2E。
- 企业微信应用消息真实员工收件与 H5 深链 E2E。
- 企业微信移动 WebView 375/390/430 及真机麦克风权限/ASR 验收。

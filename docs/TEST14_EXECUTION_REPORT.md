# 旺序AI任务中枢｜Test14 专项修复执行报告

> 日期：2026-09-07  
> 状态：修复代码与本容器可执行回归已完成；正式真实环境门禁仍待执行，不作为生产放行证明。  
> 基线：Test13-WebLogin-AIGate-Hotfix-TaskSourceOptional-smart-task-board-feature16-release-candidate.zip  
> 基线 SHA-256：5bf6644bc757d0ba3d8a1fe19cd607ff68aaf94a27a97502aea1b68f841b5b62  
> 本轮范围：用户批准的 F1 动作契约、F2 汇报周期校验、F3 提示词及输出保护，以及必要的诊断和测试。

## 1. 与本地 Test13 报告的对应关系

Test13 的本地报告记录：原 PostgreSQL 28项×3轮、Outbox 100次、非PG 510项、Web 115项等门禁通过，但创建人发送任务后访问工作台出现500。原因是服务端已返回 reassign_task，响应和Web类型未包含该值。同时发现非法 report_cycle 进入数据库才报错，以及提示词示例 weekly 不符合现有数据库约束。

本轮没有重新设计已经跑通的登录，也没有再次修改小程序“AI追问非硬门槛”的生产代码。修复基线保留任务来源选填和此前的字段保护。

## 2. 实际修改

### F1：补齐动作契约，保持原权限

- app/schemas/task_board.py：AllowedAction 增加 reassign_task。
- web/src/api/types.ts：同步联合类型。
- web/src/api/taskActions.ts、web/src/features/task-detail/format.ts：增加“更换承办人”显示名称。
- 将 reassign_task 排除出仅提交版本号的 TaskLifecycleAction；它仍需承办人、原因和版本，不误接普通动作POST。
- 不修改 task_board_query.py 的动作投影、不删除服务端动作，不放宽权限，不新增Web更换承办人页面或可点击入口。
- 工作台、任务列表、Inbox内嵌任务及available-actions的HTTP响应契约均有回归。

### F2：入库前验证可选汇报周期

- app/core/report_cycle.py：复用原数据库约束对应的完整格式，成为HTTP和服务入口共同使用的格式规则。
- CreateTaskRequest、UpdateTaskDraftRequest增加字段校验。
- TaskWorkflowService仅在创建草稿和更新草稿两处补服务级保护，覆盖绕过HTTP Schema的内部调用。
- null或未提供继续合法；weekly、中文“每周”、无效星期/时间等直接输入返回422，不再依赖数据库报500。
- 更新中省略字段保留原值，显式null可清空；不增加必填项。
- 原任务变更路径引用同一正则，校验语义不变。提醒时间算法、数据库CHECK约束均不修改。

### F3：提示词与AI输出对齐

- 仅修改 task_agent.md 的 reportCycle 规则和示例；示例由 weekly 改为null。
- 后端和ChatService的任务录入提示词增加相同约束：只有用户明确星期和时间才输出完整值；仅说“每周”时不猜时间。
- TaskIntakeService将非法AI建议归为null及低置信提示，周期不进入必填缺失集合。
- 从历史识别记录创建草稿时，仅清理无效的AI周期建议，再应用用户明确更正；用户有效值不被无效AI值覆盖。历史识别记录不回写。
- 用户明确提交非法值仍由服务校验拒绝，不静默替换为默认周期。
- ChatService运行代码未改变，只更新了其任务录入提示词。

### 诊断及验证工具

- 不清空异常处理器，不关闭响应校验。500对外响应格式保持不变。
- 内部日志增加请求标识、路由模板、异常类型、校验位置、文件/行号/函数名。
- 不记录异常消息、SQL参数、任务全文、令牌、请求头、响应原始值或堆栈局部变量；以脱敏位置记录代替可能泄露数据的完整异常字符串。
- verify-ai-send-e2e.py修复原脚本中非法的“每周”，并加入合法/空/非法周期、确认发送、幂等重试及工作台/列表/详情/动作读取。
- 新增真实浏览器用例，主动先创建并发送任务，再登录创建人，确认任务可见、进入详情、返回、刷新、读取/me。不能仅用无任务的观察者替代。
- 写入类HTTP/浏览器测试必须显式设置 STB_TEST14_ALLOW_TEST_WRITES=1，且只支持本地隔离后端。

## 3. 本容器实际执行证据

环境实际为 Python 3.13.5，而项目正式要求为Python 3.12。本表属于补充回归，不能替代3.12正式门禁。

| 检查 | 实际结果 |
|---|---|
| Test13原非PG基线 | 510 passed / 28 deselected |
| 新增39项契约测试，修复前 | 32 failed / 7 passed：复现缺动作类型及非法周期被接受 |
| 本轮专项（契约、周期、脱敏日志） | 58 passed |
| 修改后非PG累计 | 568 passed / 32 deselected |
| PostgreSQL收集检查 | 32项成功收集：保留原28项，新增4项；没有执行 |
| 小程序累计测试 | 22/22 PASS |
| 小程序JS语法 | 50 files / 0 failed |
| ChatService原有脚本 | 3/3 PASS |
| compileall | PASS（app/tests/alembic/cloud-functions/scripts） |
| 新门禁Shell语法 | PASS |
| Web类型切片 | types/taskActions/detail format及其client依赖，严格类型检查PASS |
| Web TS/TSX语法转译 | 84 files / 0 errors |
| 修改范围检查 | 白名单外0；删除0；229个受保护无关函数源码保持一致 |
| 数据库模型与迁移 | 与Test13逐文件字节一致；0新增迁移 |

类型切片使用容器的TypeScript 5.8.3，并为import.meta.env提供最小声明；这不是仓库要求的完整npm/Vite构建。没有修改项目依赖或锁文件来适应容器。

## 4. 明确未执行的门禁

| 门禁 | 原因与要求 |
|---|---|
| Python 3.12正式运行 | 本容器只有3.13.5，正式门禁脚本已正确阻断 |
| PostgreSQL 32项×3轮、原Outbox 100次 | 缺少PostgreSQL服务端、psycopg及Docker；未冒充执行 |
| Ruff | 无ruff模块；没有宣称0错误 |
| 完整Web lint/Vitest/build | 无项目node_modules，离线npm ci报ENOTCACHED，网络DNS不可用 |
| 真实Web/HTTP闭环 | 没有可用的上述后端数据库和Web依赖组合；已交付可执行用例，待本地运行 |
| 微信开发者工具API模式创建发送 | 本容器没有微信开发者工具，不能用Node测试替代 |
| 真实Qwen / 企业微信SSO | 没有对应真实运行条件；未发出真实调用 |

Test13本地已通过的数据仍是Test13证据，不能移作Test14的新运行结果。新增Web单测1项，原115项保留，但本轮没有执行完整Vitest。

## 5. 不影响无关部分的核对

以下目录或文件保持Test13字节一致：app/models/、alembic/、wechat-miniprogram/、task_board_query.py、认证/权限实现、任务拆解/执行/通知/绩效/负荷/高管实现、Web登录页面和路由、依赖清单及锁文件。

task_workflow.py、business_capabilities.py、errors.py属于共享文件。本轮仅修改批准的方法和必要导入，其他229个函数用基线源码哈希验证没有变化。

没有连接或清理用户的既有业务数据库，没有修改数据库表、字段、索引、约束、版本状态码。测试环境的模型/迁移文件一致不等于做过真实数据库结构前后比对；真实库比对须在本地门禁中完成。

## 6. 本地复验与交付

- 技术门禁：scripts/run_test14_technical_gate.sh。
- 真实HTTP及创建人浏览器门禁：scripts/run_test14_live_gate.sh。
- 范围检查：scripts/verify-test14-scope.py。
- 端口、各端打开方式、隔离数据库与命令：docs/TEST14_LOCAL_PORTS_AND_LOGIN_GUIDE.md。
- 完整验收清单：docs/TEST14_ACCEPTANCE_CHECKLIST.md。

累计包外层目录改为 smart-task-board-test14，避免继续依赖“feature-15”目录名判断版本。小程序生产文件完全未改；单独小程序ZIP仅改交付名称，与Test13对应小程序包内容相同。本次必须更新累计包中的后端/Web；使用独立ChatService时还需同步本轮提示词，不能只重新导入小程序。

最终ZIP生成后在全新目录重新解压，执行范围校验、非PG、小程序、ChatService及语法复验，结果另见外置验证记录。最终SHA-256见TEST14_SHA256.txt，避免把自引用哈希写入ZIP内部。

## 7. 结论

IMPLEMENTATION：完成本轮限定修复。
LOCAL SUPPLEMENTAL REGRESSION：通过本容器可执行项。
FORMAL PG / WEB / MINI PROGRAM API / REAL PROVIDERS：待真实环境执行。
RELEASE：候选，不宣称“全部开发成功”或生产已放行。

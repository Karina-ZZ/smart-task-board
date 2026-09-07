# Test15 交付执行说明与修复记录

> **Test15版本说明**：本次仅统一交付名称、解压目录和说明文档，不新增业务修改。
> 业务代码、测试脚本、配置模板、数据库模型和迁移均与Test14最后交付一致。
> 脚本、环境变量和库名示例中的 `test14` / `TEST14` 为保留的兼容标识，不要全局替换为Test15。
> 以前的测试结果属于Test14历史证据；Test15本次仅执行打包一致性和原修改范围检查，未重跑功能测试。
> **正式环境验收状态不变：仍为候选版本，未获生产放行。**

## 本次名称和目录

- 累计源码：`Test15-TaskAction-ReportCycle-Hotfix-smart-task-board-feature16-release-candidate.zip`
- 解压目录：`smart-task-board-test15`
- 小程序：`Test15-wechat-miniprogram.zip`，与Test14的对应ZIP逐字节一致。
- 当前校验值以外置 `TEST15_SHA256.txt` 为准；下方历史记录中的Test14包名与哈希不代表新包。
- 新包仍使用 `scripts/run_test14_technical_gate.sh`、`scripts/run_test14_live_gate.sh` 和原有显式写入许可。

## 下方为原Test14修复记录（历史原文）

保留原日期、版本名和测试结果，不将其改写为Test15新执行证据。

---

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


---

# Test15 验收状态与最后一轮历史验收记录

> **Test15版本说明**：本次仅统一交付名称、解压目录和说明文档，不新增业务修改。
> 业务代码、测试脚本、配置模板、数据库模型和迁移均与Test14最后交付一致。
> 脚本、环境变量和库名示例中的 `test14` / `TEST14` 为保留的兼容标识，不要全局替换为Test15。
> 以前的测试结果属于Test14历史证据；Test15本次仅执行打包一致性和原修改范围检查，未重跑功能测试。
> **正式环境验收状态不变：仍为候选版本，未获生产放行。**

## Test15本次检查的边界

本次只更新交付版本名，并执行ZIP完整性、原修改范围、文件逐字节对比和小程序包一致性检查。实际打包检查结果见 `TEST15_REVERSE_ACCEPTANCE.txt`；未重跑pytest、PG、Web、微信开发者工具或外部模型调用。

## 沿用状态

| 项目 | 状态 |
|---|---|
| Test14最后一轮补充回归 | 568 passed / 32 deselected；58项专项已包含在568项中 |
| 小程序和ChatService历史补充测试 | 22/22、50个JS语法、3/3纯逻辑通过 |
| 真实PG、完整Web、小程序API页面、外部服务 | 仍需正式环境执行；本次改名不补充这些证据 |
| 生产放行 | 未放行 |

正式复验请从 `smart-task-board-test15` 目录执行，命令见 `TEST15_LOCAL_PORTS_AND_LOGIN_GUIDE.md`。下方记录中的目录和哈希是原Test14执行现场，仅供追溯。

## 附录：Test14最后一轮验收原文

---

# Test14 最终验收执行记录（本轮重跑）

> 日期：2026-09-07。
> 结论：可执行的补充回归通过；正式技术门禁及真实前后端闭环被环境条件阻断。未达到生产放行标准。
> 本轮是验收执行，不是新增功能或新修复版本；没有修改交付源码、数据库模型、迁移或用户的既有业务数据。

## 1. 验收对象与执行地点

候选包：`Test14-TaskAction-ReportCycle-Hotfix-smart-task-board-feature16-release-candidate.zip`。

SHA-256：`b9c3e275f452795770b891f858690e71dfda7f08eaac088a6496a24fd4c45b27`，与已交付的 TEST14_SHA256.txt 一致。

本次重新解压到独立目录：`test14_final_validation/source/smart-task-board-test14`，共540个候选文件。开始和结束都做了范围核查，结束后又逐文件对照原ZIP：540个文件字节一致，修改0，缺失0。运行产生的缓存不属于交付源码，也没有重新打进应用包。

执行地点是当前Linux容器，不是用户的macOS电脑。当前容器的127.0.0.1也不是用户电脑的127.0.0.1。本轮没有连接用户此前运行在5174/8001或5432/46479上的服务。

本轮命令时间记录在日志中，使用UTC；对应北京时间为2026-09-07 13:52以后。

## 2. 实际通过项

| 项目 | 结果 | 证据 |
|---|---|---|
| Test14专项：动作契约、周期校验、脱敏诊断 | 58 passed | logs/07_hotfix_tests.log、test14_hotfix.xml |
| 后端非PostgreSQL累计回归 | 568 passed / 32 deselected | logs/08_backend_non_pg.log、test14_nonpg.xml |
| PostgreSQL测试收集 | 32项收集成功，未运行 | logs/06_pg_collection.log |
| 小程序Node累计测试 | 22/22 PASS | logs/09_miniprogram.log |
| 小程序JavaScript语法 | 50个文件全部通过 | logs/10_js_syntax.log |
| ChatService原有纯逻辑测试脚本 | 3/3 PASS | logs/11_chat_*.log |
| Python compileall | PASS | logs/12_compileall.log |
| 两个Test14门禁及Web启动Shell语法 | PASS | logs/13_shell_syntax.log |
| Test13→Test14修改范围检查 | 30个已批准的修改/新增文件；删除0、白名单外0 | logs/03_scope.log、logs/17_scope_final.log |
| 受保护函数及交付文件一致性 | 229个受保护函数通过；Test14本轮540个文件未变化 | source_integrity.json |

58项专项已包含在568项累计测试中，不能相加宣称626项独立通过。32项PG是未选中，不是已经执行通过。小程序Node测试与ChatService纯逻辑测试，也不等同于开发者工具API模式或真实模型联通。

## 3. 正式门禁的真实阻断

### 3.1 Python正式版本不满足

直接运行 `bash scripts/run_test14_technical_gate.sh`：退出码127，`python3.12: command not found`。

显式把当前Python交给同一脚本检查：退出码1，`TEST14 BLOCKED: formal acceptance requires Python 3.12`。没有修改脚本绕过版本要求。

本环境实际Python为3.13.5。尝试用离线缓存安装3.12失败，缓存中没有对应运行时。证据：logs/01_formal_python_gate.log、02_python312_offline.log、18_python_version_guard.log。

本环境pytest为9.0.2，也低于项目开发依赖声明的>=9.0.3；因此本轮Python测试全部明确归类为补充回归，不能当作符合项目环境的正式验收。

### 3.2 环境依赖健康检查未通过

`python -m pip check` 返回1：预置moviepy 2.2.1要求Pillow<12，而容器预置Pillow为12.3.0。

这是当前容器环境中的依赖冲突，项目依赖清单没有要求moviepy。没有为通过检查去修改项目依赖或容器公共包。证据：logs/04_pip_check.log。

`python -m ruff check .` 未执行成功，原因是本环境没有ruff模块，不能报告“Ruff 0错误”。证据：logs/05_ruff.log。

### 3.3 PostgreSQL与Outbox门禁未运行

当前未安装PostgreSQL服务端、psql、Docker或psycopg；本容器46479没有监听服务。未创建替代SQLite数据库来冒充PG验证，也未连接其他数据库。

因此32项×3轮、Outbox 100次并发、真实数据库结构前后比对均为BLOCKED。测试收集成功只证明用例可以被发现。证据：availability.json、environment.json、logs/06_pg_collection.log。

### 3.4 完整Web门禁未运行成功

尝试 `npm ci --offline --no-audit --no-fund` 返回ENOTCACHED，缺少锁文件所需的缓存包。当前pypi.org和registry.npmjs.org均解析失败，无法在线补齐。

继续分别执行：
- `npm run lint`：eslint未安装，退出127。
- `npm test -- --run`：vitest未安装，退出127。
- `npm run build`：缺少@testing-library/jest-dom及vitest/globals类型依赖，退出2。

这些是依赖不完整导致的环境阻断，不能计为Web测试通过，也不能据此断言产品逻辑有新缺陷。没有删除类型检查、修改锁文件或改用其他版本依赖。

证据：logs/14_npm_ci_offline.log、19_web_lint_attempt.log、20_web_test_attempt.log、21_web_build_attempt.log。

### 3.5 真实浏览器、小程序API与外部服务

容器有Chromium，但没有可用的项目Web依赖和真实PostgreSQL后端组合；本容器5174、8001未运行服务。因此“创建并发送真实任务→创建人Web登录→工作台显示该任务→详情→返回→刷新”没有运行，不能宣称闭环已经通过。

未提供写入许可时，Test14 live gate和HTTP探针按预期拒绝继续。该结果仅验证安全开关有效，不是业务E2E结果。证据：logs/15_live_gate_no_consent.log、16_http_probe_no_consent.log。

本容器没有微信开发者工具。真实小程序API页面创建发送、真实Qwen/ChatService、正式企业微信SSO均未执行，不以Node测试替代。

## 4. 对F1/F2/F3的本轮结论

F1已有动作类型及响应契约测试通过；F2创建/更新周期格式与服务保护测试通过；F3非法AI周期建议、用户更正保护与提示词相关测试通过。已运行用例中没有新的断言失败。

但仍缺正式环境证据：
1. 创建人真实发送任务后，工作台、列表、动作接口实际返回200，且包含刚发送任务ID和reassign_task。
2. 非法周期创建和更新实际返回422，数据库没有业务残留或字段/版本变化；空值和合法值正常。
3. 小程序API模式不回答AI，手动补齐9项并完成真实保存、发送、返回工作台。

所以本轮状态继续是：`SUPPLEMENTAL_REGRESSION=PASS`、`FORMAL_GATE=BLOCKED`、`REAL_E2E=NOT_EXECUTED`、`RELEASE=NOT_APPROVED`。不能把用户此前的Test13通过数据移作Test14结果。

## 5. 下一步正式执行入口（本轮未在用户电脑运行）

在用户已具备Python3.12、PostgreSQL16、项目依赖和微信开发者工具的本地环境，从Test14新目录执行；先按独立端口文档准备并确认专用测试数据库。

技术门禁使用原安全守卫要求的全新空测试库，先显式设置POSTGRES_TEST_DATABASE_URL，再运行：

```bash
cd smart-task-board-test14
PYTHON_BIN="$PWD/.venv/bin/python" bash scripts/run_test14_technical_gate.sh
```

真实Web/HTTP门禁须先按TEST14_LOCAL_PORTS_AND_LOGIN_GUIDE.md启动专用联调后端和Web，确认没有连接旧demo或业务库，再运行：

```bash
STB_TEST14_ALLOW_TEST_WRITES=1 \
PYTHON_BIN="$PWD/.venv/bin/python" \
STB_REAL_E2E_BROWSER_CHANNEL=chrome \
  bash scripts/run_test14_live_gate.sh
```

这些命令不是让操作者直接复用未知的46479数据库。原门禁要求空测试库并会运行现有迁移；如果该端口属于旧实例，不得自动停止、删除或清空它。技术门禁库与Web联调库继续分离。

本轮只新增本执行报告与证据，不生成新的应用版本。Test14原源码包和小程序包继续保持原SHA-256。
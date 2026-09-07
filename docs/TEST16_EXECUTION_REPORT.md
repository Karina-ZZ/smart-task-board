# Test16 幂等重放专项修复执行报告

> 日期：2026-09-07  
> 交付根目录：`smart-task-board-test16`  
> 基线：Test15累计源码，540个文件  
> 基线SHA-256：`98227a47a780548ffb5f152578ebff8e46205ccb751587bc594094024385ff0e`  
> 状态：代码修复完成；本容器补充回归通过；正式PG、完整Web与设备门禁待在合格环境执行。不是生产放行证明。

## 一、证据口径

本轮针对用户《TEST15_本地验收测试报告_综合结论版》和《TEST15_测试失败详情与报错》。
报告已证明：Test15的原32项PG中1项连续三轮失败，真实8001后端也能复现同Key重放500，
四个响应字段均出现DetachedInstanceError；其他已执行项目通过，高管页面本地自动化不再阻断。
用户的Test15本地结果不能当作Test16新执行结果。

本轮没有操作用户电脑、46479门禁实例或46480联调实例。本文“实际执行”指当前Linux执行容器。

## 二、修改范围

唯一修改的生产代码文件：

`app/services/task_workflow.py`

只在以下三个已有幂等命中分支添加 `uow.session.expunge(cached)`，各附两行解释注释：

1. `confirm_and_send`；
2. `reassign_task`；
3. `_lifecycle_transition`（取消、撤回通过此分支重放）。

总计新增3行可执行语句和6行注释，没有删除原有业务语句。
另外两处相同模式不是凭猜测一起改：先用真实SQLAlchemy Session和原UnitOfWork复现，
更换承办人、取消、撤回均出现与确认发送相同的四字段读取失败，再纳入同根因修复。

没有改变首次操作的状态流转、权限、版本、日志和通知逻辑。没有改登录、AI追问、周期校验、
高管业务代码。没有修改全局UnitOfWork、Session配置、共享幂等查找、HTTP路由、响应Schema、
数据库模型、Alembic、依赖文件或小程序。已有测试文件和原PG安全守卫逐字保留。

## 三、为什么实际采用回滚前安全脱离，而不是统一改为四字段DTO

先核对调用方发现：已有Service调用及测试还读取Task的task_source、cancel_reason、
main_assignee_employee_no、accepted_at、effective_at、latest_decomposition_id等字段。
直接把整个方法改成只返回四字段DTO，会改变这些调用方的合同。

本轮因此保留两条路径相同的 `Task` 返回类型：
- `find_idempotent_task` 在当前新会话内调用 `session.get(Task, task_id)`，加载任务标量字段；
- 命中后在退出UnitOfWork前，将这个已加载对象从会话移除；
- 原UnitOfWork仍按原样rollback并close；
- 返回对象不再被该rollback标记为过期，路由可按原Schema读取四个标量字段。

这不是关闭数据库连接、清空数据库、删除任务，也不是新增commit。
只从当前Session的对象管理集合中安全移除这一只读结果。数据库事务行为没有改变。
任务关系的延迟加载不因此被承诺为可用；当前动作响应只读标量，测试另检查全部映射标量均已加载。

幂等查询仍按key、actor、action、task_id限定。保留“返回当前任务”的既有语义，不新增历史响应快照。
若任务随后被撤回，再重放旧发送请求，返回当前状态，不重新发送、不恢复旧状态。

## 四、新增测试与修改前后直接对照

### 4.1 真实ORM生命周期测试与FastAPI响应测试：34项

- `tests/services/test_test16_replay_lifetime.py`：26项。
- `tests/api/test_test16_replay_response.py`：8项。

两份测试使用独立内存SQLite列结构夹具、真实Task/OperationLog映射、真实Session、
未修改的UnitOfWork、真实服务方法和Pydantic/FastAPI响应校验。
不Mock成功响应，不Mockrollback/close。成功操作记录是预置夹具事实，不冒充首次发送链路。

SQLite夹具只建本测试私有的列结构，未复制PostgreSQL约束和锁；
不修改生产metadata，不替代PG集成测试或首次发送验收。

在重新解压的、生产代码完全未改的Test15上运行同一组新测试：
**24 failed / 10 passed**。
在Test16上运行：
**34 passed**。

覆盖两种expire_on_commit配置、三个源码分支/四个公开动作、多次重放、
全部标量可读、仍执行rollback且不commit、普通未提交修改仍被回滚、
key/actor/action/task范围、后续状态不被旧请求还原，以及实际HTTP响应构造。

### 4.2 新增真实PG用例：8项，已收集、未在本容器执行

文件：`tests/integration/test_test16_replay_postgresql.py`。

- 确认发送、更换承办人、取消、撤回：首次成功后相同请求重放三次，比较任务、参与人、
  状态日志、通知、操作日志与节点记录，检查没有重放副作用（4项）。
- 新Key旧版本、其他操作人、未授权更换承办人的原校验仍有效（1项）。
- 同Key在不同任务和不同动作下正确隔离（1项）。
- 发送后撤回，再重放旧发送请求不重新发送（1项）。
- 同Key同时到达，保持原有成功/版本冲突合同，随后重试成功且只有一次发送副作用（1项）。

并发测试不把原有409冲突悄悄改成无条件200；禁止500，且后续同Key重放必须成功。
保留原32项，包括用户报告中失败的那一条，原断言不变。总计40项PG正式候选用例。

### 4.3 新增真实浏览器用例

`web/e2e/dev-20-test16-replay-workbench.spec.ts`。

使用真实本地API：登录准备任务→来源为空→确认发送→保持原版本和同Key重放三次→
核对任务版本、状态、无节点→浏览器创建人登录→工作台包含该任务→详情→返回→刷新。
不Mock认证、发送、列表和工作台。原dev-18/dev-19保持原样并继续运行。
本容器尚未执行这条浏览器用例。

## 五、本容器实际结果

| 检查 | 结果 |
|---|---|
| 修改前同组真实ORM/API复现 | 24 failed / 10 passed（预期红灯） |
| 修改后专项 | 34 passed |
| 后端非PG累计 | 602 passed / 40 deselected |
| PG收集 | 40项收集成功；未执行 |
| 小程序Node累计 | 22/22 PASS |
| 小程序JS语法 | 50文件，0失败 |
| ChatService纯逻辑脚本 | 3/3 PASS |
| Python compileall | PASS |
| 两个Test16门禁Shell语法 | PASS |
| Alembic heads（不连接数据库） | c2d3e4f5a6b7，单head |
| 生产代码范围检查 | 仅三个新增detach块，其他workflow字节一致 |
| 原模型、迁移、共享幂等、UoW、Web应用、小程序、依赖 | 与Test15一致 |

34项专项已经包含在602项累计内，不能相加。40项PG是deselected/收集结果，不是通过结果。
最终ZIP重新解压后的结果另见外部 `TEST16_REVERSE_ACCEPTANCE.txt`。

## 六、本容器正式门禁阻断与限制

实际环境：Python 3.13.5、pytest 9.0.2、SQLAlchemy 2.0.50、Pydantic 2.13.4、
FastAPI 0.128.2、Node 22.16.0。与正式要求及用户本地环境不是完全相同版本。

已实际尝试：
- 新正式技术门禁在Python 3.12检查处停止，EXIT=1。
- 缺少PostgreSQL服务端、Docker和psycopg，不能执行PG40项×3或Outbox100次。
- 缺Ruff；`python -m ruff check .`不能运行。
- `pip check`发现容器预装moviepy/Pillow冲突；没有为此修改项目依赖。
- `npm ci --offline`缺yocto-queue缓存失败；无法运行完整项目Web lint/Vitest/build/浏览器。
- 没有微信开发者工具、真实Qwen凭据或企业微信SSO环境。
- 包源域名解析失败，当前不能在线补齐上述环境。

本轮补充回归不替代正式Python3.12、PG、Ruff、Web、设备及外部服务验收。
不伪造“原PG失败用例已在本轮真实PG转绿”，须本地新包复验。

## 七、正式执行入口

- 技术门禁：`bash scripts/run_test16_technical_gate.sh`
- 真实HTTP/浏览器：`bash scripts/run_test16_live_gate.sh`
- 范围检查：`python scripts/verify-test16-scope.py`

新技术门禁沿用未修改的 `scripts/run_postgresql_gate.sh`：
仅接收原安全目标、空库检查、既有迁移、全部PG三轮、原5×20压力和累计非PG回归。
不创建、清空、删除数据库或容器。

Test14脚本和原范围清单作为历史文件保留，不能拿旧范围白名单验证Test16新增文件。
当前交付请使用Test16入口，不通过修改旧白名单或旧PG守卫放行。

## 八、当前判定

IMPLEMENTATION = DONE（限定上述三个重放分支）
SUPPLEMENTAL_REGRESSION = PASS
FORMAL_PG / WEB / DEVICE_GATE = PENDING LOCAL EXECUTION
PRODUCTION_RELEASE = NOT_APPROVED

用户此前已通过的Test15门禁仍是历史有效证据，但不能替代Test16新代码的正式复验。
下一步以40项PG三轮全过、Outbox100次、真实创建人发送/重放/工作台闭环与无关功能回归作为技术放行依据。
正式企业微信SSO和真实Qwen继续独立验收。

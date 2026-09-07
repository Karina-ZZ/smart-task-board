# 功能16专项修复执行报告｜Web登录稳定启动 + AI确认非硬门槛

> 执行日期：2026-09-07  
> 修改基线：`Test11-WebLogin-Hotfix-TaskSourceOptional-smart-task-board-feature16-release-candidate.zip`  
> 基线 SHA-256：`7d743aaff0772386f0cc06d5aa48169a83bb1738c4c65844c74241047fd36e40`  
> 目标：解决“打开旧5173实例导致Web登录看似未修复”的重复误判，并强化“AI需要你确认不是独立发送门槛”的页面与测试合同。  
> 保护边界：不修改数据库结构、不改任务状态机、不改企业微信生产认证、不改AI拆解/执行/通知/绩效/负荷/高管业务实现。

## 1. 本轮实际修改

### 1.1 Web登录

新增：

- `config-examples/web-demo.env.example`
  - 独立 prototype 演示配置模板；
  - 默认与本地已验证的 `5174 + 8001` 配合；
  - 明确禁止覆盖正式 WeCom 配置。
- `scripts/start-web-demo.sh`
  - 从脚本自身定位当前候选包目录；
  - 默认使用前端5174、后端8001；
  - 端口被占用时拒绝复用未知/旧实例；
  - 校验 prototype/CORS/测试用户配置；
  - 真实检查 FastAPI `/health/ready` 与 `/api/v1/auth/prototype-users`；
  - 不执行迁移、不seed、不清库；
  - Vite与FastAPI由同一终端进程管理，Ctrl+C只结束本次启动的进程。
- `web/e2e/dev-18-real-login.spec.ts`
  - 不使用 `page.route(...fulfill)`；
  - 在显式 `STB_REAL_E2E=1` 时对运行中的真实前后端进行登录验证；
  - 默认使用本地验收已验证可运行的系统Chrome channel。
- `web/src/pages/LoginPage.tsx`
  - prototype用户接口发生普通网络连接失败时，登录页给出“登录服务不可用”的专项提示和重试；
  - `ApiError`仍展示后端安全业务错误；
  - 不改变token、路由安全返回或后端认证接口。
- `web/src/app/router.test.tsx`
  - 带回用户本地报告已验证的异步等待修正：`getByLabelText` → `await findByLabelText`。

### 1.2 AI需要确认不是独立硬门槛

保留最新基线已经完成的业务规则，不重新修改后端发送状态机：

```text
9项真实必填完整 + 原有权限/状态/版本/日期校验通过
→ 允许进入确认发送

AI仍有 confirmQuestions / missingFields / lowConfidenceFields
→ 仅作为辅助提示，不是独立发送门槛
```

本轮强化：

- `wechat-miniprogram/pages/create-details/index.wxml`
  - AI卡片明确说明：“可回答AI继续整理，也可直接在下方补齐；必填信息完整后即可进入发送确认”。
- `wechat-miniprogram/pages/create-details/index.js`
  - `next()`改为可读的显式流程并增加业务注释；
  - 只调用现有9项字段 `validate()` 与真实 `saveDraft()`；
  - 不读取 `needsClarification` 作为发送门槛。
- `wechat-miniprogram/tests/task-creation-clarification-hotfix.test.js`
  - 不再只测试 `validate()`；
  - 新增直接执行 `next()` 的页面级合同：`needsClarification=true`、AI问题仍保留、9项必填完整时，必须保存当前草稿并进入 `/pages/create-confirm/index`。
- `tests/integration/test_core_workflow_api_postgresql.py`
  - 现有真实PostgreSQL核心工作流的创建payload改为 `task_source=null`；
  - 下一次执行原28项PG门禁时，会同时验证选填来源贯穿真实创建→提交确认→发送主链路。
- `scripts/verify-ai-send-e2e.py`
  - 新增真实HTTP专项验证；
  - prototype登录→创建`task_source=null`草稿→提交确认→confirm-and-send→重新读取任务；
  - 预期最终为待接受且创建阶段无节点；
  - 不迁移、不seed、不清理数据库，必须对隔离测试库运行。

## 2. 独立端口与打开方式文档

新增：

```text
docs/LOCAL_PORTS_AND_LOGIN_GUIDE.md
```

正式区分：

```text
Web本地演示：浏览器打开 http://127.0.0.1:5174/login
FastAPI本地API：http://127.0.0.1:8001（不是登录页面）
旧默认5173/8000：只作为普通开发端口，不能据此判断版本
微信小程序mock：微信开发者工具，无真实后端落库
微信小程序API联调：微信开发者工具 + 隔离FastAPI
正式企业微信：从企业微信应用入口进入，不使用本地开发端口
```

并写明如何使用 `lsof` 检查5173/5174对应进程的真实工作目录。

## 3. 数据库与其他业务保护结果

本轮生产实现未修改：

```text
app/
alembic/
cloud-functions/
```

数据库变化：

```text
新增业务表：0
新增字段：0
修改字段类型：0
修改约束/索引：0
新增/修改Alembic migration：0
```

唯一后端目录相关差异位于**测试代码**：

```text
tests/integration/test_core_workflow_api_postgresql.py
```

用于让原PG核心链路显式覆盖 `task_source=null`，没有修改生产数据库逻辑。

默认冻结且未修改：任务接受/退回、AI拆解、节点执行、汇报、卡点、变更、验收、归档、通知、绩效、优先级、负荷、冲突、高管看板、员工筛选、企业微信认证、ChatService业务代码。

## 4. 本执行环境实际测试

### 4.1 后端非PostgreSQL累计回归

执行：

```bash
DATABASE_URL=sqlite+pysqlite:///:memory: python3 -m pytest -q -m 'not postgresql'
```

结果：

```text
510 passed / 28 deselected
```

其中专项包含：

```text
test_confirm_send_allows_optional_task_source              PASS
test_confirm_send_still_rejects_missing_required_task_goal PASS
```

### 4.2 微信小程序累计Node测试

结果：

```text
22 / 22 test files PASS
```

本轮新增页面级断言已证明：

```text
needsClarification=true
AI问题仍存在
9项必填完整
→ next()保存当前草稿
→ 进入发送确认页
```

### 4.3 小程序JS语法

结果：

```text
50 files / 0 failed
```

### 4.4 Python/脚本

```text
python compileall                             PASS
bash -n scripts/start-web-demo.sh            PASS
scripts/run-login-ai-hotfix-checks.sh        PASS
verify-ai-send-e2e.py py_compile             PASS
STATIC_HOTFIX_CHECKS_PASS                    PASS
```

### 4.5 Web源码语法

当前执行环境没有项目 `web/node_modules`，离线 `npm ci` 又因npm缓存缺包无法完成，因此没有伪造完整 npm gate。

已对本轮修改的4个TypeScript/TSX文件执行TypeScript transpile syntax检查：

```text
web/src/pages/LoginPage.tsx                   PASS
web/src/pages/LoginPage.test.tsx              PASS
web/src/app/router.test.tsx                   PASS
web/e2e/dev-18-real-login.spec.ts             PASS
```

## 5. 用户本地已提供的Test11真实环境基线

用户上传的 `TEST11_WebLogin-Hotfix_本地验收报告.md` 已记录旧WebLogin-Hotfix基线在真实本地环境：

```text
Ruff 0 error
PostgreSQL 28/28 × 3遍
Outbox 5项 × 20遍 = 100/100
非PG 508 passed / 28 deselected
Web 18 files / 114 tests
Vite build PASS
微信小程序开发者工具编译运行 PASS（当次 mode=mock）
真实 Web：5174 + FastAPI 8001 + PostgreSQL demo 登录链路 E2E_PASS
```

该报告还确认造成“Hotfix看起来没生效”的实际原因之一是：

```text
5173 的 Vite 进程工作目录是 2026-09-04 旧目录
```

本轮 `start-web-demo.sh` 与端口文档就是为防止该问题再次发生。

## 6. 仍必须在用户真实环境执行的最终门禁

因为本执行容器没有：

```text
Python 3.12 venv
Docker/PostgreSQL server
完整 web/node_modules
微信开发者工具
```

以下不能在本环境声明新候选包已最终PASS：

1. 原28项PostgreSQL专项在本轮新包执行3遍；
2. 原Outbox 100/100；
3. Web `npm ci → lint → 115+ Vitest（数量以实际为准）→ build`；
4. `dev-18-real-login.spec.ts` 对5174/8001真实环境运行；
5. `verify-ai-send-e2e.py` 对隔离PG运行；
6. 微信开发者工具切到API联调模式后手工/自动化执行“不回答AI→补齐9项→真实发送→待接受”。

这些命令和打开方式已经写入 `docs/LOCAL_PORTS_AND_LOGIN_GUIDE.md`。

## 7. 当前结论

```text
IMPLEMENTATION：DONE
WEB_OLD_PORT_REUSE_GUARD：DONE
PORT_AND_LOGIN_DOCUMENT：DONE
AI_CLARIFICATION_HARD_GATE_CODE：REMOVED / GUARDED BY PAGE-NEXT TEST
DATABASE_SCHEMA_CHANGE：0
BACKEND_NON_PG：510 PASS
MINIPROGRAM_NODE_TESTS：22/22 PASS
MINIPROGRAM_JS_SYNTAX：50 PASS
WEB_CHANGED_SOURCE_SYNTAX：PASS
REAL_WEB_LOGIN_NEW_CANDIDATE：PENDING USER LOCAL RERUN
REAL_POSTGRESQL_NEW_CANDIDATE：PENDING USER LOCAL RERUN
WECHAT_API_MODE_REAL_SEND：PENDING USER LOCAL RERUN
```

因此本轮已经完成代码修改和可执行的专项验收入口，但遵守项目通过标准：**在用户本地把真实PG、Web和微信API模式重新跑完之前，不把最终候选包宣称为“全部开发成功”。**

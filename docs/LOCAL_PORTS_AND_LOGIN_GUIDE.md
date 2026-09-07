# 旺序AI任务中枢｜本地端口与登录打开方式说明

> 适用版本：Test11 WebLogin Hotfix + TaskSourceOptional/Clarification Hotfix 后续候选包  
> 日期：2026-09-07  
> 目的：明确“本地 Web 演示登录”“本地 API”“微信小程序联调”“正式企业微信入口”的区别，避免再次打开旧目录中的 5173 服务而误判版本。

## 1. 一眼区分四类入口

| 场景 | 用户怎么打开 | 默认地址/入口 | 是否是真实后端 | 登录方式 | 备注 |
|---|---|---|---:|---|---|
| Web 本地演示/验收 | **电脑浏览器打开** | `http://127.0.0.1:5174/login` | 是 | prototype 演示身份 | 本候选包推荐的本地 Web 联调入口 |
| FastAPI 本地后端 | 浏览器/curl 只用于检查 API | `http://127.0.0.1:8001` | 是 | 由 API 决定 | **不是用户登录页面**；Swagger 为 `/docs` |
| 微信小程序 mock 演示 | 微信开发者工具导入 `wechat-miniprogram/` | 无浏览器端口 | 否 | mock | 只验证页面/交互，不证明数据落真实后端 |
| 微信小程序 API 联调 | 微信开发者工具导入专项联调副本 | `apiBaseUrl` 指向隔离 FastAPI | 是 | prototype 或批准的 WeCom 测试方式 | 用于创建/发送等真实前后端联调 |
| 正式企业微信 | **从企业微信应用入口打开** | 最终部署的 HTTPS 应用地址 | 是 | `wx.qy.login()` / WeCom | 不使用 5174/8001；最终域名需部署时配置 |

## 2. 为什么本地 Web 固定推荐 5174 + 8001

2026-09-07 Test11 本地验收已经真实跑通过：

```text
Web/Vite       http://127.0.0.1:5174
FastAPI        http://127.0.0.1:8001
PostgreSQL     127.0.0.1:46479（当次 demo 库）
```

当次还发现：

```text
5173 上存在 2026-09-04 旧目录遗留 Vite 进程
8000 被另一个同项目实例占用
```

因此，**端口本身不代表版本**。如果你打开 `5173`，有可能看到旧目录代码；必须同时确认进程工作目录。

本候选包新增 `scripts/start-web-demo.sh`，默认选择已经验证过的 `5174 + 8001`，并在端口已被占用时直接停止，避免无意复用旧进程。

## 3. Web 本地演示怎么打开

### 3.1 首次准备

在项目根目录：

```bash
cp config-examples/web-demo.env.example /tmp/stb-web-demo.env
```

编辑 `/tmp/stb-web-demo.env`，只填写**隔离演示数据库**和演示 JWT。不要把正式企业微信 Secret 或生产数据库写进这个文件。

需要保证：

```text
APP_ENV=development
AUTH_MODE=prototype
PROTOTYPE_AUTH_ENABLED=true
ALLOW_TEST_EMPLOYEE_HEADER=false
PROTOTYPE_USER_EMPLOYEE_NOS=E-CREATOR,E-ASSIGNEE,E-REVIEWER,E-OBSERVER
CORS_ALLOWED_ORIGINS 包含 http://127.0.0.1:5174
```

并确保 `.venv` 已按 Python 3.12 准备、`web/node_modules` 已通过 `npm ci` 安装。

### 3.2 启动

```bash
WANGXU_WEB_DEMO_ENV_FILE=/tmp/stb-web-demo.env ./scripts/start-web-demo.sh
```

脚本会：

1. 锁定**当前脚本所在的项目目录**；
2. 拒绝复用已经被占用的 5174/8001；
3. 校验 prototype 配置与 CORS；
4. 启动 FastAPI；
5. 真实请求 `/health/ready`；
6. 真实请求 `/api/v1/auth/prototype-users`，要求至少存在一个演示用户；
7. 启动当前目录的 Vite；
8. 打印最终打开地址。

脚本**不会**：

- 自动执行 Alembic；
- 自动 seed；
- 创建/删除数据库；
- 杀掉 5173/8000 上的未知进程；
- 修改正式企业微信配置。

### 3.3 用户打开地址

浏览器打开：

```text
http://127.0.0.1:5174/login
```

不要把下面地址当成登录页：

```text
http://127.0.0.1:8001
```

`8001` 是 FastAPI；需要看接口文档时打开：

```text
http://127.0.0.1:8001/docs
```

停止本次 5174/8001 服务：在启动脚本所在终端按 `Ctrl+C`。

## 4. 5173 / 8000 到底是什么

项目原来的 `scripts/start-dev.sh` 使用：

```text
前端 5173
后端 8000
```

这仍然可以作为普通开发端口，但**不能根据端口判断它是不是最新候选包**。2026-09-07 本地验收已经出现过“5173 指向旧目录”的真实情况。

因此当前发布候选排查与验收统一使用：

```text
5174 = 当前候选包 Web 本地演示
8001 = 当前候选包 Web 本地演示 FastAPI
```

如果将来主动改端口，可以设置：

```bash
STB_WEB_DEMO_FRONTEND_PORT=5184 \
STB_WEB_DEMO_BACKEND_PORT=8011 \
WANGXU_WEB_DEMO_ENV_FILE=/tmp/stb-web-demo.env \
./scripts/start-web-demo.sh
```

同时必须把新前端 Origin 加入该演示 env 的 `CORS_ALLOWED_ORIGINS`。

## 5. 正式企业微信怎么打开

正式环境与 Web 本地 prototype 演示是两套入口。

正式使用时：

```text
员工
  ↓
企业微信
  ↓
旺序任务中枢应用
  ↓
企业微信配置的 HTTPS 应用首页
  ↓
wx.qy.login() 获取一次性 code
  ↓
FastAPI /api/v1/auth/wecom
  ↓
业务 JWT
```

因此员工**不需要**手工输入 `5174`、`8001`、`5173` 或 `8000`。

最终生产域名/外部端口目前未在本候选包中固定，需公司服务器部署时配置。通常会由 HTTPS 反向代理暴露 Web 和 API，但具体域名、证书、反向代理规则以《生产部署与上线交接文档》和公司 IT 配置为准。

**禁止**把本地 `AUTH_MODE=prototype` 配置复制到生产环境。生产必须使用批准的 `AUTH_MODE=wecom`。

## 6. 微信小程序的两种运行方式

### 6.1 mock 模式

`wechat-miniprogram/config.js` 默认：

```js
mode: "mock"
```

优点：不用启动后端也可以看页面。  
限制：**不能证明创建、保存、发送、数据库落表等真实链路已经跑通。**

### 6.2 API 联调模式

需要在**测试副本**中改为：

```js
mode: "api"
apiBaseUrl: "http://测试后端地址"
```

并配置批准的测试认证方式。

正式验收“AI问题未回答仍可确认发送”时，必须使用 API 联调模式或正式测试环境，不能只用 mock 模式。

## 7. 如何确认自己没有打开旧目录

如果页面表现和最新包不一致，先查端口对应进程的工作目录。

macOS 示例：

```bash
lsof -nP -iTCP:5173 -sTCP:LISTEN
lsof -nP -iTCP:5174 -sTCP:LISTEN
```

拿到 PID 后：

```bash
lsof -a -p <PID> -d cwd
```

正确的 5174 应指向**你本次解压并执行的候选包 `web/` 目录**。

不要看到一个 Vite 页面能打开，就默认它是最新代码。

## 8. 本次两个专项问题的验收入口

### Web 登录

```text
打开：http://127.0.0.1:5174/login
验证：演示用户 → 登录 → /workbench → /me → 再访问 /login 自动返回工作台
```

真实自动化命令（服务已启动）：

```bash
cd web
STB_REAL_E2E=1 \
STB_REAL_E2E_EMPLOYEE_NO=E-CREATOR \
STB_REAL_E2E_API_BASE_URL=http://127.0.0.1:8001 \
PLAYWRIGHT_BASE_URL=http://127.0.0.1:5174 \
PLAYWRIGHT_SKIP_WEBSERVER=true \
npx playwright test e2e/dev-18-real-login.spec.ts --project=mobile-390
```

### AI问题未回答仍可发送

后端真实 HTTP 证明（服务已启动，演示用户已准备）：

```bash
STB_E2E_API_BASE_URL=http://127.0.0.1:8001 \
STB_E2E_CREATOR=E-CREATOR \
STB_E2E_ASSIGNEE=E-ASSIGNEE \
STB_E2E_REPORTER=E-REVIEWER \
STB_E2E_REVIEWER=E-REVIEWER \
./scripts/verify-ai-send-e2e.py
```

该脚本不会回答任何 AI 问题；它验证“9项必填完整 + task_source=null”能够真实创建、提交确认、确认发送并重新读取任务。它不会迁移或清理数据库，因此必须对隔离测试库运行。

小程序页面还需在微信开发者工具 API 模式完成：

```text
AI仍有待确认项
→ 不填写AI回答
→ 手工补齐9项必填
→ 任务来源留空
→ 进入发送确认
→ 最终发送
→ 任务详情/数据库核对为待接受
```

## 9. 最容易混淆的结论

```text
5174/8001 = 本地真实前后端联调，但登录方式是 prototype 演示身份。
mock 小程序 = 页面演示，不代表后端联通。
正式企业微信 = 企业微信应用入口，不使用本地开发端口。
5173/8000 = 旧默认开发端口，可能存在旧目录进程，不能用端口名判断版本。
```

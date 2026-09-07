# 旺序AI任务中枢 V1.1｜Web 登录路由 Hotfix 执行报告

> 执行日期：2026-09-07  
> 基线包：`Test11-smart-task-board-feature16-release-candidate.zip`  
> 基线 SHA-256：`14156239ae7e5a269791120e016d65161149f62e797d8a1a6e2b5edf04d68b9a`  
> Hotfix 包：`Test11-WebLogin-Hotfix-smart-task-board-feature16-release-candidate.zip`  
> Hotfix SHA-256：`ce32ea5b724111a16d2f6a24e9790654a3cb8f821a58b70590ed473f0af19ef9`

## 1. 问题结论

原 Web `/login` 路由仍指向 `RoutePlaceholders.LoginRoute`，因此用户实际看到的是 DEV-02 开发占位文案。项目中已有真实的 `LoginPage`，但此前没有接入生产路由。

本次只修复 Web 登录路由和登录后安全返回，不修改后端认证、数据库、微信小程序、云函数或 Feature 01～16 核心业务。

## 2. 实际改动

### 2.1 生产代码

1. `web/src/app/router.tsx`
   - `/login` 从 `<LoginRoute />` 改为 `<LoginPage />`。
   - 不再从 `RoutePlaceholders` 导入 `LoginRoute`。
   - 其他占位路由保持不变。

2. `web/src/pages/LoginPage.tsx`
   - 读取 `location.state.source`。
   - 复用 `readReturnSourceState()` 与 `resolveReturnTarget()`。
   - 直接登录时默认进入 `/workbench`。
   - 从 `/tasks`、任务详情或带查询参数的内部路由跳转到登录时，登录成功后恢复原路由。
   - 外部或不安全返回地址回退到 `/workbench`。
   - 已登录用户访问 `/login` 时直接进入安全目标。
   - 已登录状态下不再请求演示用户列表。

### 2.2 测试代码

更新：

- `web/src/app/router.test.tsx`
- `web/src/pages/LoginPage.test.tsx`
- `web/e2e/dev-06-auth-permissions.spec.ts`
- `web/e2e/dev-07-task-intake.spec.ts`

覆盖：

- `/login` 必须渲染“选择演示身份”，不得再显示 DEV-02。
- 匿名访问保护路由后进入真实登录页。
- 登录后恢复 `/tasks?status=pending_accept`。
- 登录后保留 query 和 hash。
- 不安全外部返回地址被拦截。
- 已登录用户访问 `/login` 自动离开登录页。
- Task Intake 的匿名跳转测试同步到真实登录页合同。

## 3. 白名单差异检查

以原 Test11 ZIP 重新解压得到的干净目录为基线，Hotfix 最终只有以下 6 个文件内容发生变化：

```text
web/src/app/router.tsx
web/src/pages/LoginPage.tsx
web/src/app/router.test.tsx
web/src/pages/LoginPage.test.tsx
web/e2e/dev-06-auth-permissions.spec.ts
web/e2e/dev-07-task-intake.spec.ts
```

检查结果：

```text
added: 0
removed: 0
changed: 6
WHITELIST_DIFF_PASS
```

以下目录与 Test11 基线内容完全一致：

```text
app/
alembic/
wechat-miniprogram/
cloud-functions/
```

数据库表、字段和 Alembic migration 均未变化。

## 4. 当前环境已执行测试

### 4.1 ZIP 生成前

```text
后端非 PostgreSQL：508 passed / 28 deselected
微信小程序累计测试：21 / 21 PASS
微信小程序 JS 语法：49 checked / 0 failed
Python compileall：PASS
ChatService task_intake：PASS
ChatService auth：PASS
ChatService config：PASS
```

### 4.2 Web 源码静态检查

当前环境无法联网安装 `web/node_modules`，因此没有伪造 `npm lint/test/build` 通过结论。

已实际执行：

```text
TypeScript transpile syntax：81 个 web/src + web/e2e 文件，0 error
Hotfix 路由/安全返回合同：17 / 17 PASS
修改文件 trailing whitespace：0
旧 Web E2E 登录占位断言扫描：0 条残留
```

### 4.3 ZIP 反向验收

最终 ZIP 解压到全新目录后：

```text
文件数：514 / 514
缺失文件：0
新增文件：0
内容不一致：0
ZIP_REVERSE_CONTENT_PASS

后端非 PostgreSQL：508 passed / 28 deselected
微信小程序累计测试：21 / 21 PASS
微信小程序 JS 语法：49 checked / 0 failed
Python compileall：PASS
ChatService：3 / 3 PASS
TypeScript syntax：81 files / 0 errors
Hotfix contract：17 / 17 PASS
```

## 5. 本地正式 Web 门禁

由于执行容器无法访问 npm registry，以下门禁必须在已有依赖或可联网的本地/CI 环境运行：

```bash
cd web
npm ci
npm run lint
npm test -- --run
npm run build
npx playwright test \
  e2e/dev-06-auth-permissions.spec.ts \
  e2e/dev-07-task-intake.spec.ts
```

通过标准：

```text
ESLint：0 error
Vitest：0 failed（基线109项，本次新增登录测试后数量应增加）
TypeScript + Vite build：PASS
Playwright DEV-06 / DEV-07：0 failed
```

## 6. 不在本次范围

本次没有：

- 修改企业微信 `wx.qy.login()`；
- 修改 `/api/v1/auth/wecom`；
- 新增账号密码或短信登录；
- 修改 token / refresh token 机制；
- 修改用户表、权限模型或状态机；
- 清理其他 Web Placeholder；
- 修改管理员后台登录；
- 新增数据库迁移。

## 7. 当前状态

```text
IMPLEMENTATION：DONE
WHITELIST REVIEW：PASS
BACKEND / MINI PROGRAM REGRESSION：PASS
ZIP REVERSE ACCEPTANCE：PASS
WEB FULL NPM GATE：PENDING LOCAL/CI EXECUTION
REAL WECOM E2E：UNCHANGED / BLOCKED BY ENVIRONMENT
```

该包可作为 Test11 的 Web 登录路由 Hotfix 候选；完成上述 Web 正式门禁后再替换生产部署制品。

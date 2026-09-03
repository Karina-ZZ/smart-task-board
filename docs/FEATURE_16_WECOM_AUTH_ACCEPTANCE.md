# 功能16前置P0｜企业微信正式登录与 LoginService 退出验收记录

> 日期：2026-09-03  
> 状态：代码实现完成；本地可执行门禁通过；真实企业微信环境门禁待执行。  
> 范围：只替换身份认证入口与 ChatService 调用鉴权，不改变任务、看板、通知规则、状态机、权限计算、绩效、负荷或功能15员工筛选。

## 1. 最终生产登录链路

```text
wx.qy.login()
→ 一次性 code
→ POST /api/v1/auth/wecom
→ FastAPI 服务端获取企业微信应用 access_token
→ /cgi-bin/miniprogram/jscode2session
→ userid + corpid
→ 校验 corpid
→ users.wecom_user_id
→ 现有 employee_no
→ 现有 AuthenticationService.issue()
→ 现有 accessToken + refreshToken
→ GET /api/v1/me
→ 原有角色/授权范围/任务权限
```

企业微信只证明身份。`employee_no`、`users.role_type`、`user_authorized_scopes`、任务关系与任务状态仍由旺序现有模型决定。

## 2. LoginService 退出

已从运行源码删除：

```text
cloud-functions/LoginService/
```

小程序生产代码已删除：

- `loginServiceBaseUrl`；
- `requestSmsCode()`；
- `loginByPhone()`；
- `wangxu.cloudAiToken` 持久化 token；
- 手机号验证码登录回退逻辑。

历史 Feature05/15 验收文档可继续保留 LoginService 文字作为历史证据；不代表当前运行代码仍启用该服务。

## 3. ChatService 鉴权替换

业务 access token 不直接共享给 ChatService。小程序使用当前旺序 access token请求：

```text
POST /api/v1/auth/ai-token
```

FastAPI 签发 5 分钟短时 JWT：

```text
sub = employee_no
scope = task-intake
aud = wangxu-chat
```

ChatService 生产环境要求 `CHAT_REQUIRE_AUTH=true`，只接受该 token。请求 body 中的 `currentUser.employeeNo` 仍可作为 AI 提示上下文，但不再作为认证身份来源。

## 4. 数据库变化

本次“正式登录替换”新增业务表/字段/Alembic migration：

```text
0
```

继续使用已经存在的：

```text
users.wecom_user_id
users.employee_no
auth_refresh_tokens
```

以及前一步已经独立完成的：

```text
departments.wecom_department_id
```

未知企业微信 userid 不自动 INSERT users；返回绑定失败。禁用用户也不能建立业务会话。

## 5. 修改边界

允许改动集中在：

- FastAPI auth schema/route/service/security/config；
- WeCom integration client；
- UserRepository 的 `wecom_user_id` 查询；
- 小程序 session bootstrap / cloud-ai auth；
- ChatService auth；
- 认证专项测试与当前文档。

未修改任务创建、拆解、执行、汇报、变更、验收、归档、通知业务规则、负荷、优先级、绩效、高管看板和功能15查询逻辑。

## 6. 自动化证据

### FastAPI / 后端

```text
企业微信 client/service/API auth 专项：21 passed
后端非PostgreSQL累计：475 passed, 28 deselected
Python compileall：PASS
```

新增覆盖：

- 企业微信 access_token 服务端获取与缓存；
- `jscode2session` code→userid/corpid；
- access_token 失效后只刷新一次；
- corpId 不匹配拒绝；
- 未绑定/disabled 用户拒绝；
- `/auth/wecom` 请求不能注入 employee_no；
- `/auth/ai-token` 必须有现有旺序 Bearer；
- AI token 的 `sub/aud/scope` 正确。

### 微信小程序

```text
累计测试：20/20 PASS
```

包含：

- `wx.qy.login()` 首次登录；
- 并发首次请求复用一次登录；
- access/refresh session 沿用旧机制；
- ChatService 前先获取 FastAPI 短时 AI token；
- AI token 内存复用；
- 生产源码无 LoginService URL / SMS 登录函数 / cloudAiToken。

### ChatService

```text
test_task_intake.py：PASS
test_auth.py：PASS
```

覆盖合法 task-intake token、缺 token、错误 scope。

## 7. 仍未执行的真实环境门禁

以下不能在当前无真实企业微信凭据/企业微信开发者工具的容器中伪造为 PASS：

1. 真实 `CorpID + AppSecret` 获取 access_token；
2. 企业微信开发者工具“企业微信模式”中的 `wx.qy.login()`；
3. 应用可见范围内成员真实 userid 映射；
4. 其他企业 corpid / 未绑定成员 / disabled成员真机验证；
5. 真实 PostgreSQL refresh-token / 事务门禁；
6. React Web、Ruff全量、微信开发者工具最终发布门禁。

因此 DEV-18 继续为 `IN_PROGRESS`，不能标记最终发布成功。

# 企业微信自建应用 + H5 第一版部署配置

## 1. 推荐入口

建议同域部署：

```text
https://task.company.com/               -> React H5
https://task.company.com/api/v1/*       -> FastAPI
```

企业微信自建应用主页配置为 `https://task.company.com/`，网页 OAuth 回调配置为：

```text
https://task.company.com/auth/wecom/callback
```

## 2. 后端环境变量

复制 `config-examples/backend.env.example` 后配置真实值，至少包括：

```text
APP_ENV=production
AUTH_MODE=wecom
ALLOW_TEST_EMPLOYEE_HEADER=false
WECOM_CORP_ID=企业CorpID
WECOM_AGENT_ID=自建应用AgentID
WECOM_APP_SECRET=仅服务器保存的应用Secret
WECOM_H5_BASE_URL=https://task.company.com
JWT_SECRET_KEY=至少32字符随机密钥
CHAT_SERVICE_JWT_SECRET_KEY=与ChatService验证侧一致的至少32字符随机密钥
```

严禁把 `WECOM_APP_SECRET`、JWT Secret、ChatService Secret 放入 React/Vite 环境变量。

## 3. H5 构建环境变量

基于 `web/.env.wecom.example`：

```text
VITE_AUTH_MODE=wecom
VITE_API_BASE_URL=https://task.company.com
VITE_WECOM_CORP_ID=企业CorpID
VITE_WECOM_AGENT_ID=自建应用AgentID
VITE_WECOM_REDIRECT_URI=https://task.company.com/auth/wecom/callback
VITE_CHAT_SERVICE_BASE_URL=https://正式ChatService地址
```

CorpID/AgentID 是公开标识；应用 Secret 仍然只能在 FastAPI 服务器。

## 4. 企业微信后台

- 创建或选择“旺序AI任务中枢”自建应用。
- 设置应用可见范围。
- 设置应用主页为正式 H5 地址。
- 设置网页授权/可信域名为 H5 域名。
- 将 FastAPI 调用企业微信 API 的公网出口 IP 配入应用可信 IP。
- 配置 HTTPS 正式证书。
- 确保 `users.wecom_user_id` 已绑定真实企业微信 `userid`。

## 5. 登录链路

```text
企业微信应用主页
→ /login
→ open.weixin.qq.com OAuth (snsapi_base)
→ /auth/wecom/callback?code=...&state=...
→ POST /api/v1/auth/wecom
→ FastAPI /cgi-bin/auth/getuserinfo
→ userid
→ users.wecom_user_id
→ employee_no
→ 旺序 JWT
→ 原目标页面
```

OAuth `state` 与原始内部 return target 都保存在当前浏览器会话中，并在 callback 校验。

## 6. 企业微信应用消息

生产 `AUTH_MODE=wecom` 下，通知 Outbox 使用真实 `WeComApplicationMessageProvider`：

```text
notifications/outbox
→ employee_no
→ users.wecom_user_id
→ /cgi-bin/message/send
→ 企业微信自建应用消息
```

当前第一版 Provider 的通用深链落到 `/notifications`；用户打开具体任务后仍由 FastAPI 二次校验权限。后续如 Outbox Provider 合同增加 `task_id`，可进一步改成直接任务深链，不需要改变通知生成规则。

## 7. Nginx 关键要求

- `/` 回退 `index.html`，支持 React Router 刷新深链。
- `/api/` 反向代理 FastAPI。
- 传递 `X-Forwarded-Proto`、`X-Forwarded-For`、`Host`。
- HTTPS only；生产禁止 prototype/test-header auth。
- H5 与 API 同域时可减少 CORS 与 OAuth 配置复杂度。

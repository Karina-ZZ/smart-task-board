# RELEASE-01｜生产环境变量说明

## 1. FastAPI：`/etc/wangxu/backend.env`

| 变量 | 必填 | 敏感 | 说明 |
|---|---:|---:|---|
| `APP_ENV` | 是 | 否 | 生产必须为 `production` |
| `DATABASE_URL` | 是 | 是 | PostgreSQL连接串；Compose内主机名使用 `postgres` |
| `AUTH_MODE` | 是 | 否 | 生产必须为 `wecom` |
| `ALLOW_TEST_EMPLOYEE_HEADER` | 是 | 否 | 生产必须为 `false` |
| `PROTOTYPE_AUTH_ENABLED` | 是 | 否 | 生产必须为 `false` |
| `WECOM_CORP_ID` | 是 | 是 | 企业微信CorpID |
| `WECOM_AGENT_ID` | 是 | 是 | 企业微信应用AgentID |
| `WECOM_APP_SECRET` | 是 | 是 | 企业微信应用Secret |
| `JWT_SECRET_KEY` | 是 | 是 | 旺序业务JWT，至少32字符 |
| `CHAT_SERVICE_JWT_SECRET_KEY` | 是 | 是 | AI短Token共享Secret，至少32字符 |
| `CORS_ALLOWED_ORIGINS` | 条件 | 否 | Web开放时填写精确HTTPS Origin |

`JWT_SECRET_KEY` 与 `CHAT_SERVICE_JWT_SECRET_KEY` 必须是两个不同的随机值。

## 2. ChatService：`/etc/wangxu/chatservice.env`

| 变量 | 必填 | 敏感 | 说明 |
|---|---:|---:|---|
| `APP_ENV` | 是 | 否 | 生产必须 `production` |
| `CHAT_REQUIRE_AUTH` | 是 | 否 | 生产必须 `true` |
| `CHAT_SERVICE_JWT_SECRET_KEY` | 是 | 是 | 必须与FastAPI同名值完全一致 |
| `DASHSCOPE_API_KEY` | 是 | 是 | Qwen/DashScope API Key |
| `QWEN_MODEL` | 是 | 否 | 默认 `qwen-plus` |
| `QWEN_ASR_MODEL` | 条件 | 否 | 启用语音转写时填写 |
| `MYSQL_*` | 否 | 是 | 仅ChatService会话/审计，不存任务业务真数据 |

## 3. 部署进程变量

这些变量用于部署脚本，不写入应用源码：

```text
WANGXU_BACKEND_ENV_FILE=/etc/wangxu/backend.env
WANGXU_CHAT_ENV_FILE=/etc/wangxu/chatservice.env
WANGXU_TLS_CERT_DIR=/etc/wangxu/tls
WANGXU_API_DOMAIN=api.example.com
WANGXU_AI_DOMAIN=ai.example.com
WANGXU_BACKUP_DIR=/var/backups/wangxu/postgres
WANGXU_BACKUP_RETENTION_DAYS=30
```

## 4. 禁止进入源码的内容

以下真实值不得写入Git、ZIP、小程序、Web JS、截图或日志：

- `WECOM_APP_SECRET`；
- `DASHSCOPE_API_KEY`；
- PostgreSQL密码；
- `JWT_SECRET_KEY`；
- `CHAT_SERVICE_JWT_SECRET_KEY`；
- 任何有效Access Token/Refresh Token。

## 5. Secret生成

分别运行两次：

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

第一次用于 `JWT_SECRET_KEY`；第二次同时填入FastAPI和ChatService的 `CHAT_SERVICE_JWT_SECRET_KEY`。

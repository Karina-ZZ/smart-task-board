# ChatService cloud function

`cloud-functions/ChatService` is the only runtime cloud function in this directory. The historical SMS `LoginService` has been removed from the production source tree. User identity now originates from WeCom and is converted by FastAPI into the existing Smart Task Board session.

## 1. Mini Program configuration

Only the ChatService URL remains in `wechat-miniprogram/config.js`:

```js
cloudServices: {
  chatServiceBaseUrl: "https://your-chat-service.example.com",
}
```

WeCom application secrets, Smart Task Board JWT secrets, Qwen keys and MySQL passwords must never be placed in the Mini Program.

## 2. Authentication boundary

The Mini Program authenticates through:

```text
wx.qy.login()
→ POST /api/v1/auth/wecom
→ FastAPI maps users.wecom_user_id to employee_no
→ existing Smart Task Board access/refresh session
```

Before calling ChatService, the Mini Program requests a short-lived token from:

```text
POST /api/v1/auth/ai-token
Authorization: Bearer <Smart Task Board access token>
```

The token is scoped to `task-intake` and is kept only in Mini Program memory. ChatService does not trust `currentUser.employeeNo` in the request body as an authenticated identity.

## 3. ChatService

Entrypoint: `ChatService/app.py`

API:

- `POST /task-intake/extract`
- `POST /task-intake/clarify`
- `POST /task-intake/transcribe`
- `GET /health`

Production configuration is loaded from the dedicated ChatService secret file. Local default: `secrets/chatservice.env`; server override: set `WANGXU_CHAT_ENV_FILE=/etc/wangxu/chatservice.env`. Use `config-examples/chatservice.env.example` as the template. The recommended keys are:

```text
APP_ENV=production
CHAT_REQUIRE_AUTH=true
CHAT_SERVICE_JWT_SECRET_KEY=<same value as FastAPI CHAT_SERVICE_JWT_SECRET_KEY>
CHAT_SERVICE_JWT_ISSUER=smart-task-board
CHAT_SERVICE_JWT_AUDIENCE=wangxu-chat
DASHSCOPE_API_KEY=<DashScope key>
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_MODEL=qwen-plus
QWEN_ASR_MODEL=<optional audio-capable model>
QWEN_TIMEOUT_SECONDS=30
MYSQL_HOST=...
MYSQL_PORT=3306
MYSQL_DATABASE=...
MYSQL_USER=...
MYSQL_PASSWORD=...
```

See `docs/SECRETS_CONFIGURATION_GUIDE.md` for exact local/server replacement steps.

Production startup refuses `CHAT_REQUIRE_AUTH=false` or the development JWT secret.

## 4. Database boundary

`mysql/schema.sql` may retain the historical LoginService account/session tables for non-destructive migration compatibility, but the current runtime does not read or write them. ChatService may continue using `chat_sessions`, `chat_messages`, and `llm_request_logs` for conversation and LLM observability.

Smart Task Board business truth remains in PostgreSQL (`users`, `tasks`, `task_inputs`, `ai_extraction_records`, etc.). Do not duplicate task lifecycle data into MySQL.

## 5. Qwen boundary

The task-intake prompt explicitly forbids node/dependency generation and estimated hours. ChatService generates suggestions only. FastAPI validates people, dates and task weight before persisting each extraction round.

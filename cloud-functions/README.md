# Feature 05 Cloud Functions

This directory contains two independently deployable Flask cloud functions plus the optional MySQL 8.0 support schema.

## 1. Mini Program configuration

Only change these values in `wechat-miniprogram/config.js` when the cloud functions are redeployed:

```js
cloudServices: {
  loginServiceBaseUrl: "https://your-login-service.example.com",
  chatServiceBaseUrl: "https://your-chat-service.example.com",
}
```

Qwen keys, MySQL passwords and JWT secrets must never be placed in the Mini Program.

## 2. LoginService

Entrypoint: `LoginService/app.py`

API:

- `POST /sms/code` `{ "phone": "13800138000" }`
- `POST /login/phone` `{ "phone": "13800138000", "code": "123456" }`
- `GET /health`

Important environment variables:

```text
APP_ENV=production
SMS_PROVIDER=aliyun_dypnsapi
SMS_CODE_HASH_SECRET=<strong random secret>
CLOUD_JWT_SECRET=<same secret used by ChatService>
CLOUD_JWT_ISSUER=wangxu-cloud-login
CLOUD_JWT_AUDIENCE=wangxu-cloud-chat
MYSQL_HOST=...
MYSQL_PORT=3306
MYSQL_DATABASE=...
MYSQL_USER=...
MYSQL_PASSWORD=...
ALIYUN_ACCESS_KEY_ID=...
ALIYUN_ACCESS_KEY_SECRET=...
ALIYUN_DYPN_ENDPOINT=dypnsapi.aliyuncs.com
ALIYUN_SMS_SIGN_NAME=...
ALIYUN_SMS_TEMPLATE_CODE=...
```

Local development can use `SMS_PROVIDER=mock`. The returned `debugCode` is disabled when `APP_ENV=production`.

## 3. ChatService

Entrypoint: `ChatService/app.py`

API:

- `POST /task-intake/extract`
- `POST /task-intake/clarify`
- `POST /task-intake/transcribe`
- `GET /health`

Important environment variables:

```text
APP_ENV=production
CHAT_REQUIRE_AUTH=false
QWEN_API_KEY=<DashScope key>
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_MODEL=qwen-plus
QWEN_ASR_MODEL=<optional audio-capable model>
QWEN_TIMEOUT_SECONDS=30
MYSQL_HOST=...
MYSQL_PORT=3306
MYSQL_DATABASE=...
MYSQL_USER=...
MYSQL_PASSWORD=...
CLOUD_JWT_SECRET=<same value as LoginService>
CLOUD_JWT_ISSUER=wangxu-cloud-login
CLOUD_JWT_AUDIENCE=wangxu-cloud-chat
```

`CHAT_REQUIRE_AUTH=false` keeps Feature 05 address-only integration usable while the Mini Program does not yet expose a phone-login UI. For production exposure, enable `CHAT_REQUIRE_AUTH=true` after wiring the provided LoginService client functions into the approved login UX.

## 4. Database boundary

`mysql/schema.sql` is only for LoginService/ChatService account, conversation and LLM-observability records. Smart Task Board business truth remains in PostgreSQL (`tasks`, `task_inputs`, `ai_extraction_records`, etc.). Do not duplicate task lifecycle data into MySQL.

## 5. Qwen boundary

The task-intake prompt explicitly forbids node/dependency generation and estimated hours. ChatService generates suggestions only. FastAPI validates people, dates and task weight before persisting each extraction round.

# 旺序任务中枢：密钥与企业微信配置替换操作手册

> 适用范围：功能16 / DEV-18 企业微信正式登录与 ChatService。  
> 目标：真实密钥只存在于开发者电脑或服务器，不写入源码、小程序、Git 或交付 ZIP。

## 1. 需要维护的真实配置

本项目把密钥拆成两个文件，避免一个服务获得不需要的秘密。

### FastAPI：`backend.env`

负责：

- 企业微信 `CorpId`
- 企业微信 `AgentId`
- 企业微信自建应用 `Secret`
- PostgreSQL 连接信息
- 旺序业务 JWT Secret
- FastAPI 给 ChatService 签发短时 AI Token 的共享 Secret

### ChatService：`chatservice.env`

负责：

- 通义千问 / DashScope API Key
- Qwen 模型配置
- ChatService AI Token 验证 Secret
- 可选 MySQL 会话/LLM审计库信息

> `CHAT_SERVICE_JWT_SECRET_KEY` 必须在两个文件中填写同一个值。它只用于 FastAPI 与 ChatService 之间验证短时 `task-intake` Token，不是企业微信 Secret，也不是通义千问 Key。

---

## 2. 本地第一次配置

在项目根目录执行：

```bash
mkdir -p secrets
cp config-examples/backend.env.example secrets/backend.env
cp config-examples/chatservice.env.example secrets/chatservice.env
```

然后打开：

```text
secrets/backend.env
secrets/chatservice.env
```

填写真实值。

### `secrets/backend.env` 至少替换

```text
WECOM_CORP_ID=企业微信CorpId
WECOM_AGENT_ID=企业微信自建应用AgentId
WECOM_APP_SECRET=企业微信自建应用Secret
JWT_SECRET_KEY=旺序业务JWT随机密钥
CHAT_SERVICE_JWT_SECRET_KEY=FastAPI与ChatService共享的AI Token随机密钥
DATABASE_URL=真实PostgreSQL连接串
```

### `secrets/chatservice.env` 至少替换

```text
DASHSCOPE_API_KEY=通义千问Key
CHAT_SERVICE_JWT_SECRET_KEY=与backend.env完全相同的值
```

不要把真实 Key 填进：

```text
wechat-miniprogram/config.js
config-examples/*.example
README.md
任何测试文件
```

---

## 3. 如何生成两个随机 JWT Secret

macOS / Linux 在终端分别执行两次：

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

第一次结果放入：

```text
backend.env -> JWT_SECRET_KEY
```

第二次结果同时放入：

```text
backend.env     -> CHAT_SERVICE_JWT_SECRET_KEY
chatservice.env -> CHAT_SERVICE_JWT_SECRET_KEY
```

两个 Secret 不要设置成同一个值。

---

## 4. 本地启动方式

### 4.1 PostgreSQL

Docker Compose 的 `${POSTGRES_*}` 插值需要显式指定 backend 配置文件：

```bash
docker compose --env-file secrets/backend.env up -d postgres
```

然后执行：

```bash
alembic upgrade head
```

### 4.2 FastAPI

默认情况下，项目会自动读取：

```text
secrets/backend.env
```

因此项目根目录直接启动即可：

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

无需把 CorpId / Secret 手工 `export` 到终端。

### 4.3 ChatService

ChatService 默认自动读取：

```text
secrets/chatservice.env
```

启动方式按现有云函数/Flask方式执行。例如本地：

```bash
cd cloud-functions/ChatService
python app.py
```

无论从哪个目录启动，默认配置路径都按项目根目录解析。

---

## 5. 本地替换信息时怎么操作

### 更换通义千问 Key

只编辑：

```text
secrets/chatservice.env
```

修改：

```text
DASHSCOPE_API_KEY=新Key
```

保存后重启 ChatService。FastAPI 不需要修改。

### 更换企业微信 Secret

只编辑：

```text
secrets/backend.env
```

修改：

```text
WECOM_APP_SECRET=新Secret
```

保存后重启 FastAPI。

### 更换 CorpId / AgentId

只编辑：

```text
WECOM_CORP_ID=
WECOM_AGENT_ID=
```

保存后重启 FastAPI。更换企业主体后，还必须确认数据库中的 `users.wecom_user_id`、`departments.wecom_department_id` 与新企业通讯录重新绑定；仅修改 CorpId 并不会自动迁移组织数据。

### 更换 `CHAT_SERVICE_JWT_SECRET_KEY`

必须同时修改：

```text
secrets/backend.env
secrets/chatservice.env
```

两个文件填完全相同的新值，然后同时重启 FastAPI 和 ChatService。只改一边会导致 ChatService 将 FastAPI 新签发的 AI Token 判为无效。

### 更换 `JWT_SECRET_KEY`

只改 FastAPI 的 `backend.env`，但这会使旧的旺序登录 Token 失效，在线用户通常需要重新登录。不要把它作为日常 Key 轮换项随意修改。

---

## 6. 云服务器推荐放置位置

生产服务器不要把真实密钥放在源码目录。推荐：

```text
/opt/wangxu/smart-task-board/     # 程序代码
/etc/wangxu/backend.env           # FastAPI秘密
/etc/wangxu/chatservice.env       # Qwen/ChatService秘密
```

创建目录和权限：

```bash
sudo mkdir -p /etc/wangxu
sudo cp config-examples/backend.env.example /etc/wangxu/backend.env
sudo cp config-examples/chatservice.env.example /etc/wangxu/chatservice.env
sudo chmod 700 /etc/wangxu
sudo chmod 600 /etc/wangxu/backend.env /etc/wangxu/chatservice.env
```

然后用编辑器填写真实配置：

```bash
sudo nano /etc/wangxu/backend.env
sudo nano /etc/wangxu/chatservice.env
```

FastAPI 启动进程增加：

```text
WANGXU_BACKEND_ENV_FILE=/etc/wangxu/backend.env
```

ChatService 启动进程增加：

```text
WANGXU_CHAT_ENV_FILE=/etc/wangxu/chatservice.env
```

例如临时手工启动：

```bash
WANGXU_BACKEND_ENV_FILE=/etc/wangxu/backend.env \
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

ChatService：

```bash
WANGXU_CHAT_ENV_FILE=/etc/wangxu/chatservice.env \
python cloud-functions/ChatService/app.py
```

正式生产建议把这两个路径写入 systemd / Docker / 云服务启动配置，而不是每次手工输入。

---

## 7. 云服务器以后替换 Key 的最短操作

通义千问 Key：

```bash
sudo nano /etc/wangxu/chatservice.env
# 修改 DASHSCOPE_API_KEY
# 保存
# 只重启 ChatService
```

企业微信 Secret / CorpId / AgentId：

```bash
sudo nano /etc/wangxu/backend.env
# 修改 WECOM_CORP_ID / WECOM_AGENT_ID / WECOM_APP_SECRET
# 保存
# 只重启 FastAPI
```

因此后续发布新代码时，不需要把真实密钥重新打进源码 ZIP，也不会因为重新解压程序目录而覆盖 `/etc/wangxu/`。

---

## 8. 启动安全校验

`AUTH_MODE=wecom` 时 FastAPI 会拒绝以下配置缺失：

```text
WECOM_CORP_ID
WECOM_AGENT_ID
WECOM_APP_SECRET
JWT_SECRET_KEY（至少32字符）
DATABASE_URL
```

生产 ChatService 会拒绝：

```text
DASHSCOPE_API_KEY / QWEN_API_KEY 为空
CHAT_REQUIRE_AUTH != true
CHAT_SERVICE_JWT_SECRET_KEY 缺失、过短或仍是开发默认值
```

这意味着配置错了会在启动阶段明确失败，而不是等用户登录或调用 Qwen 时才出现隐蔽错误。

---

## 9. Git / ZIP 安全规则

`.gitignore` 已忽略：

```text
secrets/*
```

只保留空目录占位 `.gitkeep`。正式交付 ZIP 也不应该包含：

```text
secrets/backend.env
secrets/chatservice.env
```

打包前建议检查：

```bash
find secrets -type f -maxdepth 1 -print
```

正常源码包只应看到：

```text
secrets/.gitkeep
```

如果看到 `backend.env` 或 `chatservice.env`，停止打包并删除 ZIP 中的密钥文件。

---

## 10. 发生泄露后的处理

如果真实 Secret 曾经进入 Git、聊天、工单、公开 ZIP 或日志，不要只“从文件里删除”。应立即在对应平台**吊销/重置**：

- 通义千问 Key：在 DashScope/阿里云控制台生成新 Key，旧 Key 作废；
- 企业微信 Secret：企业微信管理后台重置自建应用 Secret；
- `JWT_SECRET_KEY`：生成新值并重启 FastAPI，接受现有会话失效；
- `CHAT_SERVICE_JWT_SECRET_KEY`：两边同时轮换并同时重启；
- 数据库密码：数据库和 `DATABASE_URL` 同步轮换。

轮换后再检查日志、Git历史和已经分发的 ZIP，确认没有继续暴露。

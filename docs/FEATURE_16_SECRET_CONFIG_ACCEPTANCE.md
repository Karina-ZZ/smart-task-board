# 功能16：密钥文件配置基线验收记录

> 日期：2026-09-03  
> 范围：只新增安全配置加载、模板与操作文档；不修改任务/看板/通知/状态机等业务规则。

## 实现

- 本地 FastAPI 默认读取 `secrets/backend.env`。
- 本地 ChatService 默认读取 `secrets/chatservice.env`。
- 服务器可分别通过 `WANGXU_BACKEND_ENV_FILE`、`WANGXU_CHAT_ENV_FILE` 指向 `/etc/wangxu/*.env`。
- 进程环境变量优先于 env 文件，便于未来接云 Secret Manager。
- 增加 `WECOM_AGENT_ID` 配置并在 `AUTH_MODE=wecom` 下做启动校验。
- ChatService 支持标准 `CHAT_SERVICE_JWT_SECRET_KEY`，同时保留旧 `WANGXU_AI_JWT_SECRET` 兼容读取。
- `secrets/*` 被 Git 忽略，仅保留 `.gitkeep`。
- 新增 `config-examples/backend.env.example`、`config-examples/chatservice.env.example`。
- 新增 `docs/SECRETS_CONFIGURATION_GUIDE.md` 说明本地、服务器替换和密钥轮换。

## 测试证据

- `python -m compileall -q app cloud-functions`：PASS。
- 后端非 PostgreSQL：`476 passed, 28 deselected`。
- ChatService：`test_auth.py`、`test_task_intake.py`、`test_config_file.py`：PASS。
- 微信小程序累计：`20/20 PASS`。
- 微信 JS `node --check`：PASS。
- Ruff：当前执行容器未安装 `ruff`，本轮未宣称该门禁通过；功能16正式 Python 3.12 环境仍需执行完整 Ruff 门禁。
- 真实 PostgreSQL：本次配置改造未修改业务/数据库结构；正式 DEV-18 PostgreSQL 门禁仍按既定计划执行。

## 安全结论

最终交付包不得包含 `secrets/backend.env` 或 `secrets/chatservice.env`。真实 CorpId/AgentId/Secret、DashScope Key、数据库密码和 JWT Secret 均由部署者在本地/服务器自行填写。

# RELEASE-01 Deployment Engineering

本目录仅承载生产部署工程，不承载业务规则。

## Compose路径

```bash
export WANGXU_BACKEND_ENV_FILE=/etc/wangxu/backend.env
export WANGXU_CHAT_ENV_FILE=/etc/wangxu/chatservice.env
export WANGXU_TLS_CERT_DIR=/etc/wangxu/tls
export WANGXU_API_DOMAIN=api.example.com
export WANGXU_AI_DOMAIN=ai.example.com

./deploy/scripts/preflight.sh
./deploy/scripts/deploy-compose.sh
```

## Host/systemd路径

`deploy/systemd/` 提供FastAPI和ChatService的服务模板。两种路径二选一，不应同时启动同一端口。

## 重要边界

RELEASE-01没有修改任何功能01～16业务代码，也没有实现真实企业微信通知Provider、通知Worker或通讯录同步。后续必须按独立Release开发和验收。

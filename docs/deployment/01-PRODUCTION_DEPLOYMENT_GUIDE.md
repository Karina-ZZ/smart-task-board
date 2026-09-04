# 旺序AI任务中枢｜生产部署与上线交接文档

> 版本：RELEASE-01 / V1.0  
> 基线：Feature16 / DEV-18 Test8 Release Candidate（本交付可见的最新完整源码包）  
> 目标：补齐生产部署工程，不修改功能01～16业务代码、状态机、页面、API语义或业务迁移。

## 1. 本阶段边界

RELEASE-01只新增：

- `deploy/` 下的 Docker、Nginx、systemd、环境模板与运维脚本；
- `docs/deployment/` 上线交接资料；
- RELEASE-01静态部署验收。

明确不修改：

- `app/` 业务代码；
- `alembic/versions/` 业务迁移；
- `wechat-miniprogram/pages/` 与 `wechat-miniprogram/utils/`；
- `web/src/`；
- 现有业务测试。

真实企业微信通知 Provider、通讯录同步和通知 Worker 属于后续 RELEASE 阶段，不在本阶段伪造实现。

## 2. 生产架构

```text
企业微信小程序
      |
   HTTPS 443
      |
+-----+----------------------+
|                            |
api.<company-domain>     ai.<company-domain>
|                            |
Nginx                        Nginx
|                            |
FastAPI                   ChatService
|                            |
PostgreSQL                   +--> Qwen/DashScope
```

PostgreSQL是任务业务唯一真数据源。ChatService可选使用MySQL保存AI会话/调用审计，但不得复制任务业务表。

## 3. 推荐服务器目录

```text
/opt/wangxu/releases/<version>/     # 每个发布包独立目录
/opt/wangxu/current -> releases/... # 当前版本软链接
/etc/wangxu/backend.env             # FastAPI生产秘密
/etc/wangxu/chatservice.env         # ChatService/Qwen秘密
/etc/wangxu/tls/fullchain.pem       # TLS证书
/etc/wangxu/tls/privkey.pem         # TLS私钥
/var/backups/wangxu/postgres/       # 数据库备份
```

生产秘密不得放在源码目录、ZIP、小程序或Web前端。

## 4. 首次准备

### 4.1 安装基础环境

Compose部署路径要求：

- Linux服务器；
- Docker Engine；
- Docker Compose plugin；
- `curl`；
- 可访问企业微信API和DashScope；
- DNS已将API域名和AI域名解析到服务器；
- 已准备有效HTTPS证书。

### 4.2 创建配置目录

```bash
sudo mkdir -p /etc/wangxu/tls /var/backups/wangxu/postgres /opt/wangxu/releases
sudo chmod 700 /etc/wangxu
```

复制生产模板：

```bash
sudo cp deploy/env/backend.env.production.example /etc/wangxu/backend.env
sudo cp deploy/env/chatservice.env.production.example /etc/wangxu/chatservice.env
sudo chmod 600 /etc/wangxu/backend.env /etc/wangxu/chatservice.env
```

填写真实值后，放置：

```text
/etc/wangxu/tls/fullchain.pem
/etc/wangxu/tls/privkey.pem
```

## 5. 配置运行变量

部署终端设置：

```bash
export WANGXU_BACKEND_ENV_FILE=/etc/wangxu/backend.env
export WANGXU_CHAT_ENV_FILE=/etc/wangxu/chatservice.env
export WANGXU_TLS_CERT_DIR=/etc/wangxu/tls
export WANGXU_API_DOMAIN=api.example.com
export WANGXU_AI_DOMAIN=ai.example.com
```

详细变量见 `02-PRODUCTION_ENVIRONMENT_VARIABLES.md`。

## 6. 预检

```bash
./deploy/scripts/preflight.sh
```

预检会阻止：

- 非 `APP_ENV=production`；
- 非 `AUTH_MODE=wecom`；
- 测试员工头仍开启；
- ChatService未强制鉴权；
- JWT Secret不足32字符；
- FastAPI/ChatService共享AI Token Secret不一致；
- 缺失企业微信或Qwen配置；
- 缺失TLS证书；
- 疑似测试数据库连接。

## 7. 首次部署

```bash
./deploy/scripts/deploy-compose.sh
```

脚本顺序：

1. 生产预检；
2. 渲染Nginx配置；
3. 验证Compose；
4. 拉取PostgreSQL/Nginx镜像；
5. 构建FastAPI/ChatService镜像；
6. 启动PostgreSQL；
7. 执行 `alembic upgrade head`；
8. 启动FastAPI、ChatService、Nginx；
9. 执行健康检查。

数据库迁移只执行升级，不自动降级。

## 8. 健康检查

```bash
./deploy/scripts/health-check.sh
```

必须通过：

```text
https://api.example.com/health/live
https://api.example.com/health/ready
https://ai.example.com/health
```

`/health/ready`会实际校验PostgreSQL连接。

## 9. 生产数据库

Compose中的PostgreSQL只位于内部Docker网络，不映射宿主机5432端口，避免直接暴露公网。

首次生产库必须从空库通过Alembic建立，不复制测试库。

上线前检查：

```bash
docker compose -f deploy/docker-compose.production.yml run --rm backend alembic heads
docker compose -f deploy/docker-compose.production.yml run --rm backend alembic current
```

迁移head以交付版本实际结果为准，不在部署脚本中硬编码。

## 10. 小程序生产配置

本RELEASE-01不会修改当前小程序功能代码和本地开发配置。正式企业微信接入阶段必须再完成：

- `project.config.json` 使用正式AppID；
- `wechat-miniprogram/config.js` 从 `mode: "mock"` 改为 `mode: "api"`；
- `apiBaseUrl` 指向正式FastAPI HTTPS地址；
- `chatServiceBaseUrl` 指向正式ChatService HTTPS地址；
- 真实Secret仍不得写入小程序。

## 11. 企业微信与人员绑定

正式登录关系：

```text
企业微信 userid
 -> users.wecom_user_id
 -> users.employee_no
 -> 旺序任务权限
```

企业微信身份不得替代内部 `employee_no`。首次上线前应完成正式员工、部门、角色和授权范围数据初始化。

## 12. RELEASE-01后仍需完成

本阶段故意不修改业务代码，因此以下生产能力仍需后续开发/验收：

1. 真实企业微信消息发送 Provider；
2. 提醒调度 Worker；
3. 企业微信通讯录全量/增量同步；
4. 正式AppID和真实 `wx.qy.login` E2E；
5. 真实Qwen生产Smoke；
6. 最终Outbox多轮并发门禁。

在这些完成前只能判定“部署工程就绪”，不能判定生产GO。

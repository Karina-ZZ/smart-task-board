# RELEASE-01 生产部署工程验收记录

> 目标：新增部署与运维基础，不影响当前功能代码。

## 1. 新增范围

- `deploy/Dockerfile.backend`
- `deploy/Dockerfile.chatservice`
- `deploy/docker-compose.production.yml`
- `deploy/nginx/wangxu.conf.template`
- `deploy/env/*.production.example`
- `deploy/systemd/*.service`
- `deploy/scripts/*.sh`
- `docs/deployment/*.md`

## 2. 未修改范围

本阶段不得修改：

```text
app/
alembic/versions/
wechat-miniprogram/pages/
wechat-miniprogram/utils/
web/src/
tests/
```

交付前使用SHA-256清单比较上述目录，必须得到0差异。

## 3. 部署合同

至少验证：

1. 所有Shell脚本通过 `bash -n`；
2. Compose中PostgreSQL没有宿主机端口发布；
3. backend/chatservice/nginx/postgres服务均存在；
4. 生产env模板强制 `APP_ENV=production`；
5. FastAPI模板强制 `AUTH_MODE=wecom`；
6. ChatService模板强制 `CHAT_REQUIRE_AUTH=true`；
7. Nginx模板仅开放HTTP跳HTTPS和HTTPS反向代理；
8. 备份脚本生成custom-format dump和SHA-256；
9. 恢复脚本默认拒绝破坏性恢复；
10. 代码回滚不自动执行数据库downgrade。

## 4. 尚未宣称通过的真实环境门禁

由于本阶段不持有公司生产服务器、正式TLS证书、CorpID/AgentID/Secret或正式Qwen Key，不宣称：

- Docker真实生产部署PASS；
- 企业微信真实E2E PASS；
- Qwen公网调用PASS；
- 企业微信真实通知PASS。

这些应在公司预发/生产环境执行。

## 5. 本次实际验收结果

在当前执行环境实际完成：

```text
RELEASE-01静态部署合同                 PASS
所有deploy Shell脚本 bash -n           PASS
生产Compose YAML解析                    PASS
Nginx模板渲染 + nginx -t                PASS
Python compileall                        PASS
后端非PostgreSQL累计                     495 passed / 28 deselected
微信小程序累计                           21/21 PASS
微信小程序全部JS node --check            PASS
```

当前环境没有Docker CLI，因此没有伪造 `docker compose build/up` 通过；真实Compose启动必须在公司预发服务器执行。

`web/node_modules` 不在当前Release ZIP中，因此本轮未重复Web lint/test/build；本阶段对 `web/src/` 做了逐文件SHA-256保护比较且0差异。

## 6. 业务代码零影响证据

开发前后对以下受保护目录逐文件计算SHA-256：

```text
app/
alembic/versions/
wechat-miniprogram/pages/
wechat-miniprogram/utils/
web/src/
tests/
```

共比较361个文件，前后清单摘要均为：

```text
c0b0752d81788632631974bcfd1269f833eb5b83370725af6eb33f968daed58b
```

差异：

```text
0
```

因此RELEASE-01没有改变功能01～16现有业务代码、页面、业务迁移或现有测试。

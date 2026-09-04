# RELEASE-01 生产部署工程执行报告

## 结论

RELEASE-01已完成部署工程基础，并保持功能01～16受保护业务目录逐文件SHA-256零差异。

本阶段只新增 `deploy/` 和 `docs/deployment/`，没有修改业务Service/API/Model、业务迁移、微信页面/工具、Web业务源码或既有测试。

## 新增能力

- FastAPI生产Dockerfile；
- ChatService + Gunicorn生产Dockerfile；
- PostgreSQL/FastAPI/ChatService/Nginx生产Compose；
- PostgreSQL仅内部网络，不发布5432宿主端口；
- API/AI双子域名HTTPS Nginx模板；
- production env模板；
- Compose生产预检；
- Nginx配置渲染；
- 健康检查；
- PostgreSQL备份、受保护恢复；
- Release软链接切换与代码回滚；
- systemd替代部署模板；
- 5份生产部署/企业微信/发布/运维文档；
- RELEASE-01静态部署合同与清单。

## 实际验收

```text
RELEASE-01静态部署合同          PASS
Shell bash -n                   PASS
Compose YAML解析                PASS
Nginx渲染 + nginx -t            PASS
compileall                      PASS
非PG累计                        495 passed / 28 deselected
小程序累计                      21/21 PASS
小程序JS语法                    PASS
受保护361文件SHA-256            0差异
```

当前执行环境无Docker CLI，因此未伪造 `docker compose build/up` 通过；应在公司预发服务器完成真实Compose部署门禁。

## 明确未提前开发

为避免影响现有功能，本阶段没有提前修改业务代码实现：

- 真实企业微信通知Provider；
- 通知调度Worker；
- 企业微信通讯录同步；
- 正式小程序AppID/API地址；
- 任何新业务表或Alembic迁移。

这些按后续RELEASE阶段单独开发、测试和验收。

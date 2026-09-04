# RELEASE-01｜生产运维、备份与回滚

## 1. 日常健康检查

```bash
export WANGXU_API_DOMAIN=api.example.com
export WANGXU_AI_DOMAIN=ai.example.com
./deploy/scripts/health-check.sh
```

检查：

- FastAPI进程存活；
- FastAPI数据库ready；
- ChatService存活；
- PostgreSQL容器健康；
- Nginx状态；
- 磁盘、CPU、内存；
- 通知失败量和Qwen失败量（后续监控平台接入）。

## 2. PostgreSQL备份

```bash
sudo WANGXU_BACKUP_DIR=/var/backups/wangxu/postgres \
  ./deploy/scripts/backup-postgres.sh
```

默认保留30天，可通过 `WANGXU_BACKUP_RETENTION_DAYS` 调整。

备份会生成：

```text
*.dump
*.dump.sha256
```

备份文件应再复制到NAS/对象存储/异机位置，不能只保存在数据库同一磁盘。

## 3. 恢复演练

`restore-postgres.sh` 是破坏性操作保护脚本，默认拒绝执行。只允许在已批准维护窗口、目标库明确后：

```bash
export WANGXU_ALLOW_RESTORE=YES
./deploy/scripts/restore-postgres.sh /path/to/backup.dump
```

恢复后必须：

1. `alembic upgrade head`；
2. `/health/ready`；
3. 业务Smoke；
4. 权限专项检查。

## 4. 代码发布与版本切换

建议：

```text
/opt/wangxu/releases/20260904-release01
/opt/wangxu/releases/20260910-release02
/opt/wangxu/current -> 当前版本
```

激活版本：

```bash
./deploy/scripts/activate-release.sh /opt/wangxu/releases/<version>
```

然后从 `/opt/wangxu/current` 执行部署。

## 5. 代码回滚

```bash
./deploy/scripts/rollback-code.sh /opt/wangxu/releases/<previous-version>
```

该脚本只切回和重建旧代码，不会执行数据库downgrade。

## 6. 数据库回滚原则

禁止因应用异常直接执行：

```text
alembic downgrade -1
```

必须先判断：

- 新迁移是否破坏性；
- 新字段是否已有生产数据；
- 上一版本代码是否兼容新Schema；
- 是否应该恢复备份而不是down migration。

优先采用“旧代码兼容新Schema”的代码回滚路径。

## 7. 生产日志禁止项

日志不得输出：

- 完整JWT/Refresh Token；
- 企业微信Secret；
- Qwen API Key；
- 数据库密码；
- 其他生产密钥。

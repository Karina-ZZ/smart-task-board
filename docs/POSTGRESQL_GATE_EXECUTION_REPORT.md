# PostgreSQL真实集成测试执行记录

> 执行日期：2026-09-03
> 基线：功能13正式源码
> 目标Alembic head：`b1c2d3e4f5a6`
> 当前结论：`BLOCKED_BY_EXECUTION_ENVIRONMENT`，不是业务测试失败。

## 1. 已实际完成

- 从功能13正式ZIP建立独立测试副本。
- 确认项目声明依赖 `psycopg[binary]>=3.2,<4.0`。
- 确认正式项目要求 Python `>=3.12,<3.13`。
- 确认当前执行容器实际为 Python 3.13.5，因此不满足正式PG门禁解释器条件。
- 确认当前容器没有 `psql` / `postgres` / `pg_ctl` / `psycopg`。
- 尝试 `apt-get update/install postgresql postgresql-client`：失败，原因是软件源网络不可达/超时。
- 尝试 `pip install psycopg[binary]`：失败，原因是DNS解析不可用。
- 搜索本机PostgreSQL二进制、apt缓存和pip离线wheel：均不存在。
- Alembic PostgreSQL offline SQL从base生成到head成功，共1267行，最终revision为`b1c2d3e4f5a6`。
- 更新原21项PG专项的旧revision/table基线：`f7b8c9d0e1f2` -> `b1c2d3e4f5a6`，并加入`task_decomposition_records`；7个PG测试文件的EXPECTED_TABLES均与当前ORM 28表完全一致。
- 原21项PG专项收集确认：21项。
- 新增功能13真实PG专项：7项；合计28项PG测试可收集。
- 新增PG测试文件完成Python语法检查。
- 修改测试基线/新增PG测试后，非PG累计回归：`436 passed, 28 deselected`。

## 2. 新增功能13 PG专项

1. `assignment_status` PostgreSQL CHECK真实约束。
2. `pending`协办节点在真实事务中禁止执行。
3. 承接过程中提醒生成异常时，节点状态/taskVersion完整rollback。
4. 两个连接并发accept同一协办节点，只允许一个业务结果。
5. accept/reject并发竞争，最终状态必须唯一且语义一致。
6. 两连接并发插入同一notification occurrence，唯一约束只保留一条。
7. 两outbox worker并发发送同一notification，必须只调用一次provider。

第7项是专门用于发现真实并发重复推送风险的门禁测试。

## 3. 当前环境阻塞

正式PG门禁仍不能宣告PASS，因为当前执行环境同时缺少：

- PostgreSQL server/client；
- Python `psycopg` 驱动；
- Python 3.12（当前是3.13.5）；
- 外网/DNS，因此无法在线安装前述依赖。

所以本轮没有产生任何伪造的`21/28 PostgreSQL passed`结论。

## 4. 已提供的一键执行入口

- `scripts/provision_postgresql_gate_docker.sh`：在有Docker/网络的环境启动严格隔离的PostgreSQL 16测试库，固定为`127.0.0.1:46479/smarttaskboard_core_test`。
- `scripts/run_postgresql_gate.sh`：强制检查Python 3.12、psycopg、隔离数据库地址和空库，然后执行：
  1. Alembic空库upgrade到head；
  2. 28项PG专项；
  3. 5个关键并发测试各连续20轮；
  4. 436项非PG累计回归；
  5. 全部通过才输出`POSTGRESQL_GATE_PASS`。

## 5. 通过标准

只有实际得到以下结果才可把正式验收中的PG限制取消：

```text
Alembic empty-db upgrade: PASS (b1c2d3e4f5a6)
PostgreSQL专项: 28 passed / 0 failed / 0 skipped
关键并发测试: 5类 x 20轮，全部PASS
非PG累计: 436 passed
POSTGRESQL_GATE_PASS
```

本记录中的`BLOCKED_BY_EXECUTION_ENVIRONMENT`表示运行条件不足，不表示以上测试已经通过。

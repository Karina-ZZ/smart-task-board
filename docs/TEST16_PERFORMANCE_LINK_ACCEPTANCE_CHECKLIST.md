# Test16 绩效关联显示 Hotfix 本地验收清单

## A. 小程序 mock 页面

1. 导入本次新的 Test16 Performance-Link-Hotfix 小程序目录。
2. 确认运行目录是本次新包，不要复用旧 Test16 目录。
3. 创建任务并在“关联绩效指标”中选择一个指标。
4. 页面应立即显示已选择的绩效指标名称。
5. 保存草稿并进入发送确认。
6. 确认发送任务。
7. 打开任务详情 → “绩效”。
8. 必须仍显示同一绩效指标、业务单元、匹配等级/原因，不得显示“未关联已确认绩效指标”。
9. 选择“不关联绩效”后重新进入详情，绩效区域应恢复未关联状态。

## B. 真实 PostgreSQL 合同

在项目批准的隔离测试库上执行：

```bash
export RUN_POSTGRESQL_INTEGRATION=1
export POSTGRES_TEST_DATABASE_URL='postgresql+psycopg://...@127.0.0.1:46479/smarttaskboard_core_test'
export DATABASE_URL="$POSTGRES_TEST_DATABASE_URL"
./.venv/bin/python -m pytest -q \
  tests/integration/test_business_capabilities_postgresql.py::test_confirmed_performance_relation_survives_send_and_detail_reload_postgresql \
  -m postgresql
```

通过标准：

- draft 阶段确认关系为 `is_confirmed=true`；
- 发送后任务状态为 `pending_acceptance`；
- 重新读取任务详情仍返回同一 `metric_id` / `metric_name`；
- 数据库中正式关系没有被取消或复制。

## C. 累计回归

至少重新执行：

- Test16 正式 PostgreSQL 门禁；
- 原 Outbox 并发门禁；
- 小程序累计测试；
- 微信开发者工具 API 模式页面验证；
- 后端非 PostgreSQL 累计回归。

本 Hotfix 不要求修改数据库结构，也不得通过重建、删表或清理业务数据来获得通过。

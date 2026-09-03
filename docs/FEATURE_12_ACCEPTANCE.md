# 功能12验收记录：绩效、优先级、负荷与冲突

## 最终口径

- 绩效匹配不再二次调用 Qwen/LLM；Qwen 仅负责功能05的任务字段结构化。
- FastAPI 从 `tasks + departments + performance_metrics` 读取权威数据，生成 `task_performance_matches` 候选。
- 绩效总分：类型25% + 事业部25% + 指标名称25% + 定义/公式20% + 交付物5%。
- 文本相似度：中文字符2～4 gram TF-IDF，余弦相似度80% + 指标关键词覆盖率20%。
- `>=80` 强相关，`50-79.99` 弱相关，`<50` 无明显相关；只有创建人确认的唯一 `is_confirmed=true` 关系进入优先级。
- 创建人选择“不关联绩效”会真实清除后端正式确认关系，不是本地假状态。
- 优先级：重要性45%任务权重 + 35%正式绩效 + 20%汇报层级；紧急性60%时间压力 + 25%逾期 + 15%突发；默认阈值70。
- `remaining_hours` 按 Asia/Shanghai 工作日每日容量窗口计算；当前数据模型没有节假日/班次表，因此没有擅自假设09:00-18:00班次。
- 员工负荷仅统计 `effective_at IS NOT NULL` 且状态为 `in_progress/blocked/pending_report`、并与周期相交的主承办任务。
- 负荷五维：剩余工时40%、权重25%、任务数15%、突发10%、受阻/逾期10%，并保存参数快照。
- 冲突检测覆盖容量、截止集中、依赖、突发挤占；`estimated_hours` 不参与；消失的冲突转 `resolved`，不删除历史。
- 工作台/任务概览/详情只触发后端优先级重算并读取结果，客户端不实现公式。
- 不新增 `workload_snapshot_task_details`，没有提前进入后续高管负荷下钻功能。

## 数据表

读取：`tasks`, `departments`, `users`, `employee_profiles`, `performance_metrics`, `task_performance_matches`, `task_nodes`, `task_node_dependencies`, `task_issues`, `system_parameters`。

计算结果：`task_performance_matches`, `task_priority_scores`, `workload_snapshots`, `task_conflicts`。

本功能无需新增数据库字段或Alembic迁移。

## 门禁结果

- 后端非PostgreSQL累计：425 passed。
- PostgreSQL opt-in：21 skipped；当前环境未安装 `psycopg` 且未配置隔离PostgreSQL测试库，未伪装为通过。
- 迁移合同：32 passed；Alembic单一head `a9c4e7f1b2d3`。
- 微信功能01～12累计：15组 PASS。
- Python compileall：PASS。
- 全部微信JS `node --check`：PASS。
- React：本累计包无 `web/node_modules`，当前环境未执行React test/build；功能12只修改API类型/调用适配，最终包保留源码。

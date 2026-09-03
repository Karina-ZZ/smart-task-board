# 功能12验收记录：绩效、优先级、负荷与冲突

- 绩效候选不再调用 Qwen；Qwen 仅负责功能05的任务字段结构化。
- FastAPI 使用确定性规则生成绩效候选：类型25%、事业部25%、名称25%、定义/公式20%、交付物5%。
- 文本相似度使用中文字符2～4 gram TF-IDF，余弦相似度80% + 指标关键词覆盖率20%。
- 创建人可确认唯一绩效指标，也可真实选择“不关联绩效”；候选本身不进入优先级。
- 四象限、remaining_hours、员工负荷与冲突均为服务端计算字段；小程序只触发重算、读取与筛选。
- remaining_hours、负荷、冲突均不读取 estimated_hours。
- 四象限读取最新 task_priority_scores；工作台/任务概览/详情读取前触发后端优先级重算。
- 功能12不实现高管负荷任务下钻，不新增 workload_snapshot_task_details。

## 当前环境门禁

- 后端非PostgreSQL累计：425 passed；21项PostgreSQL opt-in未执行。
- 微信功能01～12：15组 PASS。
- Python / 微信JS语法检查：PASS。
- Alembic：无功能12新迁移，当前单一head `a9c4e7f1b2d3`。

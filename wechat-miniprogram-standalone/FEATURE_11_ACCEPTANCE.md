# 功能11验收记录｜完成申请、多轮验收与自动归档

状态：DONE（当前环境可执行门禁）

## 本功能完成

- 主承办人在全部有效节点完成、且不存在未关闭问题时，可提交真实完成申请。
- 完成申请只要求“完成说明 + 交付摘要”；不接收用户填写的 `actual_hours`。
- 每次重新提交生成新的 `task_completion_reviews.review_round`，历史拒绝轮次不覆盖。
- 验收人体验按最终确认实现：通过仅二次确认；退回必须填写退回意见，不要求通过意见、评分或验收备注。
- 创建人或指定验收人均可决定当前待验收轮次；无任务关系的管理员/普通员工不因此获得验收权限。
- 验收退回：当前轮次记为 rejected，任务回 `in_progress`，通知主承办人继续处理。
- 验收通过：同一事务执行 `pending_review -> completed -> archived`；`completed` 不作为长期可见状态。
- 任务 `actual_hours` 由系统按 `completed_at - start_time` 自动计算；前端只读。
- 同一验收事务创建唯一 `task_archives` 记录，`archive_snapshot = NULL`；历史非空快照继续兼容读取。
- 新增 Alembic 增量迁移，仅把 `task_archives.archive_snapshot` 调整为 nullable，不改写历史迁移。
- 完成提交、验收通过/退回均接入 `Idempotency-Key + taskVersion`；重复成功请求不会重复创建验收轮次或归档。
- 微信新增真实“提交完成”页，并把任务详情“进入任务验收”从阶段禁用改为真实跳转；所有按钮都调用真实API或真实mock合同。
- 功能12及后续绩效/优先级/负荷/冲突能力未提前混入。

## 累计门禁

- 后端非 PostgreSQL：404 passed，21 PostgreSQL 专项 deselected。
- PostgreSQL 专项：未执行；当前环境 `psycopg` 不可用，且未配置隔离 PostgreSQL 测试库，未伪装为通过。
- 微信累计：14 组 PASS（新增 `task-completion-review.test.js`）。
- Alembic：单一 head `a9c4e7f1b2d3`。
- Python `compileall`：PASS。
- 小程序全部 `.js` `node --check`：PASS。
- 微信包结构：PASS，14个页面均有 `.js/.json/.wxml/.wxss`。
- 手机横向溢出静态检查：新增完成页与详情固定操作栏均使用 `left/right:0 + max-width:750rpx + box-sizing:border-box`，未发现超视口固定宽度。
- React Web lint/test/build：当前累计包未包含 `web/node_modules`，本环境未联网安装依赖，因此本轮不可执行；功能11未修改 Web 源码。

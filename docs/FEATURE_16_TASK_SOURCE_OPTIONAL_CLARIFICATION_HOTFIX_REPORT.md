# 功能16累计候选｜任务来源选填 + AI追问覆盖修复执行报告

> 执行日期：2026-09-07  
> 修改基线：`Test11-WebLogin-Hotfix-smart-task-board-feature16-release-candidate.zip`  
> 基线 SHA-256：`ce32ea5b724111a16d2f6a24e9790654a3cb8f821a58b70590ed473f0af19ef9`  
> P0约束：任务来源改为非必填；不得影响功能01～16、Web登录Hotfix、数据库结构、状态机、权限、绩效/负荷/提醒算法。

## 1. 最终业务口径

创建人进入“确认发送”的硬必填字段由10项收敛为9项：

- 任务名称；
- 任务内容；
- 任务目标；
- 主承办人；
- 汇报对象；
- 验收人；
- 开始时间；
- 截止时间；
- 任务权重。

`task_source / 任务来源`保留为选填字段。有值时正常保存和参与既有下游语义；无值时保存为空，不阻止确认发送。`AI任务助手 / 企业微信 / 语音 / Web`等录入入口继续由`source_channel`承接，不再作为任务来源的强制默认值。

AI追问卡继续保留，但`needsClarification`不再是独立发送门禁。九项真实必填字段完整且其他既有校验通过时，即使还有AI待确认问题，也允许进入确认发送。

## 2. AI追问覆盖修复

修复“用户先手工填写，再回答AI追问后字段被整份AI草稿覆盖”的问题：

1. 追问前把页面当前`normalizedDraft`同步到创建草稿；
2. 页面记录用户明确编辑/选择过的字段；
3. AI仍负责补充本轮未解决字段；
4. 对已经由用户明确确认且不属于本轮未解决目标的字段，最终合并时保留用户值；
5. AI识别记录仍保存AI/服务端返回事实，任务草稿和后续正式任务保存用户最终确认值。

优先级：

```text
用户最新明确填写/选择
>
本轮AI对未解决字段的补充
>
上一轮AI识别值
```

## 3. 实际修改范围

后端：

- `app/services/task_workflow.py`
  - `_validate_send_ready_task()`从发送必填集合移除`task_source`；其余9项、日期、hours、节点/依赖门禁完全不变。

微信小程序：

- `wechat-miniprogram/pages/create/index.js`
  - 不再把任务来源默认成“AI任务助手”。
- `wechat-miniprogram/pages/create-details/index.js`
  - 删除`needsClarification`独立硬阻断；
  - 发送前只校验9项真实必填；
  - 记录用户手工编辑字段；
  - AI追问前传入当前草稿；
  - AI回填后保护用户已确认字段；
  - 用户直接编辑/选择字段时同步消解对应AI缺失/低置信提示。
- `wechat-miniprogram/pages/create-details/index.wxml`
  - 任务来源去掉必填标记，增加选填示例。
- `wechat-miniprogram/pages/create-confirm/index.wxml`
  - 空任务来源显示“未填写”。
- `wechat-miniprogram/utils/api.js`
  - 创建任务payload允许`taskSource=null`；
  - mock AI不再默认“AI任务助手”；
  - clarification支持当前草稿和受保护字段合并。
- `wechat-miniprogram/utils/store.js`
  - mock草稿/发送合同同步允许任务来源为空。

测试/文档：

- `tests/services/test_task_workflow.py`
- `wechat-miniprogram/tests/ai-field-hydration.test.js`
- `wechat-miniprogram/tests/task-creation-clarification-hotfix.test.js`（新增）
- `docs/DEVELOPMENT_PLAN_V1.1.md`：记录本次P0冲突裁决。

## 4. 明确未修改

本次没有修改：

- `alembic/`任何迁移；
- `app/models/task.py`与`app/schemas/task.py`（二者原本已允许`task_source`为空）；
- `web/`任何文件，包括刚完成的Web登录Hotfix；
- 任务接受/退回/AI拆解状态机；
- 节点执行、汇报、变更、验收、自动归档；
- 绩效匹配五项算法和25/25/25/20/5权重；
- 优先级、负荷、冲突计算；
- 功能13通知和协办节点承接规则；
- 功能14高管看板与功能15员工任务筛选；
- ChatService Prompt、Qwen模型配置和云函数业务逻辑。

数据库结构变化：`0`。Alembic新增迁移：`0`。

## 5. 当前环境实际测试证据

专项：

```text
任务来源为空后端确认发送：PASS
其他真实必填缺失仍阻断：PASS
AI问题未回答但9项完整可进入确认发送：PASS
空来源mock发送：PASS
用户手填名称/描述/目标/来源/截止时间后再AI追问仍保留：PASS
AI仍可补充未解决汇报对象：PASS
```

累计：

```text
后端非PostgreSQL：510 passed / 28 deselected
微信小程序累计：22 / 22 test files PASS
微信JS node --check：50 files / 0 failed
Python compileall：PASS
ChatService：test_task_intake / test_auth / test_config_file 全部PASS
Alembic head：c2d3e4f5a6b7
```

## 6. 当前环境未执行门禁

当前容器没有：

```text
psycopg
psql
Docker/PostgreSQL server
微信开发者工具
```

因此28项真实PostgreSQL专项和微信开发者工具设备级验收不能在本环境声明PASS。此次无数据库结构变更，且非PG累计回归全绿；正式放行仍应在用户已有Test11本地/CI环境执行原发布门禁。

## 7. 当前结论

```text
IMPLEMENTATION：DONE
TASK_SOURCE_OPTIONAL：PASS
AI_USER_FIELD_PROTECTION：PASS
BACKEND NON-PG REGRESSION：PASS
MINIPROGRAM REGRESSION：PASS
DATABASE MIGRATION：0
WEB SOURCE CHANGE：0
REAL POSTGRESQL GATE：PENDING ENVIRONMENT
WECHAT DEVTOOLS GATE：PENDING ENVIRONMENT
```

本次只改变“任务来源允许为空”和“AI追问不得覆盖用户已确认值/不得成为额外硬门禁”，其余功能合同保持原状。

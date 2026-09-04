# 功能16 / DEV-18 Test7 AI字段回填优化快照

> 状态：可体验快照（先行交付）
> 基线：Test6-smart-task-board-feature16-release-gate.zip
> 范围：仅优化“AI识别/追问 → 任务创建页字段自动回填”链路。

## 本轮实现

1. ChatService Prompt 增加强制规则：人员字段只解析用户明确提到的人，禁止根据岗位、部门、技能、负荷、直属关系推荐人员。
2. 用户未明确提到主承办人、汇报对象、验收人、协同人时，保持 null/[] 并追问或让用户手工选择。
3. 小程序 mock 模式支持明确人员语句的自动回填，便于微信开发者工具直接体验；未提人员时不推荐。
4. 多轮追问在 mock 模式下会合并上一轮草稿，明确补充的人会写入现有 draft。
5. 创建详情页手工选择人员后，会同步清理该字段对应的 AI missing/low-confidence 状态，避免“已选人但AI仍追问”。
6. 真实 API 模式继续使用现有 FastAPI `TaskIntakeService._resolve_employee_reference()` 做 employeeNo/唯一姓名确定性匹配；0个或多个同名匹配均不猜测。
7. 未改任务发送、接受、AI节点拆解、节点执行、通知、验收、高管看板、企业微信登录等后续业务规则。

## 当前可执行验证

- `python -m compileall -q app cloud-functions/ChatService`：PASS
- ChatService `test_task_intake.py`（PYTHONPATH=.）：PASS
- 小程序累计测试：21/21 PASS
- 新增 `ai-field-hydration.test.js`：PASS
- 小程序关键修改文件 `node --check`：PASS

## 当前环境未完成门禁

- 当前执行容器缺 `psycopg`，全量后端 pytest 在收集阶段被环境依赖阻塞；不记为产品失败或通过。
- Test6 真实PG历史债务、Ruff历史债务尚未在本快照完成最终真实工具复验。
- 真实企业微信正向E2E仍需真实 AppID / CorpId / AgentId / Secret / wx.qy.login code。

## Test7 核心验收口径

- “王琳负责”且王琳唯一匹配 → 主承办人字段自动回填。
- “李明协助”且李明唯一匹配 → 协同人字段自动回填。
- 未明确说人员 → 不推荐任何人。
- 同名歧义 → 不猜，保持空并追问/人工选择。
- AI追问后明确补充人员 → 更新现有草稿并直接反馈到创建页。
- 用户手工选择人员 → 该字段不再继续显示为AI缺失项。

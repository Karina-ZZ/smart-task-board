# 功能05验收记录：AI任务输入与多轮字段追问

## 完成范围

- 工作台保持第二版 AI Hero 视觉与位置，不重做工作台布局。
- 文字输入：FastAPI登记原始输入 -> 小程序直连可替换 ChatService -> Qwen字段识别 -> FastAPI二次校验 -> ai_extraction_records落库。
- 创建信息页展示缺失/低置信追问，支持用户自然语言回答后再次调用 ChatService 整理完整任务字段。
- ChatService Prompt 严禁生成 nodes/dependencies/estimatedHours；功能05不创建正式task、不发送、不拆解节点。
- 语音：录音文件由小程序发送 ChatService `/task-intake/transcribe`；未配置ASR模型时明确失败并回退文字，不假成功。
- 云服务地址集中在 `config.js` 的 `cloudServices.loginServiceBaseUrl/chatServiceBaseUrl`。
- 云函数JWT使用独立 `wangxu.cloudAiToken`，不覆盖功能04 `wangxu.accessToken`。
- 新增可独立部署 `cloud-functions/LoginService` 与 `cloud-functions/ChatService`。
- 新增 `cloud-functions/mysql/schema.sql`，仅保存云登录/会话/LLM日志，不复制任务业务真数据。

## 新增后端兼容接口

- `POST /api/v1/task-inputs/register`：仅登记原始输入，不调用后端LLM。
- `POST /api/v1/task-inputs/{inputId}/external-extractions`：校验并保存外部ChatService/Qwen结果。

原有 `/task-inputs`、`/extract`、`/clarifications` 保留兼容；其字段识别结果也会在Service层剔除预计工时、nodes和dependencies。

## 安全边界

- 小程序不包含Qwen API Key、MySQL密码、JWT Secret。
- FastAPI重新验证人员真实性、ISO日期和任务权重；ChatService结果不能直接成为业务事实。
- 用户只能记录/读取本人提交的task input。
- LoginService短信验证码只保存HMAC摘要，JWT数据库仅保存jti/session元数据。
- `CHAT_REQUIRE_AUTH=false`为当前无手机号登录页面时的地址直连模式；生产启用公网鉴权时应改为true并接入LoginService UI。

## 测试

- 微信累计测试新增 `tests/ai-input.test.js`。
- Backend Service覆盖“原始输入不触发LLM + 外部结果二次验证”。
- Backend API覆盖新增register/external-extractions路由与OpenAPI合同。
- LoginService/ChatService纯服务测试覆盖验证码/JWT与Qwen结构化结果规范化。

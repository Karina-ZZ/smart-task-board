/**
 * Feature: Runtime configuration.
 * Responsibilities: select mock/API mode and external cloud-function endpoints without embedding secrets.
 * Does not own: authentication tokens, Qwen API keys, or request execution.
 * Plan task: WECHAT-MP-05.
 */

module.exports = {
  mode: "mock",
  apiBaseUrl: "",
  authMode: "wecom",
  prototypeEmployeeNo: "",
  requestBodyCase: "snake_case",
  requestTimeoutMs: 12000,
  aiRequestTimeoutMs: 30000,
  timezone: "Asia/Shanghai",

  // ChatService remains independently deployable; identity comes from FastAPI/WeCom.
  cloudServices: {
    chatServiceBaseUrl: "https://aichattest-chat-otqjepryyc.cn-hangzhou.fcapp.run",
  },
};

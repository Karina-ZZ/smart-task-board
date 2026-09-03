/**
 * Feature: Runtime configuration.
 * Responsibilities: select mock/API mode and external cloud-function endpoints without embedding secrets.
 * Does not own: authentication tokens, Qwen API keys, or request execution.
 * Plan task: WECHAT-MP-05.
 */

module.exports = {
  mode: "mock",
  apiBaseUrl: "",
  authMode: "prototype",
  prototypeEmployeeNo: "",
  requestBodyCase: "snake_case",
  requestTimeoutMs: 12000,
  aiRequestTimeoutMs: 30000,
  timezone: "Asia/Shanghai",

  // Feature 05: only these URLs need to change when cloud functions are redeployed.
  cloudServices: {
    loginServiceBaseUrl: "https://aichattst-login-zgtmdzmukf.cn-hangzhou.fcapp.run",
    chatServiceBaseUrl: "https://aichattest-chat-otqjepryyc.cn-hangzhou.fcapp.run",
  },
};

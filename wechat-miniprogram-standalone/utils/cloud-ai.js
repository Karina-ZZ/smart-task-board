/**
 * Feature: Cloud AI gateway for task intake.
 * Responsibilities: call replaceable LoginService/ChatService cloud functions and keep cloud JWT isolated.
 * Does not own: Smart Task Board auth, task persistence, permissions, or business validation.
 * Plan task: WECHAT-MP-05.
 */

const config = require("../config");

const CLOUD_AI_TOKEN_KEY = "wangxu.cloudAiToken";
const CLOUD_AI_EXPIRES_AT_KEY = "wangxu.cloudAiExpiresAt";

function baseUrl(name) {
  const value = config.cloudServices?.[name];
  if (!value) throw Object.assign(new Error("请先配置云函数地址"), { code: "CLOUD_SERVICE_URL_REQUIRED" });
  return String(value).replace(/\/$/, "");
}

function cloudRequest(serviceName, method, path, data, options = {}) {
  return new Promise((resolve, reject) => {
    const token = wx.getStorageSync(CLOUD_AI_TOKEN_KEY);
    wx.request({
      url: `${baseUrl(serviceName)}${path}`,
      method,
      data,
      timeout: options.timeout || config.aiRequestTimeoutMs || 30000,
      header: {
        "content-type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      success(response) {
        const payload = response.data || {};
        if (response.statusCode >= 200 && response.statusCode < 300) {
          resolve(payload.data !== undefined ? payload.data : payload);
          return;
        }
        const message = payload.error?.message || payload.message || "云服务请求失败";
        reject(Object.assign(new Error(message), {
          code: payload.error?.code || payload.code || "CLOUD_SERVICE_ERROR",
          statusCode: response.statusCode,
          requestId: payload.requestId,
        }));
      },
      fail(error) {
        reject(Object.assign(new Error(error.errMsg || "云服务网络不可用"), { code: "CLOUD_NETWORK_ERROR" }));
      },
    });
  });
}

function saveCloudSession(session) {
  if (!session?.token) return session;
  wx.setStorageSync(CLOUD_AI_TOKEN_KEY, session.token);
  if (session.expiresIn) wx.setStorageSync(CLOUD_AI_EXPIRES_AT_KEY, Date.now() + Number(session.expiresIn) * 1000);
  return session;
}

function clearCloudSession() {
  wx.removeStorageSync?.(CLOUD_AI_TOKEN_KEY);
  wx.removeStorageSync?.(CLOUD_AI_EXPIRES_AT_KEY);
  if (!wx.removeStorageSync) {
    wx.setStorageSync(CLOUD_AI_TOKEN_KEY, "");
    wx.setStorageSync(CLOUD_AI_EXPIRES_AT_KEY, "");
  }
}

function requestSmsCode(phone) {
  return cloudRequest("loginServiceBaseUrl", "POST", "/sms/code", { phone });
}

function loginByPhone(phone, code) {
  return cloudRequest("loginServiceBaseUrl", "POST", "/login/phone", { phone, code }).then(saveCloudSession);
}

function extractTaskFields(payload) {
  return cloudRequest("chatServiceBaseUrl", "POST", "/task-intake/extract", payload);
}

function clarifyTaskFields(payload) {
  return cloudRequest("chatServiceBaseUrl", "POST", "/task-intake/clarify", payload);
}

function transcribeVoice(filePath) {
  if (!wx.getFileSystemManager || !filePath) {
    return Promise.reject(Object.assign(new Error("当前设备无法读取录音，请改用文字输入"), { code: "VOICE_FILE_UNAVAILABLE" }));
  }
  return new Promise((resolve, reject) => {
    wx.getFileSystemManager().readFile({
      filePath,
      encoding: "base64",
      success(result) {
        cloudRequest("chatServiceBaseUrl", "POST", "/task-intake/transcribe", {
          audioBase64: result.data,
          fileName: filePath.split("/").pop() || "voice.mp3",
        }).then(resolve, reject);
      },
      fail() {
        reject(Object.assign(new Error("录音读取失败，请改用文字输入"), { code: "VOICE_READ_FAILED" }));
      },
    });
  });
}

module.exports = {
  CLOUD_AI_TOKEN_KEY,
  requestSmsCode,
  loginByPhone,
  clearCloudSession,
  extractTaskFields,
  clarifyTaskFields,
  transcribeVoice,
};

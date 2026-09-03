/**
 * Feature: Cloud AI gateway for task intake.
 * Responsibilities: obtain a short-lived FastAPI AI token and call the replaceable ChatService.
 * Does not own: user login, task persistence, permissions, or business validation.
 * Plan task: DEV-18 / WeCom authentication baseline.
 */

const config = require("../config");

const ACCESS_TOKEN_KEY = "wangxu.accessToken";
let aiTokenCache = null;
let aiTokenPromise = null;

function baseUrl(name) {
  const value = config.cloudServices?.[name];
  if (!value) throw Object.assign(new Error("请先配置云函数地址"), { code: "CLOUD_SERVICE_URL_REQUIRED" });
  return String(value).replace(/\/$/, "");
}

function clearAiToken() { aiTokenCache = null; }

function requestAiToken() {
  const now = Date.now();
  if (aiTokenCache?.token && aiTokenCache.expiresAt > now + 30000) return Promise.resolve(aiTokenCache.token);
  if (aiTokenPromise) return aiTokenPromise;
  const accessToken = wx.getStorageSync(ACCESS_TOKEN_KEY);
  if (!accessToken) return Promise.reject(Object.assign(new Error("请先完成企业微信登录"), { code: "AUTH_REQUIRED" }));
  aiTokenPromise = new Promise((resolve, reject) => {
    wx.request({
      url: `${config.apiBaseUrl}/api/v1/auth/ai-token`,
      method: "POST",
      data: {},
      timeout: config.requestTimeoutMs,
      header: { "content-type": "application/json", Authorization: `Bearer ${accessToken}` },
      success(response) {
        const payload = response.data || {};
        if (response.statusCode >= 200 && response.statusCode < 300 && payload.token) {
          aiTokenCache = {
            token: payload.token,
            expiresAt: Date.now() + Number(payload.expires_in || payload.expiresIn || 300) * 1000,
          };
          resolve(aiTokenCache.token);
          return;
        }
        reject(Object.assign(new Error(payload.error?.message || "AI授权获取失败"), {
          code: payload.error?.code || "AI_AUTH_TOKEN_FAILED",
          statusCode: response.statusCode,
        }));
      },
      fail(error) {
        reject(Object.assign(new Error(error.errMsg || "AI授权网络不可用"), { code: "NETWORK_ERROR" }));
      },
    });
  }).finally(() => { aiTokenPromise = null; });
  return aiTokenPromise;
}

function sendCloudRequest(serviceName, method, path, data, token, options = {}) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: `${baseUrl(serviceName)}${path}`,
      method,
      data,
      timeout: options.timeout || config.aiRequestTimeoutMs || 30000,
      header: { "content-type": "application/json", Authorization: `Bearer ${token}` },
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

function cloudRequest(serviceName, method, path, data, options = {}) {
  return requestAiToken().then((token) => sendCloudRequest(serviceName, method, path, data, token, options))
    .catch((error) => {
      if (error.statusCode !== 401 || options.authRetried) throw error;
      clearAiToken();
      return requestAiToken().then((token) => sendCloudRequest(
        serviceName, method, path, data, token, { ...options, authRetried: true },
      ));
    });
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
  clearAiToken,
  extractTaskFields,
  clarifyTaskFields,
  transcribeVoice,
};

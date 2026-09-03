/**
 * Feature: Mini Program data gateway.
 * Responsibilities: expose one Promise-based interface for local demo data and authenticated FastAPI requests.
 * Does not own: page rendering, business labels, or backend authorization.
 * Plan task: WECHAT-MP-02.
 */

const config = require("../config");
const store = require("./store");
const cloudAI = require("./cloud-ai");
const taskDetailView = require("./task-detail");

function camelKey(key) { return key.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase()); }
function snakeKey(key) { return key.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`); }
function camelize(value) {
  if (Array.isArray(value)) return value.map(camelize);
  if (!value || typeof value !== "object") return value;
  return Object.keys(value).reduce((result, key) => { result[camelKey(key)] = camelize(value[key]); return result; }, {});
}

function snakeize(value) {
  if (Array.isArray(value)) return value.map(snakeize);
  if (!value || typeof value !== "object") return value;
  return Object.keys(value).reduce((result, key) => { result[snakeKey(key)] = snakeize(value[key]); return result; }, {});
}

const ACCESS_TOKEN_KEY = "wangxu.accessToken";
const REFRESH_TOKEN_KEY = "wangxu.refreshToken";
const TOKEN_EXPIRES_AT_KEY = "wangxu.tokenExpiresAt";
let loginPromise = null;
let refreshPromise = null;
let productionCreationDraft = {};

function rawRequest(method, path, data, options) {
  return new Promise((resolve, reject) => {
    const token = wx.getStorageSync(ACCESS_TOKEN_KEY);
    wx.request({
      url: `${config.apiBaseUrl}${path}`,
      method,
      data: config.requestBodyCase === "snake_case" ? snakeize(data) : data,
      timeout: config.requestTimeoutMs,
      header: {
        "content-type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...((options && options.idempotencyKey) ? { "Idempotency-Key": options.idempotencyKey } : {}),
      },
      success(response) {
        if (response.statusCode >= 200 && response.statusCode < 300) { resolve(camelize(response.data)); return; }
        reject(Object.assign(
          new Error(response.data?.error?.message || response.data?.detail || "\u8bf7\u6c42\u5931\u8d25"),
          {
            code: response.data?.error?.code,
            requestId: response.data?.requestId || response.data?.error?.requestId,
            statusCode: response.statusCode,
          },
        ));
      },
      fail(error) { reject(Object.assign(new Error(error.errMsg || "\u7f51\u7edc\u4e0d\u53ef\u7528"), { code: "NETWORK_ERROR" })); },
    });
  });
}

function saveSession(session) {
  if (!session?.accessToken) return session;
  wx.setStorageSync(ACCESS_TOKEN_KEY, session.accessToken);
  if (session.refreshToken) wx.setStorageSync(REFRESH_TOKEN_KEY, session.refreshToken);
  if (session.expiresIn) wx.setStorageSync(TOKEN_EXPIRES_AT_KEY, Date.now() + Number(session.expiresIn) * 1000);
  return session;
}

function clearSession() {
  wx.removeStorageSync?.(ACCESS_TOKEN_KEY);
  wx.removeStorageSync?.(REFRESH_TOKEN_KEY);
  wx.removeStorageSync?.(TOKEN_EXPIRES_AT_KEY);
  if (!wx.removeStorageSync) {
    wx.setStorageSync(ACCESS_TOKEN_KEY, "");
    wx.setStorageSync(REFRESH_TOKEN_KEY, "");
    wx.setStorageSync(TOKEN_EXPIRES_AT_KEY, "");
  }
}

function loginControlled(employeeNo) {
  if (useMock()) return mock("currentUser");
  if (config.authMode !== "prototype") return Promise.reject(Object.assign(new Error("当前环境未配置企业身份认证"), { code: "AUTH_PROVIDER_REQUIRED" }));
  const target = employeeNo || config.prototypeEmployeeNo;
  if (!target) return Promise.reject(Object.assign(new Error("开发环境未配置受控测试身份"), { code: "AUTH_CREDENTIAL_REQUIRED" }));
  if (loginPromise) return loginPromise;
  loginPromise = rawRequest("POST", "/api/v1/auth/login", { employeeNo: target })
    .then((session) => {
      saveSession(session);
      return session.currentUser || rawRequest("GET", "/api/v1/me");
    })
    .finally(() => { loginPromise = null; });
  return loginPromise;
}

function getWeComLoginCode() {
  return new Promise((resolve, reject) => {
    if (!wx.qy || typeof wx.qy.login !== "function") {
      reject(Object.assign(new Error("当前环境不支持企业微信登录"), { code: "WECOM_LOGIN_UNAVAILABLE" }));
      return;
    }
    wx.qy.login({
      timeout: config.requestTimeoutMs,
      success(result) {
        const code = String(result?.code || "").trim();
        if (!code) {
          reject(Object.assign(new Error("企业微信未返回登录凭证"), { code: "WECOM_LOGIN_CODE_MISSING" }));
          return;
        }
        resolve(code);
      },
      fail(error) {
        reject(Object.assign(new Error(error?.errMsg || "企业微信登录失败"), { code: "WECOM_LOGIN_FAILED" }));
      },
    });
  });
}

function loginWeCom() {
  if (useMock()) return mock("currentUser");
  if (config.authMode !== "wecom") {
    return Promise.reject(Object.assign(new Error("当前环境未启用企业微信登录"), { code: "WECOM_AUTH_DISABLED" }));
  }
  if (loginPromise) return loginPromise;
  loginPromise = getWeComLoginCode()
    .then((code) => rawRequest("POST", "/api/v1/auth/wecom", { code }))
    .then((session) => {
      saveSession(session);
      return session.currentUser || rawRequest("GET", "/api/v1/me");
    })
    .finally(() => { loginPromise = null; });
  return loginPromise;
}

function refreshSession() {
  if (refreshPromise) return refreshPromise;
  const refreshToken = wx.getStorageSync(REFRESH_TOKEN_KEY);
  if (!refreshToken) return Promise.reject(Object.assign(new Error("登录状态已失效"), { code: "AUTH_REFRESH_UNAVAILABLE", statusCode: 401 }));
  refreshPromise = rawRequest("POST", "/api/v1/auth/refresh", { refreshToken })
    .then((session) => saveSession(session))
    .catch((error) => { clearSession(); throw error; })
    .finally(() => { refreshPromise = null; });
  return refreshPromise;
}

function recoverSession() {
  if (wx.getStorageSync(REFRESH_TOKEN_KEY)) return refreshSession();
  if (config.authMode === "wecom") return loginWeCom();
  if (config.authMode === "prototype" && config.prototypeEmployeeNo) return loginControlled(config.prototypeEmployeeNo);
  return Promise.reject(Object.assign(new Error("请先完成身份认证"), { code: "AUTH_REQUIRED", statusCode: 401 }));
}

function request(method, path, data, options) {
  const publicAuthPath = path.startsWith("/api/v1/auth/");
  const execute = () => rawRequest(method, path, data, options);
  if (publicAuthPath) return execute();
  const ready = wx.getStorageSync(ACCESS_TOKEN_KEY) ? Promise.resolve() : recoverSession();
  return ready.then(execute).catch((error) => {
    if (error.statusCode !== 401 || options?.authRetried) throw error;
    wx.removeStorageSync?.(ACCESS_TOKEN_KEY);
    if (!wx.removeStorageSync) wx.setStorageSync(ACCESS_TOKEN_KEY, "");
    return recoverSession().then(() => rawRequest(method, path, data, { ...(options || {}), authRetried: true }));
  });
}

function mock(method, ...args) { return Promise.resolve().then(() => store[method](...args)); }
function useMock() { return config.mode === "mock" || !config.apiBaseUrl; }

function normalizeTaskSummary(task) {
  return {
    ...task,
    assigneeName: task.assigneeName || task.mainAssignee?.name || "待分配",
    progressPercent: Number(task.progressPercent || 0),
  };
}

function refreshPriorities() {
  if (useMock()) return Promise.resolve([]);
  return request("POST", "/api/v1/analytics/priorities");
}

function dashboard() {
  if (useMock()) return mock("getDashboard");
  const quadrants = ["important_urgent", "important_not_urgent", "urgent_not_important", "routine"];
  return refreshPriorities().then(() => Promise.all([
    request("GET", "/api/v1/me"),
    request("GET", "/api/v1/dashboard/summary"),
    request("GET", "/api/v1/tasks?pageSize=100"),
    request("GET", "/api/v1/tasks/inbox?action_code=handle_issue&limit=20"),
    request("GET", "/api/v1/notifications"),
    ...quadrants.map((quadrant) => request("GET", `/api/v1/tasks?quadrant=${quadrant}&pageSize=100`)),
  ])).then(([user, summary, allResponse, supportResponse, notificationRows, ...quadrantResponses]) => {
    const quadrantCounts = {};
    const quadrantByTask = {};
    quadrantResponses.forEach((response, index) => {
      const quadrant = quadrants[index];
      quadrantCounts[quadrant] = response.total || 0;
      (response.items || []).forEach((task) => { quadrantByTask[task.taskId] = quadrant; });
    });
    const tasks = (allResponse.items || []).map((task) => normalizeTaskSummary({
      ...task,
      priorityQuadrant: quadrantByTask[task.taskId] || "routine",
    }));
    const count = (statuses) => tasks.filter((task) => statuses.includes(task.status)).length;
    const supportItems = (supportResponse.items || []).map((item) => ({
      ...normalizeTaskSummary(item.task),
      supportReason: item.reason || "有卡点或协作事项等待你的响应",
      supportNodeId: item.node?.nodeId || "",
    }));
    return {
      user,
      tasks,
      metrics: {
        pendingAccept: summary.pendingAcceptanceCount || count(["pending_accept", "pending_acceptance"]),
        decomposing: count(["decomposing"]),
        decompositionFailed: count(["decomposition_failed"]),
        inProgress: count(["in_progress", "blocked", "pending_report"]),
        dueWithin3Days: summary.dueWithin3DaysCount || 0,
        onTimeCompletionRate: summary.onTimeCompletionRate || 0,
        completionRatePeriodDays: summary.completionRatePeriodDays || 90,
        pendingReview: summary.completionReviewCount,
      },
      quadrantCounts,
      supportCount: supportResponse.total || 0,
      supportItems,
      unread: (notificationRows || []).filter((item) => item.actionRequired).length,
    };
  });
}
function tasks(filters) {
  if (useMock()) return mock("listTasks", filters || {});
  const query = Object.keys(filters || {}).filter((key) => filters[key] !== "").map((key) => `${encodeURIComponent(key)}=${encodeURIComponent(filters[key])}`).join("&");
  return request("GET", `/api/v1/tasks${query ? `?${query}` : ""}`).then((response) => (response.items || []).map(normalizeTaskSummary));
}
function taskOverview(filters) {
  if (filters?.source === "executive") return executiveTasks(filters).then((response) => ({ ...response, items: (response.items || []).map(normalizeTaskSummary), statusCounts: response.statusCounts || {} }));
  if (useMock()) return mock("listOverview", filters || {});
  const query = Object.keys(filters || {})
    .filter((key) => filters[key] !== "" && filters[key] !== false && filters[key] !== undefined)
    .map((key) => `${encodeURIComponent(key)}=${encodeURIComponent(filters[key])}`)
    .join("&");
  return refreshPriorities().then(() => request("GET", `/api/v1/tasks${query ? `?${query}` : ""}`)).then((response) => ({
    ...response,
    items: (response.items || []).map((item) => item.nodeId ? {
      ...item,
      ownerName: item.owner?.name || "待分配",
    } : normalizeTaskSummary(item)),
    statusCounts: response.statusCounts || {},
  }));
}
function task(taskId) { return useMock() ? mock("getTask", taskId) : request("GET", `/api/v1/tasks/${taskId}`); }
function taskStatusLogs(taskId, offset = 0, limit = 20) {
  if (useMock()) {
    return mock("getTask", taskId).then((detail) => {
      const items = (detail?.logs || []).slice(offset, offset + limit);
      return { items, limit, offset, total: detail?.logs?.length || 0 };
    });
  }
  return request("GET", `/api/v1/tasks/${taskId}/status-logs?limit=${limit}&offset=${offset}`);
}
function taskOperationLogs(taskId, offset = 0, limit = 20) {
  if (useMock()) return Promise.resolve({ items: [], limit, offset, total: 0 });
  return request("GET", `/api/v1/tasks/${taskId}/operation-logs?limit=${limit}&offset=${offset}`);
}
function taskDetail(taskId) {
  if (useMock()) {
    return mock("getTask", taskId).then((detail) => taskDetailView.buildTaskDetail({
      task: detail,
      allowedActions: detail?.allowedActions || [],
      progressReports: detail?.reports || [],
      issues: detail?.issues || [],
      statusLogs: detail?.logs || [],
      operationLogs: [],
    }));
  }
  return refreshPriorities().then(() => Promise.all([
    request("GET", `/api/v1/tasks/${taskId}`),
    request("GET", `/api/v1/tasks/${taskId}/available-actions`),
    request("GET", `/api/v1/tasks/${taskId}/status-logs?limit=100&offset=0`),
    request("GET", `/api/v1/tasks/${taskId}/progress-reports?limit=50&offset=0`),
    request("GET", `/api/v1/tasks/${taskId}/issues?limit=50&offset=0`),
    request("GET", `/api/v1/tasks/${taskId}/operation-logs?limit=20&offset=0`),
  ])).then(([detail, actions, statusLogs, reports, issues, operationLogs]) => taskDetailView.buildTaskDetail({
    task: detail,
    allowedActions: actions.allowedActions || [],
    permissions: actions,
    statusLogs: statusLogs.items || [],
    progressReports: reports.items || [],
    issues: issues.items || [],
    operationLogs: operationLogs.items || [],
  }));
}
function currentUser() { return useMock() ? mock("currentUser") : request("GET", "/api/v1/me"); }
function bootstrapSession() { return useMock() ? currentUser() : request("GET", "/api/v1/me"); }
function logout() {
  if (useMock()) return Promise.resolve();
  return rawRequest("POST", "/api/v1/auth/logout", {}).catch(() => null).then(() => { clearSession(); });
}
function creationDraft() { return useMock() ? mock("getCreationDraft") : Promise.resolve({ ...productionCreationDraft }); }
function saveCreationDraft(value) { if (useMock()) return mock("saveCreationDraft", value); productionCreationDraft = { ...productionCreationDraft, ...value }; return Promise.resolve({ ...productionCreationDraft }); }
function questionText(question) {
  if (typeof question === "string") return question;
  if (question && typeof question === "object") return question.question || question.label || "请补充任务信息";
  return "请补充任务信息";
}

function cloudContext(user, candidateUsers) {
  return {
    currentUser: {
      employeeNo: user.employeeNo,
      name: user.name,
      departmentId: user.department?.departmentId || user.departmentId || null,
      departmentName: user.department?.departmentName || "",
    },
    candidateUsers: (candidateUsers || []).map((item) => ({
      employeeNo: item.employeeNo,
      name: item.name,
      departmentId: item.departmentId || item.department?.departmentId || null,
      departmentName: item.departmentName || item.department?.departmentName || "",
      position: item.position || "",
    })),
    rules: { timezone: config.timezone || "Asia/Shanghai", now: new Date().toISOString() },
  };
}

function registerTaskInput(text, inputType = "text") {
  return request("POST", "/api/v1/task-inputs/register", {
    inputType,
    rawText: text,
    sourceChannel: "wechat_miniprogram",
  });
}

function persistCloudExtraction(inputId, cloudResult) {
  const taskDraft = cloudResult.taskDraft || cloudResult.task_draft || {};
  const confirmQuestions = (cloudResult.confirmQuestions || cloudResult.confirm_questions || []).map(questionText);
  return request("POST", `/api/v1/task-inputs/${inputId}/external-extractions`, {
    taskDraft,
    missingFields: cloudResult.missingFields || cloudResult.missing_fields || [],
    lowConfidenceFields: cloudResult.lowConfidenceFields || cloudResult.low_confidence_fields || [],
    confirmQuestions,
    confidenceScore: cloudResult.confidenceScore ?? cloudResult.confidence_score ?? null,
    agentResult: cloudResult,
  });
}

function saveCloudDraft(inputRecord, cloudResult, persisted, rawText) {
  const serverDraft = persisted.extractedJson || {};
  return saveCreationDraft({
    rawText,
    taskDescription: serverDraft.taskDescription || serverDraft.task_description || rawText,
    ...camelize(serverDraft),
    inputId: inputRecord.inputId,
    extractionId: persisted.extractionId,
    missingFields: persisted.missingFields || [],
    lowConfidenceFields: persisted.lowConfidenceFields || [],
    confirmQuestions: persisted.confirmQuestions || [],
    confidenceScore: persisted.confidenceScore,
    cloudChatSessionId: cloudResult.chatSessionId || cloudResult.chat_session_id || null,
    aiProvider: cloudResult.provider || "qwen",
  });
}

function extractTaskDraft(text) {
  const normalized = String(text || "").trim();
  if (!normalized) return Promise.reject(new Error("请先描述任务"));
  if (useMock()) {
    const mockResult = {
      rawText: normalized,
      taskDescription: normalized,
      taskName: normalized.replace(/[，。,.]/g, " ").split(" ")[0].slice(0, 20),
      taskGoal: "按描述要求完成任务并提交验收",
      taskSource: "AI任务助手",
      taskWeight: 3,
      reportCycle: "每周",
      missingFields: ["mainAssigneeEmployeeNo", "reportToEmployeeNo", "reviewerEmployeeNo", "deadline"],
      lowConfidenceFields: [],
      confirmQuestions: ["请确认主承办人、汇报对象、验收人和截止时间。"],
      confidenceScore: "0.60",
      aiProvider: "mock",
    };
    return saveCreationDraft(mockResult);
  }
  return Promise.all([registerTaskInput(normalized), currentUser(), users()])
    .then(([inputRecord, user, candidateUsers]) => cloudAI.extractTaskFields({
      input: {
        inputId: inputRecord.inputId,
        inputType: "text",
        rawText: normalized,
        sourceChannel: "wechat_miniprogram",
      },
      ...cloudContext(user, candidateUsers),
    }).then((cloudResult) => ({ inputRecord, cloudResult })))
    .then(({ inputRecord, cloudResult }) => persistCloudExtraction(inputRecord.inputId, cloudResult)
      .then((persisted) => saveCloudDraft(inputRecord, cloudResult, persisted, normalized)));
}

function clarifyTaskDraft(clarificationText) {
  const answer = String(clarificationText || "").trim();
  if (!answer) return Promise.reject(new Error("请先回答AI追问"));
  if (useMock()) {
    return creationDraft().then((draft) => saveCreationDraft({
      ...draft,
      missingFields: [],
      lowConfidenceFields: [],
      confirmQuestions: [],
      confidenceScore: "0.95",
      clarificationText: answer,
    }));
  }
  return Promise.all([creationDraft(), currentUser(), users()]).then(([draft, user, candidateUsers]) => {
    if (!draft.inputId) throw new Error("缺少任务输入记录，请返回工作台重新识别");
    return cloudAI.clarifyTaskFields({
      input: {
        inputId: draft.inputId,
        inputType: "text",
        rawText: draft.rawText || draft.taskDescription || "",
        sourceChannel: "wechat_miniprogram",
      },
      previousExtraction: {
        taskDraft: draft,
        missingFields: draft.missingFields || [],
        lowConfidenceFields: draft.lowConfidenceFields || [],
        confirmQuestions: draft.confirmQuestions || [],
        chatSessionId: draft.cloudChatSessionId || null,
      },
      clarificationAnswers: { clarificationText: answer },
      ...cloudContext(user, candidateUsers),
    }).then((cloudResult) => persistCloudExtraction(draft.inputId, cloudResult)
      .then((persisted) => saveCloudDraft({ inputId: draft.inputId }, cloudResult, persisted, draft.rawText || draft.taskDescription || "")));
  });
}

function transcribeVoice(filePath) {
  if (useMock()) return Promise.resolve({ text: "梳理Q2绩效面谈反馈，周五前输出原因分析和行动清单" });
  return cloudAI.transcribeVoice(filePath);
}

function normalizeReportCycle(value) {
  const text = String(value || "").trim();
  if (/^weekly:(MON|TUE|WED|THU|FRI|SAT|SUN)@([01][0-9]|2[0-3]):[0-5][0-9]$/.test(text)) return text;
  return "weekly:FRI@17:00";
}
function creationTaskPayload(draft) {
  return {
    taskName: draft.taskName, taskDescription: draft.taskDescription || null, taskGoal: draft.taskGoal || null, taskSource: draft.taskSource || "AI任务助手",
    mainAssigneeEmployeeNo: draft.mainAssigneeEmployeeNo || null, reportToEmployeeNo: draft.reportToEmployeeNo || null, reportToLevel: draft.reportToLevel || null, reviewerEmployeeNo: draft.reviewerEmployeeNo || null, departmentId: draft.departmentId || null,
    startTime: draft.startTime || null, deadline: draft.deadline || null, taskWeight: draft.taskWeight ? Number(draft.taskWeight) : null, deliverable: draft.deliverable || null, acceptanceCriteria: draft.acceptanceCriteria || null, isUrgent: Boolean(draft.isUrgent), reportCycle: normalizeReportCycle(draft.reportCycle),
    participants: (draft.collaboratorEmployeeNos || []).map((employeeNo) => ({ employeeNo, participantRole: "collaborator", isPrimary: false })),
    extractionRecordIds: draft.extractionId ? [draft.extractionId] : [],
  };
}
function saveTaskDraft(draft) {
  if (useMock()) return mock("saveTaskDraft", draft);
  const payload = creationTaskPayload(draft);
  const write = draft.taskId ? request("PATCH", `/api/v1/tasks/${draft.taskId}/draft`, {
    expectedTaskVersion: draft.taskVersion, taskName: payload.taskName, taskDescription: payload.taskDescription, taskGoal: payload.taskGoal, taskSource: payload.taskSource,
    mainAssigneeEmployeeNo: payload.mainAssigneeEmployeeNo, reportToEmployeeNo: payload.reportToEmployeeNo, reportToLevel: payload.reportToLevel, reviewerEmployeeNo: payload.reviewerEmployeeNo, departmentId: payload.departmentId, startTime: payload.startTime, deadline: payload.deadline, taskWeight: payload.taskWeight, deliverable: payload.deliverable, acceptanceCriteria: payload.acceptanceCriteria, isUrgent: payload.isUrgent, reportCycle: payload.reportCycle, collaboratorEmployeeNos: draft.collaboratorEmployeeNos || [],
  }) : request("POST", "/api/v1/tasks", payload, { idempotencyKey: `draft-${draft.inputId || Date.now()}` });
  return write.then((task) => saveCreationDraft({ ...draft, taskId: task.taskId, taskVersion: task.taskVersion, backendStatus: task.status }));
}
function performanceMatches(taskId, version) { return useMock() ? mock("suggestPerformanceMatches", taskId, version) : request("POST", `/api/v1/tasks/${taskId}/performance-matches/suggest?limit=10`, { expectedTaskVersion: version }); }
function confirmPerformanceMatch(taskId, matchId, version) { return useMock() ? mock("confirmPerformanceMatch", taskId, matchId, version) : request("POST", `/api/v1/tasks/${taskId}/performance-matches/${matchId}/confirm`, { expectedTaskVersion: version }); }
function clearPerformanceMatch(taskId, version) { return useMock() ? mock("clearPerformanceMatch", taskId, version) : request("POST", `/api/v1/tasks/${taskId}/performance-matches/clear`, { expectedTaskVersion: version }); }
function sendTask(payload) {
  if (useMock()) return mock("sendTask", payload);
  return saveTaskDraft(payload).then((draft) => {
    const submit = draft.backendStatus === "pending_confirmation" ? Promise.resolve({ taskId: draft.taskId, taskVersion: draft.taskVersion }) : request("POST", `/api/v1/tasks/${draft.taskId}/actions/submit-for-confirmation`, { expectedTaskVersion: draft.taskVersion });
    return submit.then((confirmed) => request("POST", `/api/v1/tasks/${confirmed.taskId}/actions/confirm-and-send`, { expectedTaskVersion: confirmed.taskVersion }, { idempotencyKey: `confirm-${confirmed.taskId}-${confirmed.taskVersion}` }));
  }).then((sent) => { productionCreationDraft = {}; return sent; });
}
function acceptTask(taskId, version) { return useMock() ? mock("acceptTask", taskId) : request("POST", `/api/v1/tasks/${taskId}/actions/accept`, { expected_task_version: version }, { idempotencyKey: `accept-${taskId}-${version}` }); }
function decomposition(taskId) {
  if (!useMock()) return request("GET", `/api/v1/tasks/${taskId}/decomposition`);
  return mock("getTask", taskId).then((current) => ({
    decompositionId: current.latestDecompositionId,
    taskId,
    status: current.decompositionStatus === "succeeded" ? "succeeded" : current.status === "decomposition_failed" ? "failed" : "pending",
    nodeCount: (current.nodes || []).length,
    errorMessage: current.decompositionError || null,
  }));
}
function executeDecomposition(taskId, decompositionId) { return useMock() ? Promise.resolve(mock("completeDecomposition", taskId)).then(() => decomposition(taskId)) : request("POST", `/api/v1/tasks/${taskId}/decomposition/execute`, { decomposition_id: decompositionId }); }
function retryDecomposition(taskId, version) { return useMock() ? mock("retryDecomposition", taskId) : request("POST", `/api/v1/tasks/${taskId}/decomposition/retry`, { expected_task_version: version }, { idempotencyKey: `decomposition-retry-${taskId}-${version}` }); }
function returnTask(taskId, version, reason) { return useMock() ? mock("returnTask", taskId, reason) : request("POST", `/api/v1/tasks/${taskId}/actions/return`, { expected_task_version: version, reason }, { idempotencyKey: `return-${taskId}-${version}` }); }
function acceptNodeAssignment(taskId, nodeId, version) { return useMock() ? mock("acceptNodeAssignment", taskId, nodeId) : request("POST", `/api/v1/tasks/${taskId}/nodes/${nodeId}/actions/accept-assignment`, { expected_task_version: version }, { idempotencyKey: `node-assignment-accept-${nodeId}-${version}` }); }
function rejectNodeAssignment(taskId, nodeId, version, reason) { return useMock() ? mock("rejectNodeAssignment", taskId, nodeId, reason) : request("POST", `/api/v1/tasks/${taskId}/nodes/${nodeId}/actions/reject-assignment`, { expected_task_version: version, reason }, { idempotencyKey: `node-assignment-reject-${nodeId}-${version}` }); }
function startNode(taskId, nodeId, version) { return useMock() ? mock("startNode", taskId, nodeId) : request("POST", `/api/v1/tasks/${taskId}/nodes/${nodeId}/actions/start`, { expected_task_version: version }, { idempotencyKey: `node-start-${nodeId}-${version}` }); }
function completeNode(taskId, nodeId, version) { return useMock() ? mock("completeNode", taskId, nodeId) : request("POST", `/api/v1/tasks/${taskId}/nodes/${nodeId}/actions/complete`, { expected_task_version: version }, { idempotencyKey: `node-${nodeId}-${version}` }); }
function submitReport(taskId, version, payload) { return useMock() ? mock("submitReport", taskId, payload) : request("POST", `/api/v1/tasks/${taskId}/progress-reports`, { expected_task_version: version, progress_percent: payload.progressPercent, stage_result: payload.stageResult || null, has_issue: payload.hasIssue, issue_note: payload.issueNote || null, remark: payload.remark || null }, { idempotencyKey: `report-${taskId}-${version}` }); }
function submitCompletion(taskId, version, payload) { return useMock() ? mock("submitCompletion", taskId, payload) : request("POST", `/api/v1/tasks/${taskId}/actions/submit-completion`, { expected_task_version: version, completion_note: payload.completionNote, deliverable_summary: payload.deliverableSummary }, { idempotencyKey: `completion-${taskId}-${version}` }); }
function reviewTask(taskId, version, reviewId, approved, reason) { if (useMock()) return mock("reviewTask", taskId, approved, reason); const action = approved ? "approve-completion" : "reject-completion"; const payload = { expected_task_version: version, completion_review_id: reviewId, ...(approved ? {} : { reject_reason: reason }) }; return request("POST", `/api/v1/tasks/${taskId}/actions/${action}`, payload, { idempotencyKey: `review-${reviewId}-${approved}` }); }
function completionReviews(taskId) { if (useMock()) { const state = store.read(); return Promise.resolve({ items: (state.reviews || []).filter((item) => item.taskId === taskId).slice().reverse() }); } return request("GET", `/api/v1/tasks/${taskId}/completion-reviews?limit=20&offset=0`); }
function submitChangeRequest(taskId, version, patch, reason) { return useMock() ? mock("submitChangeRequest", taskId, patch, reason) : request("POST", `/api/v1/tasks/${taskId}/change-requests`, { expected_task_version: version, patch_json: patch, reason }, { idempotencyKey: `change-submit-${taskId}-${version}` }); }
function approveChangeRequest(taskId, version, changeRequestId, comment) { return useMock() ? mock("decideChangeRequest", taskId, changeRequestId, true, comment) : request("POST", `/api/v1/tasks/${taskId}/change-requests/${changeRequestId}/actions/approve`, { expected_task_version: version, approval_comment: comment || null }, { idempotencyKey: `change-approve-${changeRequestId}-${version}` }); }
function rejectChangeRequest(taskId, version, changeRequestId, reason) { return useMock() ? mock("decideChangeRequest", taskId, changeRequestId, false, reason) : request("POST", `/api/v1/tasks/${taskId}/change-requests/${changeRequestId}/actions/reject`, { expected_task_version: version, reason }, { idempotencyKey: `change-reject-${changeRequestId}-${version}` }); }
function cancelChangeRequest(taskId, version, changeRequestId, reason) { return useMock() ? mock("cancelChangeRequest", taskId, changeRequestId, reason) : request("POST", `/api/v1/tasks/${taskId}/change-requests/${changeRequestId}/actions/cancel`, { expected_task_version: version, reason }, { idempotencyKey: `change-cancel-${changeRequestId}-${version}` }); }
function lifecycle(taskId, action, version, reason, employeeNo) {
  if (useMock()) return mock("lifecycle", taskId, action, reason, employeeNo);
  if (action === "reassign") return request("PUT", `/api/v1/tasks/${taskId}/assignee`, { expected_task_version: version, new_assignee_employee_no: employeeNo, reason }, { idempotencyKey: `reassign-${taskId}-${version}` });
  const map = { cancel: "cancel", withdraw: "withdraw" };
  if (!map[action]) return Promise.reject(new Error("当前服务端未开放该任务动作"));
  return request("POST", `/api/v1/tasks/${taskId}/actions/${map[action]}`, { expected_task_version: version, reason }, { idempotencyKey: `${action}-${taskId}-${version}` });
}
function normalizeNotification(item) {
  return {
    ...item,
    type: item.notificationType || item.type || "task",
    actionRequired: Boolean(item.actionRequired),
    canOpen: item.canOpen !== false,
    targetType: item.targetType || null,
    nodeId: item.nodeId || null,
    sentAt: item.sentAt || item.createdAt || "",
  };
}
function notifications(type) {
  if (useMock()) return mock("listNotifications", type).then((items) => (items || []).map(normalizeNotification));
  return request("GET", `/api/v1/notifications${type && type !== "all" ? `?notification_type=${type}` : ""}`).then((items) => (items || []).map(normalizeNotification));
}
function executiveOverview(filters) {
  if (useMock()) return mock("executiveOverview", filters || {});
  const query = Object.keys(filters || {})
    .filter((key) => filters[key] !== "" && filters[key] !== undefined && filters[key] !== null)
    .map((key) => `${encodeURIComponent(key)}=${encodeURIComponent(filters[key])}`)
    .join("&");
  return request("GET", `/api/v1/executive/overview${query ? `?${query}` : ""}`);
}
function executiveTasks(filters) {
  if (useMock()) return mock("listOverview", { ...(filters || {}), mode: "tasks" });
  const query = Object.keys(filters || {})
    .filter((key) => filters[key] !== "" && filters[key] !== undefined && filters[key] !== null && key !== "source" && key !== "mode" && key !== "employeeName")
    .map((key) => `${encodeURIComponent(key)}=${encodeURIComponent(filters[key])}`)
    .join("&");
  return request("GET", `/api/v1/executive/tasks${query ? `?${query}` : ""}`);
}
function executiveMembers(filters) {
  if (useMock()) {
    const overview = store.executiveOverview(filters || {});
    return (overview.workloadHeatmap?.members || []).map((member) => ({
      employeeNo: member.employeeNo,
      name: member.name,
      departmentId: member.departmentId,
    }));
  }
  const query = Object.keys(filters || {})
    .filter((key) => filters[key] !== "" && filters[key] !== undefined && filters[key] !== null)
    .map((key) => `${encodeURIComponent(key)}=${encodeURIComponent(filters[key])}`)
    .join("&");
  return request("GET", `/api/v1/executive/members${query ? `?${query}` : ""}`);
}
function users() { return useMock() ? Promise.resolve(store.read().users) : request("GET", "/api/v1/users"); }

module.exports = { useMock, refreshPriorities, saveSession, clearSession, loginControlled, loginWeCom, refreshSession, bootstrapSession, logout, dashboard, tasks, taskOverview, task, taskDetail, taskStatusLogs, taskOperationLogs, currentUser, creationDraft, saveCreationDraft, saveTaskDraft, performanceMatches, confirmPerformanceMatch, clearPerformanceMatch, extractTaskDraft, clarifyTaskDraft, transcribeVoice, sendTask, acceptTask, decomposition, executeDecomposition, retryDecomposition, returnTask, acceptNodeAssignment, rejectNodeAssignment, startNode, completeNode, submitReport, submitCompletion, completionReviews, reviewTask, submitChangeRequest, approveChangeRequest, rejectChangeRequest, cancelChangeRequest, lifecycle, notifications, executiveOverview, executiveTasks, executiveMembers, users };

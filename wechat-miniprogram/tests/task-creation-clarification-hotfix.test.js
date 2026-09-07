/**
 * Hotfix acceptance: optional task source and user-first clarification merge.
 * Responsibilities: verify create-details gating, optional-source mock send, and API clarification protection.
 * Does not own: real WeCom/LLM calls or backend PostgreSQL integration.
 * Plan task: P0 2026-09-07 task-source/clarification hotfix.
 */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");

// Page-level validation: AI questions are advisory and taskSource is optional.
let pageDefinition = null;
global.Page = (definition) => { pageDefinition = definition; };
global.wx = {
  showToast() {},
};
require("../pages/create-details/index.js");
assert.ok(pageDefinition, "create-details page should register");

const completeDraft = {
  taskName: "门店上线",
  taskDescription: "完成门店上线准备和核对",
  taskGoal: "按期完成上线",
  taskSource: null,
  mainAssigneeEmployeeNo: "E1001",
  reportToEmployeeNo: "E1003",
  reviewerEmployeeNo: "E1003",
  startTime: "2026-09-07T09:00:00+08:00",
  deadline: "2026-09-10T18:00:00+08:00",
  taskWeight: 4,
};
let pageError = "";
const validationContext = {
  data: { needsClarification: true },
  fail(_error, fallback) { pageError = fallback; },
};
assert.equal(pageDefinition.validate.call(validationContext, completeDraft), true);
assert.equal(pageError, "", "unanswered AI questions must not block a complete draft");

const missingGoal = { ...completeDraft, taskGoal: "" };
assert.equal(pageDefinition.validate.call(validationContext, missingGoal), false);
assert.equal(pageError, "请补齐所有必填信息");

const router = require("../utils/router");
const originalRouterGo = router.go;
let savedDraft = null;
let nextRoute = null;

// UI contract: source is visibly optional and confirmation page handles an empty value.
const detailsWxml = fs.readFileSync(path.join(root, "pages/create-details/index.wxml"), "utf8");
const confirmWxml = fs.readFileSync(path.join(root, "pages/create-confirm/index.wxml"), "utf8");
assert.match(detailsWxml, /<text class="label">任务来源<\/text>/);
assert.doesNotMatch(detailsWxml, /class="label required">任务来源/);
assert.match(confirmWxml, /draft\.taskSource \|\| '未填写'/);

// Mock workflow contract: source may be empty without changing the other send gates.
let mockStorage = {};
global.wx = {
  getStorageSync(key) { return mockStorage[key]; },
  setStorageSync(key, value) { mockStorage[key] = JSON.parse(JSON.stringify(value)); },
  removeStorageSync(key) { delete mockStorage[key]; },
};
const config = require("../config");
config.mode = "mock";
const store = require("../utils/store");
store.reset();
const sent = store.sendTask({ ...completeDraft, taskSource: null });
assert.equal(sent.status, "pending_accept");
assert.equal(sent.taskSource, null);
assert.throws(
  () => store.sendTask({ ...completeDraft, taskGoal: "", taskSource: null }),
  /REQUIRED_FIELD_MISSING/,
);

// API clarification contract: current page draft is passed to AI and protected manual fields survive
// even when the AI/server returns a stale full draft.
for (const modulePath of ["../utils/api", "../utils/cloud-ai"]) {
  delete require.cache[require.resolve(modulePath)];
}
config.mode = "api";
config.apiBaseUrl = "https://task.test";
config.cloudServices.chatServiceBaseUrl = "https://chat.test";
mockStorage = { "wangxu.accessToken": "task-board-access" };
const requests = [];

global.wx = {
  getStorageSync(key) { return mockStorage[key]; },
  setStorageSync(key, value) { mockStorage[key] = JSON.parse(JSON.stringify(value)); },
  removeStorageSync(key) { delete mockStorage[key]; },
  request(options) {
    requests.push({ url: options.url, method: options.method, data: options.data, header: options.header });
    if (options.url === "https://task.test/api/v1/auth/ai-token") {
      options.success({ statusCode: 200, data: { token: "ai-token-1", expires_in: 300, token_type: "bearer" } });
      return;
    }
    if (options.url === "https://task.test/api/v1/me") {
      options.success({ statusCode: 200, data: { employee_no: "E1001", name: "林雨欣" } });
      return;
    }
    if (options.url === "https://task.test/api/v1/users") {
      options.success({ statusCode: 200, data: [
        { employee_no: "E1001", name: "林雨欣" },
        { employee_no: "E1002", name: "王敏" },
        { employee_no: "E1003", name: "张总" },
      ] });
      return;
    }
    if (options.url === "https://chat.test/task-intake/clarify") {
      options.success({ statusCode: 200, data: { success: true, data: {
        chatSessionId: "CHAT-1",
        provider: "qwen",
        taskDraft: {
          taskName: "AI旧名称",
          taskDescription: "AI旧描述",
          taskGoal: "AI旧目标",
          taskSource: "AI旧来源",
          mainAssigneeEmployeeNo: "E1002",
          reportToEmployeeNo: "E1001",
          reviewerEmployeeNo: "E1003",
          deadline: "2026-09-09T18:00:00+08:00",
          taskWeight: 3,
        },
        missingFields: [],
        lowConfidenceFields: [],
        confirmQuestions: [],
        confidenceScore: 0.96,
      }}});
      return;
    }
    if (options.url.includes("/external-extractions")) {
      options.success({ statusCode: 201, data: {
        input_id: "11111111-1111-4111-8111-111111111111",
        extraction_id: "33333333-3333-4333-8333-333333333333",
        extracted_json: {
          task_name: "AI旧名称",
          task_description: "AI旧描述",
          task_goal: "AI旧目标",
          task_source: "AI旧来源",
          main_assignee_employee_no: "E1002",
          report_to_employee_no: "E1001",
          reviewer_employee_no: "E1003",
          deadline: "2026-09-09T18:00:00+08:00",
          task_weight: 3,
        },
        missing_fields: [],
        low_confidence_fields: [],
        confirm_questions: [],
        confidence_score: "0.96",
      }});
      return;
    }
    throw new Error(`unexpected request: ${options.url}`);
  },
};

const api = require("../utils/api");
const currentDraft = {
  ...completeDraft,
  inputId: "11111111-1111-4111-8111-111111111111",
  rawText: "门店上线，王敏负责，向谁汇报待确认",
  taskName: "用户确认名称",
  taskDescription: "用户确认描述",
  taskGoal: "用户确认目标",
  taskSource: "张总周会交办",
  mainAssigneeEmployeeNo: "E1002",
  reportToEmployeeNo: null,
  reviewerEmployeeNo: "E1003",
  deadline: "2026-09-10T18:00:00+08:00",
  missingFields: ["reportToEmployeeNo"],
  lowConfidenceFields: [],
  confirmQuestions: ["向谁汇报？"],
  cloudChatSessionId: "CHAT-1",
};

(async () => {
  // Full page-next contract: unanswered AI questions are advisory once the nine required
  // task fields are complete. This exercises next() rather than validate() alone.
  router.go = (route) => { nextRoute = route; };
  const nextContext = {
    data: { needsClarification: true },
    normalizedDraft() { return { ...completeDraft, confirmQuestions: ["向谁汇报？"] }; },
    validate(draft) { return pageDefinition.validate.call(validationContext, draft); },
    saveDraft() { savedDraft = this.normalizedDraft(); return Promise.resolve(savedDraft); },
  };
  pageDefinition.next.call(nextContext);
  await new Promise((resolve) => setImmediate(resolve));
  assert.ok(savedDraft, "next() must persist the current completed draft");
  assert.deepEqual(savedDraft.confirmQuestions, ["向谁汇报？"], "AI questions may remain advisory");
  assert.equal(nextRoute, "/pages/create-confirm/index");
  router.go = originalRouterGo;

  const clarified = await api.clarifyTaskDraft(
    "向林雨欣汇报",
    currentDraft,
    ["taskName", "taskDescription", "taskGoal", "taskSource", "deadline"],
  );
  assert.equal(clarified.taskName, "用户确认名称");
  assert.equal(clarified.taskDescription, "用户确认描述");
  assert.equal(clarified.taskGoal, "用户确认目标");
  assert.equal(clarified.taskSource, "张总周会交办");
  assert.equal(clarified.deadline, "2026-09-10T18:00:00+08:00");
  assert.equal(clarified.reportToEmployeeNo, "E1001", "AI should still fill the unresolved target field");
  assert.deepEqual(clarified.confirmQuestions, []);

  const clarifyRequest = requests.find((item) => item.url === "https://chat.test/task-intake/clarify");
  assert.ok(clarifyRequest, "clarify request should be issued");
  const requestText = JSON.stringify(clarifyRequest.data);
  assert.match(requestText, /用户确认名称/);
  assert.match(requestText, /张总周会交办/);
  assert.match(requestText, /2026-09-10T18:00:00\+08:00/);

  console.log("task-creation-clarification-hotfix.test.js: PASS");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

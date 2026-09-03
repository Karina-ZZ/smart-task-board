/** Feature 05 acceptance: replaceable cloud-function LLM extraction and clarification. */

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

let storage = {
  "wangxu.accessToken": "task-board-access",
};
const requests = [];
let extractionRound = 0;

global.wx = {
  getStorageSync(key) { return storage[key]; },
  setStorageSync(key, value) { storage[key] = JSON.parse(JSON.stringify(value)); },
  removeStorageSync(key) { delete storage[key]; },
  request(options) {
    requests.push({ url: options.url, method: options.method, data: options.data, header: options.header });
    if (options.url === "https://task.test/api/v1/task-inputs/register") {
      options.success({ statusCode: 201, data: {
        input_id: "11111111-1111-4111-8111-111111111111",
        input_type: "text",
        raw_text: options.data.raw_text,
        asr_text: null,
        source_channel: "api",
        submitted_by_employee_no: "E1001",
        submitted_at: "2026-09-02T20:00:00+08:00",
      }});
      return;
    }
    if (options.url === "https://task.test/api/v1/me") {
      options.success({ statusCode: 200, data: { employee_no: "E1001", name: "林雨欣", department_id: null } });
      return;
    }
    if (options.url === "https://task.test/api/v1/users") {
      options.success({ statusCode: 200, data: [
        { employee_no: "E1001", name: "林雨欣" },
        { employee_no: "E1002", name: "王敏" },
      ] });
      return;
    }
    if (options.url === "https://chat.test/task-intake/extract") {
      extractionRound += 1;
      options.success({ statusCode: 200, data: { success: true, data: {
        chatSessionId: "CHAT-1",
        provider: "qwen",
        taskDraft: {
          taskName: "渠道月报复核",
          taskDescription: "周五完成渠道月报复核",
          mainAssigneeEmployeeNo: "E1002",
          reportToEmployeeNo: null,
          reviewerEmployeeNo: null,
          deadline: "2026-09-04T18:00:00+08:00",
          taskWeight: 3,
        },
        missingFields: ["reportToEmployeeNo", "reviewerEmployeeNo"],
        lowConfidenceFields: [],
        confirmQuestions: ["向谁汇报？", "由谁验收？"],
        confidenceScore: 0.82,
      }}});
      return;
    }
    if (options.url === "https://chat.test/task-intake/clarify") {
      options.success({ statusCode: 200, data: { success: true, data: {
        chatSessionId: "CHAT-1",
        provider: "qwen",
        taskDraft: {
          taskName: "渠道月报复核",
          taskDescription: "周五完成渠道月报复核",
          mainAssigneeEmployeeNo: "E1002",
          reportToEmployeeNo: "E1001",
          reviewerEmployeeNo: "E1001",
          deadline: "2026-09-04T18:00:00+08:00",
          taskWeight: 3,
        },
        missingFields: [], lowConfidenceFields: [], confirmQuestions: [], confidenceScore: 0.96,
      }}});
      return;
    }
    if (options.url.includes("/external-extractions")) {
      const clarified = requests.some((item) => item.url === "https://chat.test/task-intake/clarify");
      options.success({ statusCode: 201, data: {
        input_id: "11111111-1111-4111-8111-111111111111",
        input_type: "text",
        raw_text: "周五完成渠道月报复核，王敏负责",
        asr_text: null,
        source_channel: "api",
        submitted_by_employee_no: "E1001",
        submitted_at: "2026-09-02T20:00:00+08:00",
        extraction_id: clarified ? "33333333-3333-4333-8333-333333333333" : "22222222-2222-4222-8222-222222222222",
        extracted_json: clarified ? {
          task_name: "渠道月报复核", task_description: "周五完成渠道月报复核",
          main_assignee_employee_no: "E1002", report_to_employee_no: "E1001",
          reviewer_employee_no: "E1001", deadline: "2026-09-04T18:00:00+08:00", task_weight: 3,
        } : {
          task_name: "渠道月报复核", task_description: "周五完成渠道月报复核",
          main_assignee_employee_no: "E1002", report_to_employee_no: null,
          reviewer_employee_no: null, deadline: "2026-09-04T18:00:00+08:00", task_weight: 3,
        },
        missing_fields: clarified ? [] : ["report_to_employee_no", "reviewer_employee_no"],
        low_confidence_fields: [],
        confirm_questions: clarified ? [] : ["向谁汇报？", "由谁验收？"],
        confidence_score: clarified ? "0.96" : "0.82",
        job_status: "succeeded",
      }});
      return;
    }
    throw new Error(`unexpected request: ${options.url}`);
  },
};

const config = require("../config");
config.mode = "api";
config.apiBaseUrl = "https://task.test";
config.cloudServices.loginServiceBaseUrl = "https://login.test";
config.cloudServices.chatServiceBaseUrl = "https://chat.test";

const api = require("../utils/api");

(async () => {
  const first = await api.extractTaskDraft("周五完成渠道月报复核，王敏负责");
  assert.equal(first.taskName, "渠道月报复核");
  assert.equal(first.mainAssigneeEmployeeNo, "E1002");
  assert.deepEqual(first.confirmQuestions, ["向谁汇报？", "由谁验收？"]);
  assert.equal(first.cloudChatSessionId, "CHAT-1");
  assert.equal(first.aiProvider, "qwen");
  assert.equal(storage["wangxu.creationDraft"].inputId, "11111111-1111-4111-8111-111111111111");

  const clarified = await api.clarifyTaskDraft("向林雨欣汇报，也由林雨欣验收");
  assert.equal(clarified.reportToEmployeeNo, "E1001");
  assert.equal(clarified.reviewerEmployeeNo, "E1001");
  assert.deepEqual(clarified.confirmQuestions, []);
  assert.deepEqual(clarified.missingFields, []);

  assert.equal(extractionRound, 1);
  assert.ok(requests.some((item) => item.url === "https://chat.test/task-intake/extract"));
  assert.ok(requests.some((item) => item.url === "https://chat.test/task-intake/clarify"));
  assert.ok(requests.some((item) => item.url.endsWith("/external-extractions")));
  assert.ok(requests.filter((item) => item.url.startsWith("https://chat.test")).every((item) => !String(item.data).includes("QWEN_API_KEY")));

  const root = path.resolve(__dirname, "..");
  const configSource = fs.readFileSync(path.join(root, "config.js"), "utf8");
  const cloudSource = fs.readFileSync(path.join(root, "utils/cloud-ai.js"), "utf8");
  const detailsWxml = fs.readFileSync(path.join(root, "pages/create-details/index.wxml"), "utf8");
  assert.match(configSource, /loginServiceBaseUrl/);
  assert.match(configSource, /chatServiceBaseUrl/);
  assert.match(cloudSource, /\/task-intake\/extract/);
  assert.match(cloudSource, /\/task-intake\/clarify/);
  assert.match(detailsWxml, /AI需要你确认/);
  assert.doesNotMatch(`${configSource}\n${cloudSource}`, /DASHSCOPE_API_KEY\s*=|QWEN_API_KEY\s*=/);

  console.log("ai-input.test.js: PASS");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

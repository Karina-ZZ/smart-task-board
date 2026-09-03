/**
 * Feature 15 acceptance: executive employee task filter drilldown.
 * Protects the approved three-page flow without historical snapshot-task persistence.
 */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const read = (relative) => fs.readFileSync(path.join(root, relative), "utf8");
const executiveWxml = read("pages/executive/index.wxml");
const executiveJs = read("pages/executive/index.js");
const tasksWxml = read("pages/tasks/index.wxml");
const tasksJs = read("pages/tasks/index.js");
const apiSource = read("utils/api.js");
const overview = require("../utils/task-overview");

assert.match(executiveWxml, /查看该员工任务/);
assert.match(executiveWxml, /bindtap="viewEmployeeTasks"/);
assert.match(executiveJs, /employeeNo:\s*snapshot\.employeeNo/);
assert.match(executiveJs, /\/pages\/tasks\/index/);
assert.doesNotMatch(`${executiveWxml}\n${executiveJs}`, /员工任务明细将在后续功能开放/);

assert.match(tasksWxml, /员工姓名/);
assert.match(tasksWxml, /employeeOptions/);
assert.match(tasksWxml, /高管授权范围内任务 · 可按员工筛选/);
assert.match(tasksJs, /executiveMembers/);
assert.match(tasksJs, /draftFilters\.employeeNo/);
assert.match(tasksJs, /backExecutive/);
assert.doesNotMatch(`${tasksWxml}\n${tasksJs}`, /workload_snapshot_task_details|snapshotTaskDetail/i);
assert.match(apiSource, /\/api\/v1\/executive\/members/);
assert.match(apiSource, /key !== "employeeName"/);

const summary = overview.filterSummary({
  ...overview.DEFAULT_FILTERS,
  source: "executive",
  employeeNo: "E1001",
  employeeName: "张三",
  status: "blocked",
  quadrant: "important_urgent",
  datePreset: "week",
});
assert.deepEqual(summary.slice(0, 4), ["员工：张三", "受阻", "重要且紧急", "本周开始"]);

let storage = { "wangxu.accessToken": "test-access-token" };
global.wx = {
  getStorageSync(key) { return storage[key]; },
  setStorageSync(key, value) { storage[key] = value; },
};
const config = require("../config");
config.mode = "api";
config.apiBaseUrl = "https://feature15.test";
let requestedUrl = "";
global.wx.request = (options) => {
  requestedUrl = options.url;
  options.success({ statusCode: 200, data: { items: [], page: 1, page_size: 20, total: 0, status_counts: {} } });
};
const api = require("../utils/api");
api.taskOverview({
  source: "executive",
  mode: "tasks",
  employeeNo: "E1001",
  employeeName: "张三",
  departmentId: "11111111-1111-1111-1111-111111111111",
  status: "blocked",
  quadrant: "important_urgent",
  datePreset: "week",
}).then(() => {
  assert.ok(requestedUrl.includes("/api/v1/executive/tasks?"));
  assert.ok(requestedUrl.includes("employeeNo=E1001"));
  assert.ok(requestedUrl.includes("status=blocked"));
  assert.ok(requestedUrl.includes("quadrant=important_urgent"));
  assert.ok(requestedUrl.includes("datePreset=week"));
  assert.ok(!requestedUrl.includes("employeeName"));
  console.log("executive-employee-tasks.test.js: PASS");
}).catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

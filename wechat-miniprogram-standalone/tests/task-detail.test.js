/** Feature 11 cumulative acceptance: detail exposes real completion submission and review navigation. */

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

let storage = {};
global.wx = {
  getStorageSync(key) { return storage[key]; },
  setStorageSync(key, value) { storage[key] = JSON.parse(JSON.stringify(value)); },
};

const store = require("../utils/store");
const detailView = require("../utils/task-detail");
store.reset();

const sourceTask = store.getTask("T20260901002");
const view = detailView.buildTaskDetail({
  task: sourceTask,
  progressReports: sourceTask.reports,
  issues: sourceTask.issues,
  statusLogs: sourceTask.logs,
  allowedActions: sourceTask.allowedActions,
});
assert.equal(view.task.status, "in_progress");
assert.equal(view.task.nodeCount, 3);
assert.equal(view.latestReport.progressPercent, 45);
assert.equal(view.task.actualHoursLabel, "无");
assert.equal(view.timeline.find((item) => item.current).label, "进行中");
assert.equal(detailView.canonicalStatus("pending_acceptance"), "pending_accept");
assert.equal(detailView.canonicalStatus("pending_confirmation"), "pending_confirm");

const root = path.resolve(__dirname, "..");
const wxml = fs.readFileSync(path.join(root, "pages/task-detail/index.wxml"), "utf8");
const controller = fs.readFileSync(path.join(root, "pages/task-detail/index.js"), "utf8");
const wxss = fs.readFileSync(path.join(root, "pages/task-detail/index.wxss"), "utf8");
const combined = `${wxml}\n${controller}\n${wxss}`;

for (const text of [
  "任务详情", "概览", "人员", "节点", "进度/汇报", "绩效", "任务轨迹", "基本信息",
  "人员信息", "节点执行", "最新进度汇报", "绩效关联", "查看操作记录", "复制任务编号",
]) assert.match(combined, new RegExp(text));
for (const id of ["detail-top", "detail-people", "detail-nodes", "detail-progress", "detail-performance"]) {
  assert.match(wxml, new RegExp(`id=\\"${id}\\"`));
}
assert.doesNotMatch(wxml, /预计工时/);
assert.match(controller, /api\.acceptTask/);
assert.match(controller, /api\.returnTask/);
assert.match(controller, /api\.startNode/);
assert.match(controller, /api\.completeNode/);
assert.match(controller, /openReport/);
assert.match(controller, /openCompletion/);
assert.match(controller, /openReview/);
assert.match(controller, /api\.submitChangeRequest/);
assert.match(controller, /api\.approveChangeRequest/);
assert.match(controller, /api\.rejectChangeRequest/);
assert.match(controller, /api\.lifecycle/);
assert.doesNotMatch(controller, /api\.submitCompletion|api\.reviewTask/);
assert.match(wxml, /bindtap="returnTask"/);
assert.match(wxml, /bindtap="acceptTask"/);
assert.match(wxml, /bindtap="startNode"/);
assert.match(wxml, /bindtap="completeNode"/);
assert.match(wxml, /bindtap="openReport"/);
assert.match(wxml, /bindtap="requestChange"/);
assert.match(wxml, /bindtap="reassignTask"/);
assert.match(wxml, /bindtap="withdrawTask"/);
assert.match(wxml, /bindtap="cancelTask"/);
assert.match(wxml, /wx:elif="\{\{actionMode === 'report'\}\}" class="btn primary flex" bindtap="openReport"/);
assert.match(wxml, /wx:elif="\{\{actionMode === 'complete'\}\}" class="btn primary flex" bindtap="openCompletion"/);
assert.match(wxml, /wx:elif="\{\{actionMode === 'review'\}\}" class="btn primary flex" bindtap="openReview"/);
assert.match(controller, /focusNode/);
assert.match(controller, /taskStatusLogs/);
assert.match(controller, /taskOperationLogs/);
assert.match(wxss, /grid-template-columns:\s*repeat\(5,\s*1fr\)/);

const config = require("../config");
config.mode = "api";
storage["wangxu.accessToken"] = "test-access-token";
config.apiBaseUrl = "https://detail.test";
const requested = [];
global.wx.request = (options) => {
  requested.push(options.url);
  const url = options.url;
  let data = {};
  if (/\/available-actions$/.test(url)) data = { task_id: "T1", task_version: 2, current_user_relations: ["assigned"], allowed_actions: ["report"], nodes: [] };
  else if (/\/status-logs/.test(url)) data = { items: [{ status_log_id: "L1", task_id: "T1", from_status: "pending_acceptance", to_status: "in_progress", action_type: "accept", operator_employee_no: "E1", task_version: 2, operation_source: "api", created_at: "2026-09-01T10:00:00+08:00" }], limit: 100, offset: 0, total: 1 };
  else if (/\/progress-reports/.test(url)) data = { items: [{ progress_report_id: "R1", task_id: "T1", reporter_employee_no: "E1", progress_percent: 30, stage_result: "阶段成果", remark: null, created_at: "2026-09-01T11:00:00+08:00" }], limit: 50, offset: 0, total: 1 };
  else if (/\/issues/.test(url)) data = { items: [], limit: 50, offset: 0, total: 0 };
  else if (/\/operation-logs/.test(url)) data = { items: [], limit: 20, offset: 0, total: 0 };
  else data = { task_id: "T1", task_no: "WX-1", task_name: "任务", creator_employee_no: "E1", main_assignee_employee_no: "E1", status: "in_progress", task_version: 2, task_weight: 4, nodes: [], participants: [], dependencies: [], node_participants: [], performance_matches: [] };
  options.success({ statusCode: 200, data });
};

const api = require("../utils/api");
api.taskDetail("T1").then((apiView) => {
  for (const suffix of ["/tasks/T1", "/available-actions", "/status-logs", "/progress-reports", "/issues", "/operation-logs"]) {
    assert.ok(requested.some((url) => url.includes(suffix)), `task detail must request ${suffix}`);
  }
  assert.equal(apiView.allowedActions[0], "report");
  assert.deepEqual(apiView.currentUserRelations, ["assigned"]);
  assert.equal(apiView.statusLogs[0].fromStatusLabel, "待接受");
  console.log("task-detail.test.js: PASS");
}).catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

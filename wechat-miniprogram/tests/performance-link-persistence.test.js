/**
 * Feature: Performance relation persistence in Mini Program mock task detail.
 * Responsibilities: keep creator-confirmed KPI projection visible after draft save/send and detail reload.
 * Does not own: production PostgreSQL persistence or KPI matching algorithms.
 * Plan task: TEST16-PERFORMANCE-LINK-HOTFIX.
 */

const assert = require("node:assert/strict");

let storage = {};
global.wx = {
  getStorageSync(key) { return storage[key]; },
  setStorageSync(key, value) { storage[key] = JSON.parse(JSON.stringify(value)); },
};

const store = require("../utils/store");
const detailView = require("../utils/task-detail");

store.reset();

// Existing demo tasks that already carry a KPI name must expose the same confirmed relation DTO
// as the production detail endpoint, instead of forcing the page to understand mock-only fields.
const seeded = store.getTask("T20260902001");
assert.equal(seeded.performanceMatches.length, 1);
assert.equal(seeded.performanceMatches[0].metricName, "组织绩效责任书按期完成率");
assert.equal(seeded.performanceMatches[0].isConfirmed, true);

const draft = store.saveTaskDraft({
  taskName: "绩效关联持久化验证",
  taskDescription: "创建阶段确认绩效指标后发送任务",
  taskGoal: "任务详情仍显示同一已确认绩效指标",
  taskSource: null,
  mainAssigneeEmployeeNo: "E1002",
  reportToEmployeeNo: "E1003",
  reviewerEmployeeNo: "E1003",
  collaboratorEmployeeNos: [],
  startTime: "2026-09-07T09:00:00+08:00",
  deadline: "2026-09-09T18:00:00+08:00",
  taskWeight: 4,
});

const candidates = store.suggestPerformanceMatches(draft.taskId, draft.taskVersion);
const selected = candidates.find((item) => item.metricId === "PM1");
assert.ok(selected, "PM1 must be available as a KPI candidate");
const confirmed = store.confirmPerformanceMatch(draft.taskId, selected.performanceMatchId, draft.taskVersion);
assert.equal(confirmed.isConfirmed, true);

const selectedDraft = {
  ...draft,
  performanceMetricId: confirmed.metricId,
  performanceMetric: confirmed.metricName,
};
const sent = store.sendTask(selectedDraft);
assert.equal(sent.status, "pending_accept");
assert.equal(sent.performanceMatches.length, 1);
assert.equal(sent.performanceMatches[0].metricId, confirmed.metricId);
assert.equal(sent.performanceMatches[0].metricName, confirmed.metricName);
assert.equal(sent.performanceMatches[0].isConfirmed, true);

const reloaded = store.getTask(sent.taskId);
assert.equal(reloaded.performanceMatches.length, 1);
assert.equal(reloaded.performanceMatches[0].metricName, confirmed.metricName);
const view = detailView.buildTaskDetail({
  task: reloaded,
  progressReports: reloaded.reports,
  issues: reloaded.issues,
  statusLogs: reloaded.logs,
  allowedActions: reloaded.allowedActions,
});
assert.ok(view.performance, "detail view must keep the confirmed KPI relation");
assert.equal(view.performance.metricName, confirmed.metricName);

store.clearPerformanceMatch(sent.taskId, reloaded.taskVersion);
const cleared = store.getTask(sent.taskId);
assert.deepEqual(cleared.performanceMatches, []);
const clearedView = detailView.buildTaskDetail({ task: cleared });
assert.equal(clearedView.performance, null);

console.log("performance-link-persistence.test.js: PASS");

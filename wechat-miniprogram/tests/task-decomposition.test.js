/** Feature 07 acceptance: real decomposition API routes, resume/poll/retry page, and 5-10 mock nodes. */

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

let storage = {};
global.wx = {
  getStorageSync(key) { return storage[key]; },
  setStorageSync(key, value) { storage[key] = JSON.parse(JSON.stringify(value)); },
};

const root = path.resolve(__dirname, "..");
const apiSource = fs.readFileSync(path.join(root, "utils/api.js"), "utf8");
const pageSource = fs.readFileSync(path.join(root, "pages/decomposition/index.js"), "utf8");
const pageWxml = fs.readFileSync(path.join(root, "pages/decomposition/index.wxml"), "utf8");

for (const route of [
  "/decomposition`",
  "/decomposition/execute`",
  "/decomposition/retry`",
]) assert.match(apiSource, new RegExp(route.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
assert.match(pageSource, /api\.decomposition/);
assert.match(pageSource, /api\.executeDecomposition/);
assert.match(pageSource, /api\.retryDecomposition/);
assert.match(pageSource, /schedulePoll/);
assert.match(pageSource, /attempt\.status === "pending"/);
assert.match(pageWxml, /拆解成功前，任务不会计入负荷，也不能汇报、完成节点或验收/);
assert.doesNotMatch(pageSource, /api\.completeNode|api\.submitReport|api\.submitCompletion|api\.reviewTask|api\.lifecycle/);

const config = require("../config");
config.mode = "mock";
const store = require("../utils/store");
store.reset();
const sent = store.sendTask({
  taskName: "功能07拆解合同",
  taskDescription: "验证接受后AI拆解",
  taskGoal: "得到可执行节点",
  taskSource: "测试",
  mainAssigneeEmployeeNo: "E1001",
  reportToEmployeeNo: "E1003",
  reviewerEmployeeNo: "E1001",
  startTime: "2026-09-03T09:00:00+08:00",
  deadline: "2026-09-10T18:00:00+08:00",
  taskWeight: 4,
});
const accepted = store.acceptTask(sent.taskId);
assert.equal(accepted.status, "decomposing");
assert.equal(accepted.effectiveAt, null);
const completed = store.completeDecomposition(sent.taskId);
assert.equal(completed.status, "in_progress");
assert.ok(completed.effectiveAt);
assert.ok(completed.nodes.length >= 5 && completed.nodes.length <= 10);
assert.ok(completed.nodes.every((node) => node.sourceType === "ai" && node.decompositionId));
assert.ok(completed.nodes.every((node) => !Object.prototype.hasOwnProperty.call(node, "estimatedHours")));

console.log("task-decomposition.test.js: PASS");

/** Feature 01 acceptance: workbench data contract and prototype anchors. */

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

let storage = {};
global.wx = {
  getStorageSync(key) { return storage[key]; },
  setStorageSync(key, value) { storage[key] = JSON.parse(JSON.stringify(value)); },
};

const store = require("../utils/store");
store.reset();
const dashboard = store.getDashboard();

assert.equal(dashboard.user.employeeNo, "E1001");
assert.equal(dashboard.metrics.inProgress, 2);
assert.equal(dashboard.metrics.completionRatePeriodDays, 90);
assert.ok(Object.prototype.hasOwnProperty.call(dashboard.metrics, "dueWithin3Days"));
assert.deepEqual(Object.keys(dashboard.quadrantCounts).sort(), [
  "important_not_urgent", "important_urgent", "routine", "urgent_not_important",
]);
assert.ok(dashboard.supportItems.every((item) => item.taskId && item.supportReason));
assert.ok(dashboard.tasks.every((item) => item.assigneeName && Number.isInteger(item.progressPercent)));

const page = fs.readFileSync(path.resolve(__dirname, "../pages/workbench/index.wxml"), "utf8");
const controller = fs.readFileSync(path.resolve(__dirname, "../pages/workbench/index.js"), "utf8");
const workbenchSource = `${page}\n${controller}`;
for (const text of [
  "一句话，创建新任务", "进行中任务", "临期任务", "按期完成率", "任务风险四象限",
  "需要我支持", "任务信息管理", "待接受", "AI拆解中", "拆解失败", "待汇报", "待验收",
]) assert.match(workbenchSource, new RegExp(text));

console.log("workbench.test.js: PASS");

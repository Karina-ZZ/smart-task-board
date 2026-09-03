/** Feature 02 acceptance: task/node overview filters, paging, and prototype anchors. */

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

let storage = {};
global.wx = {
  getStorageSync(key) { return storage[key]; },
  setStorageSync(key, value) { storage[key] = JSON.parse(JSON.stringify(value)); },
};

const store = require("../utils/store");
const overview = require("../utils/task-overview");

store.reset();
const all = store.listOverview({ pageSize: 20 });
assert.equal(all.total, 4);
assert.equal(all.statusCounts.pending_acceptance, 1);
assert.equal(all.statusCounts.in_progress, 1);
assert.equal(all.statusCounts.blocked, 1);
assert.equal(all.statusCounts.pending_review, 1);

const accepted = store.listOverview({ status: "pending_acceptance" });
assert.equal(accepted.total, 1, "legacy mock pending_accept must map to V1.1 pending_acceptance");

const nodes = store.listOverview({ mode: "nodes", search: "复核核心指标" });
assert.equal(nodes.total, 1);
assert.equal(nodes.items[0].nodeName, "复核核心指标");
assert.equal(nodes.items[0].ownerName, "林雨欣");

const quadrant = store.listOverview({ quadrant: "important_urgent", pageSize: 1, page: 2 });
assert.ok(quadrant.total >= 2);
assert.equal(quadrant.items.length, 1);
assert.equal(quadrant.page, 2);

assert.deepEqual(overview.filterSummary({
  ...overview.DEFAULT_FILTERS,
  mode: "nodes",
  quadrant: "important_urgent",
  nearDue: true,
  datePreset: "custom",
  startDate: "2026-09-01",
  endDate: "2026-09-03",
}), ["我的节点任务", "重要且紧急", "未来3天临期", "2026-09-01 至 2026-09-03"]);

const root = path.resolve(__dirname, "..");
const page = fs.readFileSync(path.join(root, "pages/tasks/index.wxml"), "utf8");
const controller = fs.readFileSync(path.join(root, "pages/tasks/index.js"), "utf8");
const source = `${page}\n${controller}`;
for (const text of [
  "任务概览", "当前用户参与的任务", "任务信息管理", "更多筛选", "主任务", "我的节点任务",
  "未来3天临期", "优先级四象限", "开始时间", "应用筛选", "重置筛选", "上一页", "下一页",
]) assert.match(source, new RegExp(text));

const config = require("../config");
config.mode = "api";
storage["wangxu.accessToken"] = "test-access-token";
config.apiBaseUrl = "https://overview.test";
let requestedUrl = "";
global.wx.request = (options) => {
  requestedUrl = options.url;
  options.success({ statusCode: 200, data: { items: [], total: 0, page: 1, pageSize: 20, status_counts: {} } });
};

const api = require("../utils/api");
api.taskOverview({
  mode: "nodes",
  status: "in_progress",
  quadrant: "important_urgent",
  support: "open",
  nearDue: true,
  datePreset: "custom",
  startDate: "2026-09-01",
  endDate: "2026-09-03",
  page: 2,
  pageSize: 20,
  sortBy: "updated_at",
  sortOrder: "desc",
}).then(() => {
  for (const query of [
    "mode=nodes", "status=in_progress", "quadrant=important_urgent", "support=open", "nearDue=true",
    "datePreset=custom", "startDate=2026-09-01", "endDate=2026-09-03", "page=2",
    "pageSize=20", "sortBy=updated_at", "sortOrder=desc",
  ]) assert.ok(requestedUrl.includes(query), `server query must include ${query}`);
  console.log("task-overview.test.js: PASS");
}).catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

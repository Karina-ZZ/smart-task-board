/**
 * Feature: Function 14 executive dashboard contract.
 * Responsibilities: protect the approved executive KPI, scope, quadrant and workload interactions.
 * Does not own: FastAPI formula unit tests or PostgreSQL integration.
 * Plan task: DEV-16.
 */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
let storage = {};
global.wx = {
  getStorageSync(key) { return storage[key]; },
  setStorageSync(key, value) { storage[key] = JSON.parse(JSON.stringify(value)); },
};

const read = (relative) => fs.readFileSync(path.join(root, relative), "utf8");
const api = read("utils/api.js");
const page = read("pages/executive/index.js");
const wxml = read("pages/executive/index.wxml");
const store = require(path.join(root, "utils/store.js"));
store.reset();
store.switchUser("E1003");

assert.match(wxml, /团队任务态势/);
assert.match(wxml, /KPI关联/);
assert.match(wxml, /涉及.*绩效指标/);
assert.match(wxml, /总体进度/);
assert.match(wxml, /团队任务四象限/);
assert.match(wxml, /团队负荷热力图/);
assert.match(wxml, /负荷构成/);
assert.doesNotMatch(wxml + page, /核心KPI|核心指标|coreMetric|coreKpi/i);
assert.doesNotMatch(page, /pages\/workload-tasks/);
assert.match(api, /\/api\/v1\/executive\/overview/);
assert.match(api, /\/api\/v1\/executive\/tasks/);
assert.match(page, /source:\s*["']executive["']/);

const overview = store.executiveOverview({ departmentId: "D01", period: "week" });
assert.ok(overview.metrics);
assert.ok(Object.hasOwn(overview.metrics.kpiLinks, "linkedTaskCount"));
assert.ok(Object.hasOwn(overview.metrics.kpiLinks, "linkedMetricCount"));
assert.ok(Array.isArray(overview.workloadHeatmap.days));
assert.ok(Array.isArray(overview.workloadHeatmap.members));
assert.ok(overview.quadrants);

console.log("executive-dashboard.test.js: PASS");

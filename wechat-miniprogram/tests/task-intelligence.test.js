/**
 * Feature: DEV-14 performance, priority, workload and conflict contract.
 * Responsibilities: protect deterministic KPI matching and server-owned calculations in Mini Program wiring.
 * Does not own: FastAPI formula unit tests or PostgreSQL integration.
 * Plan task: DEV-14.
 */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const read = (relative) => fs.readFileSync(path.join(root, relative), "utf8");
const api = read("utils/api.js");
const details = read("pages/create-details/index.js");
const detailsWxml = read("pages/create-details/index.wxml");
const workbench = read("pages/workbench/index.js");

assert.match(detailsWxml, /系统候选，由创建人确认或不关联/);
assert.doesNotMatch(detailsWxml, /AI候选/);
assert.match(details, /api\.performanceMatches\(saved\.taskId, saved\.taskVersion\)/);
assert.match(details, /api\.confirmPerformanceMatch/);
assert.match(details, /api\.clearPerformanceMatch/);
assert.match(api, /performance-matches\/suggest/);
assert.match(api, /performance-matches\/clear/);
assert.match(api, /expectedTaskVersion/);
assert.match(api, /refreshPriorities/);
assert.match(api, /\/api\/v1\/analytics\/priorities/);

// The client may request recalculation and filter by server results, but it must not own the formulas.
assert.doesNotMatch(workbench, /0\.45|0\.35|0\.60|TF-IDF|cosine|workloadScore\s*=/);
assert.doesNotMatch(details + workbench, /estimatedHours|estimated_hours/);

console.log("task-intelligence.test.js: PASS");

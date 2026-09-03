/**
 * Feature: Mini Program static contract.
 * Responsibilities: verify page declarations, component targets, JSON/JS syntax inputs and unsupported WXML calls.
 * Does not own: WeChat compiler internals or visual screenshots.
 * Plan task: WECHAT-MP-08.
 */

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const app = JSON.parse(fs.readFileSync(path.join(root, "app.json"), "utf8"));
// Feature 11 adds the real completion-submission page before review.
assert.equal(app.pages.length, 14);

for (const page of app.pages) {
  for (const extension of ["js", "json", "wxml", "wxss"]) {
    assert.ok(fs.existsSync(path.join(root, `${page}.${extension}`)), `${page}.${extension} must exist`);
  }
}

function walk(directory) {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const target = path.join(directory, entry.name);
    return entry.isDirectory() ? walk(target) : [target];
  });
}

for (const file of walk(root).filter((target) => target.endsWith(".wxml"))) {
  const source = fs.readFileSync(file, "utf8");
  assert.doesNotMatch(source, /\.[A-Za-z_$][\w$]*\s*\(/, `${path.relative(root, file)} must not call JavaScript methods in WXML`);
  const stack = [];
  const tags = source.match(/<\/?[A-Za-z][^>]*>/g) || [];
  for (const tag of tags) {
    const match = tag.match(/^<\/?([A-Za-z][\w-]*)/);
    if (!match || tag.endsWith("/>") || ["input", "slider", "switch"].includes(match[1])) continue;
    if (tag.startsWith("</")) assert.equal(stack.pop(), match[1], `${path.relative(root, file)} has mismatched ${tag}`);
    else stack.push(match[1]);
  }
  assert.deepEqual(stack, [], `${path.relative(root, file)} has unclosed tags`);
  const allowed = new Set(["block", "bottom-nav", "button", "input", "label", "picker", "scroll-view", "slider", "status-badge", "switch", "task-card", "text", "textarea", "view"]);
  for (const tag of tags) {
    const match = tag.match(/^<\/?([A-Za-z][\w-]*)/);
    if (match) assert.ok(allowed.has(match[1]), `${path.relative(root, file)} uses unsupported WXML element ${match[1]}`);
  }
}

console.log("static-contract.test.js: PASS");

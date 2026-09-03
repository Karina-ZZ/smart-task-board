const assert = require("assert");
const fs = require("fs");
const path = require("path");

const root = path.join(__dirname, "..");
const read = (relative) => fs.readFileSync(path.join(root, relative), "utf8");
const app = JSON.parse(read("app.json"));
const detail = read("pages/task-detail/index.js");
const detailWxml = read("pages/task-detail/index.wxml");
const completion = read("pages/completion/index.js");
const completionWxml = read("pages/completion/index.wxml");
const review = read("pages/review/index.js");
const reviewWxml = read("pages/review/index.wxml");
const api = read("utils/api.js");

assert.ok(app.pages.includes("pages/completion/index"));
assert.match(detail, /actionMode = "complete"/);
assert.match(detail, /openCompletion\(\)/);
assert.match(detail, /openReview\(\)/);
assert.match(detailWxml, />提交完成</);
assert.match(detailWxml, />进入任务验收</);

assert.match(completion, /api\.submitCompletion/);
assert.match(completion, /completionNote/);
assert.match(completion, /deliverableSummary/);
assert.match(completionWxml, /完成说明 \*/);
assert.match(completionWxml, /交付摘要 \*/);
assert.doesNotMatch(completion + completionWxml, /actualHours|actual_hours|实际工时.*input/);

assert.match(review, /api\.completionReviews/);
assert.match(review, /api\.reviewTask/);
assert.match(review, /退回原因必填/);
assert.match(reviewWxml, /通过并归档/);
assert.match(reviewWxml, /交付摘要/);
assert.doesNotMatch(reviewWxml, /通过意见|验收评分|验收备注/);

assert.match(api, /Idempotency-Key|idempotencyKey/);
assert.match(api, /completion_review_id/);
console.log("task-completion-review.test.js: PASS");

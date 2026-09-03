/**
 * Feature: Runnable V1.1 workflow acceptance.
 * Responsibilities: verify create/send/accept/decompose/execute/review/archive without WeChat DevTools.
 * Does not own: browser rendering, FastAPI integration, or production credentials.
 * Plan task: WECHAT-MP-08.
 */

const assert = require("node:assert/strict");

let storage = {};
global.wx = {
  getStorageSync(key) { return storage[key]; },
  setStorageSync(key, value) { storage[key] = JSON.parse(JSON.stringify(value)); },
};

const store = require("../utils/store");

store.reset();
assert.equal(store.currentUser().employeeNo, "E1001");

store.saveCreationDraft({ rawText: "测试完整流程" });
assert.equal(store.getCreationDraft().rawText, "测试完整流程");

const sent = store.sendTask({
  taskName: "验证小程序完整主链路",
  taskDescription: "创建人确认发送后由承办人接受并触发AI拆解。",
  taskGoal: "完成状态流验证",
  mainAssigneeEmployeeNo: "E1001",
  reportToEmployeeNo: "E1003",
  reviewerEmployeeNo: "E1001",
  collaboratorEmployeeNos: [],
  deadline: "2026-09-10T18:00:00+08:00",
  taskWeight: 4,
  acceptanceCriteria: "全部节点完成并通过验收",
});
assert.equal(sent.status, "pending_accept");
assert.equal(sent.nodes.length, 0, "sending must not create nodes");

const accepted = store.acceptTask(sent.taskId);
assert.equal(accepted.status, "decomposing");
assert.equal(accepted.effectiveAt, null);

const effective = store.completeDecomposition(sent.taskId);
assert.equal(effective.status, "in_progress");
assert.equal(effective.decompositionStatus, "succeeded");
assert.ok(effective.effectiveAt);
assert.equal(effective.nodes.length, 5);

for (const node of effective.nodes) {
  store.startNode(sent.taskId, node.nodeId);
  store.completeNode(sent.taskId, node.nodeId);
}
const executable = store.getTask(sent.taskId);
assert.equal(executable.progressPercent, 100);
assert.ok(executable.allowedActions.includes("submit_completion"));

const pendingReview = store.submitCompletion(sent.taskId, { completionNote: "完成", deliverableSummary: "文字成果" });
assert.equal(pendingReview.status, "pending_review");
assert.equal(pendingReview.review.reviewStatus, "submitted");

const archived = store.reviewTask(sent.taskId, true, "");
assert.equal(archived.status, "archived");
assert.ok(archived.actualHours >= 0);
assert.ok(!Object.prototype.hasOwnProperty.call(archived, "archiveSnapshot"));

store.switchUser("E1003");
assert.equal(store.currentUser().roleType, "executive");
assert.ok(store.executiveOverview().members.length > 0);

console.log("workflow.test.js: PASS");

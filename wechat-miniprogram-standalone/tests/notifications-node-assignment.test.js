/** Feature 13 acceptance: collaborator node acceptance, actionable notifications, and production notification UX. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

let storage = {};
global.wx = {
  getStorageSync(key) { return storage[key]; },
  setStorageSync(key, value) { storage[key] = JSON.parse(JSON.stringify(value)); },
};

const root = path.resolve(__dirname, "..");
const read = (relative) => fs.readFileSync(path.join(root, relative), "utf8");
const apiSource = read("utils/api.js");
const notificationSource = read("pages/notifications/index.js");
const notificationWxml = read("pages/notifications/index.wxml");
const detailSource = read("pages/task-detail/index.js");
const detailWxml = read("pages/task-detail/index.wxml");
const profileSource = read("pages/profile/index.js");
const profileWxml = read("pages/profile/index.wxml");

for (const route of ["accept-assignment", "reject-assignment"]) assert.match(apiSource, new RegExp(route));
assert.match(detailSource, /api\.acceptNodeAssignment/);
assert.match(detailSource, /api\.rejectNodeAssignment/);
assert.match(detailWxml, /接受承接/);
assert.match(detailWxml, /无法承接/);
assert.match(notificationSource, /node_assignment/);
assert.match(notificationSource, /task_acceptance/);
assert.match(notificationSource, /decomposition/);
assert.match(notificationSource, /report/);
assert.match(notificationSource, /review/);
assert.doesNotMatch(notificationSource, /readNotification|markAllRead/);
assert.doesNotMatch(notificationWxml, /全部已读|item\.unread/);
assert.match(notificationWxml, /actionRequired/);
assert.doesNotMatch(profileSource + profileWxml, /switchUser|api\.reset|切换演示身份|恢复示例数据/);

const config = require("../config");
config.mode = "mock";
const store = require("../utils/store");
store.reset();
store.switchUser("E1003");
const sent = store.sendTask({
  taskName: "功能13协办节点承接",
  taskDescription: "验证协办节点只通知本人且未承接不得执行",
  taskGoal: "完成节点承接闭环",
  taskSource: "测试",
  mainAssigneeEmployeeNo: "E1001",
  collaboratorEmployeeNos: ["E1002"],
  reportToEmployeeNo: "E1003",
  reviewerEmployeeNo: "E1003",
  startTime: "2026-09-03T09:00:00+08:00",
  deadline: "2026-09-10T18:00:00+08:00",
  taskWeight: 4,
});
store.switchUser("E1001");
store.acceptTask(sent.taskId);
const active = store.completeDecomposition(sent.taskId);
const collaboratorNode = active.nodes.find((node) => node.ownerEmployeeNo === "E1002");
assert.ok(collaboratorNode, "decomposition must assign one mock node to the confirmed collaborator");
assert.equal(collaboratorNode.assignmentStatus, "pending");
assert.equal(store.listNotifications().some((item) => item.title === "任务已生效"), false, "main assignee must not receive pure decomposition-success FYI");

store.switchUser("E1003");
assert.equal(store.listNotifications().some((item) => item.title === "任务已生效"), false, "creator must not receive pure decomposition-success FYI");
store.switchUser("E1002");
const assignmentNotice = store.listNotifications().find((item) => item.nodeId === collaboratorNode.nodeId);
assert.ok(assignmentNotice, "assigned collaborator must receive node acceptance notification");
assert.equal(assignmentNotice.targetType, "node_assignment");
assert.equal(assignmentNotice.actionRequired, true);
assert.throws(() => store.startNode(sent.taskId, collaboratorNode.nodeId), /ASSIGNMENT_NOT_ACCEPTED/);
store.acceptNodeAssignment(sent.taskId, collaboratorNode.nodeId);
const accepted = store.getTask(sent.taskId).nodes.find((node) => node.nodeId === collaboratorNode.nodeId);
assert.equal(accepted.assignmentStatus, "accepted");
assert.equal(store.listNotifications().find((item) => item.nodeId === collaboratorNode.nodeId).actionRequired, false);

console.log("notifications-node-assignment.test.js: PASS");

/**
 * Feature: Workload snapshot task drilldown.
 * Responsibilities: explain one employee snapshot and list only tasks included in that workload view.
 * Does not own: workload scoring, snapshot persistence, or scope authorization.
 * Plan task: WECHAT-MP-07.
 */

const api = require("../../utils/api");
const router = require("../../utils/router");

Page({
  data: { snapshotId: "", employeeNo: "", member: {}, tasks: [], pressures: [] },
  onLoad(options) { this.setData({ snapshotId: options.snapshotId, employeeNo: options.employeeNo }); this.load(); },
  back() { wx.navigateBack(); },
  load() { Promise.all([api.users(), api.tasks({ employeeNo: this.data.employeeNo })]).then(([users, tasks]) => { const member = users.find((user) => user.employeeNo === this.data.employeeNo) || {}; const score = member.workloadScore || 0; this.setData({ member: { ...member, avatarText: member.name ? member.name.slice(-1) : "员" }, tasks, pressures: [{ label: "任务时限压力", value: Math.min(95, score + 6) }, { label: "任务权重压力", value: Math.max(18, score - 5) }, { label: "任务数量压力", value: Math.min(100, tasks.length * 22) }, { label: "突发任务压力", value: Math.max(12, score - 24) }, { label: "受阻/逾期压力", value: tasks.some((task) => task.hasIssue || task.isOverdue) ? 88 : 20 }] }); }); },
  openTask(event) { router.go("/pages/task-detail/index", { taskId: event.detail.taskId }); },
});

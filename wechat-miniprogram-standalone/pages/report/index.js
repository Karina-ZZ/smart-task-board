/**
 * Feature: Progress report.
 * Responsibilities: collect mandatory progress and blocker state with optional stage results and remarks.
 * Does not own: task status calculation, actual-hours input, or collaborator permissions.
 * Plan task: WECHAT-MP-05.
 */

const api = require("../../utils/api");
const router = require("../../utils/router");

Page({
  data: { taskId: "", task: {}, progressPercent: 50, stageResult: "", hasIssue: false, issueNote: "", remark: "", submitting: false },
  onLoad(options) { this.setData({ taskId: options.taskId }); api.task(options.taskId).then((task) => this.setData({ task, progressPercent: task.progressPercent || 0 })); },
  back() { wx.navigateBack(); },
  progress(event) { this.setData({ progressPercent: event.detail.value }); },
  input(event) { this.setData({ [event.currentTarget.dataset.field]: event.detail.value }); },
  issue(event) { this.setData({ hasIssue: event.detail.value }); },
  submit() {
    if (this.data.hasIssue && !this.data.issueNote.trim()) { wx.showToast({ title: "存在卡点时必须填写说明", icon: "none" }); return; }
    this.setData({ submitting: true });
    api.submitReport(this.data.taskId, this.data.task.taskVersion, { progressPercent: this.data.progressPercent, stageResult: this.data.stageResult.trim(), hasIssue: this.data.hasIssue, issueNote: this.data.issueNote.trim(), remark: this.data.remark.trim() }).then(() => { wx.showToast({ title: "进度已提交", icon: "success" }); setTimeout(() => router.replace("/pages/task-detail/index", { taskId: this.data.taskId }), 400); }).catch((error) => { this.setData({ submitting: false }); wx.showToast({ title: error.message, icon: "none" }); });
  },
});

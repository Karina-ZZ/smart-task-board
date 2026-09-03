/**
 * Feature: Completion submission.
 * Responsibilities: collect completion note and deliverable summary, then submit one completion review round.
 * Does not own: review decisions, actual-hours calculation, or automatic archival.
 * Plan task: FEATURE-11 / DEV-13.
 */
const api = require("../../utils/api");
const router = require("../../utils/router");

Page({
  data: {
    taskId: "",
    task: {},
    completionNote: "",
    deliverableSummary: "",
    loading: true,
    submitting: false,
    error: "",
  },
  onLoad(options) { this.setData({ taskId: options.taskId || "" }); },
  onShow() { if (this.data.taskId) this.load(); },
  load() {
    this.setData({ loading: true, error: "" });
    api.taskDetail(this.data.taskId).then((view) => {
      const task = view.task || {};
      if (!(view.allowedActions || []).includes("submit_completion") && !api.useMock()) {
        this.setData({ loading: false, error: "当前任务不可提交完成" });
        return;
      }
      this.setData({ task, loading: false });
    }).catch((error) => this.setData({ loading: false, error: error.message || "任务加载失败" }));
  },
  back() { wx.navigateBack({ fail: () => router.replace("/pages/task-detail/index", { taskId: this.data.taskId }) }); },
  inputNote(event) { this.setData({ completionNote: event.detail.value }); },
  inputSummary(event) { this.setData({ deliverableSummary: event.detail.value }); },
  submit() {
    if (this.data.submitting) return;
    const completionNote = String(this.data.completionNote || "").trim();
    const deliverableSummary = String(this.data.deliverableSummary || "").trim();
    if (!completionNote) { wx.showToast({ title: "请填写完成说明", icon: "none" }); return; }
    if (!deliverableSummary) { wx.showToast({ title: "请填写交付摘要", icon: "none" }); return; }
    wx.showModal({
      title: "提交完成",
      content: "提交后任务将进入待验收，验收人可通过或退回修改。",
      confirmText: "确认提交",
      success: (result) => {
        if (!result.confirm) return;
        this.setData({ submitting: true });
        api.submitCompletion(this.data.taskId, this.data.task.taskVersion, { completionNote, deliverableSummary })
          .then(() => {
            wx.showToast({ title: "已提交验收", icon: "success" });
            setTimeout(() => router.replace("/pages/task-detail/index", { taskId: this.data.taskId }), 350);
          })
          .catch((error) => {
            this.setData({ submitting: false });
            wx.showToast({ title: error.message || "提交失败", icon: "none" });
          });
      },
    });
  },
});

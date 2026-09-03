/**
 * Feature: Completion review.
 * Responsibilities: display the immutable review round and allow approve/archive or reasoned rejection.
 * Does not own: actual-hours calculation, archive transaction, or reviewer authorization.
 * Plan task: WECHAT-MP-05.
 */

const api = require("../../utils/api");
const router = require("../../utils/router");

Page({
  data: { taskId: "", task: {}, review: {}, deciding: false, loading: true, error: "" },
  onLoad(options) { this.setData({ taskId: options.taskId }); this.load(); },
  load() {
    this.setData({ loading: true, error: "" });
    return Promise.all([api.taskDetail(this.data.taskId), api.completionReviews(this.data.taskId)])
      .then(([view, reviews]) => {
        const review = (reviews.items || []).find((item) => (item.reviewStatus || item.review_status) === "submitted") || {};
        if (!review.completionReviewId && !review.reviewId && !api.useMock()) {
          this.setData({ loading: false, error: "当前没有待验收的完成申请" });
          return;
        }
        this.setData({ task: view.task || {}, review, loading: false });
      })
      .catch((error) => this.setData({ loading: false, error: error.message || "验收信息加载失败" }));
  },
  back() { wx.navigateBack(); },
  approve() { wx.showModal({ title: "验收通过", content: "通过后任务将在同一流程中完成并自动归档，不生成归档快照。", confirmText: "通过并归档", success: (result) => { if (result.confirm) this.decide(true, ""); } }); },
  reject() { wx.showModal({ title: "退回修改", editable: true, placeholderText: "请填写验收不通过原因", confirmText: "确认退回", success: (result) => { if (!result.confirm) return; const reason = (result.content || "").trim(); if (!reason) { wx.showToast({ title: "退回原因必填", icon: "none" }); return; } this.decide(false, reason); } }); },
  decide(approved, reason) { const reviewId = this.data.review.completionReviewId || this.data.review.reviewId; this.setData({ deciding: true }); api.reviewTask(this.data.taskId, this.data.task.taskVersion, reviewId, approved, reason).then(() => { wx.showToast({ title: approved ? "已通过并归档" : "已退回修改", icon: "success" }); setTimeout(() => router.replace("/pages/task-detail/index", { taskId: this.data.taskId }), 450); }).catch((error) => { this.setData({ deciding: false }); wx.showToast({ title: error.message, icon: "none" }); }); },
});

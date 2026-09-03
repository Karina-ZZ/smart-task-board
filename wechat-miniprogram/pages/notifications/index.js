/**
 * Feature: Notification center and deep-link routing.
 * Responsibilities: filter the current user's notifications, show action-required state, and route by server-resolved target.
 * Does not own: notification recipients, task authorization, read persistence, or reminder scheduling.
 * Plan task: DEV-15 / FEATURE-13.
 */

const api = require("../../utils/api");
const access = require("../../utils/access");
const router = require("../../utils/router");

Page({
  data: {
    type: "all", items: [], visible: [], unread: 0, executive: false,
    tabs: [{ code: "all", label: "全部" }, { code: "task", label: "任务" }, { code: "reminder", label: "提醒" }, { code: "system", label: "系统" }],
  },
  onShow() { this.load(); },
  load() {
    Promise.all([api.notifications("all"), api.currentUser()])
      .then(([items, user]) => {
        this.setData({ items, executive: access.canAccessExecutive(user), unread: items.filter((item) => item.actionRequired).length });
        this.apply();
      })
      .catch((error) => wx.showToast({ title: error.message, icon: "none" }));
  },
  tab(event) { this.setData({ type: event.currentTarget.dataset.type }); this.apply(); },
  apply() { this.setData({ visible: this.data.items.filter((item) => this.data.type === "all" || item.type === this.data.type) }); },
  open(event) {
    const id = event.currentTarget.dataset.id;
    const item = this.data.items.find((notice) => notice.notificationId === id);
    if (!item) return;
    if (item.canOpen === false) {
      wx.showToast({ title: item.unavailableReason || "当前无法打开该事项", icon: "none" });
      return;
    }
    if (!item.taskId) {
      wx.showModal({ title: item.title || "系统通知", content: item.content || "无补充内容", showCancel: false });
      return;
    }
    const params = { taskId: item.taskId, ...(item.nodeId ? { nodeId: item.nodeId } : {}) };
    const targets = {
      node_assignment: ["/pages/task-detail/index", { ...params, action: "node-assignment" }],
      task_acceptance: ["/pages/task-detail/index", params],
      decomposition: ["/pages/decomposition/index", { taskId: item.taskId }],
      report: ["/pages/report/index", { taskId: item.taskId }],
      review: ["/pages/review/index", { taskId: item.taskId }],
      task_detail: ["/pages/task-detail/index", params],
    };
    const target = targets[item.targetType] || targets.task_detail;
    router.go(target[0], target[1]);
  },
});

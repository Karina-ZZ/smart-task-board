/**
 * Feature: Notification Center.
 * Responsibilities: filter message records, mark a local demo item read, and route to related tasks.
 * Does not own: enterprise message delivery, retries, or production read-state storage.
 * Plan task: WECHAT-MP-06.
 */

const api = require("../../utils/api");
const access = require("../../utils/access");
const router = require("../../utils/router");

Page({
  data: { type: "all", items: [], visible: [], unread: 0, executive: false, mockMode: api.useMock(), tabs: [{ code: "all", label: "全部" }, { code: "task", label: "任务" }, { code: "reminder", label: "提醒" }, { code: "system", label: "系统" }] },
  onShow() { this.load(); },
  load() { Promise.all([api.notifications("all"), api.currentUser()]).then(([items, user]) => { this.setData({ items, executive: access.canAccessExecutive(user), unread: items.filter((item) => item.unread).length }); this.apply(); }).catch((error) => wx.showToast({ title: error.message, icon: "none" })); },
  tab(event) { this.setData({ type: event.currentTarget.dataset.type }); this.apply(); },
  apply() { this.setData({ visible: this.data.items.filter((item) => this.data.type === "all" || item.type === this.data.type) }); },
  open(event) { const id = event.currentTarget.dataset.id; const item = this.data.items.find((notice) => notice.notificationId === id); api.readNotification(id).finally(() => { if (item && item.taskId) router.go("/pages/task-detail/index", { taskId: item.taskId }); else this.load(); }); },
  markAll() { api.markAllRead().then(() => { wx.showToast({ title: "演示消息已读", icon: "success" }); this.load(); }).catch((error) => wx.showToast({ title: error.message, icon: "none" })); },
});

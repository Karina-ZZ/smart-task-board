/**
 * Feature: Profile and demonstration controls.
 * Responsibilities: show current identity/task counts and isolate mock-only identity/reset controls.
 * Does not own: production identity, RBAC administration, or employee master data.
 * Plan task: WECHAT-MP-06.
 */

const api = require("../../utils/api");
const access = require("../../utils/access");

Page({
  data: { user: {}, users: [], taskCount: 0, actionCount: 0, archivedCount: 0, executive: false, unread: 0, mockMode: api.useMock() },
  onShow() { this.load(); },
  load() { const usersRequest = this.data.mockMode ? api.users() : Promise.resolve([]); Promise.all([api.currentUser(), usersRequest, api.tasks({}), api.notifications("all")]).then(([user, users, tasks, notices]) => this.setData({ user, users, avatarText: user.name ? user.name.slice(-1) : "序", taskCount: tasks.length, actionCount: tasks.filter((task) => (task.allowedActions || []).length).length, archivedCount: tasks.filter((task) => task.status === "archived").length, executive: access.canAccessExecutive(user), unread: notices.filter((item) => item.unread).length })); },
  switchUser(event) { const employeeNo = this.data.users[event.detail.value].employeeNo; api.switchUser(employeeNo).then(() => { wx.showToast({ title: "演示身份已切换", icon: "success" }); this.load(); }); },
  reset() { wx.showModal({ title: "重置本地演示数据", content: "这只会恢复小程序本地示例，不会访问或清理任何服务器数据库。", confirmText: "确认重置", success: (result) => { if (result.confirm) api.reset().then(() => { wx.showToast({ title: "已恢复", icon: "success" }); this.load(); }); } }); },
});

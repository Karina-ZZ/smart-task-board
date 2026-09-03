/**
 * Feature: Production profile summary.
 * Responsibilities: show server identity, related-task counts, archived count, and current action-required total.
 * Does not own: role switching, demo-data reset, or identity administration.
 * Plan task: DEV-15 / FEATURE-13.
 */

const api = require("../../utils/api");
const access = require("../../utils/access");

Page({
  data: { user: {}, taskCount: 0, actionCount: 0, archivedCount: 0, executive: false, unread: 0 },
  onShow() { this.load(); },
  load() {
    Promise.all([api.currentUser(), api.tasks({}), api.notifications("all")])
      .then(([user, tasks, notices]) => {
        const actionCount = notices.filter((item) => item.actionRequired).length;
        this.setData({
          user,
          avatarText: user.name ? user.name.slice(-1) : "序",
          taskCount: tasks.length,
          actionCount,
          archivedCount: tasks.filter((task) => task.status === "archived").length,
          executive: access.canAccessExecutive(user),
          unread: actionCount,
        });
      })
      .catch((error) => wx.showToast({ title: error.message || "个人信息加载失败", icon: "none" }));
  },
});

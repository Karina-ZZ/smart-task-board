/**
 * Feature: Executive team dashboard.
 * Responsibilities: show authorized team metrics and open employee workload task drilldown.
 * Does not own: workload algorithms, scope authorization, or employee data aggregation.
 * Plan task: WECHAT-MP-07.
 */

const api = require("../../utils/api");
const access = require("../../utils/access");
const router = require("../../utils/router");

Page({
  data: { loading: true, denied: false, user: {}, overview: {}, unread: 0 },
  onShow() { this.load(); },
  load() { Promise.all([api.currentUser(), api.notifications("all")]).then(([user, notices]) => { if (!access.canAccessExecutive(user)) { this.setData({ user, denied: true, loading: false, unread: notices.filter((item) => item.unread).length }); return; } return api.executiveOverview().then((overview) => this.setData({ user, overview: { ...overview, members: (overview.members || []).map((member) => ({ ...member, avatarText: member.name ? member.name.slice(-1) : "员" })) }, loading: false, denied: false, unread: notices.filter((item) => item.unread).length })); }).catch((error) => { wx.showToast({ title: error.message, icon: "none" }); this.setData({ loading: false }); }); },
  openMember(event) { router.go("/pages/workload-tasks/index", { snapshotId: this.data.overview.snapshotId, employeeNo: event.currentTarget.dataset.employeeNo }); },
  profile() { wx.reLaunch({ url: "/pages/profile/index" }); },
});

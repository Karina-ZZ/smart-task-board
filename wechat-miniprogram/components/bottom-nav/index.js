/**
 * Feature: Second-version bottom navigation.
 * Responsibilities: show role-aware destinations with the Workbench circle signature.
 * Does not own: route authorization or current-user querying.
 * Plan task: WECHAT-MP-01.
 */

const ROUTES = {
  workbench: "/pages/workbench/index",
  tasks: "/pages/tasks/index",
  executive: "/pages/executive/index",
  notifications: "/pages/notifications/index",
  profile: "/pages/profile/index",
};

Component({
  properties: {
    active: { type: String, value: "workbench" },
    executive: { type: Boolean, value: false },
    unread: { type: Number, value: 0 },
  },
  methods: {
    navigate(event) {
      const key = event.currentTarget.dataset.key;
      const url = ROUTES[key];
      if (!url || key === this.data.active) return;
      wx.reLaunch({ url });
    },
  },
});

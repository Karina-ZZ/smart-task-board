/**
 * Feature: Executive team dashboard.
 * Responsibilities: render authorized team metrics, quadrants, workload heatmap, and snapshot breakdown.
 * Does not own: metric formulas, scope authorization, workload calculation, or employee-task drilldown.
 * Plan task: DEV-16.
 */

const api = require("../../utils/api");
const access = require("../../utils/access");
const router = require("../../utils/router");

const PERIODS = [
  { value: "week", label: "本周" },
  { value: "month", label: "本月" },
];
const QUADRANTS = [
  { value: "important_urgent", label: "重要且紧急", tone: "danger" },
  { value: "important_not_urgent", label: "重要不紧急", tone: "warning" },
  { value: "not_important_urgent", label: "紧急不重要", tone: "amber" },
  { value: "not_important_not_urgent", label: "常规任务", tone: "teal" },
];
const LEVEL_LABELS = { idle: "空闲", normal: "正常", busy: "偏忙", overloaded: "过载" };

function metricText(value, suffix) {
  if (value === null || value === undefined) return "--";
  return `${Number(value).toFixed(Number(value) % 1 ? 1 : 0)}${suffix || ""}`;
}

Page({
  data: {
    loading: true,
    error: "",
    denied: false,
    user: {},
    overview: {},
    periods: PERIODS,
    period: "week",
    departmentId: "",
    departmentOptions: [{ departmentId: "", departmentName: "全部负责部门" }],
    departmentIndex: 0,
    quadrants: [],
    selectedSnapshot: null,
    sheetOpen: false,
    unread: 0,
  },

  onShow() { this.load(); },

  load() {
    this.setData({ loading: true, error: "", denied: false });
    return Promise.all([api.currentUser(), api.notifications("all")])
      .then(([user, notices]) => {
        const unread = (notices || []).filter((item) => item.actionRequired).length;
        if (!access.canAccessExecutive(user)) {
          this.setData({ user, denied: true, loading: false, unread });
          return null;
        }
        return api.executiveOverview({
          departmentId: this.data.departmentId || undefined,
          period: this.data.period,
        }).then((overview) => {
          const departments = overview.scope?.departments || [];
          const departmentOptions = [
            { departmentId: "", departmentName: "全部负责部门" },
            ...departments,
          ];
          const selectedIndex = Math.max(0, departmentOptions.findIndex((item) => String(item.departmentId || "") === String(this.data.departmentId || "")));
          const quadrantData = QUADRANTS.map((item) => ({
            ...item,
            count: Number(overview.quadrants?.[item.value] || 0),
          }));
          const workloadHeatmap = {
            days: (overview.workloadHeatmap?.days || []).map((day) => ({ ...day, shortDate: String(day.date || "").slice(5) })),
            members: (overview.workloadHeatmap?.members || []).map((member) => ({ ...member, avatarText: member.name ? member.name.slice(-1) : "员" })),
          };
          this.setData({
            user,
            unread,
            overview: {
              ...overview,
              workloadHeatmap,
              activeCountText: metricText(overview.metrics?.activeTasks?.count),
              onTimeText: metricText(overview.metrics?.onTimeRate?.rate, "%"),
              kpiTaskText: metricText(overview.metrics?.kpiLinks?.linkedTaskCount),
              kpiMetricText: metricText(overview.metrics?.kpiLinks?.linkedMetricCount),
              progressText: metricText(overview.metrics?.overallProgress?.rate, "%"),
            },
            departmentOptions,
            departmentIndex: selectedIndex,
            quadrants: quadrantData,
            loading: false,
            denied: false,
          });
        });
      })
      .catch((error) => {
        if (error.statusCode === 403) {
          this.setData({ denied: true, loading: false, error: "" });
          return;
        }
        this.setData({ error: error.message || "团队态势加载失败", loading: false });
      });
  },

  chooseDepartment(event) {
    const index = Number(event.detail.value || 0);
    const option = this.data.departmentOptions[index] || this.data.departmentOptions[0];
    this.setData({ departmentId: option.departmentId || "", departmentIndex: index }, () => this.load());
  },

  choosePeriod(event) {
    const period = event.currentTarget.dataset.period;
    if (!period || period === this.data.period) return;
    this.setData({ period, sheetOpen: false, selectedSnapshot: null }, () => this.load());
  },

  openQuadrant(event) {
    const quadrant = event.currentTarget.dataset.quadrant;
    router.go("/pages/tasks/index", {
      source: "executive",
      mode: "tasks",
      quadrant,
      departmentId: this.data.departmentId || undefined,
      period: this.data.period,
      datePreset: this.data.period,
      reset: 1,
    });
  },

  openSnapshot(event) {
    const memberIndex = Number(event.currentTarget.dataset.memberIndex);
    const cellIndex = Number(event.currentTarget.dataset.cellIndex);
    const member = this.data.overview.workloadHeatmap?.members?.[memberIndex];
    const snapshot = member?.cells?.[cellIndex];
    if (!snapshot?.snapshotId) return;
    this.setData({
      selectedSnapshot: {
        ...snapshot,
        employeeNo: member.employeeNo,
        employeeName: member.name,
        employeeDepartmentId: member.departmentId,
        workloadLevelLabel: LEVEL_LABELS[snapshot.workloadLevel] || snapshot.workloadLevel || "-",
      },
      sheetOpen: true,
    });
  },

  viewEmployeeTasks() {
    const snapshot = this.data.selectedSnapshot;
    if (!snapshot?.employeeNo) return;
    router.go("/pages/tasks/index", {
      source: "executive",
      mode: "tasks",
      employeeNo: snapshot.employeeNo,
      employeeName: snapshot.employeeName || snapshot.employeeNo,
      departmentId: this.data.departmentId || snapshot.employeeDepartmentId || undefined,
      period: this.data.period,
      datePreset: this.data.period,
      reset: 1,
    });
  },

  closeSheet() { this.setData({ sheetOpen: false, selectedSnapshot: null }); },
  stopOverlay() {},
  retry() { this.load(); },
  profile() { wx.reLaunch({ url: "/pages/profile/index" }); },
});

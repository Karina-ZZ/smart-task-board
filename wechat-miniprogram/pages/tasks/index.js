/**
 * Feature 02: Task/node overview page.
 * Owns URL/storage-restorable UI filters and server-side pagination only.
 */

const api = require("../../utils/api");
const access = require("../../utils/access");
const router = require("../../utils/router");
const { statusView } = require("../../utils/constants");
const { dateLabel } = require("../../utils/format");
const {
  DEFAULT_FILTERS,
  STATUS_OPTIONS,
  QUICK_STATUSES,
  QUADRANT_OPTIONS,
  DATE_OPTIONS,
  SORT_OPTIONS,
  ORDER_OPTIONS,
  filterSummary,
  labelOf,
  mergeFilters,
} = require("../../utils/task-overview");

const FILTER_KEY = "wangxu.taskOverviewFilters";
const SCROLL_KEY = "wangxu.taskOverviewScroll";
const NODE_STATUS_LABELS = { pending: "未开始", in_progress: "进行中", completed: "已完成" };

function optionFilters(options) {
  const result = {};
  ["mode", "status", "quadrant", "support", "datePreset", "startDate", "endDate", "search", "sortBy", "sortOrder"].forEach((key) => {
    if (options[key] !== undefined && options[key] !== "") result[key] = options[key];
  });
  if (options.nearDue === "true") result.nearDue = true;
  if (options.page) result.page = Math.max(1, Number(options.page) || 1);
  return result;
}

Page({
  data: {
    loading: true,
    error: "",
    items: [],
    total: 0,
    maxPage: 1,
    filters: { ...DEFAULT_FILTERS },
    draftFilters: { ...DEFAULT_FILTERS },
    filterOpen: false,
    filterSummary: [],
    statusCards: QUICK_STATUSES,
    quickStatuses: QUICK_STATUSES,
    statusOptions: STATUS_OPTIONS,
    quadrantOptions: QUADRANT_OPTIONS,
    dateOptions: DATE_OPTIONS,
    sortOptions: SORT_OPTIONS,
    orderOptions: ORDER_OPTIONS,
    sortLabel: "截止时间",
    orderLabel: "升序",
    executive: false,
    unread: 0,
  },

  onLoad(options) {
    const routeFilters = optionFilters(options);
    const hasRouteFilters = Object.keys(routeFilters).length > 0;
    const stored = options.reset === "1" || hasRouteFilters ? {} : wx.getStorageSync(FILTER_KEY);
    const filters = mergeFilters(stored, routeFilters);
    this.setData({ filters });
    wx.setStorageSync(FILTER_KEY, filters);
  },

  onShow() { this.load(true); },
  onPullDownRefresh() { this.load(false).finally(() => wx.stopPullDownRefresh()); },
  onPageScroll(event) { wx.setStorageSync(SCROLL_KEY, event.scrollTop); },

  load(restoreScroll) {
    this.setData({ loading: true, error: "" });
    return Promise.all([
      api.taskOverview(this.data.filters),
      api.currentUser(),
      api.notifications("all"),
    ]).then(([result, user, notices]) => {
      const statusCounts = result.statusCounts || {};
      const statusCards = QUICK_STATUSES.map((item) => ({ ...item, count: statusCounts[item.value] || 0 }));
      const items = (result.items || []).map((item) => ({
        ...item,
        statusLabel: statusView(item.status).label,
        taskStatusLabel: statusView(item.taskStatus).label,
        nodeStatusLabel: NODE_STATUS_LABELS[item.status] || item.status,
        deadlineLabel: dateLabel(item.plannedDeadline),
      }));
      const total = Number(result.total || 0);
      const maxPage = Math.max(1, Math.ceil(total / this.data.filters.pageSize));
      const filters = this.data.filters.page > maxPage ? { ...this.data.filters, page: maxPage } : this.data.filters;
      this.setData({
        items,
        total,
        maxPage,
        filters,
        statusCards,
        filterSummary: filterSummary(filters),
        executive: access.canAccessExecutive(user),
        unread: (notices || []).filter((item) => item.actionRequired).length,
        loading: false,
      }, () => {
        if (restoreScroll) wx.pageScrollTo({ scrollTop: Number(wx.getStorageSync(SCROLL_KEY) || 0), duration: 0 });
      });
    }).catch((error) => this.setData({ error: error.message || "任务概览加载失败", loading: false }));
  },

  updateFilters(patch, scroll) {
    const filters = mergeFilters(this.data.filters, patch, { page: 1 });
    wx.setStorageSync(FILTER_KEY, filters);
    this.setData({ filters, filterOpen: false }, () => {
      this.load(false).then(() => {
        if (scroll !== false) wx.pageScrollTo({ selector: "#overview-task-section", duration: 300 });
      });
    });
  },

  selectStatus(event) {
    this.updateFilters({ mode: "tasks", status: event.currentTarget.dataset.status });
  },

  setMode(event) { this.updateFilters({ mode: event.currentTarget.dataset.mode }); },

  openFilter() {
    const draftFilters = { ...this.data.filters };
    this.setData({
      filterOpen: true,
      draftFilters,
      sortLabel: labelOf(SORT_OPTIONS, draftFilters.sortBy),
      orderLabel: labelOf(ORDER_OPTIONS, draftFilters.sortOrder),
    });
  },

  closeFilter() { this.setData({ filterOpen: false }); },
  stopOverlay() {},
  chooseDraftMode(event) { this.setData({ "draftFilters.mode": event.currentTarget.dataset.value }); },
  chooseDraftStatus(event) { this.setData({ "draftFilters.status": event.currentTarget.dataset.value }); },
  chooseDraftQuadrant(event) { this.setData({ "draftFilters.quadrant": event.currentTarget.dataset.value }); },
  chooseDraftDatePreset(event) { this.setData({ "draftFilters.datePreset": event.currentTarget.dataset.value }); },
  toggleNearDue(event) { this.setData({ "draftFilters.nearDue": event.detail.value }); },
  toggleSupport(event) { this.setData({ "draftFilters.support": event.detail.value ? "open" : "" }); },
  inputSearch(event) { this.setData({ "draftFilters.search": event.detail.value }); },
  chooseStartDate(event) { this.setData({ "draftFilters.startDate": event.detail.value }); },
  chooseEndDate(event) { this.setData({ "draftFilters.endDate": event.detail.value }); },
  chooseSort(event) {
    const item = SORT_OPTIONS[Number(event.detail.value)];
    this.setData({ "draftFilters.sortBy": item.value, sortLabel: item.label });
  },
  chooseOrder(event) {
    const item = ORDER_OPTIONS[Number(event.detail.value)];
    this.setData({ "draftFilters.sortOrder": item.value, orderLabel: item.label });
  },

  applyDraftFilters() {
    const draft = { ...this.data.draftFilters, search: this.data.draftFilters.search.trim(), page: 1 };
    if (draft.datePreset === "custom" && (!draft.startDate || !draft.endDate)) {
      wx.showToast({ title: "请选择完整的开始和结束日期", icon: "none" });
      return;
    }
    if (draft.datePreset === "custom" && draft.startDate > draft.endDate) {
      wx.showToast({ title: "结束日期不能早于开始日期", icon: "none" });
      return;
    }
    if (draft.datePreset !== "custom") { draft.startDate = ""; draft.endDate = ""; }
    wx.setStorageSync(FILTER_KEY, draft);
    this.setData({ filters: draft, filterOpen: false }, () => this.load(false).then(() => wx.pageScrollTo({ selector: "#overview-task-section", duration: 300 })));
  },

  resetFilters() {
    const filters = { ...DEFAULT_FILTERS };
    wx.setStorageSync(FILTER_KEY, filters);
    wx.setStorageSync(SCROLL_KEY, 0);
    this.setData({ filters, draftFilters: filters, filterOpen: false }, () => this.load(false).then(() => wx.pageScrollTo({ selector: "#overview-task-section", duration: 300 })));
  },

  previousPage() { if (this.data.filters.page > 1) this.setPage(this.data.filters.page - 1); },
  nextPage() { if (this.data.filters.page < this.data.maxPage) this.setPage(this.data.filters.page + 1); },
  setPage(page) {
    const filters = { ...this.data.filters, page };
    wx.setStorageSync(FILTER_KEY, filters);
    this.setData({ filters }, () => this.load(false).then(() => wx.pageScrollTo({ selector: "#overview-task-section", duration: 250 })));
  },

  openTask(event) {
    const taskId = event.detail ? event.detail.taskId : event.currentTarget.dataset.taskId;
    router.go("/pages/task-detail/index", { taskId });
  },
  openNode(event) {
    router.go("/pages/task-detail/index", {
      taskId: event.currentTarget.dataset.taskId,
      nodeId: event.currentTarget.dataset.nodeId,
    });
  },
  openNotifications() { wx.reLaunch({ url: "/pages/notifications/index" }); },
  retry() { this.load(false); },
});

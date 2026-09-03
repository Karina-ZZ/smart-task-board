/** Feature 01: Employee task workbench, aligned to the second-version prototype. */

const api = require("../../utils/api");
const access = require("../../utils/access");
const router = require("../../utils/router");

const STATUS_GROUPS = {
  pending_accept: ["pending_accept", "pending_acceptance"],
  decomposing: ["decomposing"],
  decomposition_failed: ["decomposition_failed"],
  in_progress: ["in_progress"],
  blocked: ["blocked"],
  pending_report: ["pending_report"],
  pending_review: ["pending_review"],
};

const STATUS_TABS = [
  { key: "pending_accept", label: "待接受" },
  { key: "decomposing", label: "AI拆解中" },
  { key: "decomposition_failed", label: "拆解失败" },
  { key: "in_progress", label: "进行中" },
  { key: "blocked", label: "受阻" },
  { key: "pending_report", label: "待汇报" },
  { key: "pending_review", label: "待验收" },
];

function chinaDateParts() {
  const formatter = new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai", month: "numeric", day: "numeric", weekday: "short", hour: "numeric", hour12: false,
  });
  const parts = formatter.formatToParts(new Date()).reduce((result, item) => {
    result[item.type] = item.value;
    return result;
  }, {});
  const hour = Number(parts.hour || 8);
  const greeting = hour < 6 ? "夜深了" : hour < 11 ? "早上好" : hour < 14 ? "中午好" : hour < 18 ? "下午好" : "晚上好";
  return { greeting, dateLabel: `${parts.month}月${parts.day}日 · ${parts.weekday}` };
}

Page({
  data: {
    loading: true, submitting: false, listening: false, error: "", user: {}, metrics: {}, quadrantCounts: {},
    supportCount: 0, supportItems: [], unread: 0, allTasks: [], visibleTasks: [], taskFilter: "in_progress",
    quadrantFilter: "", statusTabs: STATUS_TABS, draftText: "", executive: false, greeting: "早上好", dateLabel: "",
  },

  onLoad() {
    this.setData(chinaDateParts());
    this.recorder = wx.getRecorderManager();
    this.recorder.onStop((result) => {
      this.setData({ listening: false });
      wx.showLoading({ title: "语音转文字" });
      api.transcribeVoice(result?.tempFilePath).then((transcript) => {
        const draftText = String(transcript?.text || transcript?.transcript || "").trim();
        if (!draftText) throw new Error("未识别到有效语音，请改用文字输入");
        this.setData({ draftText });
        return api.saveCreationDraft({ rawText: draftText, taskDescription: draftText, inputType: "voice" });
      }).then(() => {
        wx.hideLoading();
        wx.showToast({ title: "语音已转为文字", icon: "success" });
      }).catch((error) => {
        wx.hideLoading();
        wx.showToast({ title: error.message || "语音识别失败，请改用文字", icon: "none" });
      });
    });
    this.recorder.onError(() => {
      this.setData({ listening: false });
      wx.showToast({ title: "录音失败，请改用文字", icon: "none" });
    });
  },

  onShow() { this.load(); },
  onPullDownRefresh() { this.load().finally(() => wx.stopPullDownRefresh()); },

  load() {
    this.setData({ loading: true, error: "" });
    return Promise.all([api.dashboard(), api.creationDraft()])
      .then(([data, draft]) => {
        this.setData({
          ...data,
          allTasks: data.tasks || [],
          avatarText: data.user.name ? data.user.name.slice(-1) : "序",
          executive: access.canAccessExecutive(data.user),
          draftText: draft.rawText || draft.taskDescription || this.data.draftText,
          loading: false,
        }, () => this.applyFilters());
      })
      .catch((error) => this.setData({ error: error.message || "工作台加载失败", loading: false }));
  },

  applyFilters() {
    const statuses = STATUS_GROUPS[this.data.taskFilter] || [];
    const visibleTasks = this.data.allTasks.filter((task) => {
      const statusMatch = !statuses.length || statuses.includes(task.status);
      const quadrantMatch = !this.data.quadrantFilter || task.priorityQuadrant === this.data.quadrantFilter;
      return statusMatch && quadrantMatch;
    });
    this.setData({ visibleTasks });
  },

  inputDraft(event) {
    const draftText = event.detail.value;
    this.setData({ draftText });
    clearTimeout(this.saveTimer);
    this.saveTimer = setTimeout(() => api.saveCreationDraft({ rawText: draftText, taskDescription: draftText }), 250);
  },

  submitDraft() {
    const text = this.data.draftText.trim();
    if (!text) { wx.showToast({ title: "请先描述任务", icon: "none" }); return; }
    this.setData({ submitting: true });
    wx.showLoading({ title: "AI识别中" });
    api.extractTaskDraft(text).then(() => {
      wx.hideLoading();
      this.setData({ submitting: false });
      router.go("/pages/create-details/index");
    }).catch((error) => {
      wx.hideLoading();
      this.setData({ submitting: false });
      wx.showToast({ title: error.message || "识别失败", icon: "none" });
    });
  },

  toggleVoice() {
    if (this.data.listening) { this.recorder.stop(); return; }
    wx.authorize({
      scope: "scope.record",
      success: () => { this.setData({ listening: true }); this.recorder.start({ duration: 60000, format: "mp3" }); },
      fail: () => wx.showModal({
        title: "需要麦克风权限", content: "请在设置中允许录音，或直接输入文字。", confirmText: "去设置",
        success: (result) => { if (result.confirm) wx.openSetting(); },
      }),
    });
  },

  selectStatus(event) { this.setData({ taskFilter: event.currentTarget.dataset.status }, () => this.applyFilters()); },
  selectQuadrant(event) {
    const quadrant = event.currentTarget.dataset.quadrant;
    this.setData({ quadrantFilter: this.data.quadrantFilter === quadrant ? "" : quadrant }, () => {
      this.applyFilters();
      wx.pageScrollTo({ selector: "#task-section", duration: 300 });
    });
  },
  clearQuadrant() { this.setData({ quadrantFilter: "" }, () => this.applyFilters()); },
  openTask(event) {
    const taskId = event.detail ? event.detail.taskId : event.currentTarget.dataset.taskId;
    const nodeId = event.detail ? event.detail.nodeId : event.currentTarget.dataset.nodeId;
    router.go("/pages/task-detail/index", { taskId, ...(nodeId ? { nodeId } : {}) });
  },
  openTasks() { wx.reLaunch({ url: "/pages/tasks/index?reset=1" }); },
  openNotifications() { wx.reLaunch({ url: "/pages/notifications/index" }); },
  openProfile() { wx.reLaunch({ url: "/pages/profile/index" }); },
  retry() { this.load(); },
});

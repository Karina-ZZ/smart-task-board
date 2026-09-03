/**
 * Feature: Task Detail change and lifecycle controls (Feature 10).
 * Responsibilities: prior task actions plus change requests, reassignment, withdraw, and cancel.
 * Does not own: completion review approval or automatic archival.
 * Plan task: DEV-12 / FEATURE-10.
 */

const api = require("../../utils/api");
const access = require("../../utils/access");
const taskDetailView = require("../../utils/task-detail");
const router = require("../../utils/router");

const TABS = [
  { key: "overview", label: "概览", target: "detail-top" },
  { key: "people", label: "人员", target: "detail-people" },
  { key: "nodes", label: "节点", target: "detail-nodes" },
  { key: "progress", label: "进度/汇报", target: "detail-progress" },
  { key: "performance", label: "绩效", target: "detail-performance" },
];

function errorKind(error) {
  if (error && error.statusCode === 403) return "forbidden";
  if (error && error.statusCode === 404) return "not-found";
  return "request";
}

function sortLogs(items) {
  return items.slice().sort((left, right) => String(right.createdAt || "").localeCompare(String(left.createdAt || "")));
}

function editableModal(title, placeholderText, confirmText = "确认") {
  return new Promise((resolve) => {
    wx.showModal({
      title,
      editable: true,
      placeholderText,
      confirmText,
      success: (result) => resolve(result.confirm ? String(result.content || "").trim() : null),
      fail: () => resolve(null),
    });
  });
}

Page({
  data: {
    taskId: "",
    focusNodeId: "",
    task: null,
    nodes: [],
    timeline: [],
    latestReport: null,
    performance: null,
    loading: true,
    error: "",
    errorKind: "",
    tabs: TABS,
    activeTab: "overview",
    expandedNodeId: "",
    actionMode: "readonly",
    readonlyReason: "当前任务仅提供查看能力",
    logOpen: false,
    logLoading: false,
    logItems: [],
    statusLogOffset: 0,
    statusLogTotal: 0,
    operationLogOffset: 0,
    operationLogTotal: 0,
    logHasMore: false,
    moreOpen: false,
    executive: false,
    unread: 0,
    actionSubmitting: false,
    nodeSubmittingId: "",
    currentEmployeeNo: "",
    allowedActions: [],
    pendingChangeRequest: null,
    canSubmitChange: false,
    canCancelChange: false,
    canApproveChange: false,
    canRejectChange: false,
    canReassign: false,
    canWithdraw: false,
    canCancelTask: false,
  },

  onLoad(options) {
    const taskId = options.taskId || "";
    const focusNodeId = options.nodeId || "";
    this.sectionOffsets = [];
    this.setData({ taskId, focusNodeId, expandedNodeId: focusNodeId });
  },

  onShow() {
    if (!this.data.taskId) {
      this.setData({ loading: false, error: "缺少任务编号", errorKind: "not-found" });
      return;
    }
    this.load();
  },

  onPageScroll(event) {
    if (!this.sectionOffsets || !this.sectionOffsets.length || this.scrollingToSection) return;
    const marker = event.scrollTop + 190;
    let active = this.sectionOffsets[0];
    this.sectionOffsets.forEach((section) => { if (section.top <= marker) active = section; });
    if (active && active.key !== this.data.activeTab) this.setData({ activeTab: active.key });
  },

  back() {
    wx.navigateBack({ fail: () => wx.reLaunch({ url: "/pages/tasks/index" }) });
  },

  load() {
    this.setData({ loading: true, error: "", errorKind: "" });
    return Promise.all([
      api.taskDetail(this.data.taskId),
      api.currentUser().catch(() => ({})),
    ]).then(([view, user]) => {
      const allowed = view.allowedActions || [];
      let actionMode = "readonly";
      if (allowed.includes("accept") || allowed.includes("return")) actionMode = "accept";
      else if (allowed.includes("submit_completion")) actionMode = "complete";
      else if (allowed.includes("approve_review") || allowed.includes("approve_completion")) actionMode = "review";
      else if (allowed.includes("report") || allowed.includes("submit_progress_report")) actionMode = "report";
      this.initialStatusLogs = view.statusLogs || [];
      this.initialOperationLogs = view.operationLogs || [];
      const currentEmployeeNo = user.employeeNo || "";
      const pendingChangeRequest = (view.task.changeRequests || []).find((item) => item.status === "pending") || null;
      const nodes = (view.nodes || []).map((node) => ({
        ...node,
        canExecute: node.ownerEmployeeNo === currentEmployeeNo && ["in_progress", "blocked", "pending_report"].includes(view.task.status),
      }));
      this.setData({
        task: view.task,
        nodes,
        timeline: view.timeline,
        latestReport: view.latestReport,
        performance: view.performance,
        loading: false,
        actionMode,
        executive: access.canAccessExecutive(user),
        currentEmployeeNo,
        allowedActions: allowed,
        pendingChangeRequest,
        canSubmitChange: allowed.includes("submit_change_request"),
        canCancelChange: allowed.includes("cancel_change_request"),
        canApproveChange: allowed.includes("approve_change_request"),
        canRejectChange: allowed.includes("reject_change_request"),
        canReassign: allowed.includes("reassign_task"),
        canWithdraw: allowed.includes("withdraw_task"),
        canCancelTask: allowed.includes("cancel_task"),
      }, () => {
        wx.nextTick(() => {
          this.cacheSectionOffsets();
          if (this.data.focusNodeId) this.focusNode(this.data.focusNodeId);
        });
      });
    }).catch((error) => {
      const kind = errorKind(error);
      const messages = {
        forbidden: "你没有权限查看该任务",
        "not-found": "任务不存在或已被移除",
        request: error.message || "任务加载失败，请稍后重试",
      };
      this.setData({ loading: false, errorKind: kind, error: messages[kind] });
    });
  },

  retry() { this.load(); },

  openReport() {
    if (!this.data.taskId || this.data.actionMode !== "report") return;
    router.go("/pages/report/index", { taskId: this.data.taskId });
  },

  openCompletion() {
    if (!this.data.taskId || this.data.actionMode !== "complete") return;
    router.go("/pages/completion/index", { taskId: this.data.taskId });
  },

  openReview() {
    if (!this.data.taskId || this.data.actionMode !== "review") return;
    router.go("/pages/review/index", { taskId: this.data.taskId });
  },

  acceptTask() {
    const task = this.data.task;
    if (!task || this.data.actionSubmitting) return;
    wx.showModal({
      title: "接受任务",
      content: "接受后系统将立即启动AI拆解。拆解成功前任务不会生效。",
      confirmText: "接受并拆解",
      success: (result) => {
        if (!result.confirm) return;
        this.setData({ actionSubmitting: true });
        api.acceptTask(this.data.taskId, task.taskVersion)
          .then(() => router.replace("/pages/decomposition/index", { taskId: this.data.taskId }))
          .catch((error) => {
            this.setData({ actionSubmitting: false });
            wx.showToast({ title: error.message || "接受任务失败", icon: "none" });
          });
      },
    });
  },

  returnTask() {
    const task = this.data.task;
    if (!task || this.data.actionSubmitting) return;
    wx.showModal({
      title: "退回任务",
      content: "请填写退回原因，创建人将收到通知。",
      editable: true,
      placeholderText: "请输入退回原因",
      confirmText: "确认退回",
      success: (result) => {
        if (!result.confirm) return;
        const reason = String(result.content || "").trim();
        if (!reason) {
          wx.showToast({ title: "请填写退回原因", icon: "none" });
          return;
        }
        this.setData({ actionSubmitting: true });
        api.returnTask(this.data.taskId, task.taskVersion, reason)
          .then(() => {
            this.setData({ actionSubmitting: false });
            wx.showToast({ title: "任务已退回", icon: "success" });
            this.load();
          })
          .catch((error) => {
            this.setData({ actionSubmitting: false });
            wx.showToast({ title: error.message || "退回任务失败", icon: "none" });
          });
      },
    });
  },

  cacheSectionOffsets() {
    const query = wx.createSelectorQuery().in(this);
    TABS.forEach((tab) => query.select(`#${tab.target}`).boundingClientRect());
    query.selectViewport().scrollOffset();
    query.exec((results) => {
      const viewport = results[results.length - 1] || { scrollTop: 0 };
      this.sectionOffsets = TABS.map((tab, index) => ({
        key: tab.key,
        target: tab.target,
        top: results[index] ? results[index].top + viewport.scrollTop : Number.MAX_SAFE_INTEGER,
      }));
    });
  },

  selectTab(event) {
    const { tab, target } = event.currentTarget.dataset;
    this.setData({ activeTab: tab });
    this.scrollToSection(target);
  },

  scrollToSection(target) {
    const query = wx.createSelectorQuery().in(this);
    query.select(`#${target}`).boundingClientRect();
    query.selectViewport().scrollOffset();
    query.exec((result) => {
      const rect = result[0];
      const viewport = result[1] || { scrollTop: 0 };
      if (!rect) return;
      this.scrollingToSection = true;
      wx.pageScrollTo({
        scrollTop: Math.max(0, viewport.scrollTop + rect.top - 126),
        duration: 220,
        complete: () => { setTimeout(() => { this.scrollingToSection = false; }, 260); },
      });
    });
  },

  tabTouchStart(event) { this.tabTouchX = event.changedTouches?.[0]?.clientX; },
  tabTouchEnd(event) {
    const end = event.changedTouches?.[0]?.clientX;
    if (this.tabTouchX === undefined || end === undefined) return;
    const distance = end - this.tabTouchX;
    if (Math.abs(distance) < 45) return;
    const index = TABS.findIndex((tab) => tab.key === this.data.activeTab);
    const next = Math.min(TABS.length - 1, Math.max(0, index + (distance < 0 ? 1 : -1)));
    const target = TABS[next];
    if (target && target.key !== this.data.activeTab) {
      this.setData({ activeTab: target.key });
      this.scrollToSection(target.target);
    }
  },

  toggleNode(event) {
    const nodeId = event.currentTarget.dataset.nodeId;
    this.setData({ expandedNodeId: this.data.expandedNodeId === nodeId ? "" : nodeId });
  },

  focusNode(nodeId) {
    const exists = this.data.nodes.some((node) => node.nodeId === nodeId);
    if (!exists) return;
    this.setData({ activeTab: "nodes", expandedNodeId: nodeId }, () => {
      wx.nextTick(() => this.scrollToSection(`node-${nodeId}`));
    });
  },

  showIssue(event) {
    const nodeId = event.currentTarget.dataset.nodeId;
    const node = this.data.nodes.find((item) => item.nodeId === nodeId);
    if (!node || !node.issue) return;
    wx.showModal({
      title: node.issue.title || "节点卡点",
      content: node.issue.description || "无补充说明",
      showCancel: false,
      confirmText: "知道了",
    });
  },

  startNode(event) {
    const nodeId = event.currentTarget.dataset.nodeId;
    const task = this.data.task;
    if (!nodeId || !task || this.data.nodeSubmittingId) return;
    this.setData({ nodeSubmittingId: nodeId });
    api.startNode(this.data.taskId, nodeId, task.taskVersion)
      .then(() => this.load())
      .catch((error) => wx.showToast({ title: error.message || "开始节点失败", icon: "none" }))
      .finally(() => this.setData({ nodeSubmittingId: "" }));
  },

  completeNode(event) {
    const nodeId = event.currentTarget.dataset.nodeId;
    const task = this.data.task;
    if (!nodeId || !task || this.data.nodeSubmittingId) return;
    wx.showModal({
      title: "完成节点",
      content: "确认该节点已完成并达到节点交付要求？",
      confirmText: "确认完成",
      success: (result) => {
        if (!result.confirm) return;
        this.setData({ nodeSubmittingId: nodeId });
        api.completeNode(this.data.taskId, nodeId, task.taskVersion)
          .then(() => this.load())
          .catch((error) => wx.showToast({ title: error.message || "完成节点失败", icon: "none" }))
          .finally(() => this.setData({ nodeSubmittingId: "" }));
      },
    });
  },

  openLogs() {
    this.setData({
      logOpen: true,
      logItems: [],
      statusLogOffset: 0,
      operationLogOffset: 0,
      statusLogTotal: 0,
      operationLogTotal: 0,
      logHasMore: true,
    }, () => this.loadMoreLogs());
  },

  closeLogs() { this.setData({ logOpen: false }); },
  stopBubble() {},

  loadMoreLogs() {
    if (this.data.logLoading || !this.data.logHasMore) return Promise.resolve();
    const limit = 20;
    this.setData({ logLoading: true });
    return Promise.all([
      api.taskStatusLogs(this.data.taskId, this.data.statusLogOffset, limit),
      api.taskOperationLogs(this.data.taskId, this.data.operationLogOffset, limit),
    ]).then(([statusPage, operationPage]) => {
      const statusItems = (statusPage.items || []).map((item) => taskDetailView.normalizeStatusLog(item, {}));
      const operationItems = (operationPage.items || []).map((item) => taskDetailView.normalizeOperationLog(item, {}));
      const statusOffset = this.data.statusLogOffset + statusItems.length;
      const operationOffset = this.data.operationLogOffset + operationItems.length;
      const statusTotal = Number(statusPage.total || 0);
      const operationTotal = Number(operationPage.total || 0);
      this.setData({
        logItems: sortLogs(this.data.logItems.concat(statusItems, operationItems)),
        statusLogOffset: statusOffset,
        operationLogOffset: operationOffset,
        statusLogTotal: statusTotal,
        operationLogTotal: operationTotal,
        logHasMore: statusOffset < statusTotal || operationOffset < operationTotal,
        logLoading: false,
      });
    }).catch((error) => {
      this.setData({ logLoading: false, logHasMore: false });
      wx.showToast({ title: error.message || "操作记录加载失败", icon: "none" });
    });
  },

  openMore() { this.setData({ moreOpen: true }); },
  closeMore() { this.setData({ moreOpen: false }); },
  copyTaskNo() {
    if (!this.data.task?.taskNo) return;
    wx.setClipboardData({ data: this.data.task.taskNo, complete: () => this.setData({ moreOpen: false }) });
  },

  requestChange() {
    if (!this.data.canSubmitChange || !this.data.task) return;
    this.closeMore();
    const choices = ["修改截止时间", "修改任务权重", "修改任务名称"];
    wx.showActionSheet({
      itemList: choices,
      success: async ({ tapIndex }) => {
        const configs = [
          { key: "deadline", title: "新的截止时间", placeholder: "例如 2026-09-10T18:00:00+08:00" },
          { key: "taskWeight", title: "新的任务权重", placeholder: "请输入1-5" },
          { key: "taskName", title: "新的任务名称", placeholder: "请输入任务名称" },
        ];
        const config = configs[tapIndex];
        if (!config) return;
        let value = await editableModal(config.title, config.placeholder, "下一步");
        if (!value) return;
        if (config.key === "taskWeight") {
          const weight = Number(value);
          if (!Number.isInteger(weight) || weight < 1 || weight > 5) {
            wx.showToast({ title: "任务权重必须为1-5", icon: "none" });
            return;
          }
          value = weight;
        }
        if (config.key === "deadline" && !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(value)) {
          wx.showToast({ title: "请输入带时区的ISO时间", icon: "none" });
          return;
        }
        const reason = await editableModal("变更原因", "请说明为什么需要调整", "提交申请");
        if (!reason) {
          wx.showToast({ title: "请填写变更原因", icon: "none" });
          return;
        }
        this.setData({ actionSubmitting: true });
        api.submitChangeRequest(this.data.taskId, this.data.task.taskVersion, { [config.key]: value }, reason)
          .then(() => { wx.showToast({ title: "变更申请已提交", icon: "success" }); return this.load(); })
          .catch((error) => wx.showToast({ title: error.message || "提交变更失败", icon: "none" }))
          .finally(() => this.setData({ actionSubmitting: false }));
      },
    });
  },

  cancelPendingChange() {
    const change = this.data.pendingChangeRequest;
    if (!this.data.canCancelChange || !change) return;
    this.closeMore();
    editableModal("取消变更申请", "请填写取消原因", "确认取消").then((reason) => {
      if (!reason) return;
      this.setData({ actionSubmitting: true });
      api.cancelChangeRequest(this.data.taskId, this.data.task.taskVersion, change.changeRequestId, reason)
        .then(() => this.load())
        .catch((error) => wx.showToast({ title: error.message || "取消申请失败", icon: "none" }))
        .finally(() => this.setData({ actionSubmitting: false }));
    });
  },

  approveChange() {
    const change = this.data.pendingChangeRequest;
    if (!this.data.canApproveChange || !change) return;
    this.closeMore();
    editableModal("同意变更", "审批意见（可选）", "确认同意").then((comment) => {
      if (comment === null) return;
      this.setData({ actionSubmitting: true });
      api.approveChangeRequest(this.data.taskId, this.data.task.taskVersion, change.changeRequestId, comment)
        .then(() => { wx.showToast({ title: "变更已生效", icon: "success" }); return this.load(); })
        .catch((error) => wx.showToast({ title: error.message || "审批失败", icon: "none" }))
        .finally(() => this.setData({ actionSubmitting: false }));
    });
  },

  rejectChange() {
    const change = this.data.pendingChangeRequest;
    if (!this.data.canRejectChange || !change) return;
    this.closeMore();
    editableModal("拒绝变更", "请填写拒绝原因", "确认拒绝").then((reason) => {
      if (!reason) return;
      this.setData({ actionSubmitting: true });
      api.rejectChangeRequest(this.data.taskId, this.data.task.taskVersion, change.changeRequestId, reason)
        .then(() => this.load())
        .catch((error) => wx.showToast({ title: error.message || "拒绝失败", icon: "none" }))
        .finally(() => this.setData({ actionSubmitting: false }));
    });
  },

  reassignTask() {
    if (!this.data.canReassign || !this.data.task) return;
    this.closeMore();
    api.users().then((response) => {
      const users = (response.items || response || []).filter((item) => item.employeeNo && item.employeeNo !== this.data.task.mainAssigneeEmployeeNo);
      if (!users.length) throw new Error("没有可选的新承办人");
      wx.showActionSheet({
        itemList: users.map((item) => `${item.name || item.employeeNo} · ${item.employeeNo}`),
        success: async ({ tapIndex }) => {
          const selected = users[tapIndex];
          if (!selected) return;
          const reason = await editableModal("更换承办人", `更换为${selected.name || selected.employeeNo}的原因`, "确认更换");
          if (!reason) return;
          this.setData({ actionSubmitting: true });
          api.lifecycle(this.data.taskId, "reassign", this.data.task.taskVersion, reason, selected.employeeNo)
            .then(() => { wx.showToast({ title: "已重新发送待接受", icon: "success" }); return this.load(); })
            .catch((error) => wx.showToast({ title: error.message || "更换承办人失败", icon: "none" }))
            .finally(() => this.setData({ actionSubmitting: false }));
        },
      });
    }).catch((error) => wx.showToast({ title: error.message || "人员加载失败", icon: "none" }));
  },

  withdrawTask() { this.runLifecycleWithReason("withdraw", "撤回任务", "请填写撤回原因", "确认撤回"); },
  cancelTask() { this.runLifecycleWithReason("cancel", "取消任务", "请填写取消原因", "确认取消"); },
  runLifecycleWithReason(action, title, placeholder, confirmText) {
    const allowed = action === "withdraw" ? this.data.canWithdraw : this.data.canCancelTask;
    if (!allowed || !this.data.task) return;
    this.closeMore();
    editableModal(title, placeholder, confirmText).then((reason) => {
      if (!reason) return;
      this.setData({ actionSubmitting: true });
      api.lifecycle(this.data.taskId, action, this.data.task.taskVersion, reason)
        .then(() => { wx.showToast({ title: action === "withdraw" ? "任务已撤回" : "任务已取消", icon: "success" }); return this.load(); })
        .catch((error) => wx.showToast({ title: error.message || "任务操作失败", icon: "none" }))
        .finally(() => this.setData({ actionSubmitting: false }));
    });
  },
});

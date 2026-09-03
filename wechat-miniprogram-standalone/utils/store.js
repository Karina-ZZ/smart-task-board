/**
 * Feature: Local demonstration repository and V1.1 workflow.
 * Responsibilities: make every Mini Program journey runnable without external credentials while enforcing role/state guards.
 * Does not own: production persistence, server authorization, or enterprise messaging.
 * Plan task: WECHAT-MP-02.
 */

const STORAGE_KEY = "wangxu.task-hub.v1.1";

function clone(value) { return JSON.parse(JSON.stringify(value)); }
function now() { return new Date().toISOString(); }
function id(prefix) { return `${prefix}${Date.now()}${Math.floor(Math.random() * 1000)}`; }

function seed() {
  const users = [
    { employeeNo: "E1001", name: "林雨欣", roleType: "employee", departmentId: "D01", departmentName: "人力资源部", workloadScore: 68, workloadLevel: "适中" },
    { employeeNo: "E1002", name: "周子航", roleType: "employee", departmentId: "D01", departmentName: "人力资源部", workloadScore: 82, workloadLevel: "偏高" },
    { employeeNo: "E1003", name: "蔡经理", roleType: "executive", departmentId: "D01", departmentName: "人力资源部", workloadScore: 54, workloadLevel: "适中" },
    { employeeNo: "E1004", name: "陈思琪", roleType: "employee", departmentId: "D02", departmentName: "信息中心", workloadScore: 43, workloadLevel: "轻载" },
    { employeeNo: "E1005", name: "系统管理员", roleType: "admin", departmentId: "D99", departmentName: "系统管理", workloadScore: 0, workloadLevel: "-" },
  ];
  const tasks = [
    {
      taskId: "T20260902001", taskNo: "WX-260902-001", taskName: "确认Q2组织绩效指标口径", taskDescription: "核对各单位Q2指标口径、目标值与数据来源，形成可确认清单。", taskGoal: "在周五前完成口径确认并提交验收。", taskSource: "管理例会", creatorEmployeeNo: "E1003", mainAssigneeEmployeeNo: "E1001", reportToEmployeeNo: "E1003", reviewerEmployeeNo: "E1003", collaboratorEmployeeNos: ["E1002"], departmentId: "D01", status: "pending_accept", startTime: "2026-09-02T09:00:00+08:00", deadline: "2026-09-05T18:00:00+08:00", taskWeight: 4, priorityQuadrant: "important_urgent", progressPercent: 0, reportCycle: "每周", performanceMetric: "组织绩效责任书按期完成率", acceptanceCriteria: "口径、责任人和数据来源全部确认", taskVersion: 1, effectiveAt: null, decompositionStatus: null, hasIssue: false, createdAt: "2026-09-02T09:00:00+08:00", updatedAt: "2026-09-02T09:00:00+08:00"
    },
    {
      taskId: "T20260901002", taskNo: "WX-260901-002", taskName: "完成招聘运营月报数据复核", taskDescription: "复核招聘达成率、周期、需求与入职数据，输出异常说明。", taskGoal: "形成可直接用于月度汇报的数据结论。", taskSource: "月度运营", creatorEmployeeNo: "E1003", mainAssigneeEmployeeNo: "E1001", reportToEmployeeNo: "E1003", reviewerEmployeeNo: "E1003", collaboratorEmployeeNos: ["E1004"], departmentId: "D01", status: "in_progress", startTime: "2026-09-01T09:00:00+08:00", deadline: "2026-09-08T18:00:00+08:00", taskWeight: 4, priorityQuadrant: "important_not_urgent", progressPercent: 45, reportCycle: "每周", performanceMetric: "招聘达成率", acceptanceCriteria: "关键指标复核无误，异常均有原因说明", taskVersion: 3, effectiveAt: "2026-09-01T09:08:00+08:00", decompositionStatus: "succeeded", hasIssue: false, createdAt: "2026-09-01T08:40:00+08:00", updatedAt: "2026-09-02T11:00:00+08:00"
    },
    {
      taskId: "T20260829003", taskNo: "WX-260829-003", taskName: "智能任务看板交互验收", taskDescription: "检查工作台、任务详情、汇报与验收页面的移动端交互。", taskGoal: "完成第二版交互验收。", taskSource: "产品迭代", creatorEmployeeNo: "E1002", mainAssigneeEmployeeNo: "E1004", reportToEmployeeNo: "E1003", reviewerEmployeeNo: "E1001", collaboratorEmployeeNos: ["E1001"], departmentId: "D02", status: "pending_review", startTime: "2026-08-29T10:00:00+08:00", deadline: "2026-09-03T18:00:00+08:00", taskWeight: 5, priorityQuadrant: "important_urgent", progressPercent: 100, reportCycle: "按节点", performanceMetric: "产品按期交付率", acceptanceCriteria: "主要路径全部可点击，移动端无横向溢出", taskVersion: 5, effectiveAt: "2026-08-29T10:05:00+08:00", decompositionStatus: "succeeded", hasIssue: false, createdAt: "2026-08-29T09:20:00+08:00", updatedAt: "2026-09-02T10:20:00+08:00"
    },
    {
      taskId: "T20260828004", taskNo: "WX-260828-004", taskName: "跨部门数据权限确认", taskDescription: "确认人资与信息中心的数据范围、字段脱敏和访问审批。", taskGoal: "关闭上线前权限风险。", taskSource: "上线预案", creatorEmployeeNo: "E1003", mainAssigneeEmployeeNo: "E1001", reportToEmployeeNo: "E1003", reviewerEmployeeNo: "E1003", collaboratorEmployeeNos: ["E1004"], departmentId: "D01", status: "blocked", startTime: "2026-08-28T09:00:00+08:00", deadline: "2026-09-01T18:00:00+08:00", taskWeight: 5, priorityQuadrant: "important_urgent", progressPercent: 60, reportCycle: "每日", performanceMetric: "系统上线按期率", acceptanceCriteria: "权限矩阵经IT与业务共同确认", taskVersion: 4, effectiveAt: "2026-08-28T09:10:00+08:00", decompositionStatus: "succeeded", hasIssue: true, createdAt: "2026-08-28T08:30:00+08:00", updatedAt: "2026-09-02T09:45:00+08:00"
    }
  ];
  const nodes = [
    { nodeId: "N2001", taskId: "T20260901002", nodeOrder: 1, nodeName: "核对需求与入职口径", ownerEmployeeNo: "E1001", status: "completed", progressPercent: 100, actionDetail: "按需求编号去重并核对财年范围", plannedDeadline: "2026-09-02T12:00:00+08:00", dependencyNodeIds: [] },
    { nodeId: "N2002", taskId: "T20260901002", nodeOrder: 2, nodeName: "复核核心指标", ownerEmployeeNo: "E1001", status: "in_progress", progressPercent: 40, actionDetail: "复算招聘达成率与平均周期", plannedDeadline: "2026-09-05T18:00:00+08:00", dependencyNodeIds: ["N2001"] },
    { nodeId: "N2003", taskId: "T20260901002", nodeOrder: 3, nodeName: "整理异常说明", ownerEmployeeNo: "E1004", status: "pending", progressPercent: 0, actionDetail: "为异常值补充业务原因与证据", plannedDeadline: "2026-09-07T18:00:00+08:00", dependencyNodeIds: ["N2002"] },
    { nodeId: "N3001", taskId: "T20260829003", nodeOrder: 1, nodeName: "检查工作台与导航", ownerEmployeeNo: "E1004", status: "completed", progressPercent: 100, actionDetail: "核对导航和工作台组件", plannedDeadline: "2026-08-30T18:00:00+08:00", dependencyNodeIds: [] },
    { nodeId: "N3002", taskId: "T20260829003", nodeOrder: 2, nodeName: "检查详情与验收", ownerEmployeeNo: "E1004", status: "completed", progressPercent: 100, actionDetail: "核对状态动作与原因弹窗", plannedDeadline: "2026-09-01T18:00:00+08:00", dependencyNodeIds: ["N3001"] },
    { nodeId: "N4001", taskId: "T20260828004", nodeOrder: 1, nodeName: "梳理字段权限", ownerEmployeeNo: "E1001", status: "in_progress", progressPercent: 60, actionDetail: "整理角色到字段的可见范围", plannedDeadline: "2026-09-01T12:00:00+08:00", dependencyNodeIds: [] },
  ];
  nodes.forEach((node) => { if (!node.assignmentStatus) node.assignmentStatus = "accepted"; });
  const logs = tasks.flatMap((task) => [
    { logId: id("L"), taskId: task.taskId, actionLabel: "创建任务", toStatus: "draft", operatorEmployeeNo: task.creatorEmployeeNo, reason: "", createdAt: task.createdAt },
    { logId: id("L"), taskId: task.taskId, actionLabel: task.status === "pending_accept" ? "确认发送" : "任务生效", toStatus: task.status === "pending_accept" ? "pending_accept" : "in_progress", operatorEmployeeNo: task.creatorEmployeeNo, reason: "", createdAt: task.updatedAt },
  ]);
  return {
    version: 1,
    currentEmployeeNo: "E1001",
    users,
    authorizedScopes: [
      { authorizedScopeId: "SCOPE-D01", employeeNo: "E1003", scopeType: "department", scopeId: "D01", permissionType: "view", status: "active" },
    ],
    tasks,
    nodes,
    reports: [
      { reportId: "R2001", taskId: "T20260901002", reporterEmployeeNo: "E1001", progressPercent: 45, stageResult: "完成需求口径核对，招聘周期差异已定位。", hasIssue: false, issueNote: "", remark: "待业务确认1项跨月需求。", reportTime: "2026-09-02T11:00:00+08:00" },
    ],
    issues: [
      { issueId: "I4001", taskId: "T20260828004", title: "跨部门数据授权未确认", description: "信息中心尚未确认字段脱敏范围。", issueType: "blocker", status: "open", ownerEmployeeNo: "E1003", createdAt: "2026-09-01T14:00:00+08:00" },
    ],
    changeRequests: [],
    reviews: [
      { reviewId: "RV3001", taskId: "T20260829003", roundNo: 1, reviewStatus: "submitted", submitterEmployeeNo: "E1004", reviewerEmployeeNo: "E1001", completionNote: "全部交互已检查并修复。", deliverableSummary: "验收记录与截图说明", submittedAt: "2026-09-02T10:20:00+08:00" },
    ],
    performanceMetrics: [
      { metricId: "PM1", metricType: "KPI", metricName: "组织绩效责任书按期完成率", period: "2026Q3", businessUnit: "人力资源部", weight: 20, matchReason: "任务目标与指标名称高度相关" },
      { metricId: "PM2", metricType: "KPI", metricName: "招聘达成率", period: "2026Q3", businessUnit: "人力资源部", weight: 25, matchReason: "任务内容涉及招聘运营" },
      { metricId: "PM3", metricType: "项目", metricName: "产品按期交付率", period: "2026Q3", businessUnit: "信息中心", weight: 20, matchReason: "任务属于产品交付" },
    ],
    notifications: [
      { notificationId: "NO1", taskId: "T20260902001", recipientEmployeeNo: "E1001", type: "task", title: "新任务待接受", content: "“确认Q2组织绩效指标口径”等待你接受。", actionRequired: true, targetType: "task_acceptance", canOpen: true, sentAt: "2026-09-02T09:01:00+08:00" },
      { notificationId: "NO2", taskId: "T20260829003", recipientEmployeeNo: "E1001", type: "task", title: "任务待验收", content: "“智能任务看板交互验收”已提交完成申请。", actionRequired: true, targetType: "review", canOpen: true, sentAt: "2026-09-02T10:21:00+08:00" },
      { notificationId: "NO3", taskId: "T20260828004", recipientEmployeeNo: "E1003", type: "reminder", title: "卡点持续未关闭", content: "跨部门数据授权卡点仍在处理中。", actionRequired: true, targetType: "task_detail", canOpen: true, sentAt: "2026-09-02T09:46:00+08:00" },
    ],
    logs,
    creationDraft: null,
  };
}

function ensureInitialized() {
  if (!wx.getStorageSync(STORAGE_KEY)) wx.setStorageSync(STORAGE_KEY, seed());
}
function read() { ensureInitialized(); return clone(wx.getStorageSync(STORAGE_KEY)); }
function write(state) { wx.setStorageSync(STORAGE_KEY, state); return clone(state); }
function reset() { return write(seed()); }
function userByNo(state, employeeNo) { return state.users.find((user) => user.employeeNo === employeeNo); }

function activeScopes(state, employeeNo) {
  return (state.authorizedScopes || []).filter((scope) => scope.employeeNo === employeeNo && scope.status === "active");
}

function currentUser(state) {
  const resolved = state || read();
  const user = userByNo(resolved, resolved.currentEmployeeNo);
  if (!user) return null;
  const scopes = activeScopes(resolved, user.employeeNo);
  const scopedTeamAccess = scopes.some((scope) => ["department", "user", "all_demo_data"].includes(scope.scopeType));
  const canAccessExecutive = user.roleType === "executive" || (user.roleType === "admin" && scopedTeamAccess);
  const allowedRoutes = [
    "/workbench", "/tasks", "/task/:taskId", "/task/:taskId/report", "/task/:taskId/review",
    "/task/:taskId/decomposition", "/create/details", "/create/confirm", "/notifications", "/profile",
  ];
  if (canAccessExecutive) allowedRoutes.push("/executive", "/executive/employee-tasks");
  const canViewAllTasks = user.roleType === "admin";
  const capabilities = ["task:read:related"];
  if (canViewAllTasks) capabilities.push("task:read:all");
  if (canAccessExecutive) capabilities.push("executive:read");
  if (user.roleType === "admin") capabilities.push("permissions:manage");
  return {
    ...user,
    roles: [user.roleType],
    scopes,
    permissions: {
      canAccessExecutive,
      canManagePermissions: user.roleType === "admin",
      canViewAllTasks,
      canViewAllDemoData: ["executive", "admin"].includes(user.roleType) && scopes.some((scope) => scope.scopeType === "all_demo_data"),
      allowedRoutes,
      capabilities,
    },
    authMode: "mock",
  };
}

function hasDirectTaskRelation(state, user, task) {
  if ([task.creatorEmployeeNo, task.mainAssigneeEmployeeNo, task.reportToEmployeeNo, task.reviewerEmployeeNo].includes(user.employeeNo)) return true;
  if ((task.collaboratorEmployeeNos || []).includes(user.employeeNo)) return true;
  if (state.nodes.some((node) => node.taskId === task.taskId && node.ownerEmployeeNo === user.employeeNo)) return true;
  return state.issues.some((issue) => issue.taskId === task.taskId && [issue.ownerEmployeeNo, issue.reportedByEmployeeNo].includes(user.employeeNo));
}

function scopeMatchesTask(scope, task) {
  if (scope.permissionType !== "view" && scope.permissionType !== "manage" && scope.permissionType !== "export") return false;
  if (scope.scopeType === "all_demo_data") return true;
  if (scope.scopeType === "department") return scope.scopeId === task.departmentId;
  if (scope.scopeType === "user") {
    return [task.creatorEmployeeNo, task.mainAssigneeEmployeeNo, task.reportToEmployeeNo, task.reviewerEmployeeNo].includes(scope.scopeId);
  }
  return false;
}

function canViewTask(state, user, task) {
  if (user.roleType === "admin") return true;
  if (hasDirectTaskRelation(state, user, task)) return true;
  if (user.roleType !== "executive") return false;
  return activeScopes(state, user.employeeNo).some((scope) => scopeMatchesTask(scope, task));
}

function taskRelations(state, employeeNo, task) {
  const relations = [];
  if (task.creatorEmployeeNo === employeeNo) relations.push("created");
  if (task.mainAssigneeEmployeeNo === employeeNo) relations.push("assigned");
  if (task.reportToEmployeeNo === employeeNo) relations.push("report_to");
  if (task.reviewerEmployeeNo === employeeNo) relations.push("reviewer");
  if ((task.collaboratorEmployeeNos || []).includes(employeeNo)) relations.push("participant");
  if (state.nodes.some((node) => node.taskId === task.taskId && node.ownerEmployeeNo === employeeNo)) relations.push("node_owner");
  if (state.issues.some((issue) => issue.taskId === task.taskId && [issue.ownerEmployeeNo, issue.reportedByEmployeeNo].includes(employeeNo))) relations.push("issue_participant");
  return [...new Set(relations)];
}

function enrichTask(state, task) {
  const assignee = userByNo(state, task.mainAssigneeEmployeeNo);
  const creator = userByNo(state, task.creatorEmployeeNo);
  const reviewer = userByNo(state, task.reviewerEmployeeNo);
  const taskNodes = state.nodes.filter((node) => node.taskId === task.taskId).sort((a, b) => a.nodeOrder - b.nodeOrder);
  const reports = state.reports.filter((report) => report.taskId === task.taskId).sort((a, b) => b.reportTime.localeCompare(a.reportTime));
  const issues = state.issues.filter((issue) => issue.taskId === task.taskId);
  const logs = state.logs.filter((log) => log.taskId === task.taskId).sort((a, b) => b.createdAt.localeCompare(a.createdAt));
  const review = state.reviews.filter((item) => item.taskId === task.taskId).sort((a, b) => b.roundNo - a.roundNo)[0] || null;
  const changeRequests = (state.changeRequests || []).filter((item) => item.taskId === task.taskId).sort((a, b) => String(b.createdAt).localeCompare(String(a.createdAt)));
  return { ...task, assigneeName: assignee?.name || "待分配", creatorName: creator?.name || "-", reviewerName: reviewer?.name || "-", reportToName: userByNo(state, task.reportToEmployeeNo)?.name || "-", collaboratorNames: (task.collaboratorEmployeeNos || []).map((no) => userByNo(state, no)?.name).filter(Boolean), nodes: taskNodes, reports, issues, logs, review, changeRequests, currentUserRelations: taskRelations(state, state.currentEmployeeNo, task), isOverdue: !!task.deadline && new Date(task.deadline).getTime() < Date.now() && !["archived", "cancelled", "withdrawn", "closed"].includes(task.status), allowedActions: actionsFor(state, task, taskNodes, review) };
}

function actionsFor(state, task, taskNodes, review) {
  const employeeNo = state.currentEmployeeNo;
  const isCreator = task.creatorEmployeeNo === employeeNo;
  const isAssignee = task.mainAssigneeEmployeeNo === employeeNo;
  const isReviewer = task.reviewerEmployeeNo === employeeNo;
  const actions = [];
  if (task.status === "pending_accept" && isAssignee) actions.push("accept", "return");
  if (task.status === "decomposition_failed" && isAssignee) actions.push("retry_decomposition");
  if (["in_progress", "blocked", "pending_report"].includes(task.status) && isAssignee) actions.push("report");
  const pendingChange = (state.changeRequests || []).find((item) => item.taskId === task.taskId && item.status === "pending");
  if (["in_progress", "blocked", "pending_report"].includes(task.status) && isAssignee) actions.push(pendingChange ? "cancel_change_request" : "submit_change_request");
  if (pendingChange && isCreator) actions.push("approve_change_request", "reject_change_request");
  const hasOpenIssue = state.issues.some((issue) => issue.taskId === task.taskId && ["open", "processing"].includes(issue.status));
  if (["in_progress", "blocked"].includes(task.status) && isAssignee && taskNodes.length && taskNodes.every((node) => node.status === "completed") && !hasOpenIssue) actions.push("submit_completion");
  if (task.status === "pending_review" && isReviewer && review?.reviewStatus === "submitted") actions.push("approve_review", "reject_review");
  if (isCreator && ["pending_accept", "returned", "decomposing", "decomposition_failed", "in_progress", "blocked", "pending_report"].includes(task.status)) actions.push("reassign_task", "withdraw_task");
  if (isCreator && !["archived", "cancelled", "withdrawn", "closed", "merged"].includes(task.status)) actions.push("cancel_task");
  return actions;
}

function log(state, task, actionLabel, fromStatus, reason, operatorEmployeeNo) {
  state.logs.unshift({ logId: id("L"), taskId: task.taskId, actionLabel, fromStatus, toStatus: task.status, operatorEmployeeNo: operatorEmployeeNo || state.currentEmployeeNo, reason: reason || "", createdAt: now() });
}
function notify(state, task, recipients, title, content, type, extra) {
  [...new Set((Array.isArray(recipients) ? recipients : [recipients]).filter(Boolean))].forEach((recipientEmployeeNo) => {
    state.notifications.unshift({
      notificationId: id("NO"), taskId: task.taskId, recipientEmployeeNo, type: type || "task",
      title, content, sentAt: now(), actionRequired: false, canOpen: true, targetType: null, nodeId: null,
      ...(extra || {}),
    });
  });
}
function mutateTask(taskId, mutator) {
  const state = read();
  const task = state.tasks.find((item) => item.taskId === taskId);
  if (!task) throw new Error("TASK_NOT_FOUND");
  mutator(state, task);
  task.updatedAt = now();
  task.taskVersion += 1;
  write(state);
  return enrichTask(state, task);
}

function listTasks(filters) {
  const state = read();
  const user = currentUser(state);
  let tasks = state.tasks.filter((task) => canViewTask(state, user, task));
  if (filters?.status) tasks = tasks.filter((task) => task.status === filters.status);
  if (filters?.quadrant) tasks = tasks.filter((task) => task.priorityQuadrant === filters.quadrant);
  if (filters?.employeeNo) tasks = tasks.filter((task) => task.mainAssigneeEmployeeNo === filters.employeeNo);
  if (filters?.support) tasks = tasks.filter((task) => task.hasIssue);
  if (filters?.keyword) tasks = tasks.filter((task) => `${task.taskName}${task.taskNo}`.includes(filters.keyword));
  return tasks.sort((a, b) => String(a.deadline).localeCompare(String(b.deadline))).map((task) => enrichTask(state, task));
}

function canonicalStatus(status) {
  if (status === "pending_accept") return "pending_acceptance";
  if (status === "pending_confirm") return "pending_confirmation";
  return status;
}

function overviewDateRange(filters) {
  if (filters.datePreset === "all") return null;
  if (filters.datePreset === "custom") {
    const start = new Date(`${filters.startDate}T00:00:00+08:00`);
    const end = new Date(`${filters.endDate}T00:00:00+08:00`);
    end.setDate(end.getDate() + 1);
    return [start.getTime(), end.getTime()];
  }
  const start = new Date();
  start.setHours(0, 0, 0, 0);
  if (filters.datePreset === "week") start.setDate(start.getDate() - ((start.getDay() + 6) % 7));
  else start.setDate(1);
  const end = new Date(start);
  if (filters.datePreset === "week") end.setDate(end.getDate() + 7);
  else end.setMonth(end.getMonth() + 1);
  return [start.getTime(), end.getTime()];
}

function listOverview(filters) {
  const state = read();
  const user = currentUser(state);
  const config = { ...require("./task-overview").DEFAULT_FILTERS, ...(filters || {}) };
  let relatedTasks = listTasks({});
  if (config.source === "executive" && config.departmentId) relatedTasks = relatedTasks.filter((task) => task.departmentId === config.departmentId);
  if (config.source === "executive" && config.employeeNo) relatedTasks = relatedTasks.filter((task) => task.mainAssigneeEmployeeNo === config.employeeNo);
  const terminal = ["completed", "archived", "cancelled", "withdrawn", "merged", "closed"];
  const statusCounts = {};
  ["pending_acceptance", "in_progress", "blocked", "pending_report", "pending_review"].forEach((status) => {
    statusCounts[status] = relatedTasks.filter((task) => canonicalStatus(task.status) === status).length;
  });
  const dateRange = overviewDateRange(config);
  const nearDueEnd = Date.now() + (3 * 86400000);
  const matchesTask = (task, deadlineValue, startValue, itemStatus) => {
    if (config.status && canonicalStatus(task.status) !== config.status) return false;
    if (config.quadrant && task.priorityQuadrant !== config.quadrant) return false;
    if (config.support === "open" && !task.hasIssue) return false;
    if (config.mode !== "nodes" && config.search && !`${task.taskName}${task.taskNo || ""}`.toLowerCase().includes(config.search.toLowerCase())) return false;
    if (config.nearDue) {
      const deadline = new Date(deadlineValue).getTime();
      if (!deadline || deadline < Date.now() || deadline > nearDueEnd || terminal.includes(canonicalStatus(task.status)) || canonicalStatus(itemStatus) === "completed") return false;
    }
    if (dateRange) {
      const startTime = new Date(startValue).getTime();
      if (!startTime || startTime < dateRange[0] || startTime >= dateRange[1]) return false;
    }
    return true;
  };

  let items;
  if (config.mode === "nodes") {
    items = state.nodes.filter((node) => {
      const task = relatedTasks.find((item) => item.taskId === node.taskId);
      const canSee = node.ownerEmployeeNo === user.employeeNo || (node.collaboratorEmployeeNos || []).includes(user.employeeNo);
      const searchMatch = task && (!config.search || `${task.taskName}${task.taskNo || ""}${node.nodeName}`.toLowerCase().includes(config.search.toLowerCase()));
      return task && canSee && searchMatch && matchesTask(task, node.plannedDeadline, node.plannedStartTime, node.status);
    }).map((node) => {
      const task = relatedTasks.find((item) => item.taskId === node.taskId);
      const deadline = new Date(node.plannedDeadline).getTime();
      return {
        ...node,
        taskNo: task.taskNo,
        taskName: task.taskName,
        taskStatus: task.status,
        ownerName: userByNo(state, node.ownerEmployeeNo)?.name || "待分配",
        isOverdue: !!deadline && deadline < Date.now() && node.status !== "completed",
        daysUntilDeadline: deadline ? Math.ceil((deadline - Date.now()) / 86400000) : null,
      };
    });
  } else {
    items = relatedTasks.filter((task) => matchesTask(task, task.deadline, task.startTime, task.status));
  }

  const sortValue = (item) => {
    const task = config.mode === "nodes" ? relatedTasks.find((candidate) => candidate.taskId === item.taskId) : item;
    const values = {
      deadline: config.mode === "nodes" ? item.plannedDeadline : task.deadline,
      created_at: task.createdAt,
      updated_at: task.updatedAt,
      status: canonicalStatus(task.status),
      task_weight: Number(task.taskWeight || 0),
    };
    const value = values[config.sortBy];
    if (["deadline", "created_at", "updated_at"].includes(config.sortBy)) return new Date(value || 8640000000000000).getTime();
    return value;
  };
  items.sort((left, right) => {
    const a = sortValue(left);
    const b = sortValue(right);
    const result = typeof a === "number" && typeof b === "number" ? a - b : String(a).localeCompare(String(b));
    return config.sortOrder === "desc" ? -result : result;
  });
  const total = items.length;
  const pageSize = Math.max(1, Number(config.pageSize) || 20);
  const page = Math.max(1, Number(config.page) || 1);
  const offset = (page - 1) * pageSize;
  return { items: items.slice(offset, offset + pageSize), total, page, pageSize, statusCounts };
}

function getTask(taskId) {
  const state = read();
  const task = state.tasks.find((item) => item.taskId === taskId);
  return task ? enrichTask(state, task) : null;
}

function getDashboard() {
  const state = read();
  const user = currentUser(state);
  const tasks = listTasks({});
  const count = (status) => tasks.filter((task) => status.includes(task.status)).length;
  const terminal = ["completed", "archived", "cancelled", "withdrawn", "merged", "closed"];
  const nowTime = Date.now();
  const nearDueEnd = nowTime + (3 * 86400000);
  const quadrantCounts = {};
  ["important_urgent", "important_not_urgent", "urgent_not_important", "routine"].forEach((key) => {
    quadrantCounts[key] = tasks.filter((task) => task.priorityQuadrant === key && !terminal.includes(task.status)).length;
  });
  const completed = tasks.filter((task) => {
    if (!["completed", "archived"].includes(task.status) || !task.completedAt) return false;
    return nowTime - new Date(task.completedAt).getTime() <= 90 * 86400000;
  });
  const onTime = completed.filter((task) => task.deadline && new Date(task.completedAt).getTime() <= new Date(task.deadline).getTime());
  const supportItems = tasks.filter((task) => {
    if (!task.hasIssue) return false;
    return task.mainAssigneeEmployeeNo === user.employeeNo || (task.collaboratorEmployeeNos || []).includes(user.employeeNo);
  }).map((task) => {
    const issue = state.issues.find((item) => item.taskId === task.taskId && ["open", "processing"].includes(item.status));
    return { ...task, supportReason: issue ? issue.title : "有协作事项等待你的响应" };
  });
  return {
    user,
    tasks,
    metrics: {
      pendingAccept: count(["pending_accept", "pending_acceptance"]),
      decomposing: count(["decomposing"]),
      decompositionFailed: count(["decomposition_failed"]),
      inProgress: count(["in_progress", "blocked", "pending_report"]),
      dueWithin3Days: tasks.filter((task) => {
        const deadline = new Date(task.deadline).getTime();
        return deadline >= nowTime && deadline <= nearDueEnd && !terminal.includes(task.status);
      }).length,
      onTimeCompletionRate: completed.length ? Math.round((onTime.length / completed.length) * 100) : 0,
      completionRatePeriodDays: 90,
      pendingReview: count(["pending_review"]),
    },
    quadrantCounts,
    supportCount: supportItems.length,
    supportItems,
    unread: listNotifications("all").filter((item) => item.actionRequired).length,
  };
}

function saveCreationDraft(patch) {
  const state = read();
  state.creationDraft = { ...(state.creationDraft || {}), ...patch, savedAt: now() };
  write(state);
  return clone(state.creationDraft);
}
function getCreationDraft() { return read().creationDraft || {}; }

function saveTaskDraft(payload) {
  const state = read();
  const creator = currentUser(state);
  let task = payload.taskId ? state.tasks.find((item) => item.taskId === payload.taskId) : null;
  if (task && task.creatorEmployeeNo !== creator.employeeNo) throw new Error("SCOPE_DENIED");
  if (task && !["draft", "pending_confirm", "pending_confirmation", "returned"].includes(task.status)) throw new Error("STATUS_NOT_ALLOWED");
  const values = {
    taskName: payload.taskName, taskDescription: payload.taskDescription, taskGoal: payload.taskGoal, taskSource: payload.taskSource || "AI任务助手",
    mainAssigneeEmployeeNo: payload.mainAssigneeEmployeeNo, reportToEmployeeNo: payload.reportToEmployeeNo, reviewerEmployeeNo: payload.reviewerEmployeeNo || creator.employeeNo,
    collaboratorEmployeeNos: payload.collaboratorEmployeeNos || [], departmentId: payload.departmentId || creator.departmentId,
    startTime: payload.startTime || now(), deadline: payload.deadline, taskWeight: Number(payload.taskWeight || 3), deliverable: payload.deliverable || "",
    acceptanceCriteria: payload.acceptanceCriteria || "", isUrgent: Boolean(payload.isUrgent), reportCycle: payload.reportCycle || "每周",
    performanceMetricId: payload.performanceMetricId || null, performanceMetric: payload.performanceMetric || "不关联绩效", effectiveAt: null, decompositionStatus: null, progressPercent: 0, hasIssue: false,
  };
  if (!task) {
    task = { taskId: id("T"), taskNo: null, creatorEmployeeNo: creator.employeeNo, status: "draft", taskVersion: 1, priorityQuadrant: Number(values.taskWeight) >= 4 ? "important_not_urgent" : "routine", createdAt: now(), updatedAt: now(), ...values };
    state.tasks.unshift(task);
    log(state, task, "保存任务草稿", "");
  } else {
    Object.assign(task, values);
    if (["pending_confirm", "pending_confirmation"].includes(task.status)) task.status = "draft";
    task.taskVersion += 1; task.updatedAt = now(); log(state, task, "更新任务草稿", task.status);
  }
  state.creationDraft = { ...payload, ...values, taskId: task.taskId, taskVersion: task.taskVersion, backendStatus: task.status, savedAt: now() };
  write(state); return clone(state.creationDraft);
}

function listPerformanceMetrics() { return read().performanceMetrics || []; }
function suggestPerformanceMatches(taskId, _version) {
  const state = read(); const task = state.tasks.find((item) => item.taskId === taskId);
  if (!task) throw new Error("TASK_NOT_FOUND");
  return (state.performanceMetrics || []).map((metric, index) => ({ performanceMatchId: `${taskId}-${metric.metricId}`, taskId, metricId: metric.metricId, metricName: metric.metricName, metricType: metric.metricType, period: metric.period, businessUnit: metric.businessUnit, totalScore: String(Math.max(55, 92-index*13)), matchLevel: index===0 ? "strong" : "weak", matchReason: metric.matchReason, isConfirmed: task.performanceMetricId === metric.metricId }));
}
function confirmPerformanceMatch(taskId, performanceMatchId, _version) {
  const state=read(); const task=state.tasks.find((item)=>item.taskId===taskId);
  if (!task || task.creatorEmployeeNo !== state.currentEmployeeNo) throw new Error("SCOPE_DENIED");
  const metricId=String(performanceMatchId).split("-").pop(); const metric=(state.performanceMetrics||[]).find((item)=>item.metricId===metricId);
  if (!metric) throw new Error("MATCH_NOT_FOUND"); task.performanceMetricId=metric.metricId; task.performanceMetric=metric.metricName; write(state); return { performanceMatchId, taskId, metricId, metricName: metric.metricName, isConfirmed: true };
}

function clearPerformanceMatch(taskId, _version) {
  const state=read(); const task=state.tasks.find((item)=>item.taskId===taskId);
  if (!task || task.creatorEmployeeNo !== state.currentEmployeeNo) throw new Error("SCOPE_DENIED");
  task.performanceMetricId=null; task.performanceMetric="不关联绩效"; write(state); return [];
}

function sendTask(payload) {
  const saved = saveTaskDraft(payload); const state = read(); const task = state.tasks.find((item) => item.taskId === saved.taskId);
  const required=[task.taskName,task.taskDescription,task.taskGoal,task.taskSource,task.mainAssigneeEmployeeNo,task.reportToEmployeeNo,task.reviewerEmployeeNo,task.startTime,task.deadline,task.taskWeight];
  if (required.some((value)=>value===null||value===undefined||value==="")) throw new Error("REQUIRED_FIELD_MISSING");
  if (new Date(task.deadline).getTime() < new Date(task.startTime).getTime()) throw new Error("DATE_RANGE_INVALID");
  if (state.nodes.some((node)=>node.taskId===task.taskId)) throw new Error("CREATOR_NODES_NOT_ALLOWED");
  const before=task.status; task.status="pending_accept"; task.taskVersion += 2; task.taskNo=task.taskNo || `WX-${String(Date.now()).slice(-9)}`; task.confirmedAt=now(); task.sentAt=task.confirmedAt; task.acceptedAt=null; task.updatedAt=task.confirmedAt;
  log(state, task, "确认发送", before); notify(state, task, task.mainAssigneeEmployeeNo, "新任务待接受", `“${task.taskName}”等待你接受。`); state.creationDraft=null; write(state); return enrichTask(state, task);
}

function acceptTask(taskId) {
  return mutateTask(taskId, (state, task) => {
    if (task.status !== "pending_accept" || task.mainAssigneeEmployeeNo !== state.currentEmployeeNo) throw new Error("STATUS_OR_PERMISSION_DENIED");
    const before = task.status;
    task.status = "decomposing";
    task.decompositionStatus = "processing";
    task.latestDecompositionId = id("DC");
    log(state, task, "接受任务并启动AI拆解", before);
  });
}

function completeDecomposition(taskId) {
  return mutateTask(taskId, (state, task) => {
    if (task.status !== "decomposing") return;
    const before = task.status;
    const deadline = task.deadline;
    [
      ["明确范围与验收口径", "梳理目标、边界与验收标准", []],
      ["收集并核对关键信息", "汇总数据、人员与依赖信息", [1]],
      ["完成核心产出", "按任务目标形成可检查成果", [2]],
      ["内部复核成果", "核对成果完整性并修正遗漏", [3]],
      ["整理交付并提交验收", "按验收口径整理文字交付说明并提交", [4]],
    ].forEach((item, index) => {
      const nodeId = id(`N${index + 1}`);
      const collaborator = (task.collaboratorEmployeeNos || [])[0];
      const ownerEmployeeNo = collaborator && index === 2 ? collaborator : task.mainAssigneeEmployeeNo;
      const assignmentStatus = ownerEmployeeNo === task.mainAssigneeEmployeeNo ? "accepted" : "pending";
      state.nodes.push({ nodeId, taskId, nodeOrder: index + 1, nodeName: item[0], ownerEmployeeNo, assignmentStatus, assignmentRespondedAt: null, assignmentRejectReason: "", status: "pending", progressPercent: 0, actionDetail: item[1], plannedDeadline: deadline, dependencyNodeIds: item[2].map((order) => state.nodes.filter((node) => node.taskId === taskId && node.nodeOrder === order)[0]?.nodeId).filter(Boolean), sourceType: "ai", decompositionId: task.latestDecompositionId });
      if (assignmentStatus === "pending") notify(state, task, ownerEmployeeNo, "节点待承接", `“${item[0]}”需要你确认是否承接。`, "task", { nodeId, targetType: "node_assignment", actionRequired: true });
    });
    task.status = "in_progress";
    task.decompositionStatus = "succeeded";
    task.effectiveAt = now();
    log(state, task, "AI拆解成功，任务生效", before);
  });
}

function retryDecomposition(taskId) {
  return mutateTask(taskId, (state, task) => {
    if (task.status !== "decomposition_failed" || task.mainAssigneeEmployeeNo !== state.currentEmployeeNo) throw new Error("STATUS_OR_PERMISSION_DENIED");
    const before = task.status;
    task.status = "decomposing";
    task.decompositionStatus = "processing";
    task.latestDecompositionId = id("DC");
    log(state, task, "重新发起AI拆解", before);
  });
}

function returnTask(taskId, reason) {
  return mutateTask(taskId, (state, task) => {
    if (!reason) throw new Error("REASON_REQUIRED");
    if (task.status !== "pending_accept" || task.mainAssigneeEmployeeNo !== state.currentEmployeeNo) throw new Error("STATUS_OR_PERMISSION_DENIED");
    const before = task.status;
    task.status = "returned";
    task.returnReason = reason;
    log(state, task, "退回任务", before, reason);
    notify(state, task, task.creatorEmployeeNo, "任务已退回", `承办人退回任务：${reason}`);
  });
}

function acceptNodeAssignment(taskId, nodeId) {
  return mutateTask(taskId, (state, task) => {
    const node = state.nodes.find((item) => item.nodeId === nodeId && item.taskId === taskId);
    if (!node || node.ownerEmployeeNo !== state.currentEmployeeNo) throw new Error("SCOPE_DENIED");
    if (state.currentEmployeeNo === task.mainAssigneeEmployeeNo || node.assignmentStatus !== "pending") throw new Error("STATUS_NOT_ALLOWED");
    node.assignmentStatus = "accepted"; node.assignmentRespondedAt = now(); node.assignmentRejectReason = "";
    log(state, task, `接受协办节点：${node.nodeName}`, task.status);
    state.notifications.forEach((item) => { if (item.nodeId === nodeId && item.recipientEmployeeNo === state.currentEmployeeNo) item.actionRequired = false; });
  });
}

function rejectNodeAssignment(taskId, nodeId, reason) {
  const cleanReason = String(reason || "").trim();
  if (!cleanReason) throw new Error("REASON_REQUIRED");
  return mutateTask(taskId, (state, task) => {
    const node = state.nodes.find((item) => item.nodeId === nodeId && item.taskId === taskId);
    if (!node || node.ownerEmployeeNo !== state.currentEmployeeNo) throw new Error("SCOPE_DENIED");
    if (state.currentEmployeeNo === task.mainAssigneeEmployeeNo || node.assignmentStatus !== "pending") throw new Error("STATUS_NOT_ALLOWED");
    node.assignmentStatus = "rejected"; node.assignmentRespondedAt = now(); node.assignmentRejectReason = cleanReason;
    log(state, task, `拒绝协办节点：${node.nodeName}`, task.status, cleanReason);
    state.notifications.forEach((item) => { if (item.nodeId === nodeId && item.recipientEmployeeNo === state.currentEmployeeNo) item.actionRequired = false; });
    notify(state, task, task.mainAssigneeEmployeeNo, "协办节点无法承接", `“${node.nodeName}”的负责人无法承接：${cleanReason}`, "task", { nodeId, targetType: "task_detail", actionRequired: true });
  });
}

function startNode(taskId, nodeId) {
  return mutateTask(taskId, (state, task) => {
    if (!["in_progress", "blocked", "pending_report"].includes(task.status)) throw new Error("STATUS_NOT_ALLOWED");
    const node = state.nodes.find((item) => item.nodeId === nodeId && item.taskId === taskId);
    if (!node || node.ownerEmployeeNo !== state.currentEmployeeNo) throw new Error("SCOPE_DENIED");
    if (state.currentEmployeeNo !== task.mainAssigneeEmployeeNo && (node.assignmentStatus || "accepted") !== "accepted") throw new Error("ASSIGNMENT_NOT_ACCEPTED");
    if (node.status !== "pending") throw new Error("STATUS_NOT_ALLOWED");
    const unmet = (node.dependencyNodeIds || []).some((dependencyId) => state.nodes.find((item) => item.nodeId === dependencyId)?.status !== "completed");
    if (unmet) throw new Error("DEPENDENCY_INCOMPLETE");
    node.status = "in_progress";
    log(state, task, `开始节点：${node.nodeName}`, task.status);
  });
}

function completeNode(taskId, nodeId) {
  return mutateTask(taskId, (state, task) => {
    if (!["in_progress", "blocked", "pending_report"].includes(task.status)) throw new Error("STATUS_NOT_ALLOWED");
    const node = state.nodes.find((item) => item.nodeId === nodeId && item.taskId === taskId);
    if (!node || node.ownerEmployeeNo !== state.currentEmployeeNo) throw new Error("SCOPE_DENIED");
    if (state.currentEmployeeNo !== task.mainAssigneeEmployeeNo && (node.assignmentStatus || "accepted") !== "accepted") throw new Error("ASSIGNMENT_NOT_ACCEPTED");
    if (node.status !== "in_progress") throw new Error("STATUS_NOT_ALLOWED");
    const unmet = (node.dependencyNodeIds || []).some((dependencyId) => state.nodes.find((item) => item.nodeId === dependencyId)?.status !== "completed");
    if (unmet) throw new Error("DEPENDENCY_INCOMPLETE");
    node.status = "completed";
    node.progressPercent = 100;
    node.completedAt = now();
    const nodes = state.nodes.filter((item) => item.taskId === taskId);
    task.progressPercent = Math.round(nodes.reduce((sum, item) => sum + item.progressPercent, 0) / nodes.length);
    log(state, task, `完成节点：${node.nodeName}`, task.status);
  });
}

function submitReport(taskId, payload) {
  return mutateTask(taskId, (state, task) => {
    if (!["in_progress", "blocked", "pending_report"].includes(task.status) || task.mainAssigneeEmployeeNo !== state.currentEmployeeNo) throw new Error("STATUS_OR_PERMISSION_DENIED");
    if (payload.hasIssue && !payload.issueNote) throw new Error("REASON_REQUIRED");
    const before = task.status;
    state.reports.unshift({ reportId: id("R"), taskId, reporterEmployeeNo: state.currentEmployeeNo, progressPercent: Number(payload.progressPercent), stageResult: payload.stageResult || "", hasIssue: !!payload.hasIssue, issueNote: payload.issueNote || "", remark: payload.remark || "", reportTime: now() });
    task.progressPercent = Number(payload.progressPercent);
    task.hasIssue = !!payload.hasIssue;
    task.status = payload.hasIssue ? "blocked" : "in_progress";
    if (payload.hasIssue) state.issues.unshift({ issueId: id("I"), taskId, title: "进度汇报卡点", description: payload.issueNote, issueType: "blocker", status: "open", ownerEmployeeNo: task.creatorEmployeeNo, createdAt: now() });
    log(state, task, payload.hasIssue ? "提交进度并上报卡点" : "提交进度汇报", before, payload.issueNote || "");
    notify(state, task, [task.creatorEmployeeNo, task.reportToEmployeeNo].filter((no) => no !== state.currentEmployeeNo), "任务进度已更新", `“${task.taskName}”当前进度 ${payload.progressPercent}%。`, "reminder");
  });
}

function submitCompletion(taskId, payload) {
  return mutateTask(taskId, (state, task) => {
    const nodes = state.nodes.filter((node) => node.taskId === taskId);
    const openIssues = state.issues.some((issue) => issue.taskId === taskId && ["open", "processing"].includes(issue.status));
    if (!nodes.length || !nodes.every((node) => node.status === "completed") || openIssues) throw new Error("COMPLETION_PRECONDITION_FAILED");
    if (task.mainAssigneeEmployeeNo !== state.currentEmployeeNo) throw new Error("SCOPE_DENIED");
    const before = task.status;
    task.status = "pending_review";
    task.progressPercent = 100;
    const roundNo = state.reviews.filter((item) => item.taskId === taskId).length + 1;
    state.reviews.push({ reviewId: id("RV"), taskId, roundNo, reviewStatus: "submitted", submitterEmployeeNo: state.currentEmployeeNo, reviewerEmployeeNo: task.reviewerEmployeeNo, completionNote: payload.completionNote || "任务已按要求完成", deliverableSummary: payload.deliverableSummary || "文字成果说明", submittedAt: now() });
    log(state, task, "提交完成申请", before);
    notify(state, task, [task.creatorEmployeeNo, task.reviewerEmployeeNo], "任务待验收", `“${task.taskName}”已提交第 ${roundNo} 轮验收。`);
  });
}

function reviewTask(taskId, approved, reason) {
  return mutateTask(taskId, (state, task) => {
    const review = state.reviews.filter((item) => item.taskId === taskId).sort((a, b) => b.roundNo - a.roundNo)[0];
    if (!review || review.reviewStatus !== "submitted" || task.status !== "pending_review" || review.reviewerEmployeeNo !== state.currentEmployeeNo) throw new Error("STATUS_OR_PERMISSION_DENIED");
    if (!approved && !reason) throw new Error("REASON_REQUIRED");
    const before = task.status;
    review.reviewStatus = approved ? "approved" : "rejected";
    review.reviewedAt = now();
    review.rejectReason = approved ? "" : reason;
    if (approved) {
      task.status = "archived";
      task.completedAt = now();
      task.archivedAt = task.completedAt;
      task.actualHours = Math.max(0, Math.round((new Date(task.completedAt) - new Date(task.startTime)) / 3600000));
      log(state, task, "验收通过并自动归档", before);
      notify(state, task, task.mainAssigneeEmployeeNo, "任务验收通过", `“${task.taskName}”已自动归档。`);
    } else {
      task.status = "in_progress";
      log(state, task, "验收退回修改", before, reason);
      notify(state, task, task.mainAssigneeEmployeeNo, "验收未通过", `请继续处理：${reason}`);
    }
  });
}

function lifecycle(taskId, action, reason, employeeNo) {
  return mutateTask(taskId, (state, task) => {
    if (task.creatorEmployeeNo !== state.currentEmployeeNo) throw new Error("SCOPE_DENIED");
    if (["cancel", "withdraw", "reassign"].includes(action) && !reason) throw new Error("REASON_REQUIRED");
    const before = task.status;
    const oldAssignee = task.mainAssigneeEmployeeNo;
    if (action === "cancel") { task.status = "cancelled"; task.cancelReason = reason; }
    if (action === "withdraw") { task.status = "withdrawn"; task.withdrawReason = reason; }
    if (action === "reassign") {
      if (!userByNo(state, employeeNo) || employeeNo === oldAssignee) throw new Error("ASSIGNEE_INVALID");
      task.mainAssigneeEmployeeNo = employeeNo; task.status = "pending_accept"; task.decompositionStatus = null; task.latestDecompositionId = null; task.effectiveAt = null; task.acceptedAt = null;
    }
    log(state, task, action === "cancel" ? "取消任务" : action === "withdraw" ? "撤回任务" : "更换承办人", before, reason || "");
    if (action === "reassign") {
      notify(state, task, oldAssignee, "任务承办人已变更", reason);
      notify(state, task, task.mainAssigneeEmployeeNo, "新任务待接受", "任务已重新发送给你，请接受后启动AI拆解。");
    } else {
      notify(state, task, task.mainAssigneeEmployeeNo, `任务已${action === "cancel" ? "取消" : "撤回"}`, reason);
    }
  });
}

function submitChangeRequest(taskId, patch, reason) {
  const state = read();
  const task = state.tasks.find((item) => item.taskId === taskId);
  if (!task) throw new Error("TASK_NOT_FOUND");
  if (task.mainAssigneeEmployeeNo !== state.currentEmployeeNo) throw new Error("SCOPE_DENIED");
  if (!["in_progress", "blocked", "pending_report"].includes(task.status)) throw new Error("STATUS_CHANGED");
  if (!reason || !patch || !Object.keys(patch).length) throw new Error("CHANGE_EMPTY");
  state.changeRequests = state.changeRequests || [];
  if (state.changeRequests.some((item) => item.taskId === taskId && item.status === "pending")) throw new Error("CHANGE_PENDING");
  const change = { changeRequestId: id("CR"), taskId, requesterEmployeeNo: state.currentEmployeeNo, patchJson: patch, reason, beforeSnapshot: clone(task), afterSnapshot: { ...clone(task), ...patch }, status: "pending", requesterTaskVersion: task.taskVersion, baseTaskVersion: task.taskVersion, createdAt: now() };
  state.changeRequests.push(change);
  log(state, task, "发起变更申请", task.status, reason);
  notify(state, task, task.creatorEmployeeNo, "任务变更待处理", reason);
  write(state);
  return { taskId, status: task.status, taskVersion: task.taskVersion, changeRequest: clone(change) };
}

function decideChangeRequest(taskId, changeRequestId, approved, reason) {
  const state = read();
  const task = state.tasks.find((item) => item.taskId === taskId);
  const change = (state.changeRequests || []).find((item) => item.changeRequestId === changeRequestId && item.taskId === taskId);
  if (!task || !change) throw new Error("CHANGE_NOT_FOUND");
  if (task.creatorEmployeeNo !== state.currentEmployeeNo) throw new Error("SCOPE_DENIED");
  if (change.status !== "pending" || change.baseTaskVersion !== task.taskVersion) throw new Error("VERSION_CONFLICT");
  if (!approved && !reason) throw new Error("REASON_REQUIRED");
  change.status = approved ? "approved" : "rejected";
  change.decisionByEmployeeNo = state.currentEmployeeNo;
  change.decisionComment = reason || "";
  change.decisionAt = now();
  if (approved) {
    Object.assign(task, change.patchJson);
    task.taskVersion += 1;
    task.updatedAt = now();
  }
  log(state, task, approved ? "同意变更申请" : "拒绝变更申请", task.status, reason || "");
  notify(state, task, change.requesterEmployeeNo, approved ? "任务变更已同意" : "任务变更未通过", reason || "创建人已确认变更。");
  write(state);
  return { taskId, status: task.status, taskVersion: task.taskVersion, changeRequest: clone(change) };
}

function cancelChangeRequest(taskId, changeRequestId, reason) {
  const state = read();
  const task = state.tasks.find((item) => item.taskId === taskId);
  const change = (state.changeRequests || []).find((item) => item.changeRequestId === changeRequestId && item.taskId === taskId);
  if (!task || !change) throw new Error("CHANGE_NOT_FOUND");
  if (change.requesterEmployeeNo !== state.currentEmployeeNo) throw new Error("SCOPE_DENIED");
  if (change.status !== "pending" || !reason) throw new Error("STATUS_CHANGED");
  change.status = "cancelled"; change.cancellationReason = reason; change.cancelledAt = now();
  write(state);
  return { taskId, status: task.status, taskVersion: task.taskVersion, changeRequest: clone(change) };
}

function notificationProjection(state, item) {
  const task = item.taskId ? state.tasks.find((row) => row.taskId === item.taskId) : null;
  const node = item.nodeId ? state.nodes.find((row) => row.nodeId === item.nodeId && row.taskId === item.taskId) : null;
  const actor = currentUser(state);
  const canOpen = !task || Boolean(actor && canViewTask(state, actor, task));
  let targetType = item.targetType || null;
  let actionRequired = Boolean(item.actionRequired);
  if (task && canOpen) {
    if (node && node.ownerEmployeeNo === state.currentEmployeeNo && node.assignmentStatus === "pending") { targetType = "node_assignment"; actionRequired = true; }
    else if (task.status === "pending_accept" && task.mainAssigneeEmployeeNo === state.currentEmployeeNo) { targetType = "task_acceptance"; actionRequired = true; }
    else if (task.status === "decomposition_failed" && task.mainAssigneeEmployeeNo === state.currentEmployeeNo) { targetType = "decomposition"; actionRequired = true; }
    else if (task.status === "pending_review" && [task.creatorEmployeeNo, task.reviewerEmployeeNo].includes(state.currentEmployeeNo)) { targetType = "review"; actionRequired = true; }
    else if (task.status === "pending_report" && task.mainAssigneeEmployeeNo === state.currentEmployeeNo) { targetType = "report"; actionRequired = true; }
    else if (targetType === "node_assignment" || targetType === "task_acceptance" || targetType === "review" || targetType === "report") { targetType = "task_detail"; actionRequired = false; }
  }
  return { ...item, targetType, actionRequired, canOpen, unavailableReason: canOpen ? "" : "当前已无权查看该任务" };
}
function listNotifications(type) {
  const state = read();
  return state.notifications
    .filter((item) => item.recipientEmployeeNo === state.currentEmployeeNo)
    .map((item) => notificationProjection(state, item))
    .filter((item) => !type || type === "all" || item.type === type)
    .sort((a, b) => b.sentAt.localeCompare(a.sentAt));
}
function readNotification(notificationId) {
  const state = read();
  const item = state.notifications.find((notification) => notification.notificationId === notificationId && notification.recipientEmployeeNo === state.currentEmployeeNo);
  if (item) item.unread = false;
  write(state);
  return item;
}
function markAllRead() { const state = read(); state.notifications.forEach((item) => { if (item.recipientEmployeeNo === state.currentEmployeeNo) item.unread = false; }); write(state); }
function switchUser(employeeNo) { const state = read(); if (!userByNo(state, employeeNo)) throw new Error("USER_NOT_FOUND"); state.currentEmployeeNo = employeeNo; write(state); return currentUser(state); }

function executiveOverview(filters) {
  const state = read();
  const actor = currentUser(state);
  if (!actor?.permissions?.canAccessExecutive) throw new Error("PERMISSION_DENIED");
  const scopes = activeScopes(state, actor.employeeNo).filter((scope) => scope.scopeType === "department" && ["view", "manage", "export"].includes(scope.permissionType));
  const authorizedDepartmentIds = [...new Set(scopes.map((scope) => scope.scopeId))];
  if (!authorizedDepartmentIds.length) throw new Error("SCOPE_DENIED");
  const requestedDepartmentId = filters?.departmentId || "";
  if (requestedDepartmentId && !authorizedDepartmentIds.includes(requestedDepartmentId)) throw new Error("SCOPE_DENIED");
  const selectedDepartmentIds = new Set(requestedDepartmentId ? [requestedDepartmentId] : authorizedDepartmentIds);
  const teamTasks = state.tasks.filter((task) => selectedDepartmentIds.has(task.departmentId));
  const execution = teamTasks.filter((task) => ["in_progress", "blocked", "pending_report"].includes(task.status) && task.effectiveAt);
  const progressTasks = teamTasks.filter((task) => ["in_progress", "blocked", "pending_report", "pending_review"].includes(task.status) && task.effectiveAt);
  const linkedTasks = progressTasks.filter((task) => Boolean(task.performanceMetric));
  const linkedMetrics = new Set(linkedTasks.map((task) => task.performanceMetric));
  const weightTotal = progressTasks.reduce((sum, task) => sum + Number(task.taskWeight || 0), 0);
  const weightedProgress = progressTasks.reduce((sum, task) => sum + Number(task.progressPercent || 0) * Number(task.taskWeight || 0), 0);
  const quadrants = { important_urgent: 0, important_not_urgent: 0, not_important_urgent: 0, not_important_not_urgent: 0, unscored_count: 0 };
  execution.forEach((task) => {
    const code = task.priorityQuadrant === "urgent_not_important" ? "not_important_urgent" : task.priorityQuadrant === "routine" ? "not_important_not_urgent" : task.priorityQuadrant;
    if (Object.prototype.hasOwnProperty.call(quadrants, code)) quadrants[code] += 1;
    else quadrants.unscored_count += 1;
  });
  const period = filters?.period === "month" ? "month" : "week";
  const base = new Date("2026-09-01T00:00:00+08:00");
  const dayCount = period === "month" ? 22 : 5;
  const days = [];
  for (let index = 0; days.length < dayCount && index < 40; index += 1) {
    const day = new Date(base); day.setDate(base.getDate() + index);
    if (day.getDay() === 0 || day.getDay() === 6) continue;
    days.push({ date: day.toISOString().slice(0, 10), label: `周${"日一二三四五六"[day.getDay()]}` });
  }
  const members = state.users.filter((user) => selectedDepartmentIds.has(user.departmentId) && user.roleType !== "admin").map((user, userIndex) => ({
    employeeNo: user.employeeNo,
    name: user.name,
    departmentId: user.departmentId,
    cells: days.map((day, dayIndex) => {
      const score = Math.max(0, Math.min(100, Number(user.workloadScore || 0) + ((dayIndex + userIndex) % 3) * 4 - 4));
      const level = score <= 40 ? "idle" : score <= 70 ? "normal" : score <= 90 ? "busy" : "overloaded";
      return {
        date: day.date, snapshotId: `MOCK-${user.employeeNo}-${day.date}`, workloadScore: score, workloadLevel: level,
        activeTaskCount: execution.filter((task) => task.mainAssigneeEmployeeNo === user.employeeNo).length,
        urgentTaskCount: execution.filter((task) => task.mainAssigneeEmployeeNo === user.employeeNo && task.isUrgent).length,
        blockedTaskCount: execution.filter((task) => task.mainAssigneeEmployeeNo === user.employeeNo && task.status === "blocked").length,
        overdueTaskCount: 0,
        hoursPressure: score, weightPressure: Math.max(0, score - 8), countPressure: Math.max(0, score - 4), urgentPressure: 0, blockedOverduePressure: execution.some((task) => task.mainAssigneeEmployeeNo === user.employeeNo && task.status === "blocked") ? 70 : 0,
      };
    }),
  }));
  return {
    scope: {
      selectedDepartmentId: requestedDepartmentId || null,
      departments: authorizedDepartmentIds.map((departmentId) => ({ departmentId, departmentName: state.users.find((user) => user.departmentId === departmentId)?.departmentName || departmentId, departmentType: "department", parentDepartmentId: null })),
    },
    period: { type: period },
    metrics: {
      activeTasks: { count: execution.length, previousCount: execution.length, changeRate: 0, changeDirection: "flat" },
      onTimeRate: { completedCount: 0, onTimeCount: 0, rate: null, previousRate: null, changePercentagePoints: null },
      kpiLinks: { linkedTaskCount: new Set(linkedTasks.map((task) => task.taskId)).size, linkedMetricCount: linkedMetrics.size },
      overallProgress: { rate: weightTotal ? Math.round((weightedProgress / weightTotal) * 100) / 100 : null, taskCount: progressTasks.length, dataQualityIssueCount: 0 },
    },
    quadrants,
    workloadHeatmap: { days, members },
    members,
  };
}

module.exports = { ensureInitialized, read, reset, currentUser, listTasks, listOverview, getTask, getDashboard, getCreationDraft, saveCreationDraft, saveTaskDraft, listPerformanceMetrics, suggestPerformanceMatches, confirmPerformanceMatch, clearPerformanceMatch, sendTask, acceptTask, completeDecomposition, retryDecomposition, returnTask, acceptNodeAssignment, rejectNodeAssignment, startNode, completeNode, submitReport, submitCompletion, reviewTask, lifecycle, submitChangeRequest, decideChangeRequest, cancelChangeRequest, listNotifications, readNotification, markAllRead, switchUser, executiveOverview };

/**
 * Feature: Task detail read model.
 * Responsibilities: normalize task-detail read APIs into the second-version page view model.
 * Does not own: authorization, workflow writes, persisted calculations, or task state transitions.
 * Plan task: FEATURE-03.
 */

const { statusView, QUADRANTS } = require("./constants");
const { dateLabel, remainingLabel } = require("./format");

const LEGACY_STATUS = {
  pending_acceptance: "pending_accept",
  pending_confirmation: "pending_confirm",
};

const TERMINAL = ["archived", "completed", "cancelled", "withdrawn", "merged", "closed"];
const ACTIVE_ISSUE = ["open", "processing"];
const NODE_STATUS = { pending: "待开始", in_progress: "进行中", blocked: "受阻", completed: "已完成", cancelled: "已取消" };
const ACTION_LABEL = {
  submit_confirm: "提交确认",
  submitted_for_confirmation: "提交确认",
  send: "确认发送",
  confirm_and_send: "确认发送",
  accept: "接受任务",
  reject: "退回任务",
  return: "退回任务",
  complete: "提交完成",
  approve: "验收通过",
  reject_review: "验收退回",
  archive: "自动归档",
  cancel: "取消任务",
  withdraw: "撤回任务",
};

function canonicalStatus(status) { return LEGACY_STATUS[status] || status || ""; }
function asArray(value) { return Array.isArray(value) ? value : []; }
function number(value, fallback = 0) {
  const result = Number(value);
  return Number.isFinite(result) ? result : fallback;
}
function safeText(value, fallback = "无") {
  if (value === null || value === undefined || value === "") return fallback;
  return String(value);
}
function formatHours(value) {
  if (value === null || value === undefined || value === "") return "无";
  return `${number(value)} 小时`;
}
function personInitial(name, fallback = "人") { return safeText(name, fallback).slice(0, 1); }

function peopleMap(detail) {
  const result = {};
  asArray(detail.people).forEach((person) => { result[person.employeeNo] = person.name; });
  const fallbacks = [
    [detail.creatorEmployeeNo, detail.creatorName],
    [detail.mainAssigneeEmployeeNo, detail.assigneeName],
    [detail.reviewerEmployeeNo, detail.reviewerName],
    [detail.reportToEmployeeNo, detail.reportToName],
  ];
  fallbacks.forEach(([employeeNo, name]) => { if (employeeNo && name) result[employeeNo] = name; });
  return result;
}

function participantRole(participant) {
  return participant.participantRole || participant.role || "";
}

function taskPeople(detail, names) {
  const collaborators = asArray(detail.collaboratorNames).length
    ? detail.collaboratorNames
    : asArray(detail.participants)
      .filter((item) => ["collaborator", "collaborator_task", "assistant"].includes(participantRole(item)))
      .map((item) => names[item.employeeNo] || item.employeeNo)
      .filter(Boolean);
  const named = (employeeNo, fallback) => names[employeeNo] || fallback || employeeNo || "未设置";
  return {
    creatorName: named(detail.creatorEmployeeNo, detail.creatorName),
    assigneeName: named(detail.mainAssigneeEmployeeNo, detail.assigneeName),
    reviewerName: named(detail.reviewerEmployeeNo, detail.reviewerName),
    reportToName: named(detail.reportToEmployeeNo, detail.reportToName),
    collaboratorNames: collaborators,
  };
}

function taskProgress(detail, reports) {
  const nodes = asArray(detail.nodes);
  if (nodes.length) {
    const total = nodes.reduce((sum, node) => sum + number(node.progressPercent), 0);
    return Math.round(total / nodes.length);
  }
  if (reports.length) return number(reports[0].progressPercent);
  if (["completed", "archived"].includes(canonicalStatus(detail.status))) return 100;
  return number(detail.progressPercent);
}

function nodeView(detail, names, issues) {
  const dependencies = asArray(detail.dependencies);
  const nodeParticipants = asArray(detail.nodeParticipants);
  return asArray(detail.nodes)
    .slice()
    .sort((left, right) => (number(left.nodeOrder) - number(right.nodeOrder)) || (number(left.sortWeight) - number(right.sortWeight)))
    .map((node, index) => {
      const nodeIssues = issues.filter((issue) => issue.nodeId === node.nodeId && ACTIVE_ISSUE.includes(issue.status));
      const collaborators = nodeParticipants
        .filter((item) => item.nodeId === node.nodeId && item.employeeNo !== node.ownerEmployeeNo)
        .map((item) => names[item.employeeNo] || item.employeeNo)
        .filter(Boolean);
      const predecessors = dependencies
        .filter((item) => item.successorNodeId === node.nodeId)
        .map((item) => item.predecessorNodeId);
      return {
        ...node,
        nodeNo: String(index + 1).padStart(2, "0"),
        statusLabel: NODE_STATUS[node.status] || safeText(node.status, "未知"),
        ownerName: names[node.ownerEmployeeNo] || node.ownerName || node.ownerEmployeeNo || "未分配",
        collaboratorText: collaborators.length ? collaborators.join("、") : "无",
        plannedStartLabel: dateLabel(node.plannedStartTime),
        plannedDeadlineLabel: dateLabel(node.plannedDeadline),
        completedAtLabel: node.completedAt ? dateLabel(node.completedAt) : "未完成",
        dependencyText: predecessors.length ? predecessors.join("、") : "无",
        issue: nodeIssues[0] || null,
        hasIssue: nodeIssues.length > 0 || Boolean(node.blockedReason),
        assignmentStatus: node.assignmentStatus || "accepted",
        assignmentStatusLabel: ({ pending: "待承接", accepted: "已承接", rejected: "无法承接" })[node.assignmentStatus || "accepted"] || "已承接",
        assignmentRejectReason: node.assignmentRejectReason || "",
        sourceLabel: node.sourceType === "ai" ? "AI生成" : "",
      };
    });
}

function timelineView(status) {
  const current = canonicalStatus(status);
  const steps = [
    { key: "start", label: "未开始" },
    { key: "progress", label: "进行中" },
    { key: "blocked", label: "受阻" },
    { key: "report", label: "待汇报" },
    { key: "review", label: "待验收" },
    { key: "done", label: "已完成" },
  ];
  const currentIndex = ({
    draft: 0, pending_confirm: 0, pending_accept: 0, returned: 0,
    decomposing: 0, decomposition_failed: 0,
    in_progress: 1, blocked: 2, pending_report: 3, pending_review: 4,
    completed: 5, archived: 5,
  })[current];
  return steps.map((step, index) => ({
    ...step,
    done: Number.isInteger(currentIndex) && index < currentIndex,
    current: Number.isInteger(currentIndex) && index === currentIndex,
  }));
}

function normalizeStatusLog(item, names) {
  return {
    logId: item.statusLogId || item.logId,
    kind: "status",
    actionLabel: item.actionLabel || ACTION_LABEL[item.actionType] || safeText(item.actionType, "状态更新"),
    fromStatusLabel: item.fromStatus ? statusView(canonicalStatus(item.fromStatus)).label : "无",
    toStatusLabel: item.toStatus ? statusView(canonicalStatus(item.toStatus)).label : "无",
    reason: safeText(item.reason),
    operatorName: names[item.operatorEmployeeNo] || item.operatorName || item.operatorEmployeeNo || "系统",
    createdAt: item.createdAt,
    createdAtLabel: dateLabel(item.createdAt),
  };
}

function normalizeOperationLog(item, names) {
  return {
    logId: item.operationLogId || item.logId,
    kind: "audit",
    actionLabel: item.actionLabel || safeText(item.action, "操作记录"),
    fromStatusLabel: safeText(item.beforeData && (item.beforeData.status || item.beforeData.taskStatus)),
    toStatusLabel: safeText(item.afterData && (item.afterData.status || item.afterData.taskStatus)),
    reason: safeText(item.errorMessage || (item.afterData && item.afterData.reason)),
    operatorName: names[item.operatorEmployeeNo] || item.operatorName || item.operatorEmployeeNo || "系统",
    resultLabel: item.result === "success" ? "成功" : safeText(item.result),
    createdAt: item.createdAt,
    createdAtLabel: dateLabel(item.createdAt),
  };
}

function buildTaskDetail(bundle) {
  const detail = bundle.task || bundle || {};
  const names = peopleMap(detail);
  const people = taskPeople(detail, names);
  const reports = asArray(bundle.progressReports || detail.reports)
    .slice().sort((a, b) => String(b.reportTime || b.createdAt || "").localeCompare(String(a.reportTime || a.createdAt || "")));
  const issues = asArray(bundle.issues || detail.issues);
  const status = canonicalStatus(detail.status);
  const progressPercent = taskProgress(detail, reports);
  const nodes = nodeView(detail, names, issues);
  const performanceMatches = asArray(detail.performanceMatches || detail.performanceMatch)
    .filter((item) => item && item.isConfirmed !== false);
  const reportIssues = reports[0]
    ? issues.filter((item) => item.sourceProgressReportId === reports[0].progressReportId)
    : [];
  const latestHasIssue = reports[0] ? Boolean(reports[0].hasIssue || reportIssues.length) : false;
  const latestReport = reports[0] ? {
    ...reports[0],
    progressPercent: number(reports[0].progressPercent),
    stageResult: safeText(reports[0].stageResult),
    remark: safeText(reports[0].remark || reports[0].reportContent),
    hasIssue: latestHasIssue,
    hasIssueLabel: latestHasIssue ? "是" : "否",
    issueText: latestHasIssue ? safeText(reports[0].issueNote || reportIssues[0]?.description || reportIssues[0]?.title) : "无",
    reporterName: names[reports[0].reporterEmployeeNo] || reports[0].reporterName || reports[0].reporterEmployeeNo || "系统",
    reportTimeLabel: dateLabel(reports[0].reportTime || reports[0].createdAt),
  } : null;
  const performance = performanceMatches[0] || null;
  const allowedActions = asArray(bundle.allowedActions || detail.allowedActions);
  const statusLogs = asArray(bundle.statusLogs || detail.logs).map((item) => normalizeStatusLog(item, names));
  const operationLogs = asArray(bundle.operationLogs || detail.operationLogs).map((item) => normalizeOperationLog(item, names));
  const task = {
    ...detail,
    ...people,
    status,
    statusLabel: statusView(status).label,
    quadrantLabel: QUADRANTS[detail.priorityQuadrant] || detail.priorityQuadrantLabel || "待计算",
    startLabel: dateLabel(detail.startTime),
    deadlineLabel: dateLabel(detail.deadline),
    remainingLabel: remainingLabel(detail.deadline),
    completedAtLabel: detail.completedAt ? dateLabel(detail.completedAt) : "无",
    actualHoursLabel: formatHours(detail.actualHours),
    progressPercent,
    nodeCount: nodes.length,
    collaboratorText: people.collaboratorNames.length ? people.collaboratorNames.join("、") : "无",
    isOverdue: Boolean(detail.deadline) && new Date(detail.deadline).getTime() < Date.now() && !TERMINAL.includes(status),
    taskWeightLabel: detail.taskWeight === null || detail.taskWeight === undefined ? "无" : `${detail.taskWeight}/5`,
    urgentLabel: detail.isUrgent ? "是" : "否",
    currentUserRelations: asArray(bundle.permissions?.currentUserRelations || detail.currentUserRelations),
  };
  return {
    task,
    nodes,
    timeline: timelineView(status),
    latestReport,
    performance,
    statusLogs,
    operationLogs,
    allowedActions,
    permissions: bundle.permissions || { allowedActions, currentUserRelations: task.currentUserRelations },
    currentUserRelations: task.currentUserRelations,
  };
}

module.exports = {
  buildTaskDetail,
  canonicalStatus,
  normalizeStatusLog,
  normalizeOperationLog,
  timelineView,
};

/**
 * Feature: Test16-equivalent Workbench query projection.
 * Responsibilities: load dashboard metrics, permission-scoped tasks, priority quadrants, and concrete support inbox items.
 * Does not own: task state transitions, AI extraction, priority calculation, or authorization decisions.
 * Plan task: H5-MIGRATION-01.
 */

import { getDashboardSummary, getInbox, listTasks } from "../../api/endpoints";
import type { DashboardSummary, InboxItem, PaginatedTasks, TaskStatus, TaskSummary } from "../../api/types";

export const workbenchStatusTabs = [
  { key: "pending_accept", label: "待接受" },
  { key: "decomposing", label: "AI拆解中" },
  { key: "decomposition_failed", label: "拆解失败" },
  { key: "in_progress", label: "进行中" },
  { key: "blocked", label: "受阻" },
  { key: "pending_report", label: "待汇报" },
  { key: "pending_review", label: "待验收" },
] as const;

export type WorkbenchStatusFilter = (typeof workbenchStatusTabs)[number]["key"];
export type WorkbenchQuadrant = "important_urgent" | "important_not_urgent" | "urgent_not_important" | "routine";

export interface WorkbenchQuadrantSummary {
  id: WorkbenchQuadrant;
  label: string;
  hint: string;
  count: number;
}

export interface WorkbenchSupportItem {
  taskId: string;
  taskName: string;
  supportReason: string;
  supportNodeId: string | null;
}

export interface WorkbenchData {
  summary: DashboardSummary;
  tasks: TaskSummary[];
  quadrants: WorkbenchQuadrantSummary[];
  supportItems: WorkbenchSupportItem[];
}

const statusSet = new Set<string>([
  "draft",
  "pending_confirm",
  "pending_confirmation",
  "pending_accept",
  "pending_acceptance",
  "returned",
  "decomposing",
  "decomposition_failed",
  "in_progress",
  "blocked",
  "pending_report",
  "pending_review",
  "completed",
  "archived",
  "cancelled",
  "withdrawn",
  "merged",
  "closed",
]);

const quadrantMeta: Record<WorkbenchQuadrant, { label: string; hint: string }> = {
  important_urgent: { label: "重要且紧急", hint: "立即处理" },
  important_not_urgent: { label: "重要不紧急", hint: "计划推进" },
  urgent_not_important: { label: "紧急不重要", hint: "协同处理" },
  routine: { label: "常规任务", hint: "稳步完成" },
};

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" ? value as Record<string, unknown> : {};
}

function safeNumber(value: unknown): number {
  const number = typeof value === "number" ? value : typeof value === "string" ? Number(value) : Number.NaN;
  return Number.isFinite(number) && number >= 0 ? number : 0;
}

function safeString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function normalizeTaskStatus(value: unknown): TaskStatus {
  return typeof value === "string" && statusSet.has(value) ? value as TaskStatus : "in_progress";
}

function normalizePerson(value: unknown): { employee_no: string; name: string } {
  const record = asRecord(value);
  return {
    employee_no: safeString(record.employee_no) ?? "",
    name: safeString(record.name) ?? "未命名成员",
  };
}

function normalizePriorityQuadrant(value: unknown): WorkbenchQuadrant | null {
  if (value === "important_urgent" || value === "重要且紧急") return "important_urgent";
  if (value === "important_not_urgent" || value === "重要不紧急") return "important_not_urgent";
  if (value === "urgent_not_important" || value === "not_important_urgent" || value === "紧急不重要") return "urgent_not_important";
  if (value === "routine" || value === "not_important_not_urgent" || value === "常规任务") return "routine";
  return null;
}

function normalizeTask(value: unknown): TaskSummary | null {
  const record = asRecord(value);
  const taskId = safeString(record.task_id);
  const taskName = safeString(record.task_name);
  if (!taskId || !taskName) return null;
  return {
    task_id: taskId,
    task_no: safeString(record.task_no),
    task_name: taskName,
    status: normalizeTaskStatus(record.status),
    deadline: safeString(record.deadline),
    is_urgent: Boolean(record.is_urgent),
    task_weight: typeof record.task_weight === "number" ? record.task_weight : null,
    task_version: safeNumber(record.task_version),
    creator: normalizePerson(record.creator),
    main_assignee: record.main_assignee ? normalizePerson(record.main_assignee) : null,
    current_user_relations: Array.isArray(record.current_user_relations)
      ? record.current_user_relations.filter((item): item is string => typeof item === "string")
      : [],
    allowed_actions: Array.isArray(record.allowed_actions)
      ? record.allowed_actions.filter((item): item is TaskSummary["allowed_actions"][number] => typeof item === "string")
      : [],
    is_overdue: Boolean(record.is_overdue),
    days_until_deadline: typeof record.days_until_deadline === "number" ? record.days_until_deadline : null,
    created_at: safeString(record.created_at) ?? "",
    updated_at: safeString(record.updated_at) ?? "",
    progress_percent: safeNumber(record.progress_percent),
    priority_quadrant: normalizePriorityQuadrant(record.priority_quadrant),
  };
}

function normalizeTasks(payload: PaginatedTasks | unknown): TaskSummary[] {
  const items = asRecord(payload).items;
  if (!Array.isArray(items)) return [];
  return items.map(normalizeTask).filter((task): task is TaskSummary => task !== null);
}

function normalizeSummary(payload: DashboardSummary | unknown): DashboardSummary {
  const record = asRecord(payload);
  const recentTasks = Array.isArray(record.recent_tasks)
    ? record.recent_tasks.map(normalizeTask).filter((task): task is TaskSummary => task !== null)
    : [];
  const priorityItems = Array.isArray(record.priority_items)
    ? record.priority_items.filter((item): item is Record<string, unknown> => Boolean(item && typeof item === "object"))
    : [];
  return {
    created_task_count: safeNumber(record.created_task_count),
    assigned_task_count: safeNumber(record.assigned_task_count),
    inbox_count: safeNumber(record.inbox_count),
    in_progress_count: safeNumber(record.in_progress_count),
    pending_acceptance_count: safeNumber(record.pending_acceptance_count),
    today_task_count: safeNumber(record.today_task_count),
    due_within_3_days_count: safeNumber(record.due_within_3_days_count),
    due_within_7_days_count: safeNumber(record.due_within_7_days_count),
    overdue_count: safeNumber(record.overdue_count),
    report_due_count: safeNumber(record.report_due_count),
    open_issue_count: safeNumber(record.open_issue_count),
    blocked_task_count: safeNumber(record.blocked_task_count),
    completion_review_count: safeNumber(record.completion_review_count),
    unread_notification_count: safeNumber(record.unread_notification_count),
    open_conflict_count: safeNumber(record.open_conflict_count),
    due_window_days: safeNumber(record.due_window_days) || 7,
    on_time_completion_rate: safeNumber(record.on_time_completion_rate),
    on_time_completion_count: safeNumber(record.on_time_completion_count),
    completion_sample_count: safeNumber(record.completion_sample_count),
    completion_rate_period_days: safeNumber(record.completion_rate_period_days) || 90,
    recent_tasks: recentTasks,
    latest_workload: record.latest_workload && typeof record.latest_workload === "object" ? record.latest_workload as Record<string, unknown> : null,
    priority_items: priorityItems,
  };
}

function projectQuadrants(summary: DashboardSummary): WorkbenchQuadrantSummary[] {
  const counts: Record<WorkbenchQuadrant, number> = {
    important_urgent: 0,
    important_not_urgent: 0,
    urgent_not_important: 0,
    routine: 0,
  };
  summary.priority_items.forEach((item) => {
    const quadrant = normalizePriorityQuadrant(item.priority_quadrant ?? item.quadrant ?? item.priorityQuadrant);
    if (quadrant) counts[quadrant] += 1;
  });
  return (Object.keys(quadrantMeta) as WorkbenchQuadrant[]).map((id) => ({
    id,
    ...quadrantMeta[id],
    count: counts[id],
  }));
}

function attachPriorityQuadrants(tasks: TaskSummary[], summary: DashboardSummary): TaskSummary[] {
  const byTask = new Map<string, WorkbenchQuadrant>();
  summary.priority_items.forEach((item) => {
    const record = asRecord(item);
    const taskId = safeString(record.task_id ?? record.taskId);
    const quadrant = normalizePriorityQuadrant(record.priority_quadrant ?? record.quadrant ?? record.priorityQuadrant);
    if (taskId && quadrant) byTask.set(taskId, quadrant);
  });
  return tasks.map((task) => ({ ...task, priority_quadrant: byTask.get(task.task_id) ?? task.priority_quadrant ?? "routine" }));
}

function normalizeSupportItems(items: InboxItem[]): WorkbenchSupportItem[] {
  return items.map((item) => ({
    taskId: item.task.task_id,
    taskName: item.task.task_name,
    supportReason: item.reason || "有卡点或协作事项等待你的响应",
    supportNodeId: item.node?.node_id ?? null,
  }));
}

export async function loadWorkbenchData(): Promise<WorkbenchData> {
  const [summaryPayload, taskPagePayload, supportPayload] = await Promise.all([
    getDashboardSummary(),
    listTasks({ limit: 100, offset: 0 }),
    getInbox({ action_code: "handle_issue", limit: 20, offset: 0 }),
  ]);
  const summary = normalizeSummary(summaryPayload);
  return {
    summary,
    tasks: attachPriorityQuadrants(normalizeTasks(taskPagePayload), summary),
    quadrants: projectQuadrants(summary),
    supportItems: normalizeSupportItems(supportPayload.items),
  };
}

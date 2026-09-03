/**
 * Feature 02 core: Task/node overview filter definitions and display projection.
 * Keeps page code focused on interaction while API/store own data access.
 */

const DEFAULT_FILTERS = {
  mode: "tasks",
  status: "",
  quadrant: "",
  support: "",
  nearDue: false,
  datePreset: "all",
  startDate: "",
  endDate: "",
  search: "",
  page: 1,
  pageSize: 20,
  sortBy: "deadline",
  sortOrder: "asc",
};

const STATUS_OPTIONS = [
  { value: "", label: "全部" },
  { value: "pending_acceptance", label: "待接受" },
  { value: "decomposing", label: "AI拆解中" },
  { value: "decomposition_failed", label: "拆解失败" },
  { value: "in_progress", label: "进行中" },
  { value: "blocked", label: "受阻" },
  { value: "pending_report", label: "待汇报" },
  { value: "pending_review", label: "待验收" },
  { value: "completed", label: "已完成" },
  { value: "archived", label: "已归档" },
  { value: "cancelled", label: "已取消" },
  { value: "withdrawn", label: "已撤回" },
  { value: "merged", label: "已合并" },
  { value: "closed", label: "已关闭" },
];

const QUICK_STATUSES = STATUS_OPTIONS.filter((item) => [
  "pending_acceptance", "in_progress", "blocked", "pending_report", "pending_review",
].includes(item.value));

const QUADRANT_OPTIONS = [
  { value: "", label: "全部" },
  { value: "important_urgent", label: "重要且紧急" },
  { value: "important_not_urgent", label: "重要不紧急" },
  { value: "urgent_not_important", label: "紧急不重要" },
  { value: "routine", label: "常规任务" },
];

const DATE_OPTIONS = [
  { value: "all", label: "全部" },
  { value: "week", label: "本周" },
  { value: "month", label: "本月" },
  { value: "custom", label: "自定义" },
];

const SORT_OPTIONS = [
  { value: "deadline", label: "截止时间" },
  { value: "created_at", label: "创建时间" },
  { value: "updated_at", label: "更新时间" },
  { value: "status", label: "任务状态" },
  { value: "task_weight", label: "任务权重" },
];

const ORDER_OPTIONS = [
  { value: "asc", label: "升序" },
  { value: "desc", label: "降序" },
];

function labelOf(options, value) {
  return options.find((item) => item.value === value)?.label || value;
}

function filterSummary(filters) {
  const labels = [];
  if (filters.mode === "nodes") labels.push("我的节点任务");
  if (filters.status) labels.push(labelOf(STATUS_OPTIONS, filters.status));
  if (filters.quadrant) labels.push(labelOf(QUADRANT_OPTIONS, filters.quadrant));
  if (filters.support) labels.push("需要支持");
  if (filters.nearDue) labels.push("未来3天临期");
  if (filters.datePreset === "week") labels.push("本周开始");
  if (filters.datePreset === "month") labels.push("本月开始");
  if (filters.datePreset === "custom" && filters.startDate && filters.endDate) labels.push(`${filters.startDate} 至 ${filters.endDate}`);
  if (filters.search) labels.push(`搜索：${filters.search}`);
  if (filters.sortBy !== "deadline" || filters.sortOrder !== "asc") {
    labels.push(`${labelOf(SORT_OPTIONS, filters.sortBy)} · ${labelOf(ORDER_OPTIONS, filters.sortOrder)}`);
  }
  return labels;
}

function mergeFilters(...sources) {
  return sources.reduce((result, source) => ({ ...result, ...(source || {}) }), { ...DEFAULT_FILTERS });
}

module.exports = {
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
};

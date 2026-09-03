/**
 * Feature: Shared domain labels.
 * Responsibilities: map stable backend codes to Chinese labels and visual tones.
 * Does not own: state transitions or persisted status values.
 * Plan task: WECHAT-MP-01.
 */

const STATUS = {
  draft: ["草稿", "gray"],
  pending_confirm: ["待确认", "orange"],
  pending_confirmation: ["待确认", "orange"],
  pending_accept: ["待接受", "orange"],
  pending_acceptance: ["待接受", "orange"],
  returned: ["已退回", "red"],
  decomposing: ["AI拆解中", "blue"],
  decomposition_failed: ["拆解失败", "red"],
  in_progress: ["进行中", "blue"],
  blocked: ["受阻", "red"],
  pending_report: ["待汇报", "orange"],
  pending_review: ["待验收", "green"],
  completed: ["已完成", "green"],
  archived: ["已归档", "gray"],
  cancelled: ["已取消", "gray"],
  withdrawn: ["已撤回", "gray"],
  merged: ["已合并", "gray"],
  closed: ["已关闭", "gray"],
};

const QUADRANTS = {
  important_urgent: "重要且紧急",
  important_not_urgent: "重要不紧急",
  urgent_not_important: "紧急不重要",
  not_important_urgent: "紧急不重要",
  routine: "常规任务",
  not_important_not_urgent: "常规任务",
};

function statusView(status) {
  const value = STATUS[status] || [status || "未知", "gray"];
  return { label: value[0], tone: value[1] };
}

module.exports = { STATUS, QUADRANTS, statusView };

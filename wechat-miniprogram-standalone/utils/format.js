/**
 * Feature: Display formatting.
 * Responsibilities: provide deterministic dates, progress and remaining-time labels.
 * Does not own: server-side calculations or persisted business fields.
 * Plan task: WECHAT-MP-01.
 */

function dateLabel(value) {
  if (!value) return "未设置";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value).replace("T", " ").slice(0, 16);
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hour = String(date.getHours()).padStart(2, "0");
  const minute = String(date.getMinutes()).padStart(2, "0");
  return `${month}-${day} ${hour}:${minute}`;
}

function remainingLabel(value) {
  const deadline = new Date(value).getTime();
  if (!deadline) return "未设置截止时间";
  const diff = deadline - Date.now();
  const days = Math.ceil(Math.abs(diff) / 86400000);
  return diff < 0 ? `逾期 ${days} 天` : days === 0 ? "今天截止" : `剩余 ${days} 天`;
}

module.exports = { dateLabel, remainingLabel };

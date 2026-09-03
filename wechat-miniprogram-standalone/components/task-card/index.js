/**
 * Feature: Task summary card.
 * Responsibilities: display one task and emit a semantic open event.
 * Does not own: navigation, querying, or workflow actions.
 * Plan task: WECHAT-MP-01.
 */

const { dateLabel, remainingLabel } = require("../../utils/format");

Component({
  properties: { task: { type: Object, value: {} }, compact: { type: Boolean, value: false } },
  observers: {
    task(value) {
      if (!value || !value.taskId) return;
      this.setData({ deadlineLabel: dateLabel(value.deadline), remaining: remainingLabel(value.deadline) });
    },
  },
  data: { deadlineLabel: "", remaining: "" },
  methods: {
    open() { this.triggerEvent("open", { taskId: this.data.task.taskId }); },
  },
});

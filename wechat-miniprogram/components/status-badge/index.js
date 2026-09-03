/**
 * Feature: Status badge.
 * Responsibilities: render a shared label/tone projection for task states.
 * Does not own: status mutation.
 * Plan task: WECHAT-MP-01.
 */

const { statusView } = require("../../utils/constants");

Component({
  properties: { status: { type: String, value: "" } },
  observers: {
    status(value) { this.setData(statusView(value)); },
  },
  data: { label: "", tone: "gray" },
});

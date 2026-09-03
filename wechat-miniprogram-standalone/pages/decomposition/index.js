/**
 * Feature: Assignee-triggered AI decomposition status (Feature 07).
 * Responsibilities: resume real server decomposition, execute pending attempts, poll, and retry failures.
 * Does not own: AI prompt rules, graph validation, or database transaction logic.
 * Plan task: DEV-09 / FEATURE-07.
 */

const api = require("../../utils/api");
const router = require("../../utils/router");

const POLL_DELAY_MS = 1200;

function taskState(task) {
  if (!task) return "processing";
  if (task.status === "decomposition_failed") return "failed";
  if (task.status === "in_progress" && task.effectiveAt) return "succeeded";
  return "processing";
}

Page({
  data: {
    taskId: "",
    task: {},
    attempt: null,
    state: "processing",
    stages: ["准备任务信息", "生成执行节点", "建立前置依赖", "校验并保存结果"],
    stageIndex: 0,
    error: "",
    retrying: false,
  },

  onLoad(options) {
    this.setData({ taskId: options.taskId || "" });
    this.resume();
  },

  onShow() {
    if (this.loadedOnce) this.resume();
    this.loadedOnce = true;
  },

  onUnload() { this.stopPolling(); },
  back() { wx.navigateBack({ fail: () => router.replace("/pages/task-detail/index", { taskId: this.data.taskId }) }); },

  stopPolling() {
    if (this.timer) clearTimeout(this.timer);
    this.timer = null;
  },

  resume() {
    if (!this.data.taskId) {
      this.setData({ state: "failed", error: "缺少任务编号" });
      return Promise.resolve();
    }
    this.stopPolling();
    return Promise.all([api.task(this.data.taskId), api.decomposition(this.data.taskId)])
      .then(([task, attempt]) => {
        this.setData({ task, attempt, state: taskState(task), error: attempt.errorMessage || "" });
        if (attempt.status === "succeeded" || taskState(task) === "succeeded") {
          this.setData({ state: "succeeded", stageIndex: this.data.stages.length });
          return;
        }
        if (["failed", "invalidated"].includes(attempt.status) || task.status === "decomposition_failed") {
          this.setData({ state: "failed", error: attempt.errorMessage || "AI拆解未通过校验" });
          return;
        }
        if (attempt.status === "pending") return this.execute(attempt);
        this.setData({ state: "processing", stageIndex: Math.max(1, this.data.stageIndex) });
        this.schedulePoll();
      })
      .catch((error) => this.setData({ state: "failed", error: error.message || "拆解状态加载失败" }));
  },

  execute(attempt) {
    if (this.executing) return Promise.resolve();
    this.executing = true;
    this.setData({ state: "processing", stageIndex: 1, error: "" });
    return api.executeDecomposition(this.data.taskId, attempt.decompositionId)
      .then((updated) => {
        this.executing = false;
        this.setData({ attempt: updated, stageIndex: 3 });
        if (updated.status === "failed") {
          this.setData({ state: "failed", error: updated.errorMessage || "AI拆解未通过校验" });
          return;
        }
        return this.resume();
      })
      .catch((error) => {
        this.executing = false;
        this.setData({ state: "failed", error: error.message || "AI拆解执行失败" });
      });
  },

  schedulePoll() {
    if (this.timer) return;
    this.timer = setTimeout(() => {
      this.timer = null;
      this.poll();
    }, POLL_DELAY_MS);
  },

  poll() {
    return Promise.all([api.task(this.data.taskId), api.decomposition(this.data.taskId)])
      .then(([task, attempt]) => {
        const nextStage = attempt.status === "running" ? Math.min(2, this.data.stageIndex + 1) : this.data.stageIndex;
        this.setData({ task, attempt, stageIndex: nextStage });
        if (attempt.status === "succeeded" || taskState(task) === "succeeded") {
          this.setData({ state: "succeeded", stageIndex: this.data.stages.length, error: "" });
          return;
        }
        if (["failed", "invalidated"].includes(attempt.status) || task.status === "decomposition_failed") {
          this.setData({ state: "failed", error: attempt.errorMessage || "AI拆解未通过校验" });
          return;
        }
        this.schedulePoll();
      })
      .catch((error) => this.setData({ state: "failed", error: error.message || "拆解状态刷新失败" }));
  },

  retry() {
    if (this.data.retrying) return;
    const task = this.data.task;
    this.stopPolling();
    this.setData({ retrying: true, state: "processing", stageIndex: 0, error: "" });
    api.retryDecomposition(this.data.taskId, task.taskVersion)
      .then(() => {
        this.setData({ retrying: false });
        return this.resume();
      })
      .catch((error) => this.setData({ retrying: false, state: "failed", error: error.message || "重新拆解失败" }));
  },

  detail() { router.replace("/pages/task-detail/index", { taskId: this.data.taskId }); },
});

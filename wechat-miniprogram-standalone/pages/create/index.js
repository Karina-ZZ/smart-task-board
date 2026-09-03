/**
 * Feature: Creator step 1 - describe task.
 * Responsibilities: capture text or a voice-to-text draft and persist creation progress.
 * Does not own: task creation, node decomposition, or AI provider credentials.
 * Plan task: WECHAT-MP-04.
 */

const api = require("../../utils/api");
const router = require("../../utils/router");

Page({
  data: { text: "", listening: false, mockMode: api.useMock(), examples: ["梳理Q2绩效面谈反馈，周五前给我原因和行动清单", "完成招聘月报数据复核，发现异常及时说明"] },
  onLoad() {
    api.creationDraft().then((draft) => this.setData({ text: draft.taskDescription || draft.rawText || "" }));
    this.recorder = wx.getRecorderManager();
    this.recorder.onStop(() => {
      this.setData({ listening: false });
      if (api.useMock()) {
        const text = this.data.text || "梳理Q2绩效面谈反馈，周五前输出原因分析和行动清单";
        this.setData({ text });
        wx.showToast({ title: "语音已转为文字", icon: "success" });
      } else {
        wx.showToast({ title: "录音完成，请接入企业ASR服务", icon: "none" });
      }
    });
    this.recorder.onError(() => { this.setData({ listening: false }); wx.showToast({ title: "录音失败，请改用文字", icon: "none" }); });
  },
  back() { wx.navigateBack(); },
  input(event) { this.setData({ text: event.detail.value }); },
  useExample(event) { this.setData({ text: event.currentTarget.dataset.text }); },
  toggleVoice() {
    if (this.data.listening) { this.recorder.stop(); return; }
    wx.authorize({ scope: "scope.record", success: () => { this.setData({ listening: true }); this.recorder.start({ duration: 60000, format: "mp3" }); }, fail: () => wx.showModal({ title: "需要麦克风权限", content: "请在设置中允许录音，或直接输入文字。", confirmText: "去设置", success: (result) => { if (result.confirm) wx.openSetting(); } }) });
  },
  next() {
    const text = this.data.text.trim();
    if (!text) { wx.showToast({ title: "请先描述任务", icon: "none" }); return; }
    wx.showLoading({ title: "AI识别中" });
    api.saveCreationDraft({ rawText: text, taskDescription: text, taskName: text.replace(/[，。,.]/g, " ").split(" ")[0].slice(0, 20), taskGoal: "按描述要求完成任务并提交验收", taskSource: "AI任务助手", taskWeight: 3, reportCycle: "每周" }).then(() => { wx.hideLoading(); router.go("/pages/create-details/index"); }).catch((error) => { wx.hideLoading(); wx.showToast({ title: error.message, icon: "none" }); });
  },
});

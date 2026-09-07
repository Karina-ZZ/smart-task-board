/**
 * Feature: Test16-equivalent employee Workbench.
 * Responsibilities: reproduce the approved mobile Workbench components, direct AI intake, filters, support items, and task-card navigation.
 * Does not own: task creation confirmation, AI provider implementation, priority calculation, or backend authorization.
 * Plan task: H5-MIGRATION-01.
 */

import { type FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { submitTaskInput } from "../../api/endpoints";
import type { TaskInputType, TaskSummary } from "../../api/types";
import { createReturnSource } from "../../app/return-state";
import { useAuth } from "../../auth/useAuth";
import { transcribeBrowserRecording } from "../../integrations/chat-service";
import { Button, EmptyState, ErrorState, Skeleton, useToast } from "../../shared/components";
import { type WorkbenchQuadrant, type WorkbenchStatusFilter, workbenchStatusTabs } from "./api";
import { useWorkbenchData } from "./hooks";
import "./WorkbenchPage.css";

const DRAFT_KEY = "smarttaskboard.dev07.intake-draft";
const STATUS_GROUPS: Record<WorkbenchStatusFilter, string[]> = {
  pending_accept: ["pending_accept", "pending_acceptance"],
  decomposing: ["decomposing"],
  decomposition_failed: ["decomposition_failed"],
  in_progress: ["in_progress"],
  blocked: ["blocked"],
  pending_report: ["pending_report"],
  pending_review: ["pending_review"],
};

const statusLabels: Record<string, string> = {
  pending_accept: "待接受",
  pending_acceptance: "待接受",
  decomposing: "AI拆解中",
  decomposition_failed: "拆解失败",
  in_progress: "进行中",
  blocked: "受阻",
  pending_report: "待汇报",
  pending_review: "待验收",
  completed: "已完成",
  archived: "已归档",
  returned: "已退回",
};

function chinaDateParts() {
  const formatter = new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    month: "numeric",
    day: "numeric",
    weekday: "short",
    hour: "numeric",
    hour12: false,
  });
  const parts = formatter.formatToParts(new Date()).reduce<Record<string, string>>((result, item) => {
    result[item.type] = item.value;
    return result;
  }, {});
  const hour = Number(parts.hour || 8);
  const greeting = hour < 6 ? "夜深了" : hour < 11 ? "早上好" : hour < 14 ? "中午好" : hour < 18 ? "下午好" : "晚上好";
  return { greeting, dateLabel: `${parts.month}月${parts.day}日 · ${parts.weekday}` };
}

function formatDeadline(value: string | null) {
  if (!value) return "未设置截止时间";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "未设置截止时间";
  return new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit" }).format(date);
}

function remainingLabel(task: TaskSummary) {
  if (task.is_overdue) return "已逾期";
  if (typeof task.days_until_deadline !== "number") return "时间待定";
  if (task.days_until_deadline === 0) return "今天截止";
  if (task.days_until_deadline === 1) return "明天截止";
  if (task.days_until_deadline > 1) return `剩${task.days_until_deadline}天`;
  return "已逾期";
}

function draftFromSession() {
  try {
    const value = JSON.parse(sessionStorage.getItem(DRAFT_KEY) || "{}") as { rawText?: unknown };
    return typeof value.rawText === "string" ? value.rawText : "";
  } catch {
    return "";
  }
}

function persistDraft(rawText: string, inputId: string | null = null, intake: unknown = null) {
  sessionStorage.setItem(DRAFT_KEY, JSON.stringify({ rawText, inputId, intake }));
}

function WorkbenchLoading() {
  return (
    <section className="stb-workbench" aria-label="正在加载工作台">
      <Skeleton height={52} />
      <Skeleton height={146} />
      <Skeleton height={94} />
      <Skeleton height={180} />
      <Skeleton height={150} />
    </section>
  );
}

function TaskCard({ task, onOpen }: { task: TaskSummary; onOpen: () => void }) {
  const progress = Math.min(100, Math.max(0, task.progress_percent ?? 0));
  return (
    <button className="stb-workbench-task" type="button" onClick={onOpen} aria-label={`打开任务 ${task.task_name}`}>
      <span className="stb-workbench-task__head">
        <span className={`stb-workbench-status stb-workbench-status--${task.status}`}>{statusLabels[task.status] ?? task.status}</span>
        <span className="stb-workbench-task__number">{task.task_no ?? "未编号"}</span>
      </span>
      <strong className="stb-workbench-task__name">{task.task_name}</strong>
      <span className="stb-workbench-task__meta">
        <span>{task.main_assignee?.name ?? "待分配"}</span>
        <span>·</span>
        <span className={task.is_overdue ? "stb-workbench-danger" : undefined}>{remainingLabel(task)}</span>
      </span>
      <span className="stb-workbench-task__progress"><i style={{ width: `${progress}%` }} /></span>
      <span className="stb-workbench-task__foot">
        <span>{formatDeadline(task.deadline)}</span>
        <b>{progress}%</b>
      </span>
    </button>
  );
}

export function WorkbenchPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const { showToast } = useToast();
  const query = useWorkbenchData();
  const [taskFilter, setTaskFilter] = useState<WorkbenchStatusFilter>("in_progress");
  const [quadrantFilter, setQuadrantFilter] = useState<WorkbenchQuadrant | "">("");
  const [draftText, setDraftText] = useState(draftFromSession);
  const [inputType, setInputType] = useState<TaskInputType>("text");
  const [submitting, setSubmitting] = useState(false);
  const [voiceState, setVoiceState] = useState<"idle" | "listening" | "transcribing">("idle");
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const taskSectionRef = useRef<HTMLElement | null>(null);
  const date = useMemo(chinaDateParts, []);

  useEffect(() => () => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
  }, []);

  useEffect(() => {
    persistDraft(draftText);
  }, [draftText]);

  async function submitDraft(event?: FormEvent) {
    event?.preventDefault();
    const text = draftText.trim();
    if (!text) {
      showToast("请先描述任务");
      return;
    }
    setSubmitting(true);
    try {
      const result = await submitTaskInput({ input_type: inputType, raw_text: text, source_channel: "web" });
      persistDraft(text, result.input_id, result);
      navigate("/create/details", { state: { source: createReturnSource(location, "工作台") } });
    } catch (error) {
      showToast(error instanceof Error ? error.message : "识别失败，请稍后重试");
    } finally {
      setSubmitting(false);
    }
  }

  async function toggleVoice() {
    if (voiceState === "listening" && recorderRef.current) {
      recorderRef.current.stop();
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      showToast("当前企业微信环境不支持录音，请改用文字输入");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const chunks: BlobPart[] = [];
      const recorder = new MediaRecorder(stream);
      recorderRef.current = recorder;
      recorder.ondataavailable = (event) => { if (event.data.size) chunks.push(event.data); };
      recorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
        recorderRef.current = null;
        const blob = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
        if (!blob.size) {
          setVoiceState("idle");
          showToast("没有录到有效语音，请重新录入");
          return;
        }
        try {
          setVoiceState("transcribing");
          const text = await transcribeBrowserRecording(blob);
          setInputType("voice");
          setDraftText(text);
          showToast("语音已转为文字");
        } catch (error) {
          showToast(error instanceof Error ? error.message : "语音识别失败，请改用文字");
        } finally {
          setVoiceState("idle");
        }
      };
      recorder.onerror = () => {
        stream.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
        recorderRef.current = null;
        setVoiceState("idle");
        showToast("录音失败，请改用文字输入");
      };
      setVoiceState("listening");
      recorder.start();
    } catch {
      setVoiceState("idle");
      showToast("需要麦克风权限，请允许后重试或直接输入文字");
    }
  }

  if (query.isLoading) return <WorkbenchLoading />;
  if (query.isError) {
    return <ErrorState title="工作台加载失败" detail="请检查网络后重新加载。" action={<Button onClick={() => void query.refetch()}>重新加载</Button>} />;
  }
  if (!query.data) return null;

  const { summary, tasks, quadrants, supportItems } = query.data;
  const statuses = STATUS_GROUPS[taskFilter];
  const visibleTasks = tasks.filter((task) => {
    const statusMatch = statuses.includes(task.status);
    const quadrantMatch = !quadrantFilter || task.priority_quadrant === quadrantFilter;
    return statusMatch && quadrantMatch;
  });
  const inProgress = tasks.filter((task) => ["in_progress", "blocked", "pending_report"].includes(task.status)).length;
  const avatarText = user?.name ? user.name.slice(-1) : "序";

  function selectStatus(value: WorkbenchStatusFilter) {
    setTaskFilter(value);
    window.setTimeout(() => taskSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 0);
  }

  function selectQuadrant(value: WorkbenchQuadrant) {
    setQuadrantFilter((current) => current === value ? "" : value);
    window.setTimeout(() => taskSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 0);
  }

  function openTask(taskId: string, nodeId?: string | null) {
    navigate(`/task/${encodeURIComponent(taskId)}${nodeId ? `#node-${encodeURIComponent(nodeId)}` : ""}`, {
      state: { source: createReturnSource(location, "工作台") },
    });
  }

  return (
    <div className="stb-workbench" data-testid="workbench-page">
      <header className="stb-workbench-header">
        <div className="stb-workbench-greeting-copy">
          <h1>{date.greeting}，{user?.name ?? "同事"}</h1>
          <span>{date.dateLabel}</span>
        </div>
        <div className="stb-workbench-header-actions">
          <button type="button" className="stb-workbench-bell" aria-label="打开消息" onClick={() => navigate("/notifications", { state: { source: createReturnSource(location, "工作台") } })}>
            <span aria-hidden="true">♢</span>
            {summary.unread_notification_count > 0 && <i />}
          </button>
          <button type="button" className="stb-workbench-avatar" aria-label="打开个人中心" onClick={() => navigate("/profile", { state: { source: createReturnSource(location, "工作台") } })}>{avatarText}</button>
        </div>
      </header>

      <section className="stb-workbench-ai" aria-label="一句话创建新任务">
        <span className="stb-workbench-ai__watermark" aria-hidden="true">AI</span>
        <div className="stb-workbench-ai__copy">
          <h2>一句话，创建新任务</h2>
          <p>自动识别目标、人员和截止时间</p>
        </div>
        <form className="stb-workbench-ai__input-row" onSubmit={(event) => void submitDraft(event)}>
          <input
            value={draftText}
            maxLength={1000}
            onChange={(event) => { setInputType("text"); setDraftText(event.target.value); }}
            placeholder="描述任务，例如：周五前完成招聘月报复核…"
            aria-label="任务描述"
          />
          <button type="button" className={voiceState === "listening" ? "stb-workbench-ai__voice is-recording" : "stb-workbench-ai__voice"} onClick={() => void toggleVoice()} aria-label="语音描述">
            {voiceState === "listening" ? "■" : voiceState === "transcribing" ? "…" : "◉"}
          </button>
          <button type="submit" className="stb-workbench-ai__send" disabled={submitting} aria-label="识别任务信息">{submitting ? "…" : "➜"}</button>
        </form>
      </section>

      <section className="stb-workbench-metric-strip" aria-label="任务指标">
        <button type="button" onClick={() => selectStatus("in_progress")}>
          <span>进行中任务</span><strong className="blue">{inProgress}</strong><small>项</small>
        </button>
        <div><span>临期任务</span><strong className="red">{summary.due_within_3_days_count}</strong><small>项</small></div>
        <div><span>按期完成率</span><strong className="teal">{summary.on_time_completion_rate}</strong><small>%</small><em>近{summary.completion_rate_period_days}天</em></div>
      </section>

      <section className="stb-workbench-panel">
        <div className="stb-workbench-panel__head">
          <h2>任务风险四象限</h2>
          {quadrantFilter ? <button type="button" onClick={() => setQuadrantFilter("")}>清除筛选</button> : <span>点击筛选任务</span>}
        </div>
        <div className="stb-workbench-quadrants">
          {quadrants.map((item) => (
            <button key={item.id} type="button" className={`stb-workbench-quadrant stb-workbench-quadrant--${item.id}${quadrantFilter === item.id ? " is-selected" : ""}`} onClick={() => selectQuadrant(item.id)}>
              <i aria-hidden="true">{item.id === "important_urgent" ? "!" : item.id === "important_not_urgent" ? "◆" : item.id === "urgent_not_important" ? "↗" : "✓"}</i>
              <span><b>{item.label}</b><small>{item.hint}</small></span>
              <strong>{item.count}</strong>
            </button>
          ))}
        </div>
      </section>

      <section className="stb-workbench-support">
        <div className="stb-workbench-panel__head stb-workbench-support__head">
          <h2><i aria-hidden="true">↔</i>需要我支持</h2>
          <span className="stb-workbench-support__badge">{supportItems.length}项待响应</span>
        </div>
        {supportItems.length ? supportItems.map((item) => (
          <button key={`${item.taskId}:${item.supportNodeId ?? "task"}`} type="button" className="stb-workbench-support__row" onClick={() => openTask(item.taskId, item.supportNodeId)}>
            <span><b>{item.taskName}</b><small>{item.supportReason}</small></span><em>查看 ›</em>
          </button>
        )) : <div className="stb-workbench-support__empty">当前没有待响应的协作事项</div>}
      </section>

      <section className="stb-workbench-task-section" ref={taskSectionRef}>
        <div className="stb-workbench-panel__head stb-workbench-task-heading">
          <h2>任务信息管理</h2>
          <button type="button" onClick={() => navigate("/tasks?reset=1")}>全部任务 ›</button>
        </div>
        <div className="stb-workbench-status-tabs" role="tablist" aria-label="任务状态筛选">
          {workbenchStatusTabs.map((tab) => (
            <button key={tab.key} type="button" role="tab" aria-selected={taskFilter === tab.key} className={taskFilter === tab.key ? "is-active" : ""} onClick={() => selectStatus(tab.key)}>{tab.label}</button>
          ))}
        </div>
        {quadrantFilter && <div className="stb-workbench-filter-notice"><span>已叠加四象限筛选</span><button type="button" onClick={() => setQuadrantFilter("")}>清除</button></div>}
        {visibleTasks.length ? <div className="stb-workbench-task-list">{visibleTasks.map((task) => <TaskCard key={task.task_id} task={task} onOpen={() => openTask(task.task_id)} />)}</div> : <EmptyState title="当前筛选下暂无任务" />}
      </section>
    </div>
  );
}

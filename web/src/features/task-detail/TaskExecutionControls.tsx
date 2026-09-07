/**
 * Feature: Test16-equivalent H5 task and node execution controls.
 * Responsibilities: render server-authorized task action bar, more-actions sheet, node assignment/execution actions, and structured dialogs.
 * Does not own: authorization rules, state transitions, version checks, idempotency, or transaction semantics.
 * H5 migration: page 06 task detail.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { acceptNodeAssignment, listUsers, rejectNodeAssignment } from "../../api/endpoints";
import {
  decideChangeRequest,
  reassignTask,
  runNodeAction,
  runTaskAction,
  submitChangeRequest,
} from "../../api/taskActions";
import type { AvailableActions, TaskCreationPerson, TaskDetail, TaskNode } from "../../api/types";
import { useAuth } from "../../auth/useAuth";
import { Button, Dialog, Input, Sheet, useToast } from "../../shared/components";

interface TaskControlsProps {
  task: TaskDetail;
  actions: AvailableActions;
  onRefresh: () => Promise<unknown> | void;
  onOpenLogs: () => void;
  moreOpen: boolean;
  onCloseMore: () => void;
}

interface NodeControlsProps {
  task: TaskDetail;
  actions: AvailableActions;
  node: TaskNode;
  onRefresh: () => Promise<unknown> | void;
}

type ReasonAction = "return" | "withdraw_task" | "cancel_task";
type ChangeField = "deadline" | "taskWeight" | "taskName";
type ChangeDecision = "approve" | "reject" | "cancel";

type DialogState =
  | { type: "accept" }
  | { type: "reason"; action: ReasonAction; title: string; placeholder: string }
  | { type: "change"; field: ChangeField; title: string; placeholder: string }
  | { type: "changeDecision"; action: ChangeDecision; title: string; requestId: string; optional?: boolean }
  | { type: "reassignReason"; person: TaskCreationPerson }
  | null;

const changeDefinitions: Record<ChangeField, { title: string; placeholder: string; label: string }> = {
  deadline: { title: "新的截止时间", placeholder: "例如 2026-09-10T18:00:00+08:00", label: "修改截止时间" },
  taskWeight: { title: "新的任务权重", placeholder: "请输入1-5", label: "修改任务权重" },
  taskName: { title: "新的任务名称", placeholder: "请输入任务名称", label: "修改任务名称" },
};

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "操作未完成，请刷新后重试。";
}

function has(actions: AvailableActions, action: string) {
  return actions.allowed_actions.includes(action as never);
}

function actionMode(actions: AvailableActions): "accept" | "complete" | "review" | "report" | "readonly" {
  if (has(actions, "accept") || has(actions, "return")) return "accept";
  if (has(actions, "submit_completion")) return "complete";
  if (has(actions, "approve_completion") || has(actions, "reject_completion")) return "review";
  if (has(actions, "submit_progress_report")) return "report";
  return "readonly";
}

export function TaskExecutionControls({
  task,
  actions,
  onRefresh,
  onOpenLogs,
  moreOpen,
  onCloseMore,
}: TaskControlsProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [dialog, setDialog] = useState<DialogState>(null);
  const [dialogValue, setDialogValue] = useState("");
  const [changeReason, setChangeReason] = useState("");
  const [changeChoiceOpen, setChangeChoiceOpen] = useState(false);
  const [reassignOpen, setReassignOpen] = useState(false);
  const [personSearch, setPersonSearch] = useState("");

  const pendingChange = useMemo(
    () => (task.change_requests || []).find((item) => item.status === "pending") ?? null,
    [task.change_requests],
  );
  const mode = actionMode(actions);

  const peopleQuery = useQuery({
    queryKey: ["task-detail-reassign-people", personSearch],
    queryFn: () => listUsers(personSearch || undefined),
    enabled: reassignOpen,
  });
  const people = (peopleQuery.data ?? []).filter(
    (person) => person.employee_no !== task.main_assignee_employee_no,
  );

  async function refresh() {
    await onRefresh();
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["task-overview"] }),
      queryClient.invalidateQueries({ queryKey: ["notifications"] }),
      queryClient.invalidateQueries({ queryKey: ["executive-overview"] }),
      queryClient.invalidateQueries({ queryKey: ["dashboard"] }),
    ]);
  }

  const mutation = useMutation({
    mutationFn: async (fn: () => Promise<unknown>) => fn(),
    onSuccess: async () => {
      setDialog(null);
      setDialogValue("");
      setChangeReason("");
      setReassignOpen(false);
      await refresh();
    },
    onError: (error) => toast.show(errorMessage(error)),
  });

  function openReason(action: ReasonAction, title: string, placeholder: string) {
    onCloseMore();
    setDialogValue("");
    setDialog({ type: "reason", action, title, placeholder });
  }

  function submitDialog() {
    if (!dialog) return;
    if (dialog.type === "accept") {
      mutation.mutate(async () => {
        const result = await runTaskAction(task.task_id, "accept", actions.task_version);
        if (result.status === "decomposing") {
          navigate(`/task/${task.task_id}/decomposition`, { replace: true });
        }
        return result;
      });
      return;
    }
    if (dialog.type === "reason") {
      const reason = dialogValue.trim();
      if (!reason) {
        toast.show("请填写原因。");
        return;
      }
      mutation.mutate(async () => {
        const result = await runTaskAction(task.task_id, dialog.action, actions.task_version, reason);
        toast.show(dialog.action === "return" ? "任务已退回" : dialog.action === "withdraw_task" ? "任务已撤回" : "任务已取消");
        return result;
      });
      return;
    }
    if (dialog.type === "reassignReason") {
      const reason = dialogValue.trim();
      if (!reason) {
        toast.show("请填写更换承办人原因。");
        return;
      }
      mutation.mutate(async () => {
        const result = await reassignTask(task.task_id, dialog.person.employee_no, actions.task_version, reason);
        toast.show("已重新发送待接受");
        return result;
      });
      return;
    }
    if (dialog.type === "change") {
      const rawValue = dialogValue.trim();
      const reason = changeReason.trim();
      if (!rawValue || !reason) {
        toast.show("请填写新的值和变更原因。");
        return;
      }
      let value: string | number = rawValue;
      if (dialog.field === "taskWeight") {
        const weight = Number(rawValue);
        if (!Number.isInteger(weight) || weight < 1 || weight > 5) {
          toast.show("任务权重必须为1-5。");
          return;
        }
        value = weight;
      }
      if (dialog.field === "deadline" && !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(rawValue)) {
        toast.show("请输入带日期和时间的ISO格式截止时间。");
        return;
      }
      mutation.mutate(async () => {
        const backendField = dialog.field === "taskWeight" ? "task_weight" : dialog.field === "taskName" ? "task_name" : "deadline";
        await submitChangeRequest(task.task_id, actions.task_version, { [backendField]: value }, reason);
        toast.show("变更申请已提交");
      });
      return;
    }
    if (dialog.type === "changeDecision") {
      const comment = dialogValue.trim();
      if (!dialog.optional && !comment) {
        toast.show(dialog.action === "reject" ? "请填写拒绝原因。" : "请填写取消原因。");
        return;
      }
      mutation.mutate(async () => {
        await decideChangeRequest(task.task_id, dialog.requestId, actions.task_version, dialog.action, comment);
        toast.show(dialog.action === "approve" ? "变更已生效" : dialog.action === "reject" ? "变更已拒绝" : "变更申请已取消");
      });
    }
  }

  function moreAction(action: "change" | "cancelChange" | "approveChange" | "rejectChange" | "reassign" | "withdraw" | "cancel") {
    if (action === "change") {
      onCloseMore();
      setChangeChoiceOpen(true);
      return;
    }
    if (action === "reassign") {
      onCloseMore();
      setReassignOpen(true);
      return;
    }
    if (!pendingChange && ["cancelChange", "approveChange", "rejectChange"].includes(action)) return;
    if (action === "cancelChange" && pendingChange) {
      onCloseMore();
      setDialogValue("");
      setDialog({ type: "changeDecision", action: "cancel", title: "取消变更申请", requestId: pendingChange.change_request_id });
    } else if (action === "approveChange" && pendingChange) {
      onCloseMore();
      setDialogValue("");
      setDialog({ type: "changeDecision", action: "approve", title: "同意变更", requestId: pendingChange.change_request_id, optional: true });
    } else if (action === "rejectChange" && pendingChange) {
      onCloseMore();
      setDialogValue("");
      setDialog({ type: "changeDecision", action: "reject", title: "拒绝变更", requestId: pendingChange.change_request_id });
    } else if (action === "withdraw") {
      openReason("withdraw_task", "撤回任务", "请填写撤回原因");
    } else if (action === "cancel") {
      openReason("cancel_task", "取消任务", "请填写取消原因");
    }
  }

  async function copyTaskNo() {
    if (!task.task_no) return;
    try {
      await navigator.clipboard.writeText(task.task_no);
      toast.show("任务编号已复制");
    } catch {
      toast.show(`任务编号：${task.task_no}`);
    }
    onCloseMore();
  }

  const readonlyReason = task.status === "decomposing"
    ? "AI拆解完成后才能执行任务"
    : task.status === "decomposition_failed"
      ? "请进入AI拆解页重新拆解"
      : "当前任务只读";

  return (
    <>
      <div className="stb-task-action-bar" aria-label="任务操作">
        <Button variant="secondary" onClick={onOpenLogs}>查看操作记录</Button>
        {mode === "accept" && (
          <>
            {has(actions, "return") && <Button variant="secondary" onClick={() => openReason("return", "退回任务", "请输入退回原因")}>退回任务</Button>}
            {has(actions, "accept") && <Button variant="primary" onClick={() => setDialog({ type: "accept" })}>接受任务</Button>}
          </>
        )}
        {mode === "complete" && <Button variant="primary" onClick={() => navigate(`/task/${task.task_id}/completion`)}>提交完成</Button>}
        {mode === "report" && <Button variant="primary" onClick={() => navigate(`/task/${task.task_id}/report`)}>汇报进度</Button>}
        {mode === "review" && <Button variant="primary" onClick={() => navigate(`/task/${task.task_id}/review`)}>进入任务验收</Button>}
        {mode === "readonly" && (
          <Button variant="secondary" disabled>{readonlyReason}</Button>
        )}
      </div>

      <Sheet open={moreOpen} title="更多操作" onClose={onCloseMore}>
        <div className="stb-task-more-list">
          <button type="button" className="stb-task-more-action" onClick={() => void copyTaskNo()}>
            <span>#</span><div><b>复制任务编号</b><small>{task.task_no || "无"}</small></div><i>›</i>
          </button>
          {has(actions, "submit_change_request") && !pendingChange && (
            <button type="button" className="stb-task-more-action" onClick={() => moreAction("change")}>
              <span>△</span><div><b>发起变更申请</b><small>调整范围、时间或任务信息</small></div><i>›</i>
            </button>
          )}
          {pendingChange && (has(actions, "approve_change_request") || has(actions, "reject_change_request")) && (
            <div className="stb-task-change-summary"><b>待审批变更</b><small>{pendingChange.reason}</small></div>
          )}
          {has(actions, "cancel_change_request") && pendingChange && (
            <button type="button" className="stb-task-more-action" onClick={() => moreAction("cancelChange")}>
              <span>×</span><div><b>取消变更申请</b><small>撤销本人尚未审批的申请</small></div><i>›</i>
            </button>
          )}
          {has(actions, "approve_change_request") && pendingChange && (
            <button type="button" className="stb-task-more-action" onClick={() => moreAction("approveChange")}>
              <span>✓</span><div><b>同意变更申请</b><small>应用变更并记录审计</small></div><i>›</i>
            </button>
          )}
          {has(actions, "reject_change_request") && pendingChange && (
            <button type="button" className="stb-task-more-action" onClick={() => moreAction("rejectChange")}>
              <span>!</span><div><b>拒绝变更申请</b><small>保留原任务并通知承办人</small></div><i>›</i>
            </button>
          )}
          {has(actions, "reassign_task") && (
            <button type="button" className="stb-task-more-action" onClick={() => moreAction("reassign")}>
              <span>人</span><div><b>更换承办人</b><small>重新发送待接受通知</small></div><i>›</i>
            </button>
          )}
          {has(actions, "withdraw_task") && (
            <button type="button" className="stb-task-more-action" onClick={() => moreAction("withdraw")}>
              <span>↩</span><div><b>撤回任务</b><small>撤回并保留审计记录</small></div><i>›</i>
            </button>
          )}
          {has(actions, "cancel_task") && (
            <button type="button" className="stb-task-more-action stb-task-more-action--danger" onClick={() => moreAction("cancel")}>
              <span>!</span><div><b>取消任务</b><small>取消原因必填</small></div><i>›</i>
            </button>
          )}
        </div>
      </Sheet>

      <Sheet open={changeChoiceOpen} title="发起变更申请" onClose={() => setChangeChoiceOpen(false)}>
        <div className="stb-task-more-list">
          {(Object.keys(changeDefinitions) as ChangeField[]).map((field) => (
            <button key={field} type="button" className="stb-task-more-action" onClick={() => {
              setChangeChoiceOpen(false);
              setDialogValue("");
              setChangeReason("");
              setDialog({ type: "change", field, ...changeDefinitions[field] });
            }}>
              <span>△</span><div><b>{changeDefinitions[field].label}</b><small>{changeDefinitions[field].placeholder}</small></div><i>›</i>
            </button>
          ))}
        </div>
      </Sheet>

      <Sheet open={reassignOpen} title="选择新的主承办人" onClose={() => setReassignOpen(false)}>
        <div className="stb-person-sheet">
          <Input label="搜索姓名或员工号" value={personSearch} onChange={(event) => setPersonSearch(event.target.value)} />
          {peopleQuery.isLoading && <p className="stb-task-dialog-note">正在加载人员…</p>}
          {peopleQuery.isError && <p className="stb-task-dialog-error">人员加载失败，请重试。</p>}
          <div className="stb-person-options">
            {people.map((person) => (
              <button key={person.employee_no} type="button" onClick={() => {
                setReassignOpen(false);
                setDialogValue("");
                setDialog({ type: "reassignReason", person });
              }}>
                <span>{person.name.slice(0, 1)}</span>
                <div><b>{person.name}</b><small>{person.employee_no} · {person.department_name || "未分部门"}{person.workload_score ? ` · 负荷 ${person.workload_score}` : ""}</small></div>
                <i>›</i>
              </button>
            ))}
          </div>
        </div>
      </Sheet>

      <Dialog
        open={dialog !== null}
        title={dialog?.type === "accept" ? "接受任务" : dialog?.type === "reassignReason" ? "更换承办人" : dialog?.type === "change" ? dialog.title : dialog?.type === "changeDecision" ? dialog.title : dialog?.title || "任务操作"}
        onClose={() => { if (!mutation.isPending) setDialog(null); }}
        actions={(
          <>
            <Button variant="secondary" disabled={mutation.isPending} onClick={() => setDialog(null)}>取消</Button>
            <Button variant={dialog?.type === "reason" && dialog.action === "cancel_task" ? "danger" : "primary"} loading={mutation.isPending} onClick={submitDialog}>
              {dialog?.type === "accept" ? "确认接受" : dialog?.type === "changeDecision" && dialog.action === "approve" ? "确认同意" : "确认"}
            </Button>
          </>
        )}
      >
        {dialog?.type === "accept" && <p className="stb-task-dialog-note">接受后系统将立即启动AI拆解。拆解成功前任务不会生效。</p>}
        {dialog?.type === "reason" && <Input autoFocus label={dialog.placeholder} value={dialogValue} onChange={(event) => setDialogValue(event.target.value)} />}
        {dialog?.type === "reassignReason" && (
          <>
            <p className="stb-task-dialog-note">新承办人：{dialog.person.name} · {dialog.person.employee_no}</p>
            <Input autoFocus label={`更换为${dialog.person.name}的原因`} value={dialogValue} onChange={(event) => setDialogValue(event.target.value)} />
          </>
        )}
        {dialog?.type === "change" && (
          <div className="stb-task-dialog-fields">
            <Input autoFocus label={dialog.title} placeholder={dialog.placeholder} value={dialogValue} onChange={(event) => setDialogValue(event.target.value)} />
            <Input label="变更原因" placeholder="请说明为什么需要调整" value={changeReason} onChange={(event) => setChangeReason(event.target.value)} />
          </div>
        )}
        {dialog?.type === "changeDecision" && (
          <Input autoFocus label={dialog.optional ? "审批意见（可选）" : dialog.action === "reject" ? "拒绝原因" : "取消原因"} value={dialogValue} onChange={(event) => setDialogValue(event.target.value)} />
        )}
      </Dialog>
    </>
  );
}

export function NodeExecutionControls({ task, actions, node, onRefresh }: NodeControlsProps) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const { user } = useAuth();
  const [rejectOpen, setRejectOpen] = useState(false);
  const [rejectReason, setRejectReason] = useState("");
  const allowed = actions.nodes.find((item) => item.node_id === node.node_id)?.allowed_actions ?? [];
  const pendingAssignment = node.assignment_status === "pending";

  async function refresh() {
    await onRefresh();
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["task-overview"] }),
      queryClient.invalidateQueries({ queryKey: ["notifications"] }),
      queryClient.invalidateQueries({ queryKey: ["dashboard"] }),
    ]);
  }

  const mutation = useMutation({
    mutationFn: async (input: "acceptAssignment" | "rejectAssignment" | "start" | "complete") => {
      if (input === "acceptAssignment") return acceptNodeAssignment(task.task_id, node.node_id, actions.task_version);
      if (input === "rejectAssignment") {
        const reason = rejectReason.trim();
        if (!reason) throw new Error("请填写无法承接原因。");
        return rejectNodeAssignment(task.task_id, node.node_id, actions.task_version, reason);
      }
      return runNodeAction(task.task_id, node.node_id, input === "start" ? "start_node" : "complete_node", actions.task_version);
    },
    onSuccess: async (_, input) => {
      if (input === "rejectAssignment") setRejectOpen(false);
      setRejectReason("");
      toast.show(input === "acceptAssignment" ? "节点已承接" : input === "rejectAssignment" ? "已反馈无法承接" : input === "start" ? "节点已开始" : "节点已完成");
      await refresh();
    },
    onError: (error) => toast.show(errorMessage(error)),
  });

  const canStart = allowed.includes("start_node");
  const canComplete = allowed.includes("complete_node");
  const canRespond = pendingAssignment && node.owner_employee_no === user?.employee_no;
  if (!canRespond && !canStart && !canComplete) return null;

  return (
    <>
      <div className="stb-node-inline-actions">
        {canRespond && (
          <>
            <Button variant="secondary" loading={mutation.isPending} onClick={() => setRejectOpen(true)}>无法承接</Button>
            <Button variant="primary" loading={mutation.isPending} onClick={() => mutation.mutate("acceptAssignment")}>接受承接</Button>
          </>
        )}
        {!pendingAssignment && canStart && <Button variant="secondary" loading={mutation.isPending} onClick={() => mutation.mutate("start")}>开始节点</Button>}
        {!pendingAssignment && canComplete && <Button variant="primary" loading={mutation.isPending} onClick={() => mutation.mutate("complete")}>完成节点</Button>}
      </div>
      <Dialog
        open={rejectOpen}
        title="无法承接节点"
        onClose={() => setRejectOpen(false)}
        actions={<><Button variant="secondary" onClick={() => setRejectOpen(false)}>取消</Button><Button variant="primary" loading={mutation.isPending} onClick={() => mutation.mutate("rejectAssignment")}>确认退回</Button></>}
      >
        <Input autoFocus label="请填写无法承接原因" value={rejectReason} onChange={(event) => setRejectReason(event.target.value)} />
      </Dialog>
    </>
  );
}

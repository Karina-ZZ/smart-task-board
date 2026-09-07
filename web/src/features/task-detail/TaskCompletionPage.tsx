/**
 * Feature: Test16-equivalent H5 completion submission page.
 * Responsibilities: collect completion note and deliverable summary, confirm submission, and call the real submit-completion action.
 * Does not own: completion eligibility, reviewer decisions, actual-hours calculation, or automatic archival.
 * H5 migration: page 09 completion submission.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import { submitCompletion } from "../../api/taskActions";
import { useReturnNavigation } from "../../app/return-state";
import { Badge, Button, Card, Dialog, ErrorState, Skeleton, useToast } from "../../shared/components";
import { useTaskDetailBundle } from "./hooks";
import "./TaskCompletionPage.css";

function errorTitle(error: unknown) {
  if (error instanceof ApiError && error.status === 403) return "无权限提交完成";
  if (error instanceof ApiError && error.status === 404) return "任务不存在";
  return "提交完成页面暂时无法加载";
}

function errorMessage(error: unknown) {
  if (error instanceof ApiError && error.status === 409) return "任务状态或版本已变化，请返回任务详情刷新后重试。";
  return error instanceof Error ? error.message : "提交失败，请稍后重试。";
}

export function TaskCompletionPage() {
  const { taskId = "" } = useParams();
  const { goBack } = useReturnNavigation(`/task/${taskId}`);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();
  const query = useTaskDetailBundle(taskId);
  const [completionNote, setCompletionNote] = useState("");
  const [deliverableSummary, setDeliverableSummary] = useState("");
  const [confirmOpen, setConfirmOpen] = useState(false);

  const mutation = useMutation({
    mutationFn: async () => {
      if (!query.data) throw new Error("任务尚未加载。");
      const note = completionNote.trim();
      const summary = deliverableSummary.trim();
      if (!note) throw new Error("请填写完成说明。");
      if (!summary) throw new Error("请填写交付摘要。");
      return submitCompletion(taskId, query.data.actions.task_version, note, summary);
    },
    onSuccess: async () => {
      setConfirmOpen(false);
      toast.show("已提交验收");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["task-detail", taskId] }),
        queryClient.invalidateQueries({ queryKey: ["task-overview"] }),
        queryClient.invalidateQueries({ queryKey: ["notifications"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard"] }),
      ]);
      navigate(`/task/${taskId}`, { replace: true });
    },
    onError: (error) => toast.show(errorMessage(error)),
  });

  function requestSubmit() {
    if (!completionNote.trim()) {
      toast.show("请填写完成说明");
      return;
    }
    if (!deliverableSummary.trim()) {
      toast.show("请填写交付摘要");
      return;
    }
    setConfirmOpen(true);
  }

  if (query.isLoading) return <section className="stb-completion-page"><Skeleton height={70} /><Skeleton height={120} /><Skeleton height={300} /></section>;
  if (query.isError || !query.data) {
    return <ErrorState title={errorTitle(query.error)} detail={query.error instanceof ApiError ? query.error.message : "请稍后重试。"} action={<Button variant="secondary" onClick={() => void query.refetch()}>重新加载</Button>} />;
  }

  const { task, actions } = query.data;
  if (!actions.allowed_actions.includes("submit_completion")) {
    return <ErrorState title="当前任务不可提交完成" detail="只有主承办人在合法执行状态且全部有效节点完成后才能提交验收。" action={<Button variant="secondary" onClick={goBack}>返回任务详情</Button>} />;
  }

  return (
    <section className="stb-completion-page" data-testid="task-completion-page">
      <header className="stb-completion-topbar">
        <Button variant="ghost" iconOnly aria-label="返回任务详情" onClick={goBack}>‹</Button>
        <div><span>COMPLETION</span><strong>提交完成</strong></div>
      </header>

      <Card className="stb-completion-summary">
        <Badge tone="success">全部节点已完成</Badge>
        <h1>{task.task_name}</h1>
        <p>提交后进入待验收；实际工时由系统计算。</p>
      </Card>

      <Card className="stb-completion-form-card">
        <label>
          <span>完成说明 <b>*</b></span>
          <textarea maxLength={1000} placeholder="说明本次任务完成情况、验收需要关注的结果" value={completionNote} onChange={(event) => setCompletionNote(event.target.value)} />
        </label>
        <label>
          <span>交付摘要 <b>*</b></span>
          <textarea maxLength={1000} placeholder="概括最终交付成果，便于验收人快速确认" value={deliverableSummary} onChange={(event) => setDeliverableSummary(event.target.value)} />
        </label>
      </Card>

      <div className="stb-completion-note">验收通过无需填写额外意见；若验收不通过，验收人必须填写退回意见。</div>

      <div className="stb-completion-actions"><Button loading={mutation.isPending} onClick={requestSubmit}>提交验收</Button></div>

      <Dialog
        open={confirmOpen}
        title="提交完成"
        onClose={() => setConfirmOpen(false)}
        actions={<><Button variant="secondary" disabled={mutation.isPending} onClick={() => setConfirmOpen(false)}>取消</Button><Button loading={mutation.isPending} onClick={() => mutation.mutate()}>确认提交</Button></>}
      >
        <p className="stb-completion-dialog-note">提交后任务将进入待验收，验收人可通过或退回修改。</p>
      </Dialog>
    </section>
  );
}

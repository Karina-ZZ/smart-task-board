/**
 * Feature: Test16-equivalent H5 completion review page.
 * Responsibilities: display the current immutable completion round and allow authorized approval/archive or reasoned rejection.
 * Does not own: reviewer authorization, actual-hours calculation, archive transaction, or task state-machine rules.
 * H5 migration: page 10 completion review.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import { approveCompletion, rejectCompletion } from "../../api/taskActions";
import { useReturnNavigation } from "../../app/return-state";
import { Badge, Button, Card, Dialog, EmptyState, ErrorState, Skeleton, useToast } from "../../shared/components";
import { useTaskDetailBundle } from "./hooks";
import { formatDateTime } from "./format";
import "./TaskReviewPage.css";

function errorTitle(error: unknown) {
  if (error instanceof ApiError && error.status === 403) return "无权限验收任务";
  if (error instanceof ApiError && error.status === 404) return "任务不存在";
  return "验收页面暂时无法加载";
}

function errorMessage(error: unknown) {
  if (error instanceof ApiError && error.status === 409) return "任务状态或版本已变化，请返回任务详情刷新后再试。";
  return error instanceof Error ? error.message : "验收操作未完成。";
}

export function TaskReviewPage() {
  const { taskId = "" } = useParams();
  const { goBack } = useReturnNavigation(`/task/${taskId}`);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();
  const query = useTaskDetailBundle(taskId);
  const [decision, setDecision] = useState<"approve" | "reject" | null>(null);
  const [rejectReason, setRejectReason] = useState("");

  const currentReview = useMemo(
    () => [...(query.data?.reviews ?? [])]
      .sort((left, right) => right.review_round - left.review_round)
      .find((item) => item.review_status === "submitted"),
    [query.data?.reviews],
  );

  const mutation = useMutation({
    mutationFn: async () => {
      if (!query.data || !currentReview || !decision) throw new Error("当前没有可处理的验收申请。");
      if (decision === "approve") {
        return approveCompletion(taskId, query.data.actions.task_version, currentReview.completion_review_id);
      }
      const reason = rejectReason.trim();
      if (!reason) throw new Error("退回原因必填。");
      return rejectCompletion(taskId, query.data.actions.task_version, currentReview.completion_review_id, reason, null);
    },
    onSuccess: async () => {
      const approved = decision === "approve";
      setDecision(null);
      setRejectReason("");
      toast.show(approved ? "已通过并归档" : "已退回修改");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["task-detail", taskId] }),
        queryClient.invalidateQueries({ queryKey: ["task-overview"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard"] }),
        queryClient.invalidateQueries({ queryKey: ["notifications"] }),
        queryClient.invalidateQueries({ queryKey: ["executive-overview"] }),
      ]);
      navigate(`/task/${taskId}`, { replace: true });
    },
    onError: (error) => toast.show(errorMessage(error)),
  });

  if (query.isLoading) return <section className="stb-review-page"><Skeleton height={70} /><Skeleton height={160} /><Skeleton height={260} /></section>;
  if (query.isError || !query.data) {
    return <ErrorState title={errorTitle(query.error)} detail={query.error instanceof ApiError ? query.error.message : "请稍后重试。"} action={<Button variant="secondary" onClick={() => void query.refetch()}>重新加载</Button>} />;
  }

  const { task, actions, reviews } = query.data;
  if (!currentReview) {
    return <ErrorState title="当前没有待验收的完成申请" detail="请从任务详情确认任务状态或等待主承办人提交完成。" action={<Button variant="secondary" onClick={goBack}>返回任务详情</Button>} />;
  }
  const canApprove = actions.allowed_actions.includes("approve_completion");
  const canReject = actions.allowed_actions.includes("reject_completion");
  if (!canApprove && !canReject) {
    return <ErrorState title="当前无权处理验收" detail="只有本轮创建人或指定验收人可以在待验收状态处理完成申请。" action={<Button variant="secondary" onClick={goBack}>返回任务详情</Button>} />;
  }

  const completedNodes = task.nodes.filter((node) => node.status === "completed").length;
  const history = [...reviews].filter((item) => item.completion_review_id !== currentReview.completion_review_id).sort((left, right) => right.review_round - left.review_round);

  return (
    <section className="stb-review-page" data-testid="task-review-page">
      <header className="stb-review-topbar">
        <Button variant="ghost" iconOnly aria-label="返回任务详情" onClick={goBack}>‹</Button>
        <div><span>COMPLETION REVIEW</span><strong>任务验收</strong></div>
      </header>

      <section className="stb-review-hero">
        <Badge tone="success">第 {currentReview.review_round || 1} 轮验收</Badge>
        <h1>{task.task_name}</h1>
        <div className="stb-review-track"><span className="done">已接受</span><i>—</i><span className="done">执行完成</span><i>—</i><span className="current">待验收</span><i>—</i><span>自动归档</span></div>
      </section>

      <Card title="完成申请" className="stb-review-card">
        <dl className="stb-review-kv"><div><dt>提交人</dt><dd>{currentReview.submitted_by_employee_no}</dd></div><div><dt>提交时间</dt><dd>{formatDateTime(currentReview.submitted_at)}</dd></div></dl>
        <div className="stb-review-block"><span>完成说明</span><p>{currentReview.completion_note || "-"}</p></div>
        <div className="stb-review-block"><span>交付摘要</span><p>{currentReview.deliverable_summary || "-"}</p></div>
      </Card>

      <Card title="验收依据" className="stb-review-card">
        <div className="stb-review-block"><span>任务目标</span><p>{task.task_goal || "-"}</p></div>
        <div className="stb-review-block"><span>验收标准</span><p>{task.acceptance_criteria || "-"}</p></div>
        <div className="stb-review-node-summary"><span>有效节点</span><b>{task.nodes.length}</b><span>已完成</span><b>{completedNodes}</b></div>
      </Card>

      {history.length > 0 && (
        <Card title="历史验收记录" className="stb-review-card">
          <div className="stb-review-history">
            {history.map((item) => <div key={item.completion_review_id}><Badge tone={item.review_status === "approved" ? "success" : item.review_status === "rejected" ? "danger" : "warning"}>第 {item.review_round} 轮 · {item.review_status}</Badge><small>{item.reviewed_at ? formatDateTime(item.reviewed_at) : formatDateTime(item.submitted_at)}</small>{item.reject_reason && <p>退回原因：{item.reject_reason}</p>}</div>)}
          </div>
        </Card>
      )}

      {history.length === 0 && reviews.length === 0 && <EmptyState title="暂无历史验收记录" />}

      <div className="stb-review-archive-note">验收通过后系统自动计算实际工时，并立即归档；不会创建归档快照。</div>

      <div className="stb-review-actions">
        {canReject && <Button variant="secondary" disabled={mutation.isPending} onClick={() => { setRejectReason(""); setDecision("reject"); }}>退回修改</Button>}
        {canApprove && <Button loading={mutation.isPending} onClick={() => setDecision("approve")}>通过并归档</Button>}
      </div>

      <Dialog
        open={decision === "approve"}
        title="验收通过"
        onClose={() => setDecision(null)}
        actions={<><Button variant="secondary" disabled={mutation.isPending} onClick={() => setDecision(null)}>取消</Button><Button loading={mutation.isPending} onClick={() => mutation.mutate()}>确认通过</Button></>}
      >
        <p className="stb-review-dialog-note">通过后任务将在同一流程中完成并自动归档，不生成归档快照。</p>
      </Dialog>

      <Dialog
        open={decision === "reject"}
        title="退回修改"
        onClose={() => setDecision(null)}
        actions={<><Button variant="secondary" disabled={mutation.isPending} onClick={() => setDecision(null)}>取消</Button><Button loading={mutation.isPending} onClick={() => mutation.mutate()}>确认退回</Button></>}
      >
        <label className="stb-review-reject-field"><span>验收不通过原因 *</span><textarea autoFocus placeholder="请填写验收不通过原因" value={rejectReason} onChange={(event) => setRejectReason(event.target.value)} /></label>
      </Dialog>
    </section>
  );
}

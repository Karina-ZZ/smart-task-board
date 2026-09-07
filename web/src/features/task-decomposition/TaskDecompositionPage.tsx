/**
 * Feature: Test16-equivalent H5 assignee AI decomposition status.
 * Responsibilities: resume/execute/poll the accepted-task decomposition, show processing/success/failure stages, and allow authorized retry.
 * Does not own: AI provider implementation, graph validation, task-effectiveness rules, or node persistence.
 * H5 migration: page 07 AI decomposition.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import {
  executeTaskDecomposition,
  getTaskDecomposition,
  getTaskDetail,
  retryTaskDecomposition,
} from "../../api/endpoints";
import { Button, ErrorState, Skeleton } from "../../shared/components";
import "./task-decomposition.css";

const stages = ["准备任务信息", "生成执行节点", "建立前置依赖", "校验并保存结果"];

function errorMessage(error: unknown) {
  if (error instanceof ApiError) return error.message;
  return error instanceof Error ? error.message : "AI拆解状态暂时不可用。";
}

export function TaskDecompositionPage() {
  const { taskId = "" } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const task = useQuery({
    queryKey: ["decomposition-task", taskId],
    queryFn: () => getTaskDetail(taskId),
    enabled: Boolean(taskId),
    refetchInterval: (query) => query.state.data?.status === "decomposing" ? 1200 : false,
  });
  const attempt = useQuery({
    queryKey: ["task-decomposition", taskId],
    queryFn: () => getTaskDecomposition(taskId),
    enabled: Boolean(taskId),
    retry: false,
    refetchInterval: (query) => ["pending", "running"].includes(query.state.data?.status || "") ? 1200 : false,
  });

  const execute = useMutation({
    mutationFn: (decompositionId: string) => executeTaskDecomposition(taskId, decompositionId),
    onSuccess: async () => {
      await Promise.all([attempt.refetch(), task.refetch()]);
    },
  });
  const retry = useMutation({
    mutationFn: () => {
      if (!task.data) throw new Error("任务尚未加载。");
      return retryTaskDecomposition(taskId, task.data.task_version);
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["task-decomposition", taskId] }),
        attempt.refetch(),
        task.refetch(),
      ]);
    },
  });

  useEffect(() => {
    if (!attempt.data || attempt.data.status !== "pending" || execute.isPending || execute.isSuccess) return;
    void execute.mutateAsync(attempt.data.decomposition_id).catch(() => undefined);
  }, [attempt.data, execute.isPending, execute.isSuccess]);

  function goBack() {
    if (window.history.length > 1) navigate(-1);
    else navigate(`/task/${taskId}`, { replace: true });
  }

  if (!taskId) {
    return <ErrorState title="缺少任务编号" detail="请从任务详情重新进入AI拆解。" action={<Button variant="secondary" onClick={() => navigate("/tasks", { replace: true })}>返回任务概览</Button>} />;
  }
  if (task.isLoading || attempt.isLoading) {
    return <section className="stb-decomposition"><Skeleton height={70} /><Skeleton height={220} /><Skeleton height={74} /></section>;
  }
  if (task.isError) {
    return <ErrorState title="任务暂时无法加载" detail={errorMessage(task.error)} action={<Button variant="secondary" onClick={() => void task.refetch()}>重新加载</Button>} />;
  }
  if (attempt.isError && task.data?.status !== "in_progress") {
    return <ErrorState title="AI拆解记录暂时无法加载" detail={errorMessage(attempt.error)} action={<Button variant="secondary" onClick={() => void attempt.refetch()}>重试查询</Button>} />;
  }
  if (!task.data) return <ErrorState title="任务不存在" />;

  const current = attempt.data;
  const succeeded = (task.data.status === "in_progress" && Boolean(task.data.effective_at)) || current?.status === "succeeded";
  const failed = task.data.status === "decomposition_failed" || current?.status === "failed" || current?.status === "invalidated";
  const state = succeeded ? "succeeded" : failed ? "failed" : "processing";
  const stageIndex = succeeded ? stages.length : current?.status === "running" ? 2 : current?.status === "pending" ? 1 : 0;
  const error = current?.error_message || (failed ? "AI拆解未通过校验" : "");

  return (
    <section className="stb-decomposition" data-testid="task-decomposition-page">
      <header className="stb-decomposition-topbar">
        <Button variant="ghost" iconOnly aria-label="返回任务详情" onClick={goBack}>‹</Button>
        <div><span>AI DECOMPOSITION</span><strong>任务智能拆解</strong></div>
      </header>

      <section className={`stb-decomposition-hero stb-decomposition-hero--${state}`}>
        <div className="stb-decomposition-core" aria-hidden="true">✦<i /></div>
        <h1>{state === "processing" ? "正在把任务变成行动" : state === "succeeded" ? "拆解完成，任务已生效" : "拆解暂未完成"}</h1>
        <p>{state === "processing"
          ? "离开本页不会取消任务，刷新后会从服务端恢复进度"
          : state === "succeeded"
            ? `${current?.node_count || task.data.nodes.length || 0} 个节点已通过校验并写入`
            : error || "你可以重新发起拆解"}</p>
      </section>

      <section className="stb-decomposition-stage-card" aria-label="AI拆解进度">
        {stages.map((label, index) => {
          const done = state === "succeeded" || index < stageIndex;
          const active = state === "processing" && index === stageIndex;
          return (
            <div key={label} className={`stb-decomposition-stage${done ? " stb-decomposition-stage--done" : ""}${active ? " stb-decomposition-stage--active" : ""}`}>
              <span>{done ? "✓" : index + 1}</span>
              <strong>{label}</strong>
              <small>{done ? "已完成" : active ? "处理中" : "等待"}</small>
            </div>
          );
        })}
      </section>

      {failed && <div className="stb-decomposition-error" role="alert">{error || "AI拆解未通过校验"}</div>}
      {(execute.isError || retry.isError) && <ErrorState title="拆解操作未完成" detail={errorMessage(execute.error || retry.error)} />}

      <div className="stb-decomposition-notice">拆解成功前，任务不会计入负荷，也不能汇报、完成节点或验收。</div>

      <div className="stb-decomposition-actions">
        {state === "failed" && <Button loading={retry.isPending} onClick={() => retry.mutate()}>重新拆解</Button>}
        {state === "succeeded" && <Button onClick={() => navigate(`/task/${taskId}`, { replace: true })}>查看执行节点</Button>}
        {state === "processing" && <Button variant="secondary" disabled>AI处理中，请稍候</Button>}
      </div>
    </section>
  );
}

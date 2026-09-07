/**
 * Feature: Test16-equivalent H5 progress report page.
 * Responsibilities: collect mandatory progress/blocker state plus optional stage result and remark, then submit the real task-level report API.
 * Does not own: report authorization, status transitions, issue creation, actual-hours calculation, or notification rules.
 * H5 migration: page 08 progress report.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import { submitProgressReport } from "../../api/endpoints";
import { useReturnNavigation } from "../../app/return-state";
import { Badge, Button, Card, ErrorState, Skeleton, Typography, useToast } from "../../shared/components";
import { useTaskDetailBundle } from "./hooks";
import "./TaskDetailPage.css";
import "./TaskReportPage.css";

function errorTitle(error: unknown) {
  if (error instanceof ApiError && error.status === 403) return "无权限提交汇报";
  if (error instanceof ApiError && error.status === 404) return "任务不存在";
  return "汇报页面暂时无法加载";
}

function errorMessage(error: unknown) {
  if (error instanceof ApiError && error.status === 409) return "任务状态或版本已变化，请返回详情刷新后再试。";
  return error instanceof Error ? error.message : "进度汇报提交失败。";
}

export function TaskReportPage() {
  const { taskId = "" } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();
  const { goBack } = useReturnNavigation(`/task/${taskId}`);
  const query = useTaskDetailBundle(taskId);
  const latestProgress = useMemo(() => {
    const reports = [...(query.data?.reports ?? [])].sort((left, right) => right.created_at.localeCompare(left.created_at));
    return reports[0]?.progress_percent ?? 0;
  }, [query.data?.reports]);

  const [progressPercent, setProgressPercent] = useState(0);
  const [stageResult, setStageResult] = useState("");
  const [hasIssue, setHasIssue] = useState(false);
  const [issueNote, setIssueNote] = useState("");
  const [remark, setRemark] = useState("");

  useEffect(() => setProgressPercent(latestProgress), [latestProgress]);

  const mutation = useMutation({
    mutationFn: async () => {
      if (!query.data) throw new Error("任务尚未加载。");
      if (hasIssue && !issueNote.trim()) throw new Error("存在卡点时必须填写说明。");
      return submitProgressReport(taskId, {
        expected_task_version: query.data.actions.task_version,
        progress_percent: progressPercent,
        stage_result: stageResult.trim() || null,
        has_issue: hasIssue,
        issue_note: hasIssue ? issueNote.trim() : null,
        remark: remark.trim() || null,
      });
    },
    onSuccess: async () => {
      toast.show("进度已提交");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["task-detail", taskId] }),
        queryClient.invalidateQueries({ queryKey: ["task-overview"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard"] }),
        queryClient.invalidateQueries({ queryKey: ["notifications"] }),
      ]);
      navigate(`/task/${taskId}`, { replace: true });
    },
    onError: (error) => toast.show(errorMessage(error)),
  });

  if (query.isLoading) return <section className="stb-report-page"><Skeleton height={70} /><Skeleton height={360} /></section>;
  if (query.isError || !query.data) {
    return <ErrorState title={errorTitle(query.error)} detail={query.error instanceof ApiError ? query.error.message : "请稍后重试。"} action={<Button variant="secondary" onClick={() => void query.refetch()}>重试</Button>} />;
  }

  const { task, actions } = query.data;
  if (!actions.allowed_actions.includes("submit_progress_report")) {
    return <ErrorState title="当前不能提交任务级汇报" detail="只有主承办人在执行态可以提交任务级进度汇报；协办人只执行本人负责节点。" action={<Button variant="secondary" onClick={goBack}>返回任务详情</Button>} />;
  }

  return (
    <section className="stb-report-page" data-testid="task-report-page">
      <header className="stb-report-topbar">
        <Button variant="ghost" iconOnly aria-label="返回任务详情" onClick={goBack}>‹</Button>
        <div><span>PROGRESS REPORT</span><strong>提交进度汇报</strong></div>
      </header>

      <div className="stb-report-task-strip">
        <Badge tone="info">{task.task_no ?? task.task_id}</Badge>
        <strong>{task.task_name}</strong>
      </div>

      <Card className="stb-report-form-card">
        <div className="stb-report-progress-head"><label htmlFor="report-progress">当前进度 <b>*</b></label><strong>{progressPercent}%</strong></div>
        <input id="report-progress" className="stb-report-slider" type="range" min="0" max="100" step="5" value={progressPercent} onChange={(event) => setProgressPercent(Number(event.target.value))} />
        <div className="stb-report-scale"><span>0</span><span>50</span><span>100</span></div>

        <label className="stb-report-field">
          <span>阶段成果（选填）</span>
          <textarea placeholder="本阶段完成了什么？" value={stageResult} onChange={(event) => setStageResult(event.target.value)} />
        </label>

        <div className="stb-report-issue-switch">
          <div><span>是否存在卡点 <b>*</b></span><small>开启后卡点说明必填</small></div>
          <button type="button" className={`stb-switch${hasIssue ? " stb-switch--on" : ""}`} role="switch" aria-checked={hasIssue} onClick={() => setHasIssue((value) => !value)}><i /></button>
        </div>

        {hasIssue && (
          <label className="stb-report-field stb-report-field--issue">
            <span>卡点说明 <b>*</b></span>
            <textarea placeholder="说明困难、影响和需要的支持" value={issueNote} onChange={(event) => setIssueNote(event.target.value)} />
          </label>
        )}

        <label className="stb-report-field">
          <span>备注（选填）</span>
          <textarea className="stb-report-textarea-short" placeholder="补充说明" value={remark} onChange={(event) => setRemark(event.target.value)} />
        </label>

        <Typography variant="caption" className="stb-report-auto-note">实际工时由任务完成时间减开始时间自动计算，无需填写。</Typography>
      </Card>

      <div className="stb-report-actions">
        <Button loading={mutation.isPending} onClick={() => mutation.mutate()}>提交进度汇报</Button>
      </div>
    </section>
  );
}

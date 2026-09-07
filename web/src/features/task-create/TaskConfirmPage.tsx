/**
 * Feature: Test16 creator step 3 - confirm and send.
 * Responsibilities: present the authoritative task summary, execute the two-step V1.1 send workflow, and keep the sent-success state visible.
 * Does not own: AI decomposition, assignee acceptance, performance scoring, or server authorization.
 * Plan task: H5-MIGRATION-04.
 */

import { useMutation, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import { getTaskDetail, listUsers } from "../../api/endpoints";
import { runTaskAction } from "../../api/taskActions";
import type { TaskActionResult } from "../../api/types";
import { Badge, Button, Card, ErrorState, Skeleton } from "../../shared/components";
import "./task-create.css";

function errorMessage(error: unknown) {
  if (error instanceof ApiError) return error.message;
  return error instanceof Error ? error.message : "操作未完成，请稍后重试。";
}
function dateText(value: string | null) {
  if (!value) return "未设置";
  return value.replace("T", " ").replace(/([+-]\d\d:\d\d|Z)$/, "").slice(0, 16);
}

export function TaskConfirmPage() {
  const [params] = useSearchParams();
  const taskId = params.get("taskId") || "";
  const navigate = useNavigate();
  const [sentTask, setSentTask] = useState<TaskActionResult | null>(null);
  const task = useQuery({ queryKey: ["create-confirm-task", taskId], queryFn: () => getTaskDetail(taskId), enabled: Boolean(taskId) });
  const people = useQuery({ queryKey: ["task-creation-people"], queryFn: () => listUsers() });
  const peopleByNo = useMemo(() => new Map((people.data ?? []).map((person) => [person.employee_no, person.name])), [people.data]);

  const send = useMutation({
    mutationFn: async () => {
      if (!task.data) throw new Error("任务草稿尚未加载。");
      let version = task.data.task_version;
      let status = task.data.status;
      if (status === "draft") {
        const submitted = await runTaskAction(taskId, "submit_for_confirmation", version);
        version = submitted.task_version;
        status = submitted.status;
      }
      if (status !== "pending_confirm") throw new Error(`当前状态 ${status} 不能执行确认发送，请刷新任务。`);
      return runTaskAction(taskId, "confirm_and_send", version);
    },
    onSuccess: (result) => setSentTask(result),
  });

  if (!taskId) return <ErrorState title="缺少任务草稿" detail="请返回创建页面重新保存任务信息。" />;
  if (task.isLoading || people.isLoading) return <><Skeleton height={110} /><Skeleton height={300} /></>;
  if (task.isError || !task.data) return <ErrorState title="任务摘要加载失败" detail={errorMessage(task.error)} action={<Button onClick={() => void task.refetch()}>重试</Button>} />;

  const item = task.data;
  const name = (employeeNo: string | null | undefined) => employeeNo ? peopleByNo.get(employeeNo) ?? employeeNo : "-";
  const collaborators = (item.participants ?? []).filter((participant) => participant.participant_role === "collaborator").map((participant) => name(participant.employee_no));
  const confirmed = (item.performance_matches ?? []).find((match) => match.is_confirmed);
  const assigneeName = name(item.main_assignee_employee_no);

  if (sentTask) {
    return (
      <section className="stb-create-sent" data-testid="task-sent-success">
        <div className="stb-create-sent__mark">✓</div>
        <h1>任务已发送</h1>
        <span>{item.task_no ?? sentTask.task_id}</span>
        <p>已发送给主承办人 {assigneeName}，当前状态为“待接受”。接受前不会生成节点。</p>
        <Button onClick={() => navigate(`/task/${encodeURIComponent(sentTask.task_id)}`, { replace: true })}>查看任务详情</Button>
        <Button variant="secondary" onClick={() => navigate("/workbench", { replace: true })}>返回工作台</Button>
      </section>
    );
  }

  return (
    <section className="stb-create-confirm" data-testid="task-confirm-page">
      <div className="stb-create-confirm__stepper" aria-label="创建任务第3步，共3步"><div className="is-done"><b>1</b><span>描述任务</span></div><i className="is-done"/><div className="is-done"><b>2</b><span>信息确认</span></div><i className="is-done"/><div className="is-active"><b>3</b><span>确认发送</span></div></div>
      <div className="stb-create-confirm__hero"><div>✓</div><h1>任务信息已完整</h1><p>发送后进入“待接受”；只通知主承办人，不生成节点、不计入当前负荷。</p></div>
      <Card>
        <div className="stb-create-confirm__head"><strong>{item.task_name}</strong><Badge tone="warning">待接受</Badge></div>
        <p className="stb-create-confirm__description">{item.task_description || "-"}</p>
        <div className="stb-create-confirm__line" />
        <dl className="stb-create-confirm__kv">
          <div><dt>任务目标</dt><dd>{item.task_goal || "-"}</dd></div><div><dt>任务来源</dt><dd>{item.task_source || "未填写"}</dd></div><div><dt>绩效指标</dt><dd>{confirmed?.metric_name || "不关联"}</dd></div><div><dt>主承办人</dt><dd>{assigneeName}</dd></div><div><dt>汇报对象</dt><dd>{name(item.report_to_employee_no)}</dd></div><div><dt>协同人</dt><dd>{collaborators.join("、") || "无"}</dd></div><div><dt>验收人</dt><dd>{name(item.reviewer_employee_no)}</dd></div><div><dt>开始时间</dt><dd>{dateText(item.start_time)}</dd></div><div><dt>截止时间</dt><dd>{dateText(item.deadline)}</dd></div><div><dt>任务权重</dt><dd>{item.task_weight ?? "-"} / 5</dd></div><div><dt>突发任务</dt><dd>{item.is_urgent ? "是" : "否"}</dd></div><div><dt>汇报周期</dt><dd>每周 · 周五17:00</dd></div><div><dt>验收标准</dt><dd>{item.acceptance_criteria || "—"}</dd></div>
        </dl>
      </Card>
      <div className="stb-create-confirm__recipient"><span>↗</span><div><b>本次待承办信息仅发送给 {assigneeName}</b><small>其他任务相关人员按后续事件规则收取信息；管理员全局查看权限不会订阅任务通知。</small></div></div>
      <div className="stb-create-confirm__flow"><div><b>1</b><span>确认发送</span></div><em>→</em><div><b>2</b><span>主承办人接受</span></div><em>→</em><div><b>3</b><span>AI拆解生效</span></div></div>
      {send.isError && <ErrorState title="发送失败" detail={errorMessage(send.error)} />}
      <div className="stb-create-confirm__footer"><Button loading={send.isPending} onClick={() => send.mutate()}>确认发送给 {assigneeName}</Button></div>
    </section>
  );
}

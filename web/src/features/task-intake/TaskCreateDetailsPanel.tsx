/**
 * Feature: Test16 creator step 2 task-level confirmation form.
 * Responsibilities: preserve manual edits across AI clarifications, use sheet-based people/performance selectors, persist the formal draft, and continue to send confirmation.
 * Does not own: AI extraction, final sending, node decomposition, performance scoring, or server authorization.
 * Plan task: H5-MIGRATION-03.
 */

import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "../../api/client";
import {
  clearPerformanceMatch,
  confirmPerformanceMatch,
  confirmTaskInput,
  getTaskDetail,
  listUsers,
  suggestPerformanceMatches,
  updateTaskDraft,
} from "../../api/endpoints";
import type { PerformanceMatch, TaskActionResult, TaskCreationPerson, TaskIntakeResponse } from "../../api/types";
import { Badge, Button, Card, EmptyState, ErrorState, Sheet, Typography, useToast } from "../../shared/components";

interface Props { intake: TaskIntakeResponse }

type FormState = {
  task_name: string;
  task_description: string;
  task_goal: string;
  task_source: string;
  main_assignee_employee_no: string;
  report_to_employee_no: string;
  reviewer_employee_no: string;
  department_id: string;
  start_time: string;
  deadline: string;
  task_weight: string;
  deliverable: string;
  acceptance_criteria: string;
  report_cycle: string;
  is_urgent: boolean;
  collaborator_employee_nos: string[];
};

type PersonField = "main_assignee_employee_no" | "report_to_employee_no" | "reviewer_employee_no" | "collaborator_employee_nos";

const REQUIRED_FIELDS: Array<keyof FormState> = [
  "task_name", "task_description", "task_goal", "main_assignee_employee_no", "report_to_employee_no",
  "reviewer_employee_no", "start_time", "deadline", "task_weight",
];

const emptyForm: FormState = {
  task_name: "", task_description: "", task_goal: "", task_source: "",
  main_assignee_employee_no: "", report_to_employee_no: "", reviewer_employee_no: "", department_id: "",
  start_time: "", deadline: "", task_weight: "3", deliverable: "", acceptance_criteria: "",
  report_cycle: "weekly:FRI@17:00", is_urgent: false, collaborator_employee_nos: [],
};

function stringValue(value: unknown): string { return value === null || value === undefined ? "" : String(value); }
function localDateTime(value: unknown): string {
  const text = stringValue(value);
  const match = text.match(/^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})/);
  return match ? `${match[1]}T${match[2]}` : "";
}
function shanghaiIso(value: string): string | null { return value ? `${value}:00+08:00` : null; }
function rawField(raw: Record<string, unknown>, snake: string, camel: string) { return raw[snake] ?? raw[camel]; }
function extractedForm(raw: Record<string, unknown>): Partial<FormState> {
  const collaborators = rawField(raw, "collaborator_employee_nos", "collaboratorEmployeeNos");
  return {
    task_name: stringValue(rawField(raw, "task_name", "taskName")),
    task_description: stringValue(rawField(raw, "task_description", "taskDescription")),
    task_goal: stringValue(rawField(raw, "task_goal", "taskGoal")),
    task_source: stringValue(rawField(raw, "task_source", "taskSource")),
    main_assignee_employee_no: stringValue(rawField(raw, "main_assignee_employee_no", "mainAssigneeEmployeeNo")),
    report_to_employee_no: stringValue(rawField(raw, "report_to_employee_no", "reportToEmployeeNo")),
    reviewer_employee_no: stringValue(rawField(raw, "reviewer_employee_no", "reviewerEmployeeNo")),
    department_id: stringValue(rawField(raw, "department_id", "departmentId")),
    start_time: localDateTime(rawField(raw, "start_time", "startTime")),
    deadline: localDateTime(rawField(raw, "deadline", "deadline")),
    task_weight: stringValue(rawField(raw, "task_weight", "taskWeight") || 3),
    deliverable: stringValue(rawField(raw, "deliverable", "deliverable")),
    acceptance_criteria: stringValue(rawField(raw, "acceptance_criteria", "acceptanceCriteria")),
    report_cycle: "weekly:FRI@17:00",
    is_urgent: Boolean(rawField(raw, "is_urgent", "isUrgent")),
    collaborator_employee_nos: Array.isArray(collaborators) ? collaborators.map(String) : [],
  };
}
function errorMessage(error: unknown) {
  if (error instanceof ApiError) return error.message;
  return error instanceof Error ? error.message : "任务信息保存失败，请稍后重试。";
}
function matchTone(match: PerformanceMatch): "success" | "warning" | "neutral" {
  return match.match_level === "strong" ? "success" : match.match_level === "weak" ? "warning" : "neutral";
}

export function TaskCreateDetailsPanel({ intake }: Props) {
  const navigate = useNavigate();
  const { showToast } = useToast();
  const [form, setForm] = useState<FormState>(emptyForm);
  const [savedTask, setSavedTask] = useState<TaskActionResult | null>(null);
  const [saving, setSaving] = useState(false);
  const [personField, setPersonField] = useState<PersonField | null>(null);
  const [peopleKeyword, setPeopleKeyword] = useState("");
  const [metricOpen, setMetricOpen] = useState(false);
  const [metricLoading, setMetricLoading] = useState(false);
  const [metricMatches, setMetricMatches] = useState<PerformanceMatch[]>([]);
  const [confirmedMetric, setConfirmedMetric] = useState<PerformanceMatch | null>(null);
  const [actionError, setActionError] = useState("");
  const dirtyFields = useRef(new Set<keyof FormState>());
  const people = useQuery({ queryKey: ["task-creation-people"], queryFn: () => listUsers() });
  const requiredMissing = useMemo(() => REQUIRED_FIELDS.filter((field) => !String(form[field] ?? "").trim()), [form]);

  useEffect(() => {
    const ai = extractedForm(intake.extracted_json);
    setForm((current) => {
      const next = { ...current };
      (Object.keys(ai) as Array<keyof FormState>).forEach((field) => {
        if (dirtyFields.current.has(field)) return;
        const value = ai[field];
        if (value !== undefined) Object.assign(next, { [field]: value });
      });
      return next;
    });
  }, [intake.extraction_id, intake.extracted_json]);

  function update<K extends keyof FormState>(field: K, value: FormState[K]) {
    dirtyFields.current.add(field);
    setForm((current) => ({ ...current, [field]: value }));
  }

  const personOptions = people.data ?? [];
  const peopleByNo = useMemo(() => new Map(personOptions.map((person) => [person.employee_no, person])), [personOptions]);
  const filteredPeople = useMemo(() => {
    const keyword = peopleKeyword.trim().toLowerCase();
    if (!keyword) return personOptions;
    return personOptions.filter((person) => `${person.name}${person.employee_no}${person.department_name ?? ""}`.toLowerCase().includes(keyword));
  }, [peopleKeyword, personOptions]);

  function personName(employeeNo: string) { return peopleByNo.get(employeeNo)?.name ?? "请选择"; }
  function openPeople(field: PersonField) { setPeopleKeyword(""); setPersonField(field); }
  function selectPerson(person: TaskCreationPerson) {
    if (!personField) return;
    if (personField === "collaborator_employee_nos") {
      const next = [...new Set([...form.collaborator_employee_nos, person.employee_no])];
      update("collaborator_employee_nos", next);
    } else {
      update(personField, person.employee_no);
      if (personField === "main_assignee_employee_no" && person.department_id && !dirtyFields.current.has("department_id")) {
        setForm((current) => ({ ...current, department_id: person.department_id ?? "" }));
      }
    }
    setPersonField(null);
  }

  function corrections() {
    return {
      task_name: form.task_name.trim(), task_description: form.task_description.trim(), task_goal: form.task_goal.trim(),
      task_source: form.task_source.trim() || null, main_assignee_employee_no: form.main_assignee_employee_no,
      report_to_employee_no: form.report_to_employee_no, reviewer_employee_no: form.reviewer_employee_no,
      department_id: form.department_id || null, start_time: shanghaiIso(form.start_time), deadline: shanghaiIso(form.deadline),
      task_weight: Number(form.task_weight), deliverable: form.deliverable.trim() || null,
      acceptance_criteria: form.acceptance_criteria.trim() || null, report_cycle: "weekly:FRI@17:00",
      is_urgent: form.is_urgent, collaborator_employee_nos: form.collaborator_employee_nos,
    };
  }

  function validate() {
    if (requiredMissing.length) throw new Error("请补齐所有必填信息；任务来源可以不填。");
    if (form.start_time && form.deadline && new Date(form.deadline) < new Date(form.start_time)) throw new Error("截止时间不能早于开始时间。");
  }

  async function saveDraft(showSuccess = false): Promise<TaskActionResult> {
    validate();
    setSaving(true); setActionError("");
    try {
      let result: TaskActionResult;
      if (!savedTask) {
        result = await confirmTaskInput(intake.input_id, { extraction_id: intake.extraction_id, corrections: corrections() });
      } else {
        result = await updateTaskDraft(savedTask.task_id, { expected_task_version: savedTask.task_version, ...corrections() });
      }
      setSavedTask(result);
      if (showSuccess) showToast("草稿已保存");
      return result;
    } catch (error) {
      setActionError(errorMessage(error));
      throw error;
    } finally { setSaving(false); }
  }

  async function openMetrics() {
    setMetricLoading(true); setMetricOpen(true); setActionError("");
    try {
      const draft = await saveDraft(false);
      const detail = await getTaskDetail(draft.task_id);
      const current = detail.performance_matches?.find((match) => match.is_confirmed) ?? null;
      setConfirmedMetric(current);
      setSavedTask({ task_id: detail.task_id, status: detail.status, task_version: detail.task_version, updated_at: detail.updated_at });
      setMetricMatches(await suggestPerformanceMatches(detail.task_id, detail.task_version, 10));
    } catch (error) { setActionError(errorMessage(error)); }
    finally { setMetricLoading(false); }
  }

  async function chooseMetric(match: PerformanceMatch) {
    if (!savedTask) return;
    setMetricLoading(true);
    try {
      await confirmPerformanceMatch(savedTask.task_id, match.performance_match_id, savedTask.task_version);
      const detail = await getTaskDetail(savedTask.task_id);
      setSavedTask({ task_id: detail.task_id, status: detail.status, task_version: detail.task_version, updated_at: detail.updated_at });
      setConfirmedMetric(detail.performance_matches?.find((item) => item.is_confirmed) ?? match);
      setMetricOpen(false); showToast("绩效指标已确认");
    } catch (error) { setActionError(errorMessage(error)); }
    finally { setMetricLoading(false); }
  }

  async function chooseNoMetric() {
    if (!savedTask) { setConfirmedMetric(null); setMetricOpen(false); return; }
    setMetricLoading(true);
    try {
      await clearPerformanceMatch(savedTask.task_id, savedTask.task_version);
      const detail = await getTaskDetail(savedTask.task_id);
      setSavedTask({ task_id: detail.task_id, status: detail.status, task_version: detail.task_version, updated_at: detail.updated_at });
      setConfirmedMetric(null); setMetricOpen(false); showToast("已设置为不关联绩效");
    } catch (error) { setActionError(errorMessage(error)); }
    finally { setMetricLoading(false); }
  }

  async function next() {
    try {
      const draft = await saveDraft(false);
      navigate(`/create/confirm?taskId=${encodeURIComponent(draft.task_id)}`);
    } catch { /* Error state is rendered below. */ }
  }

  return (
    <>
      <Card className="stb-task-intake-panel stb-create-fields">
        <div className="stb-create-fields__head"><div><Typography variant="sectionTitle" as="h2">确认任务信息</Typography><Typography variant="caption">请核对并补齐，发送前不会生成任何节点</Typography></div><Badge tone={requiredMissing.length ? "warning" : "success"}>{requiredMissing.length ? `还缺 ${requiredMissing.length} 项必填` : "必填信息已完整"}</Badge></div>
        <Typography variant="caption">AI追问未结束也不会阻止已完整字段继续发送；人工已填写内容不会被后续AI回答覆盖。</Typography>
        {people.isError && <ErrorState title="人员列表加载失败" detail={errorMessage(people.error)} />}
        <div className="stb-create-grid">
          <label className="wide"><span>任务名称 *</span><input value={form.task_name} maxLength={50} onChange={(e) => update("task_name", e.target.value)} /></label>
          <label className="wide"><span>任务内容 *</span><textarea value={form.task_description} maxLength={1000} onChange={(e) => update("task_description", e.target.value)} /></label>
          <label className="wide"><span>任务目标 *</span><textarea value={form.task_goal} maxLength={500} onChange={(e) => update("task_goal", e.target.value)} /></label>
          <label className="wide"><span>任务来源（选填）</span><small>如：张总交办 / 周例会 / 客户需求</small><input value={form.task_source} maxLength={120} onChange={(e) => update("task_source", e.target.value)} /></label>
          <button type="button" className="stb-create-menu-row wide" onClick={() => void openMetrics()}><i>✦</i><span><b>关联绩效指标</b><small>系统候选，由创建人确认或不关联</small></span><em>{confirmedMetric?.metric_name || "请选择"}</em><strong>›</strong></button>
          <button type="button" className="stb-create-menu-row wide" onClick={() => openPeople("main_assignee_employee_no")}><i>人</i><span><b>主承办人 *</b><small>搜索姓名/工号并查看负荷</small></span><em>{personName(form.main_assignee_employee_no)}</em><strong>›</strong></button>
          <button type="button" className="stb-create-menu-row wide" onClick={() => openPeople("report_to_employee_no")}><i>报</i><span><b>汇报对象 *</b></span><em>{personName(form.report_to_employee_no)}</em><strong>›</strong></button>
          <button type="button" className="stb-create-menu-row wide" onClick={() => openPeople("reviewer_employee_no")}><i>验</i><span><b>验收人 *</b></span><em>{personName(form.reviewer_employee_no)}</em><strong>›</strong></button>
          <button type="button" className="stb-create-menu-row wide" onClick={() => openPeople("collaborator_employee_nos")}><i>协</i><span><b>协同人</b><small>仅参与授权节点，不可接受主任务</small></span><em>{form.collaborator_employee_nos.length ? `${form.collaborator_employee_nos.length}人` : "请选择"}</em><strong>›</strong></button>
          {form.collaborator_employee_nos.length > 0 && <div className="wide stb-create-chips">{form.collaborator_employee_nos.map((employeeNo) => <button key={employeeNo} type="button" onClick={() => update("collaborator_employee_nos", form.collaborator_employee_nos.filter((item) => item !== employeeNo))}>{personName(employeeNo)} ×</button>)}</div>}
          <label><span>开始时间 *</span><input type="datetime-local" value={form.start_time} onChange={(e) => update("start_time", e.target.value)} /></label>
          <label><span>截止时间 *</span><input type="datetime-local" value={form.deadline} onChange={(e) => update("deadline", e.target.value)} /></label>
          <fieldset className="wide stb-create-weight"><legend>任务权重 *</legend>{[1,2,3,4,5].map((weight) => <button type="button" key={weight} className={form.task_weight === String(weight) ? "is-selected" : ""} onClick={() => update("task_weight", String(weight))}>{weight}</button>)}</fieldset>
          <div className="wide stb-create-fixed-field"><span>汇报周期</span><b>每周 · 周五17:00</b></div>
          <label className="wide"><span>文字交付说明</span><textarea value={form.deliverable} maxLength={500} onChange={(e) => update("deliverable", e.target.value)} /></label>
          <label className="wide"><span>验收标准</span><textarea value={form.acceptance_criteria} maxLength={500} onChange={(e) => update("acceptance_criteria", e.target.value)} /></label>
          <label className="wide stb-create-urgent"><span><b>突发任务</b><small>影响后续优先级/负荷计算</small></span><input type="checkbox" checked={form.is_urgent} onChange={(e) => update("is_urgent", e.target.checked)} /></label>
        </div>
        {actionError && <ErrorState title="操作未完成" detail={actionError} />}
        <div className="stb-create-fields__actions"><Button variant="secondary" loading={saving} onClick={() => void saveDraft(true)}>保存草稿</Button><Button loading={saving} onClick={() => void next()}>进入发送确认 →</Button></div>
      </Card>

      <Sheet open={Boolean(personField)} title={personField === "main_assignee_employee_no" ? "选择主承办人" : personField === "report_to_employee_no" ? "选择汇报对象" : personField === "reviewer_employee_no" ? "选择验收人" : "添加协同人"} onClose={() => setPersonField(null)}>
        <div className="stb-create-person-sheet"><input value={peopleKeyword} onChange={(event) => setPeopleKeyword(event.target.value)} placeholder="搜索姓名或员工号" aria-label="搜索人员" />{filteredPeople.length ? filteredPeople.map((person) => <button key={person.employee_no} type="button" onClick={() => selectPerson(person)}><i>{person.name.slice(-1)}</i><span><b>{person.name}</b><small>{person.employee_no} · {person.department_name || "-"}</small></span><em>{person.workload_level || "暂无"} {person.workload_score || ""}</em></button>) : <EmptyState title="没有可选择的人员" />}</div>
      </Sheet>

      <Sheet open={metricOpen} title="选择绩效指标" onClose={() => setMetricOpen(false)}>
        <div className="stb-create-metric-sheet"><p>系统按任务内容生成候选，仍需创建人确认。</p>{metricLoading ? <div className="stb-create-sheet-loading">正在计算候选指标…</div> : <><button type="button" onClick={() => void chooseNoMetric()}><span><b>不关联绩效指标</b><small>本任务不计入具体绩效指标</small></span></button>{metricMatches.map((match) => <button type="button" key={match.performance_match_id} onClick={() => void chooseMetric(match)}><i>✦</i><span><b>{match.metric_name || match.metric_id}</b><small>{match.match_reason || match.match_level}</small></span><Badge tone={matchTone(match)}>{Number(match.total_score).toFixed(0)}分</Badge></button>)}</>}</div>
      </Sheet>
    </>
  );
}

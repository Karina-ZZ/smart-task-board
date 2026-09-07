/**
 * Feature: V1.1 task overview page.
 * Responsibilities: render server-filtered task and node overview modes with URL-restorable filters.
 * Does not own: task detail implementation, permissions, priority calculation, or node execution.
 * Plan task: DEV-04.
 */

import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useLocation, useSearchParams } from "react-router-dom";

import type { ExecutiveMember, TaskOverviewNode, TaskStatus, TaskSummary } from "../../api/types";
import { ApiError } from "../../api/client";
import { listExecutiveMembers } from "../../api/endpoints";
import { createReturnSource } from "../../app/return-state";
import { Badge, Button, Card, EmptyState, ErrorState, Progress, Sheet, Skeleton, Typography } from "../../shared/components";
import {
  datePresetOptions,
  isNodeOverviewItem,
  modeOptions,
  overviewStatusCounts,
  overviewStatuses,
  parseTaskOverviewFilters,
  quadrantOptions,
  taskOverviewSearchParams,
  type TaskOverviewFilters,
} from "./api";
import { useTaskOverview } from "./hooks";
import "./TaskOverviewPage.css";

const scrollKey = "smarttaskboard.task-overview.scroll";

const statusLabels: Record<string, string> = {
  draft: "草稿",
  pending_confirmation: "待确认",
  pending_acceptance: "待接受",
  pending_confirm: "待确认",
  pending_accept: "待接受",
  returned: "已退回",
  decomposing: "AI拆解中",
  decomposition_failed: "拆解失败",
  in_progress: "进行中",
  blocked: "受阻",
  pending_report: "待汇报",
  pending_review: "待验收",
  completed: "已完成",
  archived: "已归档",
  cancelled: "已取消",
  withdrawn: "已撤回",
  merged: "已合并",
  closed: "已关闭",
};

const nodeStatusLabels: Record<string, string> = {
  pending: "未开始",
  in_progress: "进行中",
  completed: "已完成",
};

function formatDateTime(value: string | null): string {
  if (!value) return "未设置";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "未设置";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function statusLabel(value: string) {
  return statusLabels[value] ?? value;
}

function resetPage(filters: TaskOverviewFilters): TaskOverviewFilters {
  return { ...filters, page: 1 };
}

function taskTarget(taskId: string, nodeId?: string) {
  const encodedTaskId = encodeURIComponent(taskId);
  return nodeId ? `/task/${encodedTaskId}#node-${encodeURIComponent(nodeId)}` : `/task/${encodedTaskId}`;
}

function LoadingOverview() {
  return (
    <section className="stb-task-overview stb-task-overview--loading" aria-label="正在加载任务概览">
      <Skeleton height={86} />
      <Skeleton height={116} />
      <Skeleton height={180} />
      <Skeleton height={180} />
    </section>
  );
}

function StatusCounts({
  activeStatus,
  counts,
  onSelect,
}: {
  activeStatus: TaskStatus | "";
  counts: Record<string, number>;
  onSelect: (status: TaskStatus) => void;
}) {
  return (
    <section className="stb-task-overview-status" aria-labelledby="overview-status-title">
      <Typography variant="sectionTitle" as="h2" className="stb-task-overview-status__title">
        状态概览
      </Typography>
      <div id="overview-status-title" className="stb-visually-hidden">状态概览</div>
      <div className="stb-task-overview-counts">
        {overviewStatusCounts.map((status) => (
          <button
            key={status}
            className={`stb-task-overview-count ${activeStatus === status ? "stb-task-overview-count--active" : ""}`}
            type="button"
            aria-pressed={activeStatus === status}
            onClick={() => onSelect(status)}
          >
            <span>{statusLabel(status)}任务</span>
            <strong>{counts[status] ?? 0}</strong>
          </button>
        ))}
      </div>
    </section>
  );
}

function ModeTabs({
  mode,
  onChange,
}: {
  mode: TaskOverviewFilters["mode"];
  onChange: (mode: TaskOverviewFilters["mode"]) => void;
}) {
  return (
    <div className="stb-task-overview-tabs" role="tablist" aria-label="任务概览模式">
      {modeOptions.map((item) => (
        <button
          key={item.value}
          type="button"
          role="tab"
          aria-selected={mode === item.value}
          className={mode === item.value ? "stb-task-overview-tab stb-task-overview-tab--active" : "stb-task-overview-tab"}
          onClick={() => onChange(item.value)}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}

function FilterSummary({ filters, onReset }: { filters: TaskOverviewFilters; onReset: () => void }) {
  const labels = [
    filters.mode === "nodes" ? "我的节点任务" : "",
    filters.status ? statusLabel(filters.status) : "",
    filters.quadrant ? quadrantOptions.find((item) => item.value === filters.quadrant)?.label : "",
    filters.support ? "需要支持" : "",
    filters.nearDue ? "未来3天临期" : "",
    filters.datePreset === "week" ? "本周开始" : "",
    filters.datePreset === "month" ? "本月开始" : "",
    filters.datePreset === "custom" && filters.startDate && filters.endDate ? `${filters.startDate} 至 ${filters.endDate}` : "",
    filters.search ? `搜索：${filters.search}` : "",
    filters.source === "executive" && filters.employeeNo ? `员工：${filters.employeeName || filters.employeeNo}` : "",
  ].filter(Boolean);

  if (labels.length === 0) {
    return <Typography variant="caption" as="p">当前显示全部可见任务。</Typography>;
  }

  return (
    <div className="stb-task-overview-filter-summary" aria-label="当前筛选">
      {labels.map((label) => <Badge key={label} tone="info">{label}</Badge>)}
      <Button variant="ghost" onClick={onReset}>重置筛选</Button>
    </div>
  );
}

function TaskCard({ task }: { task: TaskSummary }) {
  const location = useLocation();
  const progress = Math.min(100, Math.max(0, task.progress_percent ?? 0));
  return (
    <Link className="stb-task-overview-card" to={taskTarget(task.task_id)} state={{ source: createReturnSource(location, "任务概览") }}>
      <span className="stb-task-overview-card__head"><Badge tone={task.is_overdue ? "danger" : "info"}>{statusLabel(task.status)}</Badge><span>{task.task_no ?? "未编号"}</span></span>
      <strong>{task.task_name}</strong>
      <span className="stb-task-overview-card__meta"><span>承办：{task.main_assignee?.name ?? "未指定"}</span><span>截止：{formatDateTime(task.deadline)}</span></span>
      <Progress value={progress} label="任务进度" />
    </Link>
  );
}

function NodeTaskCard({ node }: { node: TaskOverviewNode }) {
  const location = useLocation();
  return (
    <Link
      className="stb-task-overview-card stb-task-overview-card--node"
      to={taskTarget(node.task_id, node.node_id)}
      state={{ source: createReturnSource(location, "任务概览"), nodeId: node.node_id }}
    >
      <span className="stb-task-overview-node-parent">所属任务 · {node.task_name}</span>
      <span className="stb-task-overview-card__head">
        <Badge tone={node.is_overdue ? "danger" : "success"}>{nodeStatusLabels[node.status] ?? node.status}</Badge>
        <span>{statusLabel(node.task_status)}</span>
      </span>
      <strong>{node.node_name}</strong>
      <Progress value={node.progress_percent} label="节点进度" />
      <span className="stb-task-overview-card__meta">
        <span>负责人：{node.owner?.name ?? "未指定"}</span>
        <span>截止：{formatDateTime(node.planned_deadline)}</span>
      </span>
    </Link>
  );
}

function FilterSheet({
  open, filters, members, onClose, onApply, onReset,
}: {
  open: boolean; filters: TaskOverviewFilters; members: ExecutiveMember[]; onClose: () => void; onApply: (filters: TaskOverviewFilters) => void; onReset: () => void;
}) {
  const [draft, setDraft] = useState(filters);
  useEffect(() => { if (open) setDraft(filters); }, [open, filters]);
  function patch(value: Partial<TaskOverviewFilters>) { setDraft((current) => ({ ...current, ...value })); }
  function apply() {
    if (draft.datePreset === "custom" && (!draft.startDate || !draft.endDate)) return;
    if (draft.datePreset === "custom" && draft.startDate > draft.endDate) return;
    onApply(resetPage({ ...draft, startDate: draft.datePreset === "custom" ? draft.startDate : "", endDate: draft.datePreset === "custom" ? draft.endDate : "" }));
  }
  const choices = (items: Array<{ value: string; label: string }>, value: string, onChange: (value: string) => void) => <div className="stb-task-filter__choices">{items.map((item) => <button key={item.value || "all"} type="button" className={value === item.value ? "is-active" : ""} onClick={() => onChange(item.value)}>{item.label}</button>)}</div>;
  return (
    <Sheet open={open} title="任务筛选" onClose={onClose}>
      <div className="stb-task-filter">
        {filters.source === "executive" ? <div className="stb-task-filter__group"><b>员工姓名</b><small>仅显示当前高管授权部门范围内的员工</small>{choices([{ value: "", label: "全部员工" }, ...members.map((member) => ({ value: member.employee_no, label: member.name }))], draft.employeeNo, (employeeNo) => { const member = members.find((item) => item.employee_no === employeeNo); patch({ employeeNo, employeeName: member?.name ?? "", mode: "tasks" }); })}</div> : <>
          <label><span>搜索</span><input value={draft.search} onChange={(event) => patch({ search: event.target.value })} placeholder="任务或节点名称" /></label>
          <div className="stb-task-filter__group"><b>任务类型</b>{choices(modeOptions, draft.mode, (value) => patch({ mode: value as TaskOverviewFilters["mode"] }))}</div>
        </>}
        <div className="stb-task-filter__group"><b>任务状态</b>{choices([{ value: "", label: "全部" }, ...overviewStatuses], draft.status, (value) => patch({ status: value as TaskOverviewFilters["status"] }))}</div>
        <div className="stb-task-filter__group"><b>优先级四象限</b>{choices([{ value: "", label: "全部" }, ...quadrantOptions], draft.quadrant, (value) => patch({ quadrant: value as TaskOverviewFilters["quadrant"] }))}</div>
        {filters.source !== "executive" && <><label className="stb-task-filter__check"><input type="checkbox" checked={draft.nearDue} onChange={(event) => patch({ nearDue: event.target.checked })}/><span>仅看未来3天临期</span></label><label className="stb-task-filter__check"><input type="checkbox" checked={draft.support === "open"} onChange={(event) => patch({ support: event.target.checked ? "open" : "" })}/><span>需要支持</span></label></>}
        <div className="stb-task-filter__group"><b>开始时间</b>{choices(datePresetOptions, draft.datePreset, (value) => patch({ datePreset: value as TaskOverviewFilters["datePreset"] }))}{draft.datePreset === "custom" && <div className="stb-task-filter__dates"><label><span>开始日期</span><input type="date" value={draft.startDate} onChange={(event) => patch({ startDate: event.target.value })}/></label><label><span>结束日期</span><input type="date" value={draft.endDate} onChange={(event) => patch({ endDate: event.target.value })}/></label></div>}</div>
        {filters.source !== "executive" && <div className="stb-task-filter__dates"><label><span>排序</span><select value={draft.sortBy} onChange={(event) => patch({ sortBy: event.target.value as TaskOverviewFilters["sortBy"] })}><option value="deadline">截止时间</option><option value="created_at">创建时间</option><option value="updated_at">更新时间</option><option value="status">状态</option><option value="task_weight">权重</option></select></label><label><span>顺序</span><select value={draft.sortOrder} onChange={(event) => patch({ sortOrder: event.target.value as TaskOverviewFilters["sortOrder"] })}><option value="asc">升序</option><option value="desc">降序</option></select></label></div>}
        <div className="stb-task-filter__actions"><Button variant="secondary" onClick={onReset}>重置</Button><Button onClick={apply}>应用筛选</Button></div>
      </div>
    </Sheet>
  );
}

export function TaskOverviewPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();
  const [filterOpen, setFilterOpen] = useState(false);
  const filters = useMemo(() => parseTaskOverviewFilters(searchParams), [searchParams]);
  const query = useTaskOverview(filters);
  const executiveMembers = useQuery({
    queryKey: ["executive-members", filters.departmentId],
    queryFn: () => listExecutiveMembers(filters.departmentId || null),
    enabled: filters.source === "executive",
  });

  useEffect(() => {
    const saved = sessionStorage.getItem(scrollKey);
    if (saved) requestAnimationFrame(() => window.scrollTo(0, Number(saved) || 0));
    return () => {
      sessionStorage.setItem(scrollKey, String(window.scrollY));
    };
  }, []);

  function applyFilters(next: TaskOverviewFilters) {
    setSearchParams(taskOverviewSearchParams(next));
    setFilterOpen(false);
  }

  function resetFilters() {
    applyFilters({
      ...filters, mode: "tasks", status: "", quadrant: "", support: "", nearDue: false, datePreset: "all",
      startDate: "", endDate: "", search: "", page: 1, sortBy: "deadline", sortOrder: "asc",
    });
  }

  function updateFilters(patch: Partial<TaskOverviewFilters>) {
    applyFilters(resetPage({ ...filters, ...patch }));
  }

  function setPage(page: number) {
    setSearchParams(taskOverviewSearchParams({ ...filters, page }));
  }

  const total = query.data?.total ?? 0;
  const maxPage = Math.max(1, Math.ceil(total / filters.pageSize));
  const items = query.data?.items ?? [];

  if (query.isLoading) return <LoadingOverview />;

  return (
    <section className="stb-task-overview" data-testid="task-overview-page">
      {filters.source !== "executive" && <StatusCounts
        activeStatus={filters.status}
        counts={query.data?.status_counts ?? {}}
        onSelect={(status) => updateFilters({ mode: "tasks", status })}
      />}
      <Card className="stb-task-overview-panel">
        <div className="stb-task-overview-toolbar">
          <div>
            <Typography variant="sectionTitle" as="h2">任务信息管理</Typography>
            <Typography variant="caption" as="p">
              {filters.mode === "nodes" ? "节点" : "任务"}结果 {total} 项
            </Typography>
          </div>
          <Button variant="secondary" onClick={() => setFilterOpen(true)}>更多筛选</Button>
        </div>
        {filters.source !== "executive" && <ModeTabs mode={filters.mode} onChange={(mode) => updateFilters({ mode })} />}
        {filters.source !== "executive" && <div className="stb-task-overview-quick-status" aria-label="状态快捷筛选">
          {overviewStatusCounts.map((status) => (
            <button
              key={status}
              type="button"
              aria-pressed={filters.mode === "tasks" && filters.status === status}
              onClick={() => updateFilters({ mode: "tasks", status })}
            >
              {statusLabel(status)}
            </button>
          ))}
        </div>}
        <FilterSummary filters={filters} onReset={resetFilters} />
        {query.isError && (
          <ErrorState
            title={query.error instanceof ApiError && query.error.status === 403 ? "无权查看该员工任务" : "任务概览暂时无法加载"}
            detail={query.error instanceof ApiError ? query.error.message : "请检查筛选条件后重试。"}
            action={<Button variant="secondary" onClick={() => void query.refetch()}>重试</Button>}
          />
        )}
        {!query.isError && items.length === 0 && (
          <EmptyState title={`当前筛选条件下暂无${filters.mode === "nodes" ? "节点" : "任务"}`} detail="清空筛选后可查看全部可见结果。" action={<Button variant="secondary" onClick={resetFilters}>重置筛选</Button>} />
        )}
        {!query.isError && items.length > 0 && (
          <div className="stb-task-overview-list">
            {items.map((item) => (
              isNodeOverviewItem(item)
                ? <NodeTaskCard key={item.node_id} node={item} />
                : <TaskCard key={item.task_id} task={item} />
            ))}
          </div>
        )}
        {!query.isError && total > filters.pageSize && (
          <nav className="stb-task-overview-pagination" aria-label="任务分页">
            <Button variant="secondary" disabled={filters.page <= 1} onClick={() => setPage(Math.max(1, filters.page - 1))}>上一页</Button>
            <span>{filters.page} / {maxPage}</span>
            <Button variant="secondary" disabled={filters.page >= maxPage} onClick={() => setPage(Math.min(maxPage, filters.page + 1))}>下一页</Button>
          </nav>
        )}
      </Card>
      <FilterSheet
        open={filterOpen}
        filters={filters}
        members={executiveMembers.data ?? []}
        onClose={() => setFilterOpen(false)}
        onApply={applyFilters}
        onReset={resetFilters}
      />
    </section>
  );
}

/**
 * Feature: Test16-equivalent H5 executive dashboard.
 * Responsibilities: render authorized metrics, quadrants, workload heatmap, workload sheet, and employee-task drilldown.
 * Does not own: KPI formulas, workload formulas, task-scope authorization, or employee filtering rules.
 * H5 migration: page 13 executive dashboard.
 */

import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { getExecutiveOverview } from "../../api/endpoints";
import type { ExecutiveOverview } from "../../api/types";
import { createReturnSource } from "../../app/return-state";
import { Badge, Button, Card, ErrorState, Sheet, Skeleton, Typography } from "../../shared/components";
import "./executive-dashboard.css";

type HeatmapMember = ExecutiveOverview["workload_heatmap"]["members"][number];
type HeatmapCell = HeatmapMember["cells"][number];
type SelectedCell = { member: HeatmapMember; cell: HeatmapCell } | null;

const quadrantMeta = [
  ["important_urgent", "重要且紧急", "danger"],
  ["important_not_urgent", "重要不紧急", "warning"],
  ["not_important_urgent", "紧急不重要", "amber"],
  ["not_important_not_urgent", "常规任务", "teal"],
] as const;

const levelLabels: Record<string, string> = {
  idle: "空闲",
  normal: "正常",
  busy: "偏忙",
  overloaded: "过载",
  low: "空闲",
  medium: "偏忙",
  high: "过载",
};

function percent(value: number | null) {
  if (value === null || value === undefined) return "--";
  return `${Number(value).toFixed(Number(value) % 1 ? 1 : 0)}%`;
}

function metric(value: number | null | undefined) {
  if (value === null || value === undefined) return "--";
  return Number(value).toFixed(Number(value) % 1 ? 1 : 0);
}

function levelTone(level: string | null): "success" | "warning" | "danger" | "neutral" {
  if (!level) return "neutral";
  if (["overloaded", "high", "严重过载", "过载"].includes(level)) return "danger";
  if (["busy", "medium", "偏忙"].includes(level)) return "warning";
  return "success";
}

function shortDate(value: string) {
  const match = /^(?:\d{4})-(\d{2})-(\d{2})/.exec(value);
  return match ? `${match[1]}/${match[2]}` : value;
}

export function ExecutiveDashboardPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [departmentId, setDepartmentId] = useState("");
  const [period, setPeriod] = useState<"week" | "month">("week");
  const [departmentSheetOpen, setDepartmentSheetOpen] = useState(false);
  const [selected, setSelected] = useState<SelectedCell>(null);
  const query = useQuery({
    queryKey: ["executive-overview", departmentId, period],
    queryFn: () => getExecutiveOverview(departmentId || null, period),
  });
  const data = query.data;
  const departments = data?.scope.departments ?? [];
  const selectedDepartmentName = useMemo(
    () => departments.find((item) => item.department_id === departmentId)?.department_name || "全部授权部门",
    [departments, departmentId],
  );

  function goTasks(extra: Record<string, string>) {
    const params = new URLSearchParams({
      source: "executive",
      mode: "tasks",
      period,
      datePreset: period,
      ...extra,
    });
    if (departmentId) params.set("departmentId", departmentId);
    navigate(`/tasks?${params.toString()}`, {
      state: { source: createReturnSource(location, "团队任务态势") },
    });
  }

  if (query.isLoading) {
    return (
      <section className="stb-executive stb-executive--loading" aria-label="正在计算团队态势">
        <Skeleton height={150} />
        <Skeleton height={210} />
        <Skeleton height={250} />
      </section>
    );
  }

  if (query.isError || !data) {
    return (
      <ErrorState
        title="团队态势暂时无法加载"
        detail="请确认当前账号拥有有效授权范围；服务端未授权的数据不会返回。"
        action={
          <div className="stb-executive-error-actions">
            <Button variant="secondary" onClick={() => void query.refetch()}>重试</Button>
            <Button variant="ghost" onClick={() => navigate("/profile")}>返回我的</Button>
          </div>
        }
      />
    );
  }

  return (
    <section className="stb-executive" data-testid="executive-dashboard-page">
      <header className="stb-executive-head">
        <div className="stb-executive-title-row">
          <span className="stb-executive-eyebrow">EXECUTIVE VIEW</span>
          <h1>团队任务态势</h1>
          <p>仅展示服务端授权的负责部门数据</p>
        </div>
        <div className="stb-executive-filters">
          <button type="button" className="stb-executive-department" onClick={() => setDepartmentSheetOpen(true)}>
            <span>{selectedDepartmentName}</span><span aria-hidden="true">⌄</span>
          </button>
          <div className="stb-executive-period" role="tablist" aria-label="统计周期">
            <button type="button" role="tab" aria-selected={period === "week"} className={period === "week" ? "is-active" : ""} onClick={() => setPeriod("week")}>本周</button>
            <button type="button" role="tab" aria-selected={period === "month"} className={period === "month" ? "is-active" : ""} onClick={() => setPeriod("month")}>本月</button>
          </div>
        </div>
      </header>

      <section className="stb-executive-metrics" aria-label="团队指标">
        <Card><Typography variant="caption">进行中</Typography><Typography variant="metric">{data.metrics.active_tasks.count}</Typography><small>执行态任务</small></Card>
        <Card className="stb-executive-metric--teal"><Typography variant="caption">按期率</Typography><Typography variant="metric">{percent(data.metrics.on_time_rate.rate)}</Typography><small>周期内完成</small></Card>
        <Card><Typography variant="caption">KPI关联</Typography><Typography variant="metric">{data.metrics.kpi_links.linked_task_count}</Typography><small>涉及{data.metrics.kpi_links.linked_metric_count}项绩效指标</small></Card>
        <Card><Typography variant="caption">总体进度</Typography><Typography variant="metric">{percent(data.metrics.overall_progress.rate)}</Typography><small>按任务权重加权</small></Card>
      </section>

      <section className="stb-executive-section">
        <div className="stb-executive-section-head"><h2>团队任务四象限</h2><span>点击查看对应任务</span></div>
        <div className="stb-executive-quadrants">
          {quadrantMeta.map(([key, label, tone]) => (
            <button key={key} type="button" className={`stb-executive-quadrant stb-executive-quadrant--${tone}`} onClick={() => goTasks({ quadrant: key })}>
              <i aria-hidden="true" />
              <span><strong>{data.quadrants[key]}</strong><small>{label}</small></span>
              <b aria-hidden="true">›</b>
            </button>
          ))}
        </div>
        {data.quadrants.unscored_count > 0 && <Typography variant="caption">另有 {data.quadrants.unscored_count} 项任务暂无四象限评分。</Typography>}
      </section>

      <section className="stb-executive-section">
        <div className="stb-executive-section-head"><h2>团队负荷热力图</h2><span>点击有数据的格子查看构成</span></div>
        {data.workload_heatmap.members.length === 0 ? (
          <Card><Typography variant="secondary">当前授权范围暂无员工负荷快照。</Typography></Card>
        ) : (
          <Card className="stb-executive-heat-card">
            <div className="stb-heatmap-scroll">
              <table className="stb-executive-heatmap">
                <thead><tr><th>成员</th>{data.workload_heatmap.days.map((day) => <th key={day.date}><span>{day.label}</span><small>{shortDate(day.date)}</small></th>)}</tr></thead>
                <tbody>{data.workload_heatmap.members.map((member) => <tr key={member.employee_no}>
                  <th><span className="stb-executive-member"><i>{member.name.slice(-1)}</i><span><b>{member.name}</b><small>{member.employee_no}</small></span></span></th>
                  {member.cells.map((cell) => <td key={cell.date}><button type="button" className={`stb-heat stb-heat--${cell.workload_level || "empty"}`} onClick={() => setSelected({ member, cell })} disabled={!cell.snapshot_id}>{cell.workload_score === null ? "–" : metric(cell.workload_score)}</button></td>)}
                </tr>)}</tbody>
              </table>
            </div>
          </Card>
        )}
        <div className="stb-executive-legend" aria-label="负荷等级图例"><span><i className="idle"/>空闲 ≤40</span><span><i className="normal"/>正常 ≤70</span><span><i className="busy"/>偏忙 ≤90</span><span><i className="overloaded"/>过载 &gt;90</span></div>
        {data.metrics.overall_progress.data_quality_issue_count > 0 && <div className="stb-executive-quality">发现 {data.metrics.overall_progress.data_quality_issue_count} 条待验收任务进度数据异常，当前值未被看板强制改写。</div>}
      </section>

      <Sheet open={departmentSheetOpen} title="选择部门" onClose={() => setDepartmentSheetOpen(false)}>
        <div className="stb-executive-department-list">
          <button type="button" className={!departmentId ? "is-active" : ""} onClick={() => { setDepartmentId(""); setDepartmentSheetOpen(false); }}>全部授权部门</button>
          {departments.map((item) => <button type="button" key={item.department_id} className={departmentId === item.department_id ? "is-active" : ""} onClick={() => { setDepartmentId(item.department_id); setDepartmentSheetOpen(false); }}>{item.department_name}</button>)}
        </div>
      </Sheet>

      <Sheet open={Boolean(selected)} title={selected ? `${selected.member.name} · 负荷构成` : "负荷构成"} onClose={() => setSelected(null)}>
        {selected && <div className="stb-workload-sheet">
          <Typography variant="caption">{selected.cell.date}</Typography>
          <div className="stb-workload-summary">
            <div><span>综合负荷</span><strong>{selected.cell.workload_score === null ? "--" : metric(selected.cell.workload_score)}</strong></div>
            <div><span>负荷等级</span><Badge tone={levelTone(selected.cell.workload_level)}>{levelLabels[selected.cell.workload_level || ""] || selected.cell.workload_level || "无等级"}</Badge></div>
          </div>
          <dl><div><dt>剩余工时压力</dt><dd>{metric(selected.cell.hours_pressure)}</dd></div><div><dt>任务权重压力</dt><dd>{metric(selected.cell.weight_pressure)}</dd></div><div><dt>任务数量压力</dt><dd>{metric(selected.cell.count_pressure)}</dd></div><div><dt>突发任务压力</dt><dd>{metric(selected.cell.urgent_pressure)}</dd></div><div><dt>受阻/逾期压力</dt><dd>{metric(selected.cell.blocked_overdue_pressure)}</dd></div></dl>
          <div className="stb-workload-facts"><span>执行任务 {selected.cell.active_task_count || 0}</span><span>突发 {selected.cell.urgent_task_count || 0}</span><span>受阻 {selected.cell.blocked_task_count || 0}</span><span>逾期 {selected.cell.overdue_task_count || 0}</span></div>
          <Button onClick={() => { goTasks({ employeeNo: selected.member.employee_no, employeeName: selected.member.name }); setSelected(null); }}>查看该员工任务</Button>
        </div>}
      </Sheet>
    </section>
  );
}

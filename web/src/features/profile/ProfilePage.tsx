/**
 * Feature: Test16-equivalent H5 personal profile summary.
 * Responsibilities: show server identity, related-task count, current action-required count, archived count, and the four task relationship explanations.
 * Does not own: role switching, demo-data reset, identity administration, or task authorization.
 * H5 migration: page 12 profile.
 */

import { useQuery } from "@tanstack/react-query";

import { listNotifications, listTasks } from "../../api/endpoints";
import { useAuth } from "../../auth/useAuth";
import { Badge, ErrorState, Skeleton } from "../../shared/components";
import "./profile.css";

export function ProfilePage() {
  const { user } = useAuth();
  const tasks = useQuery({ queryKey: ["profile-related-tasks"], queryFn: () => listTasks({ mode: "tasks", page: 1, pageSize: 100 }) });
  const archived = useQuery({ queryKey: ["profile-archived-tasks"], queryFn: () => listTasks({ mode: "tasks", status: "archived", page: 1, pageSize: 1 }) });
  const notifications = useQuery({ queryKey: ["profile-notifications"], queryFn: () => listNotifications(false) });

  if (!user) return <ErrorState title="尚未登录" detail="请从企业微信应用入口重新进入。" />;

  const executive = user.permissions.can_access_executive;
  const actionCount = (notifications.data ?? []).filter((item) => item.action_required).length;
  const partialError = tasks.isError || archived.isError || notifications.isError;

  return (
    <section className="stb-profile" data-testid="profile-page">
      <header className="stb-profile-head"><span>PROFILE</span><h1>我的</h1><p>身份、任务关系与使用设置</p></header>

      <section className="stb-profile-card">
        <div className="stb-profile-avatar">{user.name ? user.name.slice(-1) : "序"}</div>
        <div className="stb-profile-copy">
          <strong>{user.name}</strong>
          <span>{user.employee_no} · {user.department?.department_name || "未分配部门"}</span>
          <Badge tone={executive ? "info" : "success"}>{executive ? "高管权限" : "员工"}</Badge>
        </div>
      </section>

      <section className="stb-profile-metrics" aria-label="个人任务摘要">
        <div>{tasks.isLoading ? <Skeleton height={28} /> : <strong>{tasks.data?.total ?? 0}</strong>}<span>关联任务</span></div>
        <div>{notifications.isLoading ? <Skeleton height={28} /> : <strong>{actionCount}</strong>}<span>待我处理</span></div>
        <div>{archived.isLoading ? <Skeleton height={28} /> : <strong>{archived.data?.total ?? 0}</strong>}<span>已归档</span></div>
      </section>

      <section className="stb-profile-relations">
        <h2>任务关系说明</h2>
        <div className="stb-profile-relation-card">
          <div><span className="blue">创</span><strong>我创建的任务</strong></div>
          <div><span className="teal">承</span><strong>我主承办的任务</strong></div>
          <div><span className="orange">协</span><strong>我协同的任务</strong></div>
          <div><span className="green">验</span><strong>待我验收的任务</strong></div>
        </div>
      </section>

      {partialError && <ErrorState title="部分个人摘要加载失败" detail="身份信息不受影响，可继续使用任务功能；下次进入页面会重新加载。" />}

      <div className="stb-profile-version">旺序AI任务中枢 · H5 V1.1</div>
    </section>
  );
}

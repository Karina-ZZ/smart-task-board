/**
 * Feature: Test16-equivalent H5 notification center and deep-link routing.
 * Responsibilities: filter current-user notifications by type, show action-required state, mark opened items read, and route by server-resolved target.
 * Does not own: notification recipients, task authorization, reminder scheduling, or business permissions.
 * H5 migration: page 11 notifications.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { listNotifications, markNotificationRead } from "../../api/endpoints";
import type { NotificationItem } from "../../api/types";
import { createReturnSource } from "../../app/return-state";
import { Button, Dialog, EmptyState, ErrorState, Skeleton, useToast } from "../../shared/components";
import "./notifications.css";

type NotificationType = "all" | "task" | "reminder" | "system";

const tabs: Array<{ code: NotificationType; label: string }> = [
  { code: "all", label: "全部" },
  { code: "task", label: "任务" },
  { code: "reminder", label: "提醒" },
  { code: "system", label: "系统" },
];
const tabStorageKey = "smarttaskboard.notifications.tab";
const scrollStorageKey = "smarttaskboard.notifications.scroll";

function timeText(value: string | null | undefined) {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }).format(date);
}

function notificationIcon(type: string) {
  return type === "task" ? "任" : type === "reminder" ? "醒" : "系";
}

export function NotificationsPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [type, setType] = useState<NotificationType>(() => (sessionStorage.getItem(tabStorageKey) as NotificationType) || "all");
  const [systemNotice, setSystemNotice] = useState<NotificationItem | null>(null);
  const query = useQuery({ queryKey: ["notifications"], queryFn: () => listNotifications(false) });

  useEffect(() => {
    const saved = Number(sessionStorage.getItem(scrollStorageKey) || "0");
    if (saved) requestAnimationFrame(() => window.scrollTo(0, saved));
    return () => sessionStorage.setItem(scrollStorageKey, String(window.scrollY));
  }, []);

  const visible = useMemo(
    () => (query.data ?? []).filter((item) => type === "all" || item.notification_type === type),
    [query.data, type],
  );

  const markRead = useMutation({
    mutationFn: (item: NotificationItem) => item.read_at ? Promise.resolve(item) : markNotificationRead(item.notification_id),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["notifications"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard"] }),
      ]);
    },
    onError: () => toast.show("通知状态更新失败，请稍后重试。"),
  });

  function selectTab(next: NotificationType) {
    setType(next);
    sessionStorage.setItem(tabStorageKey, next);
  }

  async function openNotification(item: NotificationItem) {
    if (item.can_open === false) {
      toast.show(item.unavailable_reason || "当前无法打开该事项");
      return;
    }
    await markRead.mutateAsync(item).catch(() => undefined);
    if (!item.task_id) {
      setSystemNotice(item);
      return;
    }
    const returnState = { source: createReturnSource(location, "通知中心") };
    const nodeHash = item.node_id ? `#node-${item.node_id}` : "";
    if (item.target_type === "node_assignment") {
      navigate(`/task/${item.task_id}${nodeHash}`, returnState);
    } else if (item.target_type === "decomposition") {
      navigate(`/task/${item.task_id}/decomposition`, returnState);
    } else if (item.target_type === "report") {
      navigate(`/task/${item.task_id}/report`, returnState);
    } else if (item.target_type === "review") {
      navigate(`/task/${item.task_id}/review`, returnState);
    } else {
      navigate(`/task/${item.task_id}${nodeHash}`, returnState);
    }
  }

  if (query.isLoading) return <section className="stb-notifications"><Skeleton height={70} /><Skeleton height={46} /><Skeleton height={120} /><Skeleton height={120} /></section>;
  if (query.isError) return <ErrorState title="通知加载失败" detail="请稍后重试。" action={<Button variant="secondary" onClick={() => void query.refetch()}>重试</Button>} />;

  return (
    <section className="stb-notifications" data-testid="notifications-page">
      <header className="stb-notifications-head"><span>NOTIFICATIONS</span><h1>通知中心</h1><p>任务、提醒与系统消息</p></header>
      <nav className="stb-notification-tabs" aria-label="通知分类">
        {tabs.map((tab) => <button key={tab.code} type="button" className={type === tab.code ? "selected" : ""} aria-pressed={type === tab.code} onClick={() => selectTab(tab.code)}>{tab.label}</button>)}
      </nav>

      {visible.length === 0 ? (
        <EmptyState title="当前分类暂无消息" detail="新的任务、节点承接、临期和验收提醒会显示在这里。" />
      ) : (
        <div className="stb-notification-list">
          {visible.map((item) => (
            <button
              key={item.notification_id}
              className={`stb-notification-item${item.action_required ? " stb-notification-item--unread" : ""}`}
              type="button"
              onClick={() => void openNotification(item)}
              disabled={markRead.isPending}
            >
              <span className={`stb-notification-icon stb-notification-icon--${item.notification_type}`}>{notificationIcon(item.notification_type)}</span>
              <span className="stb-notification-main">
                <span className="stb-notification-title"><strong>{item.title}</strong>{item.action_required && <i />}{item.action_required && <em>待处理</em>}</span>
                <span className="stb-notification-content">{item.content}</span>
                {item.can_open === false && <span className="stb-notification-unavailable">{item.unavailable_reason || "当前已无法打开"}</span>}
                <small>{timeText(item.sent_at || item.created_at)}</small>
              </span>
              <span className="stb-notification-arrow">›</span>
            </button>
          ))}
        </div>
      )}

      <Dialog open={Boolean(systemNotice)} title={systemNotice?.title || "系统通知"} onClose={() => setSystemNotice(null)} actions={<Button onClick={() => setSystemNotice(null)}>知道了</Button>}>
        <p className="stb-system-notice-content">{systemNotice?.content || "无补充内容"}</p>
      </Dialog>
    </section>
  );
}

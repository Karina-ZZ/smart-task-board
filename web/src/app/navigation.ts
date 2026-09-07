/**
 * Feature: V1.1 route and navigation contracts.
 * Responsibilities: keep target route metadata, bottom navigation projection, active state, and role checks in the app layer.
 * Does not own: shared component rendering, business page data, or backend authorization decisions.
 * Plan task: DEV-02.
 */

import type { CurrentUser } from "../api/types";

export type NavigationItemId = "workbench" | "executive" | "tasks" | "notifications" | "profile";

export interface ShellNavigationItem {
  id: NavigationItemId;
  label: string;
  to: string;
  icon: string;
  requiresExecutive?: boolean;
}

export interface RouteContract {
  id: string;
  path: string;
  title: string;
  subtitle: string;
  navId?: NavigationItemId;
  protected: boolean;
  executiveOnly?: boolean;
  backFallback?: string;
}

export const targetRouteContracts: RouteContract[] = [
  {
    id: "login",
    path: "/login",
    title: "登录",
    subtitle: "企业微信 H5 身份入口",
    protected: false,
  },
  {
    id: "workbench",
    path: "/workbench",
    title: "工作台",
    subtitle: "摘要、任务和快捷入口",
    navId: "workbench",
    protected: true,
  },
  {
    id: "executive",
    path: "/executive",
    title: "团队任务态势",
    subtitle: "团队指标、四象限与负荷热力图",
    navId: "executive",
    protected: true,
    executiveOnly: true,
  },
  {
    id: "tasks",
    path: "/tasks",
    title: "任务概览",
    subtitle: "筛选、分页和节点模式",
    navId: "tasks",
    protected: true,
  },
  {
    id: "task-detail",
    path: "/task/:taskId",
    title: "任务详情",
    subtitle: "概览、人员、节点、进度、绩效与真实操作",
    navId: "tasks",
    protected: true,
    backFallback: "/tasks",
  },
  {
    id: "task-report",
    path: "/task/:taskId/report",
    title: "提交进度汇报",
    subtitle: "进度汇报、卡点与资源处理",
    navId: "tasks",
    protected: true,
    backFallback: "/tasks",
  },
  {
    id: "task-review",
    path: "/task/:taskId/review",
    title: "任务验收",
    subtitle: "完成申请、验收与返工",
    navId: "tasks",
    protected: true,
    backFallback: "/tasks",
  },
  {
    id: "task-decomposition",
    path: "/task/:taskId/decomposition",
    title: "AI 拆解状态",
    subtitle: "承办人接受后自动 AI 拆解与失败重试",
    navId: "tasks",
    protected: true,
    backFallback: "/tasks",
  },
  {
    id: "create-start",
    path: "/create",
    title: "描述任务",
    subtitle: "创建任务 · 1/3",
    protected: true,
    backFallback: "/workbench",
  },
  {
    id: "create-details",
    path: "/create/details",
    title: "创建任务",
    subtitle: "AI录入、多轮追问与任务级字段确认",
    protected: true,
    backFallback: "/workbench",
  },
  {
    id: "create-confirm",
    path: "/create/confirm",
    title: "确认发送",
    subtitle: "绩效确认与最终发送",
    protected: true,
    backFallback: "/create/details",
  },
  {
    id: "notifications",
    path: "/notifications",
    title: "通知中心",
    subtitle: "任务、节点、临期与验收通知",
    navId: "notifications",
    protected: true,
  },
  {
    id: "profile",
    path: "/profile",
    title: "我的",
    subtitle: "当前员工身份、权限与个人摘要",
    navId: "profile",
    protected: true,
  },
  {
    id: "executive-employee-tasks",
    path: "/executive/employee-tasks",
    title: "员工负荷任务明细",
    subtitle: "兼容入口，统一回到任务概览员工筛选",
    navId: "executive",
    protected: true,
    executiveOnly: true,
    backFallback: "/executive",
  },
];

export const shellNavigationItems: ShellNavigationItem[] = [
  { id: "workbench", label: "工作台", to: "/workbench", icon: "⌂" },
  { id: "tasks", label: "任务", to: "/tasks", icon: "▤" },
  { id: "executive", label: "团队", to: "/executive", icon: "◫", requiresExecutive: true },
  { id: "notifications", label: "消息", to: "/notifications", icon: "◉" },
  { id: "profile", label: "我的", to: "/profile", icon: "◎" },
];

export function canAccessExecutiveRoutes(user: CurrentUser | null): boolean {
  return user?.permissions.can_access_executive === true;
}

export function visibleNavigationItems(user: CurrentUser | null): ShellNavigationItem[] {
  return shellNavigationItems.filter((item) => !item.requiresExecutive || canAccessExecutiveRoutes(user));
}

function matchPathname(pathname: string, path: string): boolean {
  if (path === pathname) return true;
  if (path === "/task/:taskId") return /^\/task\/[^/]+$/.test(pathname);
  if (path === "/task/:taskId/report") return /^\/task\/[^/]+\/report$/.test(pathname);
  if (path === "/task/:taskId/review") return /^\/task\/[^/]+\/review$/.test(pathname);
  if (path === "/task/:taskId/decomposition") return /^\/task\/[^/]+\/decomposition$/.test(pathname);
  return false;
}

export function findRouteContract(pathname: string): RouteContract | undefined {
  return targetRouteContracts.find((route) => matchPathname(pathname, route.path));
}

export function activeNavigationId(pathname: string): NavigationItemId {
  return findRouteContract(pathname)?.navId ?? "workbench";
}

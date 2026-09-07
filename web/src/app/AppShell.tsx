/**
 * Feature: V1.1 application shell.
 * Responsibilities: provide protected mobile layout, role-aware Test16 bottom navigation, route title projection, and route outlet.
 * Does not own: task APIs beyond the shared unread-notification projection, AI flows, workload calculations, or feature-page business logic.
 * Plan task: H5-MIGRATION-00.
 */

import { useQuery } from "@tanstack/react-query";
import { Outlet, useLocation, useNavigate } from "react-router-dom";

import { getDashboardSummary } from "../api/endpoints";
import { useAuth } from "../auth/useAuth";
import { BottomNavigation, Button, Skeleton, TopBar } from "../shared/components";
import { activeNavigationId, findRouteContract, visibleNavigationItems } from "./navigation";
import { createReturnSource, useReturnNavigation } from "./return-state";
import "./AppShell.css";

export function RouteLoadingState() {
  return (
    <div className="stb-route-shell__loading" role="status" aria-label="正在加载路由">
      <Skeleton height={44} />
      <Skeleton height={180} />
    </div>
  );
}

export function AppShell() {
  const { user } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const contract = findRouteContract(location.pathname);
  const navigation = visibleNavigationItems(user);
  const activeId = activeNavigationId(location.pathname);
  const returnNavigation = useReturnNavigation(contract?.backFallback ?? "/workbench");
  const summaryQuery = useQuery({
    queryKey: ["shell", "dashboard-summary"],
    queryFn: getDashboardSummary,
    staleTime: 30_000,
    retry: false,
  });
  const unread = summaryQuery.data?.unread_notification_count ?? 0;
  const isWorkbench = location.pathname === "/workbench";

  function selectNavigation(id: string) {
    const target = navigation.find((item) => item.id === id);
    if (!target || target.to === location.pathname) return;
    navigate(target.to, { state: { source: createReturnSource(location) } });
  }

  return (
    <div className="stb-route-shell" data-testid="app-shell">
      {!isWorkbench && (
        <TopBar
          title={contract?.title ?? "页面不存在"}
          subtitle={contract?.subtitle}
          leading={
            contract?.backFallback ? (
              <Button variant="ghost" iconOnly aria-label="返回" onClick={returnNavigation.goBack}>
                {"<"}
              </Button>
            ) : undefined
          }
          actions={
            <Button
              className="stb-route-shell__bell"
              variant="secondary"
              iconOnly
              aria-label={unread ? `消息，${unread} 条未读` : "消息"}
              onClick={() => navigate("/notifications", { state: { source: createReturnSource(location) } })}
            >
              <span aria-hidden="true">◉</span>
              {unread > 0 && <span className="stb-route-shell__bell-dot" aria-hidden="true" />}
            </Button>
          }
        />
      )}
      <main className={isWorkbench ? "stb-route-shell__content stb-route-shell__content--workbench" : "stb-route-shell__content"}>
        <Outlet />
      </main>
      <BottomNavigation
        activeId={activeId}
        onSelect={selectNavigation}
        items={navigation.map((item) => ({
          id: item.id,
          label: item.label,
          icon: <span className="stb-route-shell__nav-icon">{item.icon}</span>,
          badge: item.id === "notifications" ? unread : undefined,
        }))}
      />
    </div>
  );
}

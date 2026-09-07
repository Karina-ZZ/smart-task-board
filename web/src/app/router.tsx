/**
 * Feature: V1.1 target router.
 * Responsibilities: define formal routes, protected boundaries, role gates, and legacy redirects.
 * Does not own: business page implementations, auth APIs, or backend permission authority.
 * Plan task: DEV-02.
 * Hotfix: V1.1 Web Login Route.
 */

import { Navigate, Outlet, Route, Routes, useLocation, useParams } from "react-router-dom";

import { useAuth } from "../auth/useAuth";
import { TaskCompletionPage, TaskDetailPage, TaskReportPage, TaskReviewPage } from "../features/task-detail";
import { TaskDecompositionPage } from "../features/task-decomposition";
import { TaskConfirmPage } from "../features/task-create";
import { ExecutiveDashboardPage } from "../features/executive-dashboard";
import { NotificationsPage } from "../features/notifications";
import { ProfilePage } from "../features/profile";
import { TaskCreateDetailsPage, TaskCreateStartPage } from "../features/task-intake";
import { TaskOverviewPage } from "../features/task-overview";
import { LoginPage } from "../pages/LoginPage";
import { WeComCallbackPage } from "../pages/WeComCallbackPage";
import { WorkbenchPage } from "../features/workbench";
import { AppShell, RouteLoadingState } from "./AppShell";
import { canAccessExecutiveRoutes } from "./navigation";
import { createReturnSource } from "./return-state";
import { ForbiddenRoute, NotFoundRoute } from "./RoutePlaceholders";

function ProtectedLayout() {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) return <RouteLoadingState />;
  if (!user) {
    return (
      <Navigate
        to="/login"
        replace
        state={{ source: createReturnSource(location) }}
      />
    );
  }

  return <AppShell />;
}

function ExecutiveBoundary() {
  const { user } = useAuth();

  if (!canAccessExecutiveRoutes(user)) return <ForbiddenRoute />;
  return <Outlet />;
}

function LegacyTaskRedirect() {
  const { taskId } = useParams();
  return <Navigate to={`/task/${taskId ?? ""}`} replace />;
}

function LegacyExecutiveEmployeeTasksRedirect() {
  const location = useLocation();
  const search = new URLSearchParams(location.search);
  search.set("source", "executive");
  return <Navigate to={`/tasks?${search.toString()}`} replace />;
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/auth/wecom/callback" element={<WeComCallbackPage />} />
      <Route path="/" element={<Navigate to="/workbench" replace />} />
      <Route element={<ProtectedLayout />}>
        <Route path="/workbench" element={<WorkbenchPage />} />
        <Route element={<ExecutiveBoundary />}>
          <Route path="/executive" element={<ExecutiveDashboardPage />} />
          <Route path="/executive/employee-tasks" element={<LegacyExecutiveEmployeeTasksRedirect />} />
        </Route>
        <Route path="/tasks" element={<TaskOverviewPage />} />
        <Route path="/tasks/:taskId" element={<LegacyTaskRedirect />} />
        <Route path="/task/:taskId" element={<TaskDetailPage />} />
        <Route path="/task/:taskId/report" element={<TaskReportPage />} />
        <Route path="/task/:taskId/completion" element={<TaskCompletionPage />} />
        <Route path="/task/:taskId/review" element={<TaskReviewPage />} />
        <Route path="/task/:taskId/decomposition" element={<TaskDecompositionPage />} />
        <Route path="/create" element={<TaskCreateStartPage />} />
        <Route path="/create/details" element={<TaskCreateDetailsPage />} />
        <Route path="/create/confirm" element={<TaskConfirmPage />} />
        <Route path="/notifications" element={<NotificationsPage />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="*" element={<NotFoundRoute />} />
      </Route>
    </Routes>
  );
}

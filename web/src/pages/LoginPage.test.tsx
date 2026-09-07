/**
 * Feature: Web prototype login page tests.
 * Responsibilities: verify identity selection, safe return navigation, authenticated redirects, and error sanitization.
 * Does not own: backend token issuance, enterprise WeCom login, or protected route authorization.
 * Hotfix: V1.1 Web Login Route.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { session } from "../api/client";
import type { CurrentUser } from "../api/types";
import { AuthContext, type AuthValue } from "../auth/auth-context";
import { jsonResponse } from "../test/test-utils";
import { LoginPage } from "./LoginPage";

const users = [
  {
    employee_no: "E-CREATOR",
    name: "测试创建人",
    department_id: null,
    department_name: "测试部门",
    role_type: "employee",
  },
];

const authenticatedUser: CurrentUser = {
  employee_no: "E-CREATOR",
  name: "测试创建人",
  department: null,
  role_type: "employee",
  roles: ["employee"],
  permissions: {
    can_access_executive: false,
    can_manage_permissions: false,
    can_view_all_demo_data: false,
    allowed_routes: ["/workbench", "/tasks"],
    capabilities: ["task:read:related"],
  },
  scopes: [],
  auth_mode: "prototype",
};

function LocationProbe() {
  const location = useLocation();
  return (
    <output data-testid="location">
      {`${location.pathname}${location.search}${location.hash}`}
    </output>
  );
}

function renderLogin({
  login,
  user = null,
  state,
}: {
  login: AuthValue["login"];
  user?: CurrentUser | null;
  state?: unknown;
}) {
  const auth: AuthValue = { user, loading: false, login, logout: vi.fn() };
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  return render(
    <QueryClientProvider client={client}>
      <AuthContext.Provider value={auth}>
        <MemoryRouter initialEntries={[{ pathname: "/login", state }]}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="*" element={<div data-testid="destination" />} />
          </Routes>
          <LocationProbe />
        </MemoryRouter>
      </AuthContext.Provider>
    </QueryClientProvider>,
  );
}

describe("LoginPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    session.clear();
  });

  it("loads prototype users and signs in with the selected identity", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(users)));
    const login = vi.fn().mockResolvedValue(undefined);
    renderLogin({ login });
    const user = userEvent.setup();

    expect(screen.getByText(/仅用于隔离开发和演示/)).toBeInTheDocument();
    await user.selectOptions(await screen.findByLabelText("演示用户"), "E-CREATOR");
    await user.click(screen.getByRole("button", { name: "进入任务看板" }));

    expect(login).toHaveBeenCalledWith("E-CREATOR");
    await waitFor(() => {
      expect(screen.getByTestId("location")).toHaveTextContent("/workbench");
    });
  });

  it("returns to the safe source path including search and hash after login", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(users)));
    const login = vi.fn().mockResolvedValue(undefined);
    renderLogin({
      login,
      state: {
        source: {
          pathname: "/tasks",
          search: "?status=pending_accept",
          hash: "#list",
        },
      },
    });
    const user = userEvent.setup();

    await user.selectOptions(await screen.findByLabelText("演示用户"), "E-CREATOR");
    await user.click(screen.getByRole("button", { name: "进入任务看板" }));

    await waitFor(() => {
      expect(screen.getByTestId("location")).toHaveTextContent(
        "/tasks?status=pending_accept#list",
      );
    });
  });

  it("falls back to workbench when the source path is unsafe", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(users)));
    const login = vi.fn().mockResolvedValue(undefined);
    renderLogin({
      login,
      state: { source: { pathname: "https://example.invalid/phishing" } },
    });
    const user = userEvent.setup();

    await user.selectOptions(await screen.findByLabelText("演示用户"), "E-CREATOR");
    await user.click(screen.getByRole("button", { name: "进入任务看板" }));

    await waitFor(() => {
      expect(screen.getByTestId("location")).toHaveTextContent("/workbench");
    });
  });

  it("redirects an authenticated user without loading prototype identities", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    renderLogin({
      login: vi.fn(),
      user: authenticatedUser,
      state: { source: { pathname: "/tasks", search: "?page=2" } },
    });

    await waitFor(() => {
      expect(screen.getByTestId("location")).toHaveTextContent("/tasks?page=2");
    });
    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.queryByLabelText("演示用户")).not.toBeInTheDocument();
  });

  it("normalizes unknown login errors without exposing their contents", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(users)));
    const login = vi.fn().mockRejectedValue({ token: "secret-token", database: "internal" });
    renderLogin({ login });
    const user = userEvent.setup();

    await user.selectOptions(await screen.findByLabelText("演示用户"), "E-CREATOR");
    await user.click(screen.getByRole("button", { name: "进入任务看板" }));

    expect(await screen.findByText("登录失败，请稍后重试。")).toBeInTheDocument();
    expect(screen.queryByText(/secret-token|internal/)).not.toBeInTheDocument();
    expect(session.getToken()).toBeNull();
    expect(screen.getByTestId("location")).toHaveTextContent("/login");
  });
});

/**
 * Test16: send and REPLAY identical writes before testing the creator's workbench.
 * Preserves Test14's original spec unmodified; requires real local API/DB.
 * Uses real FastAPI/DB and browser requests; no route fulfillment or response mocks.
 * Test database provisioning and WeCom/mini-program acceptance are separate gates.
 */
import { randomUUID } from "node:crypto";
import { expect, test, type APIRequestContext } from "@playwright/test";

const enabled = process.env.STB_REAL_E2E === "1";
const apiBase = process.env.STB_REAL_E2E_API_BASE_URL || "http://127.0.0.1:8001";
const creator = process.env.STB_REAL_E2E_EMPLOYEE_NO || "E-CREATOR";
const assignee = process.env.STB_E2E_ASSIGNEE || "E-ASSIGNEE";
const reviewer = process.env.STB_E2E_REVIEWER || "E-REVIEWER";

test.use({
  channel: process.env.STB_REAL_E2E_BROWSER_CHANNEL || "chrome",
  // A trace can capture login tokens. Keep diagnostic evidence free of credentials.
  trace: "off",
  video: "off",
});

async function prepareSentTask(request: APIRequestContext) {
  const base = new URL(apiBase);
  expect(["127.0.0.1", "localhost"]).toContain(base.hostname);
  expect(base.protocol).toBe("http:");
  expect(base.username || base.password || base.search || base.hash).toBe("");
  expect(base.pathname).toBe("/");
  expect(creator).not.toBe(process.env.STB_E2E_OBSERVER || "E-OBSERVER");
  expect(process.env.STB_TEST16_ALLOW_TEST_WRITES).toBe("1");
  const login = await request.post(`${apiBase}/api/v1/auth/login`, {
    data: { employee_no: creator },
  });
  expect(login.status()).toBe(200);
  const token = (await login.json()).access_token;
  const headers = { Authorization: `Bearer ${token}` };
  const taskId = randomUUID();
  const taskName = `Test16-${taskId.slice(0, 8)}`;
  const now = new Date();
  const created = await request.post(`${apiBase}/api/v1/tasks`, {
    headers,
    data: {
      task_id: taskId, task_name: taskName,
      task_description: "Real creator sends before workbench regression",
      task_goal: "F1 response contract and creator visibility",
      task_source: null, main_assignee_employee_no: assignee,
      report_to_employee_no: reviewer, reviewer_employee_no: reviewer,
      start_time: now.toISOString(),
      deadline: new Date(now.getTime() + 2 * 86400000).toISOString(),
      task_weight: 3, report_cycle: null,
    },
  });
  expect(created.status()).toBe(201);
  let version: number = (await created.json()).task_version;
  for (const action of ["submit-for-confirmation", "confirm-and-send"]) {
    const actionUrl = `${apiBase}/api/v1/tasks/${taskId}/actions/${action}`;
    const options = {
      headers: { ...headers, "Idempotency-Key": `test16-${taskId}-${action}` },
      data: { expected_task_version: version },
    };
    const response = await request.post(actionUrl, options);
    expect(response.status()).toBe(200);
    const result = await response.json();
    version = result.task_version;
    if (action === "confirm-and-send") {
      expect(result.status).toBe("pending_acceptance");
      for (let round = 0; round < 3; round += 1) {
        // Keep the SAME key AND original request version, not result.task_version.
        const repeated = await request.post(actionUrl, options);
        expect(repeated.status()).toBe(200);
        expect(await repeated.json()).toEqual(result);
      }
      const detail = await request.get(`${apiBase}/api/v1/tasks/${taskId}`, { headers });
      expect(detail.status()).toBe(200);
      const persisted = await detail.json();
      expect(persisted.task_version).toBe(result.task_version);
      expect(persisted.status).toBe(result.status);
      expect(persisted.task_source).toBeNull();
      expect(persisted.nodes).toHaveLength(0);
    }
  }
  const summary = await request.get(`${apiBase}/api/v1/dashboard/summary`, { headers });
  expect(summary.status()).toBe(200);
  const row = (await summary.json()).recent_tasks.find(
    (item: { task_id: string }) => item.task_id === taskId,
  );
  expect(row).toBeDefined();
  expect(row.allowed_actions).toContain("reassign_task");
  return { taskId, taskName };
}

test.describe("Test16 creator replay then workbench", () => {
  test.skip(!enabled, "Requires explicitly isolated real services; run the Test16 gate");

  test("replays three times, then shows the task after login, detail return and reload", async ({ page, request }) => {
    const { taskId, taskName } = await prepareSentTask(request);
    const failures: string[] = [];
    page.on("response", (response) => {
      if (response.url().includes("/api/v1/") && response.status() >= 400) {
        failures.push(`${response.status()} ${new URL(response.url()).pathname}`);
      }
    });
    await page.goto("/login");
    await expect(page.getByRole("heading", { name: "\u9009\u62e9\u6f14\u793a\u8eab\u4efd" })).toBeVisible();
    await page.getByLabel("\u6f14\u793a\u7528\u6237").selectOption(creator);
    await page.getByRole("button", { name: "\u8fdb\u5165\u4efb\u52a1\u770b\u677f" }).click();
    await expect(page).toHaveURL(/\/workbench$/);
    const taskLink = page.locator(`a[href^="/task/${taskId}"]`);
    await expect(taskLink).toContainText(taskName);
    await taskLink.click();
    await expect(page).toHaveURL(new RegExp(`/task/${taskId}`));
    await expect(page.getByText(taskName, { exact: true }).first()).toBeVisible();
    await page.goBack();
    await expect(taskLink).toBeVisible();
    await page.reload();
    await expect(taskLink).toBeVisible();
    const me = await page.evaluate(async (baseUrl) => {
      const token = sessionStorage.getItem("smarttaskboard.prototype.token");
      if (!token) throw new Error("access token missing");
      const response = await fetch(`${baseUrl}/api/v1/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      return { status: response.status, employeeNo: (await response.json()).employee_no };
    }, apiBase);
    expect(me).toEqual({ status: 200, employeeNo: creator });
    await page.goto("/login");
    await expect(page).toHaveURL(/\/workbench$/);
    await expect(taskLink).toBeVisible();
    expect(failures).toEqual([]);
  });
});

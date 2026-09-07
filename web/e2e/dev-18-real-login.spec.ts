/**
 * Feature: real Web login integration verification.
 * Responsibilities: exercise the running Vite + FastAPI + PostgreSQL prototype-login chain without route mocks.
 * Does not own: service startup, database seed, or enterprise WeCom SSO.
 * Hotfix: Feature16 Web Login Integration verification.
 */
import { expect, test } from "@playwright/test";

const enabled = process.env.STB_REAL_E2E === "1";
const employeeNo = process.env.STB_REAL_E2E_EMPLOYEE_NO || "E-CREATOR";
const apiBaseUrl = process.env.STB_REAL_E2E_API_BASE_URL || "http://127.0.0.1:8001";

// Test11 local acceptance succeeded with the installed system Chrome when Playwright's
// bundled Chromium was unavailable behind the proxy. Override the channel if needed.
test.use({ channel: process.env.STB_REAL_E2E_BROWSER_CHANNEL || "chrome" });

test.describe("DEV-18 real login integration", () => {
  test.skip(!enabled, "set STB_REAL_E2E=1 against the isolated Web demo services");

  test("logs in through the real backend and reads /me", async ({ page }) => {
    const apiFailures: string[] = [];
    page.on("response", (response) => {
      const url = response.url();
      if (url.includes("/api/v1/") && response.status() >= 400) {
        apiFailures.push(`${response.status()} ${url}`);
      }
    });

    await page.goto("/login");
    await expect(page.getByRole("heading", { name: "选择演示身份" })).toBeVisible();
    await page.getByLabel("演示用户").selectOption(employeeNo);
    await page.getByRole("button", { name: "进入任务看板" }).click();

    await expect(page).toHaveURL(/\/workbench$/);
    await expect(page.getByText(new RegExp(`早上好|上午好|下午好|晚上好`))).toBeVisible();

    const me = await page.evaluate(async (baseUrl) => {
      const token = sessionStorage.getItem("smarttaskboard.prototype.token");
      if (!token) throw new Error("access token missing from sessionStorage");
      const response = await fetch(`${baseUrl}/api/v1/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      return { status: response.status, body: await response.json() };
    }, apiBaseUrl);
    expect(me.status).toBe(200);
    expect(me.body.employee_no).toBe(employeeNo);

    await page.goto("/login");
    await expect(page).toHaveURL(/\/workbench$/);
    expect(apiFailures).toEqual([]);
  });
});

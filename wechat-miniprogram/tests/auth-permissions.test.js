/** Feature 04 acceptance: server identity projection, token refresh and route/data-scope UX guards. */

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

let storage = {};
const requests = [];
let loginCalls = 0;
let qyLoginCalls = 0;
let meCalls = 0;
let refreshCalls = 0;

global.wx = {
  qy: {
    login(options) {
      qyLoginCalls += 1;
      options.success({ code: "WECOM-CODE-001" });
    },
  },
  getStorageSync(key) { return storage[key]; },
  setStorageSync(key, value) { storage[key] = JSON.parse(JSON.stringify(value)); },
  removeStorageSync(key) { delete storage[key]; },
  request(options) {
    requests.push({ url: options.url, method: options.method, header: options.header, data: options.data });
    if (options.url.endsWith("/api/v1/auth/wecom")) {
      loginCalls += 1;
      assert.equal(options.data.code, "WECOM-CODE-001");
      options.success({
        statusCode: 200,
        data: {
          access_token: "access-1",
          refresh_token: "refresh-1",
          expires_in: 1800,
          token_type: "bearer",
          current_user: {
            employee_no: "E1001",
            name: "林雨欣",
            department: { department_id: "D01", department_name: "运营中心" },
            role_type: "employee",
            roles: ["employee"],
            permissions: {
              can_access_executive: false,
              can_manage_permissions: false,
              can_view_all_tasks: false,
              can_view_all_demo_data: false,
              allowed_routes: ["/workbench", "/tasks", "/profile"],
              capabilities: ["task:read:related"],
            },
            scopes: [],
            auth_mode: "wecom",
          },
        },
      });
      return;
    }
    if (options.url.endsWith("/api/v1/auth/refresh")) {
      refreshCalls += 1;
      assert.equal(options.data.refresh_token, "refresh-1");
      options.success({ statusCode: 200, data: { access_token: "access-2", refresh_token: "refresh-2", expires_in: 1800, token_type: "bearer" } });
      return;
    }
    if (options.url.endsWith("/api/v1/me")) {
      meCalls += 1;
      if (options.header.Authorization === "Bearer expired-access") {
        options.success({ statusCode: 401, data: { error: { code: "AUTH_REQUIRED", message: "expired" }, requestId: "REQ-401" } });
        return;
      }
      options.success({
        statusCode: 200,
        data: {
          employee_no: "E1001",
          name: "林雨欣",
          department: { department_id: "D01", department_name: "运营中心" },
          role_type: "employee",
          roles: ["employee"],
          permissions: {
            can_access_executive: false,
            can_manage_permissions: false,
            can_view_all_tasks: false,
            can_view_all_demo_data: false,
            allowed_routes: ["/workbench", "/tasks", "/profile"],
            capabilities: ["task:read:related"],
          },
          scopes: [],
          auth_mode: "wecom",
        },
      });
      return;
    }
    throw new Error(`unexpected request: ${options.url}`);
  },
};

const config = require("../config");
config.mode = "api";
config.apiBaseUrl = "https://auth.test";
config.authMode = "wecom";
config.prototypeEmployeeNo = "";

const api = require("../utils/api");
const access = require("../utils/access");

(async () => {
  const [bootstrapped, current] = await Promise.all([api.bootstrapSession(), api.currentUser()]);
  assert.equal(bootstrapped.employeeNo, "E1001");
  assert.equal(current.employeeNo, "E1001");
  assert.equal(loginCalls, 1, "parallel first-load requests must share one WeCom login");
  assert.equal(qyLoginCalls, 1, "wx.qy.login should run only once for parallel first-load requests");

  const loggedIn = bootstrapped;
  assert.equal(loggedIn.employeeNo, "E1001");
  assert.equal(loggedIn.permissions.canAccessExecutive, false);
  assert.equal(storage["wangxu.accessToken"], "access-1");
  assert.equal(storage["wangxu.refreshToken"], "refresh-1");
  assert.ok(Number(storage["wangxu.tokenExpiresAt"]) > Date.now());

  assert.equal(access.canAccessExecutive({ roleType: "executive", permissions: { canAccessExecutive: false } }), false, "UI must trust server projection rather than role string");
  assert.equal(access.canAccessExecutive({ roleType: "employee", permissions: { canAccessExecutive: true } }), true);
  assert.equal(access.canAccessRoute(loggedIn, "/tasks"), true);
  assert.equal(access.canAccessRoute(loggedIn, "/executive"), false);

  storage["wangxu.accessToken"] = "expired-access";
  storage["wangxu.refreshToken"] = "refresh-1";
  const recovered = await api.currentUser();
  assert.equal(recovered.employeeNo, "E1001");
  assert.equal(refreshCalls, 1, "401 recovery must rotate the refresh token exactly once");
  assert.equal(storage["wangxu.accessToken"], "access-2");
  assert.equal(storage["wangxu.refreshToken"], "refresh-2");
  assert.ok(meCalls >= 2, "protected request must retry after refresh");
  assert.ok(requests.some((item) => item.url.endsWith("/api/v1/me") && item.header.Authorization === "Bearer access-2"));

  api.clearSession();
  assert.equal(storage["wangxu.accessToken"], undefined);
  assert.equal(storage["wangxu.refreshToken"], undefined);

  config.mode = "mock";
  const store = require("../utils/store");
  store.reset();
  const employee = store.currentUser();
  assert.equal(employee.permissions.canAccessExecutive, false);
  assert.equal(employee.permissions.canViewAllTasks, false);

  store.switchUser("E1003");
  const scopedExecutive = store.currentUser();
  assert.equal(scopedExecutive.permissions.canViewAllTasks, false);

  const state = store.read();
  store.switchUser("E1005");
  const admin = store.currentUser();
  assert.equal(admin.permissions.canViewAllTasks, true);
  assert.ok(admin.permissions.capabilities.includes("task:read:all"));
  assert.equal(store.listTasks({}).length, state.tasks.length, "admin must read every task without an explicit scope");
  const unrelated = store.getTask(state.tasks[0].taskId);
  assert.deepEqual(unrelated.allowedActions, [], "admin global read must not create task business write actions");

  store.switchUser("E1001");
  assert.ok(store.listTasks({}).every((task) => task.currentUserRelations.length > 0), "employee task list must remain relation scoped");
  store.switchUser("E1003");
  const executive = store.currentUser();
  assert.equal(executive.permissions.canAccessExecutive, true);
  assert.ok(executive.scopes.length > 0);
  assert.ok(store.executiveOverview().members.length > 0);

  const root = path.resolve(__dirname, "..");
  const profileWxml = fs.readFileSync(path.join(root, "pages/profile/index.wxml"), "utf8");
  const executiveJs = fs.readFileSync(path.join(root, "pages/executive/index.js"), "utf8");
  const profileJs = fs.readFileSync(path.join(root, "pages/profile/index.js"), "utf8");
  assert.doesNotMatch(profileWxml, /切换演示身份|恢复示例数据|重置本地演示数据/, "production profile must not contain identity-switch/reset controls");
  assert.match(executiveJs, /access\.canAccessExecutive/, "executive page must consume server-projected permission");
  assert.doesNotMatch(profileJs, /switchUser|api\.reset|api\.users/, "production profile must not load or mutate demo identity state");

  console.log("auth-permissions.test.js: PASS");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

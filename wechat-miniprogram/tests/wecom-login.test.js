/** DEV-18 acceptance: WeCom is the production identity entry and LoginService is absent. */

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

let storage = {};
let qyLoginCalls = 0;
const requests = [];

global.wx = {
  qy: {
    login(options) {
      qyLoginCalls += 1;
      options.success({ code: "WECOM-CODE-ONLY" });
    },
  },
  getStorageSync(key) { return storage[key]; },
  setStorageSync(key, value) { storage[key] = JSON.parse(JSON.stringify(value)); },
  removeStorageSync(key) { delete storage[key]; },
  request(options) {
    requests.push({ url: options.url, data: options.data, header: options.header });
    if (options.url.endsWith("/api/v1/auth/wecom")) {
      assert.deepEqual(options.data, { code: "WECOM-CODE-ONLY" });
      options.success({
        statusCode: 200,
        data: {
          access_token: "access-wecom",
          refresh_token: "refresh-wecom",
          expires_in: 1800,
          token_type: "bearer",
          current_user: {
            employee_no: "E1001",
            name: "林雨欣",
            department: null,
            role_type: "employee",
            roles: ["employee"],
            permissions: {
              can_access_executive: false,
              can_manage_permissions: false,
              can_view_all_tasks: false,
              can_view_all_demo_data: false,
              allowed_routes: ["/workbench", "/tasks"],
              capabilities: ["task:read:related"],
            },
            scopes: [],
            auth_mode: "wecom",
          },
        },
      });
      return;
    }
    if (options.url.endsWith("/api/v1/me")) {
      assert.equal(options.header.Authorization, "Bearer access-wecom");
      options.success({
        statusCode: 200,
        data: {
          employee_no: "E1001", name: "林雨欣", department: null, role_type: "employee",
          roles: ["employee"], permissions: {
            can_access_executive: false, can_manage_permissions: false, can_view_all_tasks: false,
            can_view_all_demo_data: false, allowed_routes: ["/workbench", "/tasks"], capabilities: ["task:read:related"],
          }, scopes: [], auth_mode: "wecom",
        },
      });
      return;
    }
    throw new Error(`unexpected request: ${options.url}`);
  },
};

const config = require("../config");
config.mode = "api";
config.apiBaseUrl = "https://task.test";
config.authMode = "wecom";

const api = require("../utils/api");

(async () => {
  const user = await api.bootstrapSession();
  assert.equal(user.employeeNo, "E1001");
  assert.equal(qyLoginCalls, 1);
  assert.equal(requests.length, 2);
  assert.equal(storage["wangxu.accessToken"], "access-wecom");
  assert.equal(storage["wangxu.refreshToken"], "refresh-wecom");

  const root = path.resolve(__dirname, "..");
  const projectRoot = path.resolve(root, "..");
  const configSource = fs.readFileSync(path.join(root, "config.js"), "utf8");
  const cloudAiSource = fs.readFileSync(path.join(root, "utils/cloud-ai.js"), "utf8");
  assert.equal(fs.existsSync(path.join(projectRoot, "cloud-functions/LoginService")), false);
  assert.doesNotMatch(configSource, /loginServiceBaseUrl/);
  assert.doesNotMatch(cloudAiSource, /cloudAiToken|requestSmsCode|loginByPhone|LoginService/);
  assert.match(cloudAiSource, /\/api\/v1\/auth\/ai-token/);

  console.log("wecom-login.test.js: PASS");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

/** Feature 15 interaction flow: executive sheet -> employee-filtered tasks. */
const assert = require("node:assert/strict");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
let capturedPage = null;
let navigatedUrl = "";
let storage = {};

global.Page = (definition) => { capturedPage = definition; };
global.wx = {
  navigateTo({ url }) { navigatedUrl = url; },
  navigateBack() {},
  reLaunch() {},
  getStorageSync(key) { return storage[key]; },
  setStorageSync(key, value) { storage[key] = JSON.parse(JSON.stringify(value)); },
};

require(path.join(root, "pages/executive/index.js"));
assert.ok(capturedPage, "executive page must register");
capturedPage.viewEmployeeTasks.call({
  data: {
    departmentId: "11111111-1111-1111-1111-111111111111",
    period: "week",
    selectedSnapshot: {
      employeeNo: "E1001",
      employeeName: "张三",
      employeeDepartmentId: "11111111-1111-1111-1111-111111111111",
    },
  },
});
assert.ok(navigatedUrl.startsWith("/pages/tasks/index?"));
for (const expected of [
  "source=executive",
  "mode=tasks",
  "employeeNo=E1001",
  `employeeName=${encodeURIComponent("张三")}`,
  "period=week",
  "datePreset=week",
  "reset=1",
]) assert.ok(navigatedUrl.includes(expected), `navigation must include ${expected}`);

capturedPage = null;
delete require.cache[require.resolve(path.join(root, "pages/tasks/index.js"))];
require(path.join(root, "pages/tasks/index.js"));
assert.ok(capturedPage, "tasks page must register");
const instance = {
  data: JSON.parse(JSON.stringify(capturedPage.data)),
  setData(patch) { Object.assign(this.data, patch); },
};
capturedPage.onLoad.call(instance, {
  source: "executive",
  mode: "tasks",
  employeeNo: "E1001",
  employeeName: "张三",
  departmentId: "11111111-1111-1111-1111-111111111111",
  period: "week",
  datePreset: "week",
  reset: "1",
});
assert.equal(instance.data.executiveContext, true);
assert.equal(instance.data.filters.employeeNo, "E1001");
assert.equal(instance.data.filters.employeeName, "张三");
assert.equal(instance.data.filters.datePreset, "week");

console.log("executive-employee-tasks-flow.test.js: PASS");

/** Test7: explicit people mentions hydrate task draft; absent people are never recommended. */
const assert = require("node:assert/strict");

global.wx = {
  _storage: {},
  getStorageSync(key) { return this._storage[key]; },
  setStorageSync(key, value) { this._storage[key] = JSON.parse(JSON.stringify(value)); },
  removeStorageSync(key) { delete this._storage[key]; },
};
const config = require("../config");
config.mode = "mock";
config.apiBaseUrl = "";
const store = require("../utils/store");
store.ensureInitialized();
const users = store.read().users;
assert.ok(users.length >= 2, "mock fixture should contain users");
const assignee = users[0];
const collaborator = users[1];
const api = require("../utils/api");

(async () => {
  store.saveCreationDraft({});
  const explicit = await api.extractTaskDraft(`${assignee.name}负责门店上线，${collaborator.name}协助`);
  assert.equal(explicit.mainAssigneeEmployeeNo, assignee.employeeNo);
  assert.ok(explicit.collaboratorEmployeeNos.includes(collaborator.employeeNo));

  store.saveCreationDraft({});
  const absent = await api.extractTaskDraft("周三完成门店上线");
  assert.equal(absent.mainAssigneeEmployeeNo, null);
  assert.equal(absent.reportToEmployeeNo, null);
  assert.equal(absent.reviewerEmployeeNo, null);
  assert.deepEqual(absent.collaboratorEmployeeNos, []);
  assert.ok(absent.missingFields.includes("mainAssigneeEmployeeNo"));

  store.saveCreationDraft({});
  const round1 = await api.extractTaskDraft("周三完成门店上线");
  const round2 = await api.clarifyTaskDraft(`${assignee.name}负责`);
  assert.equal(round2.mainAssigneeEmployeeNo, assignee.employeeNo);
  assert.ok(!round2.missingFields.includes("mainAssigneeEmployeeNo"));
  assert.equal(round2.taskDescription, round1.taskDescription);
  console.log("ai-field-hydration.test.js: PASS");
})().catch((error) => { console.error(error); process.exitCode = 1; });

/**
 * Test16: actual page handlers + unchanged local demonstration repository.
 * Native modals are contract doubles; no device, backend, database or Qwen claim.
 */
const assert = require("node:assert/strict");
const test = require("node:test");
const { setup, settle, clone } = require("./helpers/modal-page-harness");

function mockPage(kind) {
  const h = setup(kind, "mock");
  h.store.reset();
  const taskId = kind === "accept" ? "T20260902001" : "T20260829003";
  h.page.data.taskId = taskId;
  h.page.data.task = h.store.getTask(taskId);
  h.page.data.review = kind === "approve" ? h.store.read().reviews[0] : {};
  return h;
}

for (const kind of ["accept", "approve"]) {
  test(`mock ${kind}: native cancellation leaves complete local store unchanged`, async () => {
    const h = mockPage(kind);
    const before = h.store.read();
    h.tap(); h.respondModal(false);
    await settle();
    assert.deepEqual(h.store.read(), before);
    assert.equal(h.routes.length, 0);
  });

  test(`mock ${kind}: native failure leaves complete local store unchanged`, async () => {
    const h = mockPage(kind);
    const before = h.store.read();
    h.setFault("fail"); h.tap();
    await settle();
    assert.deepEqual(h.store.read(), before);
    assert.equal(h.routes.length, 0);
    assert.equal(h.toasts.length, 1);
  });
}

test("mock accept: screenshot task -> native confirmation -> decomposing -> original decomposition page", async () => {
  const h = mockPage("accept");
  const before = h.store.getTask(h.page.data.taskId);
  h.tap();
  assert.ok(h.modals[0].confirmText.length <= 4);
  h.respondModal(true);
  await settle();
  const accepted = h.store.getTask(before.taskId);
  assert.equal(accepted.status, "decomposing");
  assert.equal(accepted.effectiveAt, null);
  assert.equal(accepted.taskVersion, before.taskVersion + 1);
  assert.equal(accepted.nodes.length, 0);
  assert.equal(h.requests.length, 0, "mock must be reported as mock, not real HTTP");
  assert.equal(h.routes[0], `/pages/decomposition/index?taskId=${before.taskId}`);
  const decomposition = h.loadPage("pages/decomposition/index.js");
  decomposition.data.taskId = before.taskId;
  await decomposition.resume();
  const completed = h.store.getTask(before.taskId);
  assert.equal(completed.status, "in_progress");
  assert.ok(completed.effectiveAt);
  assert.ok(completed.nodes.length >= 5);
  assert.equal(decomposition.data.state, "succeeded");
});

test("mock approve: native confirmation -> original review API -> archive without snapshot", async () => {
  const h = mockPage("approve");
  const before = h.store.getTask(h.page.data.taskId);
  h.tap();
  assert.ok(h.modals[0].confirmText.length <= 4);
  h.respondModal(true);
  await settle();
  h.flushTimers();
  const archived = h.store.getTask(before.taskId);
  assert.equal(archived.status, "archived");
  assert.equal(archived.taskVersion, before.taskVersion + 1);
  assert.ok(archived.completedAt);
  assert.ok(archived.archivedAt);
  assert.equal(archived.archiveSnapshot, undefined);
  assert.equal(h.store.read().reviews[0].reviewStatus, "approved");
  assert.equal(h.routes[0], `/pages/task-detail/index?taskId=${before.taskId}`);
});

test("mock accept: repository still rejects a non-assignee (no permission expansion)", async () => {
  const h = mockPage("accept");
  const before = clone(h.store.getTask(h.page.data.taskId));
  h.store.switchUser("E1002");
  h.tap(); h.respondModal(true);
  await settle();
  assert.equal(h.page.data.actionSubmitting, false);
  assert.equal(h.routes.length, 0);
  assert.equal(h.toasts.at(-1).icon, "none");
  assert.equal(h.store.getTask(before.taskId).status, before.status);
});

test("mock approve: repository still rejects a non-reviewer", async () => {
  const h = mockPage("approve");
  h.store.switchUser("E1002");
  h.tap(); h.respondModal(true);
  await settle();
  assert.equal(h.page.data.deciding, false);
  assert.equal(h.routes.length, 0);
  assert.equal(h.toasts.at(-1).icon, "none");
  assert.equal(h.store.getTask(h.page.data.taskId).status, "pending_review");
});

/**
 * Test16: native modal contracts and real page -> API-gateway request lifecycle.
 * wx.showModal and wx.request are controlled fakes, not device/HTTP E2E evidence.
 * Does not replace backend authorization, database or native-tool acceptance.
 */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const { setup, settle, clone, root } = require("./helpers/modal-page-harness");

for (const kind of ["accept", "approve"]) {
  const flag = kind === "accept" ? "actionSubmitting" : "deciding";
  test(`${kind}: valid native button label; no write before confirmation`, async () => {
    const h = setup(kind);
    h.tap();
    assert.equal(h.modals.length, 1);
    assert.ok(Array.from(h.modals[0].confirmText).length <= 4, "native confirmText max=4");
    assert.equal(h.modals[0].confirmText, kind === "accept" ? "\u786e\u8ba4\u63a5\u53d7" : "\u786e\u8ba4\u901a\u8fc7");
    await settle();
    assert.equal(h.requests.length, 0);
    assert.equal(h.routes.length, 0);
    assert.equal(h.page.data[flag], false);
  });

  test(`${kind}: confirm goes through original API/version/key then original route`, async () => {
    const h = setup(kind);
    h.tap();
    h.respondModal(true);
    await settle();
    assert.equal(h.requests.length, 1);
    const req = h.requests[0];
    assert.equal(req.method, "POST");
    assert.equal(req.header.Authorization, "Bearer modal-test-token-not-a-real-token");
    assert.equal(req.url, `https://modal-contract.invalid/api/v1/tasks/modal-task/actions/${kind === "accept" ? "accept" : "approve-completion"}`);
    assert.equal(req.header["Idempotency-Key"], kind === "accept" ? "accept-modal-task-7" : "review-modal-review-true");
    assert.deepEqual(clone(req.data), kind === "accept"
      ? { expected_task_version: 7 }
      : { expected_task_version: 7, completion_review_id: "modal-review" });
    assert.equal(h.page.data[flag], true);
    assert.equal(h.routes.length, 0);
    h.respondHttp(200, { task_id: "modal-task", task_version: 8, status: kind === "accept" ? "decomposing" : "archived" });
    await settle();
    h.flushTimers();
    assert.deepEqual(h.routes, [`/pages/${kind === "accept" ? "decomposition" : "task-detail"}/index?taskId=modal-task`]);
    assert.equal(h.requests.length, 1);
  });

  test(`${kind}: cancel is not an error and permits reopening without a write`, async () => {
    const h = setup(kind);
    h.tap();
    h.respondModal(false);
    await settle();
    assert.equal(h.requests.length, 0);
    assert.equal(h.toasts.length, 0);
    assert.equal(h.routes.length, 0);
    assert.equal(h.page.data[flag], false);
    h.tap();
    assert.equal(h.modals.length, 2);
  });

  for (const fault of ["fail", "throw"]) {
    test(`${kind}: native ${fault} gives feedback, no write, and allows retry`, async () => {
      const h = setup(kind);
      h.setFault(fault);
      assert.doesNotThrow(() => h.tap());
      await settle();
      assert.equal(h.requests.length, 0);
      assert.equal(h.routes.length, 0);
      assert.equal(h.page.data[flag], false);
      assert.equal(h.toasts.length, 1);
      assert.equal(h.toasts[0].icon, "none");
      assert.match(h.toasts[0].title, /\u786e\u8ba4.*\u5931\u8d25/);
      h.setFault("");
      h.tap();
      assert.equal(h.modals.length, 2);
      h.respondModal(true);
      await settle();
      assert.equal(h.requests.length, 1);
    });
  }

  test(`${kind}: double tapping before native response opens one modal only`, () => {
    const h = setup(kind);
    h.tap(); h.tap(); h.tap();
    assert.equal(h.modals.length, 1);
    assert.equal(h.requests.length, 0);
  });

  test(`${kind}: double tapping during request cannot submit twice`, async () => {
    const h = setup(kind);
    h.tap(); h.respondModal(true);
    await settle();
    h.tap(); h.tap();
    await settle();
    assert.equal(h.modals.length, 1);
    assert.equal(h.requests.length, 1);
  });

  test(`${kind}: preexisting submitting flag prevents any modal`, () => {
    const h = setup(kind);
    h.page.data[flag] = true;
    h.tap();
    assert.equal(h.modals.length, 0);
  });

  for (const status of [403, 409, 500]) {
    test(`${kind}: HTTP ${status} is surfaced; no success or navigation; retry safe`, async () => {
      const h = setup(kind);
      h.tap(); h.respondModal(true);
      await settle();
      h.respondHttp(status, { error: { code: "test_error", message: `HTTP ${status}` } });
      await settle();
      h.flushTimers();
      assert.equal(h.page.data[flag], false);
      assert.equal(h.toasts.at(-1).title, `HTTP ${status}`);
      assert.equal(h.toasts.at(-1).icon, "none");
      assert.equal(h.routes.length, 0);
      const first = h.requests[0];
      h.tap(); h.respondModal(true);
      await settle();
      assert.equal(h.requests.length, 2);
      assert.deepEqual(h.requests[1].data, first.data);
      assert.equal(h.requests[1].header["Idempotency-Key"], first.header["Idempotency-Key"]);
    });
  }

  test(`${kind}: transport failure releases only submitting state, preserves task`, async () => {
    const h = setup(kind);
    const taskBefore = clone(h.page.data.task);
    h.tap(); h.respondModal(true);
    await settle();
    h.requests[0].fail({ errMsg: "request:fail timeout" });
    await settle();
    assert.equal(h.page.data[flag], false);
    assert.equal(h.toasts.at(-1).title, "request:fail timeout");
    assert.deepEqual(clone(h.page.data.task), taskBefore);
    assert.equal(h.routes.length, 0);
  });
}

test("accept: no loaded task means no dialog or write", () => {
  const h = setup("accept");
  h.page.data.task = null;
  h.tap();
  assert.equal(h.modals.length, 0);
});

test("WXML still binds the real handlers; visible long labels remain allowed", () => {
  const read = (page) => fs.readFileSync(path.join(root, `pages/${page}/index.wxml`), "utf8");
  assert.match(read("task-detail"), /bindtap="acceptTask"/);
  assert.match(read("review"), /bindtap="approve"/);
  assert.match(read("review"), />\u901a\u8fc7\u5e76\u5f52\u6863</);
});

test("all static native modal button labels obey max-four contract", () => {
  let labels = 0;
  function scan(directory) {
    for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
      const file = path.join(directory, entry.name);
      if (entry.isDirectory()) scan(file);
      else if (file.endsWith(".js")) {
        const text = fs.readFileSync(file, "utf8");
        for (const match of text.matchAll(/(?:confirmText|cancelText)\s*:\s*["']([^"']*)["']/g)) {
          labels += 1;
          assert.ok(Array.from(match[1]).length <= 4, `${path.relative(root, file)}: ${match[1]}`);
        }
      }
    }
  }
  scan(path.join(root, "pages"));
  scan(path.join(root, "utils"));
  assert.ok(labels >= 2);
});

/**
 * Test16 modal patch: execute actual page handlers and the unchanged API gateway.
 * Only wx native UI/transport/timers are emulated; no real device or backend.
 * STB_MODAL_TEST_ROOT permits the identical tests to run against the old ZIP.
 */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { createRequire } = require("node:module");

const root = path.resolve(process.env.STB_MODAL_TEST_ROOT || path.join(__dirname, "../.."));
const clone = (value) => JSON.parse(JSON.stringify(value));
const settle = () => new Promise((resolve) => setImmediate(resolve));

function setup(kind, mode = "api") {
  const storage = { "wangxu.accessToken": "modal-test-token-not-a-real-token" };
  const requests = [];
  const modals = [];
  const toasts = [];
  const routes = [];
  const timers = [];
  const openModals = new Set();
  let fault = "";
  const wx = {
    getStorageSync: (key) => storage[key],
    setStorageSync: (key, value) => { storage[key] = clone(value); },
    removeStorageSync: (key) => { delete storage[key]; },
    showToast: (options) => { toasts.push(options); },
    redirectTo: (options) => { routes.push(options.url); },
    navigateTo: (options) => { routes.push(options.url); },
    request: (options) => { requests.push(options); },
    showModal(options) {
      modals.push(options);
      if (fault === "throw") throw new Error("native modal unavailable (test)");
      const invalid = [options.confirmText || "OK", options.cancelText || "No"]
        .some((text) => Array.from(text).length > 4);
      if (invalid || fault === "fail") {
        const error = { errMsg: invalid ? "showModal:fail confirmText length" : "showModal:fail unavailable" };
        options.fail?.(error);
        options.complete?.(error);
      } else {
        openModals.add(options);
      }
    },
  };
  global.wx = wx;
  const localRequire = createRequire(path.join(root, "config.js"));
  const config = localRequire("./config");
  config.mode = mode;
  config.apiBaseUrl = mode === "api" ? "https://modal-contract.invalid" : "";
  config.authMode = "prototype";
  config.prototypeEmployeeNo = "";
  const api = localRequire("./utils/api");
  const store = localRequire("./utils/store");

  function loadPage(relative) {
    const filename = path.join(root, relative);
    let definition;
    vm.runInNewContext(fs.readFileSync(filename, "utf8"), {
      require: createRequire(filename), wx, console,
      Page: (page) => { definition = page; },
      setTimeout: (callback) => { timers.push(callback); return timers.length; },
      clearTimeout: () => {},
    }, { filename });
    assert.ok(definition, `Page was registered: ${relative}`);
    const page = { ...definition, data: clone(definition.data) };
    page.setData = (values, callback) => { Object.assign(page.data, values); callback?.(); };
    return page;
  }

  const page = loadPage(kind === "accept" ? "pages/task-detail/index.js" : "pages/review/index.js");
  Object.assign(page.data, {
    taskId: "modal-task", task: { taskId: "modal-task", taskVersion: 7 },
    review: { completionReviewId: "modal-review" }, loading: false,
  });
  return {
    page, api, store, requests, modals, toasts, routes, loadPage,
    tap: () => page[kind === "accept" ? "acceptTask" : "approve"](),
    setFault: (value) => { fault = value; },
    respondModal(confirm) {
      const options = modals.at(-1);
      assert.ok(options, "a native modal must have been requested");
      assert.ok(openModals.has(options), "native validation must succeed before user can confirm");
      openModals.delete(options);
      options.success?.({ confirm, cancel: !confirm, content: "" });
      options.complete?.({ confirm, cancel: !confirm });
    },
    respondHttp(statusCode = 200, data = {}) {
      assert.ok(requests.length, "the actual API gateway must have requested HTTP");
      requests.at(-1).success({ statusCode, data });
    },
    flushTimers() { while (timers.length) timers.shift()(); },
  };
}
module.exports = { setup, settle, clone, root };

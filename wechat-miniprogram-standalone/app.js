/**
 * Feature: Mini Program application bootstrap.
 * Responsibilities: initialize the local runnable dataset and expose runtime configuration.
 * Does not own: page state, task workflow rules, or HTTP transport.
 * Plan task: WECHAT-MP-01.
 */

const config = require("./config");
const store = require("./utils/store");
const api = require("./utils/api");

App({
  globalData: { config, sessionReady: null },
  onLaunch() {
    store.ensureInitialized();
    this.globalData.sessionReady = api.bootstrapSession().catch((error) => error);
  },
});

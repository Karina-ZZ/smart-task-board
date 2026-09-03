/**
 * Feature: Mini Program route helpers.
 * Responsibilities: centralize page paths and encoded query navigation.
 * Does not own: authorization or destination page state.
 * Plan task: WECHAT-MP-01.
 */

function go(path, params) {
  const query = Object.keys(params || {})
    .filter((key) => params[key] !== undefined && params[key] !== "")
    .map((key) => `${encodeURIComponent(key)}=${encodeURIComponent(params[key])}`)
    .join("&");
  wx.navigateTo({ url: query ? `${path}?${query}` : path });
}

function replace(path, params) {
  const query = Object.keys(params || {})
    .map((key) => `${encodeURIComponent(key)}=${encodeURIComponent(params[key])}`)
    .join("&");
  wx.redirectTo({ url: query ? `${path}?${query}` : path });
}

module.exports = { go, replace };

/**
 * Feature: Enterprise WeCom H5 OAuth.
 * Responsibilities: build the self-built-app OAuth URL, preserve a safe return route, and validate callback state.
 * Does not own: application secrets, employee mapping, JWT issuance, or business authorization.
 * H5 migration: V1.
 */

const OAUTH_STATE_KEY = "smarttaskboard.wecom.oauth.state";
const OAUTH_RETURN_KEY = "smarttaskboard.wecom.oauth.return";
const SAFE_FALLBACK = "/workbench";

function safeInternalTarget(value: string | null | undefined): string {
  if (!value || !value.startsWith("/") || value.startsWith("//")) return SAFE_FALLBACK;
  try {
    const parsed = new URL(value, window.location.origin);
    if (parsed.origin !== window.location.origin) return SAFE_FALLBACK;
    return `${parsed.pathname}${parsed.search}${parsed.hash}`;
  } catch {
    return SAFE_FALLBACK;
  }
}

export function isWeComAuthMode(): boolean {
  return import.meta.env.VITE_AUTH_MODE === "wecom";
}

export function makeOauthState(): string {
  const bytes = new Uint8Array(24);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (value) => value.toString(16).padStart(2, "0")).join("");
}

export function beginWeComOauth(returnTarget: string): string {
  const corpId = String(import.meta.env.VITE_WECOM_CORP_ID || "").trim();
  const agentId = String(import.meta.env.VITE_WECOM_AGENT_ID || "").trim();
  const configuredCallback = String(import.meta.env.VITE_WECOM_REDIRECT_URI || "").trim();
  const redirectUri = configuredCallback || `${window.location.origin}/auth/wecom/callback`;
  if (!corpId || !agentId) {
    throw new Error("企业微信 H5 登录尚未配置 CorpID / AgentID。");
  }
  const state = makeOauthState();
  sessionStorage.setItem(OAUTH_STATE_KEY, state);
  sessionStorage.setItem(OAUTH_RETURN_KEY, safeInternalTarget(returnTarget));
  const search = new URLSearchParams({
    appid: corpId,
    redirect_uri: redirectUri,
    response_type: "code",
    scope: "snsapi_base",
    state,
    agentid: agentId,
  });
  return `https://open.weixin.qq.com/connect/oauth2/authorize?${search.toString()}#wechat_redirect`;
}

export function consumeWeComCallback(state: string | null): string {
  const expectedState = sessionStorage.getItem(OAUTH_STATE_KEY);
  const returnTarget = safeInternalTarget(sessionStorage.getItem(OAUTH_RETURN_KEY));
  sessionStorage.removeItem(OAUTH_STATE_KEY);
  sessionStorage.removeItem(OAUTH_RETURN_KEY);
  if (!state || !expectedState || state !== expectedState) {
    throw new Error("企业微信登录校验失败，请从应用入口重新进入。");
  }
  return returnTarget;
}

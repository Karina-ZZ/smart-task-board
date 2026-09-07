/**
 * Feature: Enterprise WeCom H5 OAuth callback.
 * Responsibilities: validate OAuth state, exchange the one-time code for the existing app session, and restore the requested route.
 * Does not own: WeCom secrets, employee provisioning, role assignment, or task authorization.
 * H5 migration: V1.
 */

import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { session } from "../api/client";
import { wecomLogin } from "../api/endpoints";
import { consumeWeComCallback } from "../integrations/wecom/oauth";
import { Card, Typography } from "../shared/components";

export function WeComCallbackPage() {
  const [params] = useSearchParams();
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function complete() {
      try {
        const code = params.get("code")?.trim();
        const state = params.get("state")?.trim() || null;
        if (!code) throw new Error("企业微信没有返回有效登录凭证。");
        const target = consumeWeComCallback(state);
        const result = await wecomLogin(code);
        if (cancelled) return;
        session.setTokens(result.access_token, result.refresh_token);
        window.location.replace(target);
      } catch (caught) {
        if (cancelled) return;
        setError(caught instanceof Error ? caught.message : "企业微信登录失败，请重新进入。");
      }
    }
    void complete();
    return () => { cancelled = true; };
  }, [params]);

  return (
    <main className="login-page">
      <Card className="login-panel">
        <div className="brand-mark large">序</div>
        <Typography variant="caption" as="p">旺序AI任务中枢</Typography>
        <Typography variant="pageTitle" as="h1">{error ? "身份验证未完成" : "正在进入任务中枢"}</Typography>
        <p>{error || "正在确认你的企业微信身份，请勿关闭当前页面。"}</p>
        {error && (
          <Link className="stb-button stb-button--secondary" to="/login">重新登录</Link>
        )}
      </Card>
    </main>
  );
}

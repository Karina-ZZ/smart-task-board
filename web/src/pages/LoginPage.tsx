/**
 * Feature: Web dual-mode login (WeCom H5 production + prototype development).
 * Responsibilities: start enterprise WeCom OAuth in production or select an isolated development identity, then restore a safe internal route.
 * Does not own: WeCom secrets, token persistence internals, employee mapping, or backend authorization.
 * Hotfix: V1.1 Web Login Route.
 */

import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { ApiError } from "../api/client";
import { listPrototypeUsers } from "../api/endpoints";
import { readReturnSourceState, resolveReturnTarget } from "../app/return-state";
import { useAuth } from "../auth/useAuth";
import { EmptyState, LoadingState } from "../components/Feedback";
import { beginWeComOauth, isWeComAuthMode } from "../integrations/wecom/oauth";

export function LoginPage() {
  const { user, login } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const source = readReturnSourceState(location.state);
  const returnTarget = resolveReturnTarget(source);
  const [employeeNo, setEmployeeNo] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [loginError, setLoginError] = useState<unknown>(null);
  const users = useQuery({
    queryKey: ["prototype-users"],
    queryFn: listPrototypeUsers,
    retry: false,
    enabled: !user,
  });
  const loginErrorMessage =
    loginError === null
      ? null
      : loginError instanceof ApiError && loginError.message.trim()
        ? loginError.message
        : "登录失败，请稍后重试。";
  const wecomMode = isWeComAuthMode();

  useEffect(() => {
    if (user || !wecomMode) return;
    try {
      window.location.replace(beginWeComOauth(returnTarget));
    } catch (error) {
      setLoginError(error);
    }
  }, [returnTarget, user, wecomMode]);

  if (user) return <Navigate to={returnTarget} replace />;
  if (wecomMode) {
    return (
      <main className="login-page">
        <section className="login-panel" aria-labelledby="login-title">
          <div className="brand-mark large">序</div>
          <p className="eyebrow">旺序AI任务中枢</p>
          <h1 id="login-title">正在进入企业应用</h1>
          <p className="prototype-warning">正在通过企业微信安全识别你的员工身份。</p>
          {loginErrorMessage ? (
            <div className="state-card error-state" role="alert">
              <strong>企业微信登录未完成</strong>
              <p>{loginErrorMessage}</p>
              <button className="button secondary" onClick={() => window.location.replace(beginWeComOauth(returnTarget))}>重新登录</button>
            </div>
          ) : (
            <LoadingState label="正在跳转企业微信身份验证…" />
          )}
        </section>
      </main>
    );
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!employeeNo) return;
    setSubmitting(true);
    setLoginError(null);
    try {
      await login(employeeNo);
      navigate(returnTarget, { replace: true });
    } catch (error) {
      setLoginError(error);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="login-page">
      <section className="login-panel" aria-labelledby="login-title">
        <div className="brand-mark large">S</div>
        <p className="eyebrow">SmartTaskBoard</p>
        <h1 id="login-title">选择演示身份</h1>
        <div className="prototype-warning" role="note">
          仅用于隔离开发和演示，不是正式企业登录。会话令牌只保存在当前标签页。
        </div>
        {users.isLoading && <LoadingState label="正在加载演示用户…" />}
        {users.isError && (
          <div className="state-card error-state" role="alert">
            <strong>登录服务不可用</strong>
            <p>
              {users.error instanceof ApiError
                ? users.error.message
                : "无法连接登录服务。请确认当前候选包的 Web 与 FastAPI 已按本地联调文档启动。"}
            </p>
            <button className="button secondary" onClick={() => void users.refetch()}>重试</button>
          </div>
        )}
        {users.data?.length === 0 && <EmptyState title="暂无演示用户" detail="请先由管理员准备隔离演示数据。" />}
        {users.data && users.data.length > 0 && (
          <form onSubmit={submit} className="stack-form">
            <label htmlFor="prototype-user">演示用户</label>
            <select id="prototype-user" value={employeeNo} onChange={(event) => setEmployeeNo(event.target.value)} required>
              <option value="">请选择身份</option>
              {users.data.map((item) => (
                <option value={item.employee_no} key={item.employee_no}>
                  {item.name} · {item.employee_no} · {item.department_name || "无部门"}
                </option>
              ))}
            </select>
            {loginErrorMessage && (
              <div className="state-card error-state" role="alert">
                <strong>登录失败</strong>
                <p>{loginErrorMessage}</p>
              </div>
            )}
            <button className="button primary wide" disabled={submitting || !employeeNo}>
              {submitting ? "正在进入…" : "进入任务看板"}
            </button>
          </form>
        )}
      </section>
    </main>
  );
}

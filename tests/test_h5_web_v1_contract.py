"""H5 Web V1 migration contracts.

These static checks protect the latest Test16 business baseline while the React H5 shell
is migrated to a WeCom self-built application. They do not replace browser, PostgreSQL,
or real WeCom end-to-end gates.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_h5_router_contains_all_test16_user_routes_without_business_placeholders() -> None:
    source = read("web/src/app/router.tsx")
    expected_routes = (
        "/auth/wecom/callback",
        "/workbench",
        "/executive",
        "/tasks",
        "/task/:taskId",
        "/task/:taskId/report",
        "/task/:taskId/completion",
        "/task/:taskId/review",
        "/task/:taskId/decomposition",
        "/create",
        "/create/details",
        "/create/confirm",
        "/notifications",
        "/profile",
    )
    for route in expected_routes:
        assert f'path="{route}"' in source
    assert "<RoutePlaceholder" not in source


def test_wecom_identity_exchange_uses_h5_oauth_not_miniprogram_code2session() -> None:
    source = read("app/integrations/wecom/client.py")
    assert "/cgi-bin/auth/getuserinfo" in source
    assert "miniprogram/jscode2session" not in source
    assert "/cgi-bin/message/send" in source


def test_web_oauth_uses_state_and_internal_return_target() -> None:
    source = read("web/src/integrations/wecom/oauth.ts")
    callback = read("web/src/pages/WeComCallbackPage.tsx")
    assert "snsapi_base" in source
    assert "state" in source
    assert "sessionStorage" in source
    assert "wecomLogin" in callback
    assert "consumeWeComCallback" in callback


def test_h5_creation_preserves_test16_hotfixes_and_valid_report_cycle() -> None:
    source = read("web/src/features/task-intake/TaskCreateDetailsPanel.tsx")
    assert "任务来源（选填）" in source
    assert "task_source" in source
    assert "estimated_hours" not in source
    assert "weekly:FRI@17:00" in source
    assert "dirtyFields" in source
    assert "AI追问未结束也不会阻止已完整字段继续发送" in source


def test_h5_voice_uses_existing_chatservice_asr_with_short_lived_ai_token() -> None:
    source = read("web/src/integrations/chat-service.ts")
    intake = read("web/src/features/task-intake/TaskIntakePage.tsx")
    assert "/task-intake/transcribe" in source
    assert "issueAiToken" in source
    assert "VITE_CHAT_SERVICE_BASE_URL" in source
    assert "MediaRecorder" in intake
    assert "transcribeBrowserRecording" in intake


def test_h5_notifications_use_real_wecom_provider_only_in_wecom_auth_mode() -> None:
    dependencies = read("app/api/dependencies.py")
    provider = read("app/integrations/wecom/message_provider.py")
    assert "WeComApplicationMessageProvider" in dependencies
    assert 'settings.auth_mode == "wecom"' in dependencies
    assert "wecom_user_id" in provider
    assert "send_application_message" in provider


def test_h5_task_detail_matches_test16_interaction_contract() -> None:
    page = read("web/src/features/task-detail/TaskDetailPage.tsx")
    controls = read("web/src/features/task-detail/TaskExecutionControls.tsx")
    parts = read("web/src/features/task-detail/TaskDetailParts.tsx")
    assert "window.prompt" not in controls
    assert "window.confirm" not in controls
    assert 'title="操作记录"' in page
    assert "ProgressIssuesPanel" not in page
    assert "ChangeRequestsPanel" not in page
    assert "CompletionReviewsPanel" not in page
    assert "renderNodeActions" in parts
    assert "aria-expanded" in parts
    assert "接受承接" in controls
    assert "无法承接" in controls
    assert "开始节点" in controls
    assert "完成节点" in controls
    assert "查看操作记录" in controls
    assert "发起变更申请" in controls
    assert "更换承办人" in controls
    assert "listUsers" in controls
    assert "接受后系统将立即启动AI拆解" in controls


def test_h5_decomposition_matches_test16_three_state_contract() -> None:
    source = read("web/src/features/task-decomposition/TaskDecompositionPage.tsx")
    assert 'const stages = ["准备任务信息", "生成执行节点", "建立前置依赖", "校验并保存结果"]' in source
    assert "正在把任务变成行动" in source
    assert "拆解完成，任务已生效" in source
    assert "拆解暂未完成" in source
    assert "拆解成功前，任务不会计入负荷，也不能汇报、完成节点或验收" in source
    assert "重新拆解" in source
    assert "查看执行节点" in source
    assert "AI处理中，请稍候" in source
    assert "executeTaskDecomposition" in source
    assert "retryTaskDecomposition" in source


def test_h5_progress_report_matches_test16_field_and_permission_contract() -> None:
    source = read("web/src/features/task-detail/TaskReportPage.tsx")
    assert "当前进度" in source
    assert "阶段成果（选填）" in source
    assert "是否存在卡点" in source
    assert "卡点说明" in source
    assert "备注（选填）" in source
    assert "实际工时由任务完成时间减开始时间自动计算，无需填写" in source
    assert 'actions.allowed_actions.includes("submit_progress_report")' in source
    assert "只有主承办人在执行态可以提交任务级进度汇报" in source
    assert "expected_task_version" in source
    assert "stage_result" in source
    assert "has_issue" in source
    assert "issue_note" in source
    assert "remark" in source
    assert "actual_hours" not in source
    assert "ProgressIssuesPanel" not in source


def test_h5_completion_page_matches_test16_submission_contract() -> None:
    source = read("web/src/features/task-detail/TaskCompletionPage.tsx")
    assert "全部节点已完成" in source
    assert "完成说明" in source
    assert "交付摘要" in source
    assert "提交验收" in source
    assert "实际工时由系统计算" in source
    assert "验收通过无需填写额外意见" in source
    assert 'actions.allowed_actions.includes("submit_completion")' in source
    assert "submitCompletion" in source
    assert "CompletionReviewsPanel" not in source
    assert "提交后任务将进入待验收" in source


def test_h5_review_page_matches_test16_review_and_archive_contract() -> None:
    source = read("web/src/features/task-detail/TaskReviewPage.tsx")
    assert "第 {currentReview.review_round || 1} 轮验收" in source
    assert "完成申请" in source
    assert "验收依据" in source
    assert "任务目标" in source
    assert "验收标准" in source
    assert "有效节点" in source and "已完成" in source
    assert "验收通过后系统自动计算实际工时，并立即归档；不会创建归档快照" in source
    assert "退回修改" in source
    assert "通过并归档" in source
    assert "退回原因必填" in source
    assert "approveCompletion" in source
    assert "rejectCompletion" in source
    assert "CompletionReviewsPanel" not in source


def test_h5_notifications_match_test16_tabs_and_deep_link_contract() -> None:
    source = read("web/src/features/notifications/NotificationsPage.tsx")
    assert '{ code: "all", label: "全部" }' in source
    assert '{ code: "task", label: "任务" }' in source
    assert '{ code: "reminder", label: "提醒" }' in source
    assert '{ code: "system", label: "系统" }' in source
    assert "item.action_required" in source
    assert "item.can_open === false" in source
    assert 'item.target_type === "node_assignment"' in source
    assert 'item.target_type === "decomposition"' in source
    assert 'item.target_type === "report"' in source
    assert 'item.target_type === "review"' in source
    assert "markNotificationRead" in source
    assert "createReturnSource" in source
    assert "smarttaskboard.notifications.tab" in source
    assert "smarttaskboard.notifications.scroll" in source


def test_h5_profile_matches_test16_user_summary_contract() -> None:
    source = read("web/src/features/profile/ProfilePage.tsx")
    assert "身份、任务关系与使用设置" in source
    assert "关联任务" in source
    assert "待我处理" in source
    assert "已归档" in source
    assert "任务关系说明" in source
    assert "我创建的任务" in source
    assert "我主承办的任务" in source
    assert "我协同的任务" in source
    assert "待我验收的任务" in source
    assert "action_required" in source
    assert "can_access_executive" in source
    assert "logout" not in source
    assert "capabilities" not in source
    assert "角色切换" not in source
    assert "重置演示数据" not in source


def test_h5_executive_dashboard_matches_test16_component_and_drilldown_contract() -> None:
    source = read("web/src/features/executive-dashboard/ExecutiveDashboardPage.tsx")
    assert "团队任务态势" in source
    assert "仅展示服务端授权的负责部门数据" in source
    assert "全部授权部门" in source
    assert "本周" in source and "本月" in source
    assert "进行中" in source
    assert "按期率" in source
    assert "KPI关联" in source
    assert "总体进度" in source
    assert "团队任务四象限" in source
    assert "团队负荷热力图" in source
    assert "查看该员工任务" in source
    assert "data_quality_issue_count" in source
    assert "active_task_count" in source
    assert "urgent_task_count" in source
    assert "blocked_task_count" in source
    assert "overdue_task_count" in source
    assert 'datePreset: period' in source
    assert 'mode: "tasks"' in source
    assert 'employeeNo: selected.member.employee_no' in source
    assert 'employeeName: selected.member.name' in source
    assert "<select" not in source

# RELEASE-01｜企业微信正式接入说明

## 1. 企业微信管理员需要准备

- CorpID；
- 旺序企业微信应用 AgentID；
- 应用 Secret；
- 正式小程序 AppID；
- 应用可见范围；
- 预发测试员工；
- API/AI域名相关可信域名配置（按企业微信后台实际要求配置）。

## 2. 身份映射

旺序内部人员唯一标识仍为 `employee_no`：

```text
WeCom userid -> users.wecom_user_id -> users.employee_no
```

不得把WeCom userid直接写入任务的 creator/main_assignee/reviewer/node owner 等 employee_no 字段。

部门建议保持：

```text
WeCom department id -> departments.wecom_department_id -> departments.department_id
```

企业微信管理员身份不自动等于旺序 `admin`；部门负责人不自动等于旺序 `executive`。旺序角色和 `user_authorized_scopes` 仍由旺序维护。

## 3. 生产配置

FastAPI：

```text
APP_ENV=production
AUTH_MODE=wecom
ALLOW_TEST_EMPLOYEE_HEADER=false
PROTOTYPE_AUTH_ENABLED=false
WECOM_CORP_ID=...
WECOM_AGENT_ID=...
WECOM_APP_SECRET=...
```

小程序在后续真实接入阶段改为：

```text
正式AppID
mode="api"
apiBaseUrl=https://api.example.com
chatServiceBaseUrl=https://ai.example.com
```

## 4. 必测登录场景

| 场景 | 预期 |
|---|---|
| active且已绑定员工 | 登录成功 |
| active高管 | 登录成功，获得服务端授予的高管查看范围 |
| disabled员工 | 拒绝登录 |
| 未绑定userid | 拒绝并提示未绑定 |
| 错误/过期code | 拒绝 |
| 客户端伪造employeeNo | 不能改变真实身份 |
| 企业微信管理员 | 不自动获得旺序admin |

## 5. 当前RELEASE-01未实现的内容

- 通讯录全量/增量同步；
- 企业微信真实通知 Provider；
- 通知调度Worker。

这些必须在后续Release中真实实现，不使用假成功或前端模拟替代。

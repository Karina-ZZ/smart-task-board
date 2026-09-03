# 企业微信身份与组织字段映射基线

> 状态：P0 已确认，作为功能16 / DEV-18 最终发布验收前的组织与身份数据基线。  
> 原则：企业微信负责“身份与组织事实”；旺序负责“业务角色、授权范围、任务关系、绩效、负荷与能力画像”。  
> 内部人员主键继续使用 `employee_no`；内部部门主键继续使用 `departments.department_id`（UUID）。企业微信外部 ID 不替代内部主键。

## 1. 成员字段映射

| 企业微信字段/语义 | 旺序表.字段 | 落库规则 | 权威性/限制 | 直接支撑功能 |
|---|---|---|---|---|
| `userid` | `users.wecom_user_id` | 直接保存，唯一 | 企业微信身份主键；不等于 `employee_no` | 企业微信免登、消息收件人映射、身份绑定 |
| `name` | `users.name` | 直接同步 | 企业微信主数据 | 人员选择、任务详情、通知展示、AI 人名解析 |
| `main_department` | `users.department_id` | 先用 `departments.wecom_department_id` 找到内部 `department_id` 再写入 | 只写主部门 | 部门权限、高管看板、员工筛选、组织归属 |
| `department[]` | 暂无一一对应字段 | 不把多部门数组塞入 `users.department_id` | 当前模型只保存主部门；多部门关系后续单独评审 | 后续跨部门组织扩展 |
| `position` | `users.position` | 直接同步 | 组织展示事实，不直接赋权 | 人员展示、承办人推荐辅助 |
| `direct_leader[]` | `users.manager_employee_no` | 先以 leader `userid` 查 `users.wecom_user_id`，再转换为 `employee_no` | 当前字段单值；多直属上级时需明确企业规则 | 直属团队、高管范围辅助、汇报对象推荐 |
| 成员状态 | `users.status` | 激活→`active`；停用/退出等不可用态→`disabled` | 不删除历史用户 | 登录门禁、人员候选过滤、离职禁用 |
| 自定义“工号” `extattr` | `users.employee_no` | **仅当企业已把该自定义字段定义为权威工号**时用于绑定/初始化 | 禁止用 `userid` 猜工号 | 全系统人员主键绑定 |
| 自定义“岗位职责” `extattr` | `employee_profiles.responsibility_text` | 可选同步 | 必须先冻结自定义字段名称/类型 | 承办人/协同人推荐 |
| 自定义“技能标签” `extattr` | `employee_profiles.skill_tags` | 可选同步并标准化 | 必须先冻结标签协议 | 节点负责人/协同人推荐 |
| `is_leader_in_dept` | 无直接字段 | 只作为组织层级建议输入 | 不得直接写 `role_type` 或断言 `org_level` | 组织治理辅助 |

## 2. 部门字段映射

| 企业微信字段/语义 | 旺序表.字段 | 落库规则 | 权威性/限制 | 直接支撑功能 |
|---|---|---|---|---|
| 部门 `id` | `departments.wecom_department_id` | **新增字段，直接保存，唯一；可空以兼容历史/手工部门** | 外部 ID，不替代内部 UUID | 企业微信部门同步、成员主部门映射 |
| 部门 `name` | `departments.department_name` | 直接同步 | 企业微信组织主数据 | 高管看板、人员筛选、任务/组织展示 |
| `parentid` | `departments.parent_department_id` | 先按 `wecom_department_id` 找到父部门内部 UUID 后写入 | 不直接把企业微信整数写到 UUID 字段 | 组织树、高管授权范围、事业部路径 |
| 部门层级 | `departments.department_path` | 旺序根据内部父子关系重新计算 | 派生字段，不复制外部字符串 | 快速查询下属组织范围 |
| 部门删除/失效事件 | `departments.status` | 映射为停用；不删除业务历史引用 | 企业微信负责组织事实，旺序保留历史 | 人员候选、高管范围有效性 |
| 部门类型 | `departments.department_type` | **不由企业微信直接覆盖** | 事业部/中心/部门是旺序业务语义 | KPI 事业部匹配、组织统计 |
| 部门负责人 `department_leader[]` | 无直接字段 | 可用于管理关系校验/建议 | 不自动授予 executive/admin | 管理关系辅助 |

## 3. 明确不由企业微信覆盖的旺序字段

| 旺序字段/数据 | 权威来源 | 原因 |
|---|---|---|
| `users.role_type` | 旺序管理员 | 企业微信部门负责人/管理员身份不等于旺序业务角色 |
| `users.org_level` | 旺序规则/管理员 | 需要公司自己的组织级别语义 |
| `user_authorized_scopes` | 旺序管理员 | 高管跨部门/临时授权属于业务授权 |
| `departments.department_type` | 旺序管理员 | 企业微信只提供组织树，不知道事业部/中心业务分类 |
| 负荷参数 | `system_parameters` / 旺序 | 企业微信不提供任务容量口径 |
| `employee_profiles` 的容量/标准任务/容忍度 | 旺序/HR | 非企业微信标准通讯录数据 |
| 任务、节点、通知、绩效、负荷、优先级 | 旺序业务表 | 属于任务系统业务事实 |

## 4. 新增字段合同

```text
departments.wecom_department_id
类型：BIGINT
nullable：true
unique：true（唯一索引）
用途：保存企业微信部门外部ID，仅用于同步/映射
```

规则：

1. `departments.department_id` 继续是所有旺序内部外键使用的 UUID。
2. 企业微信 `department.id` 只能写 `wecom_department_id`，禁止直接写内部 UUID 字段。
3. 现有部门允许 `wecom_department_id IS NULL`，便于灰度迁移；企业微信全量同步后应逐步补齐。
4. 同一个企业微信部门 ID 不得绑定到两个旺序部门。
5. 企业微信同步服务必须先同步部门，再同步成员，再解析直属上级关系。

## 5. 支撑功能总览

- 企业微信免登录：`users.wecom_user_id` → `employee_no`。
- 企业微信通知：`notification.recipient_employee_no` → `users.wecom_user_id`。
- 创建/承办/协办/汇报/验收人员选择：`users + departments`。
- 高管基础看板：部门树 + 旺序 `user_authorized_scopes`。
- 功能15员工任务筛选：授权部门成员列表 + `employee_no`。
- KPI事业部匹配：任务 `department_id` → 旺序部门树/`department_type`。
- 离职/停用门禁：企业微信成员状态 → `users.status`。
- 承办/协同推荐：企业微信职位 + 可选职责/技能 `extattr`，再叠加旺序负荷/技能规则。

## 6. 当前实施状态与后续边界

功能16前置 P0 已完成身份入口替换：

- `POST /api/v1/auth/wecom` 已实现；
- 微信小程序 `wx.qy.login()` 已接入；
- 企业微信 `userid` 仅通过 `users.wecom_user_id` 映射现有 `employee_no`，不自动创建用户；
- 原短信 `cloud-functions/LoginService` 已从运行源码删除；
- ChatService 改为只接受 FastAPI `/api/v1/auth/ai-token` 签发的短时 `task-intake` token；
- 旺序原 access/refresh token、`/me`、角色、授权范围和任务权限逻辑保持不变。

尚未在本步骤开发：

- 企业微信通讯录全量/增量同步；
- 企业微信真实应用环境验收（需要真实 CorpID/AppSecret/应用可见范围与测试成员）；
- 历史 LoginService MySQL 表的破坏性删除。历史表当前仅保留兼容，不再被运行代码读取。

后续通讯录同步必须继续以本映射文档为字段合同，不得借同步改变旺序业务权限模型。

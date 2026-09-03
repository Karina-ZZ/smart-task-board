# 功能 04 验收单：登录与权限

## 本批次开发边界

功能 04 只完成身份会话、当前用户、任务关系、员工/高管/管理员权限投影、授权数据范围、无权访问与 Token 刷新；不提前实现功能 05 AI 任务输入的新能力。

- 页面表现：不新增第二版前端不存在的业务页面，不改变功能 01～03 的 WXML/WXSS 布局。
- 身份来源：API 模式只信任后端 Token、`users.role_type` 和有效 `user_authorized_scopes`；页面不根据本地角色字符串自行升级权限。
- 开发登录：复用仓库已有受控 `prototype` Auth Service。生产/企业微信真实凭证换票需要部署方提供企业认证配置与凭证，本批次不伪造外部 OAuth/企业微信成功。
- 演示身份切换和重置：仅 `mock` 模式可见，API/生产模式隐藏且接口主动拒绝。

## 已完成

- `POST /api/v1/auth/login` / `/token` 继续复用现有 Authentication Service，受控开发登录现在一次返回 access token、refresh token 和服务端 `currentUser` 权限投影。
- `GET /api/v1/me` 统一通过 `IdentityService.current_user_context()` 返回当前用户、部门、系统身份、有效授权范围和权限能力。
- `POST /api/v1/auth/refresh` 轮换 refresh token；`POST /api/v1/auth/logout` 撤销当前员工会话。
- 小程序 API 网关自动保存 access/refresh token；受保护请求遇到 401 时只刷新一次并自动重试一次。
- 首次受控开发登录与 refresh 都使用单飞锁，避免工作台并发请求创建多套会话或竞争旋转 refresh token。
- 小程序启动时预热会话；没有可恢复会话时返回明确认证错误，不使用硬编码 `currentUser` 冒充登录。
- 服务端权限投影区分系统身份、任务读取权限和团队看板权限：普通员工不会因为存在 scope 行而获得高管团队入口；管理员默认拥有全部任务只读权限，但团队看板入口仍按独立能力投影。
- P0修正任务查看权限：管理员默认可查看全部任务及其任务范围内的只读关联数据；员工仅能查看直接任务关系；高管可查看直属人员任务并通过有效显式 scope 扩展数据范围。管理员的接受、汇报、验收等业务写权限仍只来自实际任务关系、状态与版本规则。
- 任务概览默认模式对高管/管理员允许纳入服务端授权范围候选，再由 FR-22 权限策略逐条校验；显式“我创建/我承办/参与”筛选仍保持原任务关系语义。
- `GET /tasks/{taskId}/available-actions` 增加 `current_user_relations`，与任务列表的任务关系投影保持一致；详情页只把它用于界面上下文，不作为授权依据。
- 工作台、任务概览、任务详情、通知、我的、高管页和底部“团队”入口统一读取后端 `permissions.canAccessExecutive` 投影。
- 高管页无权时保持第二版页面结构并进入明确无权状态；详情页原有 403/404 独立状态继续保留。
- “我的”页面中的切换演示身份、恢复示例数据继续严格包在 `mockMode` 条件中，API/生产模式不渲染。

## P0 权限修正记录

- 最新用户裁决：`admin` 默认拥有全部任务及任务范围内关联数据的读取权限，不要求额外 `user_authorized_scopes`。
- 该全局能力仅为读取能力；管理员对具体任务的接受、退回、节点完成、汇报、变更、撤回/取消、提交完成、验收等业务写动作，仍必须满足对应任务关系、状态与 `taskVersion` 规则。
- 当前用户权限投影新增 `canViewAllTasks=true`（API字段 `can_view_all_tasks`）与 capability `task:read:all`，供客户端明确识别该读取边界。
- 员工与高管规则不变：员工按直接任务关系；高管按直属人员与有效授权范围读取。

## 数据库与迁移

- 本功能没有新增迁移。
- 直接复用已有 `users`、`departments`、`user_authorized_scopes` 和 `auth_refresh_tokens`。
- Refresh token 仍按既有 Authentication Service 只持久化哈希，不把原始 refresh token 落库。

## 自动化验证

- 微信小程序累计测试：6/6 组通过（功能 01、02、03、04、mock 主链路、WXML 静态合同）。
- 功能 04 微信专项测试覆盖：并发首次登录单飞、Token 存储、401 自动 refresh + 重试、权限投影、路由显隐、mock 身份隔离和任务关系范围。
- 后端 Service 全量回归：133 passed。
- FastAPI API 路由全量回归：83 passed（当前容器无 `psycopg`，使用 SQLite 导入/路由测试配置；不冒充 PostgreSQL 集成结果）。
- Refresh Token 迁移合同测试：3 passed；本功能没有新增迁移。
- JavaScript `node --check` 与 Python `compileall`：通过。
- Ruff：当前容器未安装，未执行；未把该门禁伪报为通过。

## 微信开发者工具重点体验

### 默认本地演示模式

1. 保持 `config.js` 的 `mode: "mock"`，直接编译。
2. 员工身份不显示底部“团队”；进入高管页会被权限状态拦截。
3. “我的”可看到“本地演示工具”，切换到高管示例用户后出现团队入口；该工具仅用于 mock 验收。

### 真实 API 开发联调

1. 后端使用隔离开发环境并启用 `AUTH_MODE=prototype`，只允许明确配置的测试员工号。
2. 小程序 `config.js` 设置 `mode: "api"`、开发 API 地址、`authMode: "prototype"` 和受控测试 `prototypeEmployeeNo`；不要提交真实凭据或 Token。
3. 冷启动后无需手工写入 Bearer Token；客户端会取得会话并读取 `/me`。
4. 删除/使 access token 失效后再次加载页面，确认客户端通过 refresh token 恢复并重试请求。
5. 使用员工、高管和管理员测试账号分别验证：员工只看直接关系任务；高管按直属/授权范围；管理员即使没有显式 scope 也可以查看全部任务，但对无任务关系的任务不获得接受、汇报、验收等业务写动作。

## 未伪造的外部集成边界

PRD要求最终通过企业微信/微信凭证映射 `employee_no`，但附件没有提供具体 CorpId/AgentId、应用凭证、回调配置和 credential exchange 协议。本批次已经把服务端会话、Token 刷新、身份投影和前端会话接入点做好；真实企业微信换票必须在获得合法企业配置后接入现有 Auth/Identity Service，不得另建平行身份体系。

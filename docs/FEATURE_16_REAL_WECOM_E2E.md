# 功能16真实企业微信与发布E2E执行清单

本清单只用于 DEV-18 / 功能16发布验收，不改变任务、权限、状态机或看板业务规则。

## 1. 前置条件

正式证据必须同时满足：

- Python 3.12 独立虚拟环境；
- PostgreSQL 16 隔离测试库；
- `scripts/run_test5_release_gate.sh` 自动门禁通过；
- FastAPI 使用 `AUTH_MODE=wecom`；
- `WANGXU_BACKEND_ENV_FILE` 指向真实企业微信测试配置文件；
- `WANGXU_CHAT_ENV_FILE` 指向真实通义千问测试配置文件；
- 微信开发者工具已登录，`project.config.json` 使用真实 AppID；
- `wechat-miniprogram/config.js` 使用 `mode: "api"` 且 `apiBaseUrl` 指向测试 FastAPI；
- 企业微信测试应用的可见范围包含测试员工；
- `users.wecom_user_id` 已正确绑定测试账号，不允许测试过程中自动创建业务用户。

真实 Secret、Qwen Key、数据库密码不得写入小程序、Git 或交付 ZIP。

## 2. 自动门禁

在 Python 3.12 venv 中执行：

```bash
export WANGXU_BACKEND_ENV_FILE=/绝对路径/backend.env
export WANGXU_CHAT_ENV_FILE=/绝对路径/chatservice.env
./scripts/run_test5_release_gate.sh
```

脚本要求：Ruff、compileall、空库 Alembic、28 项 PostgreSQL 集成、5 项×20 轮并发、非 PG 累计、小程序测试/语法、React lint/test/build 全部通过。缺正式条件时必须 BLOCKED，不允许以 skip 作为发布证据。

## 3. 真实企业微信身份 Smoke Test

在真实小程序中临时获取一枚新鲜 `wx.qy.login()` code。code 为一次性短时凭据，不写入文件、不提交代码库。

普通员工示例：

```bash
python3 scripts/run_wecom_real_e2e.py \
  --api-base-url https://你的测试API域名 \
  --code '刚取得的一次性code' \
  --employee-no 'E001' \
  --role-type employee
```

高管示例：

```bash
python3 scripts/run_wecom_real_e2e.py \
  --api-base-url https://你的测试API域名 \
  --code '高管账号刚取得的一次性code' \
  --employee-no 'E002' \
  --role-type executive
```

脚本验证：

1. `/health/live` = 200；
2. `/health/ready` = 200；
3. `/api/v1/auth/wecom` 成功；
4. `wecom_user_id -> employee_no` 映射正确；
5. `auth_mode=wecom`；
6. `/api/v1/me` 仍返回旺序 `roles / permissions / scopes`；
7. `/api/v1/auth/ai-token` 可签发短时 task-intake token；
8. refresh 可轮换且身份不变；
9. logout 后 refresh token 不再有效；
10. 脚本不打印 access token、refresh token 或任何 Secret。

## 4. 必须人工验证的负向身份场景

至少准备以下测试账号或临时数据：

| 场景 | 预期 |
|---|---|
| 企业微信普通员工A，已绑定且 active | 登录成功，`/me.employee_no=A` |
| 企业微信高管B，已绑定且 active | 登录成功，沿用旺序原有高管权限 |
| 企业微信员工C，本地 `users.status != active` | 拒绝登录 |
| 企业微信员工D，`users.wecom_user_id` 未绑定 | `WECOM_USER_NOT_BOUND`，不得自动 INSERT users |
| 错误/过期 wx.qy.login code | 拒绝登录 |
| 返回 corpid 与配置企业不一致 | 拒绝登录 |
| 前端请求正文伪造其他 `employee_no` | 不得改变服务端认证身份 |

企业微信部门负责人、企业微信管理员不得自动映射为旺序 `executive/admin`；业务角色和授权范围继续由旺序本地数据决定。

## 5. 普通员工全生命周期 E2E

必须从真实企业微信员工身份进入小程序，不使用 prototype employeeNo 作为最终发布证据：

1. 工作台输入任务；
2. ChatService/Qwen 整理字段；
3. 人工确认字段；
4. 确认发送；
5. 主承办人收到待承接；
6. 主承办人接受，任务进入 `decomposing`；
7. AI 拆解成功并真实落 5~10 个节点；
8. 协办节点仅负责人收到“节点待承接”；
9. 未承接协办节点不得收到开始/临期/到期/逾期执行提醒；
10. 接受节点后可开始执行；
11. 进度汇报、卡点、解除卡点；
12. 全节点完成；
13. 提交验收进入 `pending_review`；
14. 验收通过；
15. 归档；
16. 页面返回、筛选、滚动位置正确恢复。

同时跑失败链：退回修改重发、AI拆解失败重试、协办拒绝且原因必填、旧 taskVersion 409、重复幂等请求单副作用、验收退回后二次提交、取消/撤回后迟到 AI 结果不得激活任务。

## 6. 高管 E2E

真实高管账号登录后执行：

1. 高管看板；
2. 部门/周期筛选；
3. 负荷热力图；
4. 点击员工；
5. “查看该员工任务”；
6. 任务概览 employeeNo 筛选；
7. employee + status + quadrant + date 联合筛选；
8. 打开任务详情；
9. 返回恢复任务筛选和滚动；
10. 再返回恢复高管部门和周期。

越权验证：篡改 departmentId、employeeNo、taskId，授权范围外查询必须由后端拒绝；高管只因可读任务，不得获得任务写权限。

## 7. Outbox / 通知发布证据

真实 PostgreSQL 必须满足：

- 并发 worker 下 provider 调用次数 = 1；
- 成功记录 `send_status=sent`；
- `retry_count=0`、`fail_reason is null`；
- 第二 dispatcher 轮次不重新发送已 sent 通知；
- 唯一 dedupe 冲突只保留一条记录；
- 5 个并发场景各 20 轮稳定通过。

真实企业微信环境再补一条 smoke：测试员工确实收到一条预期通知，点击后仍重新执行旺序当前权限和状态检查；通知本身不得授予业务权限。

## 8. 最终发布判定

只有以下全部成立才能将 DEV-18 标记为完成：

- Python 3.12 正式门禁 PASS；
- Ruff 0 error；
- PostgreSQL 28/28 PASS、0 skip；
- 5×20 并发 PASS；
- 非 PG 累计 PASS；
- React lint/test/build PASS；
- 小程序测试、JS检查、登录态 DevTools 编译 PASS；
- 真实普通员工和高管企业微信身份 PASS；
- disabled / 未绑定 / 错误企业等负向身份 PASS；
- Qwen 真实 smoke PASS；
- 普通员工任务生命周期、高管下钻、权限、幂等、版本、返回恢复 E2E PASS；
- 最终 ZIP 新目录反向验收再次全部 PASS；
- 交付 ZIP 中无真实 `.env`、Secret、Qwen Key、数据库密码。

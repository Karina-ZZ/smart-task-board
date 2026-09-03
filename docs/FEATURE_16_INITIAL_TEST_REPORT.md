# 功能16 / DEV-18 初始发布验收测试记录

> 日期：2026-09-03  
> 状态：`IN_PROGRESS`  
> 范围：在功能15累计源码上先固化企业微信组织字段基线，然后启动全链路发布门禁。  
> 说明：用户已明确要求在前置功能仍有环境门禁未闭环的情况下开始功能16测试；本记录如实保留阻塞项，不把未执行项记为 PASS。

## 1. 本轮先完成的企业微信组织字段基线

- 新增 `departments.wecom_department_id BIGINT NULL`。
- 建立唯一索引 `ix_departments_wecom_department_id`。
- 内部 `departments.department_id` UUID 不变。
- 新 Alembic revision：`c2d3e4f5a6b7`，down revision：`b1c2d3e4f5a6`。
- 字段映射合同：`docs/WECOM_IDENTITY_ORG_MAPPING.md`。
- PostgreSQL 专项测试与 gate 脚本的目标 revision 已同步到 `c2d3e4f5a6b7`。

## 2. 已执行门禁

| 门禁 | 本次结果 | 结论 |
|---|---:|---|
| Department 模型 + Alembic metadata 定点测试 | 11 passed | PASS |
| Alembic 单一 head | `c2d3e4f5a6b7` | PASS |
| Alembic PostgreSQL offline SQL | 成功生成新增列 + unique index SQL | PASS |
| Python compileall | app + cloud-functions | PASS |
| 后端非 PostgreSQL 累计 | 461 passed / 28 deselected | PASS |
| 微信小程序 npm test | 19 / 19 test files | PASS（已修复漏跑） |
| 微信全部 JS `node --check` | 46 files | PASS |
| 微信 `project.config.json` ignore schema | 对象数组 | PASS（已修复） |
| PostgreSQL 专项发现 | 28 tests | 当前环境全部 SKIP；未执行真实 PG |

## 3. 功能16测试中已修复的问题

### 3.1 小程序测试脚本漏跑

旧 `npm test` 手工枚举16个文件，漏掉3个高管/员工筛选测试。

修复：新增 `wechat-miniprogram/tests/run-all-tests.js`，自动发现并稳定排序执行全部 `*.test.js`。

结果：`19/19 PASS`。

### 3.2 微信开发者工具打包配置

旧：

```json
["README.md", "tests/**"]
```

修复为微信 schema 对象：

```json
[
  {"type": "file", "value": "README.md"},
  {"type": "folder", "value": "tests"}
]
```

本容器没有微信开发者工具，因此只能确认配置合同修正；真实 DevTools 编译仍待外部环境执行。

### 3.3 通知 Outbox 并发重复发送

`ReminderNotificationService.send_pending()` 原来只是普通 SELECT，多 worker 在 PostgreSQL 下可能同时取到同一通知并各发一次。

修复：查询增加 `FOR UPDATE SKIP LOCKED`，由数据库对待发送行做 worker 抢占。

非 PG 回归：461 passed。

仍需真实 PostgreSQL 执行：

`tests/integration/test_feature13_postgresql.py::test_concurrent_outbox_workers_must_not_double_send`

以及 gate 中的20轮并发 stress，才能正式判定该缺陷关闭。

## 4. 当前环境阻塞

### 4.1 真实 PostgreSQL

- `127.0.0.1:46479`：不可达。
- `127.0.0.1:5432`：不可达。
- 当前容器无 docker/psql。
- 正式 gate 还要求 Python 3.12 + psycopg + 隔离库 `smarttaskboard_core_test`。

因此28个真实 PG 专项、空库 upgrade/downgrade/upgrade、5项×20轮并发 stress 尚未执行。

### 4.2 Python / Ruff

当前容器只有 Python 3.13.5，而项目声明 `>=3.12,<3.13`；当前环境也没有 ruff。故正式 Python 3.12 + Ruff 门禁尚未执行。

### 4.3 React Web

源码不带 `node_modules`。本轮 `npm ci` 网络安装发生工具层超时；离线重试发现 npm cache 缺 `yocto-queue` 包，因此无法在当前容器完成 Vitest / ESLint / TypeScript / Vite / Playwright。

### 4.4 微信开发者工具

当前容器无微信开发者工具，真实编译、375/390/430设备视觉和企业微信小程序模式尚未执行。

### 4.5 企业微信正式身份链路

当前代码仍存在 `cloud-functions/LoginService`、`loginServiceBaseUrl`、`wangxu.cloudAiToken` 及手机号验证码相关客户端逻辑。字段映射基线已经冻结，但以下内容尚未开发：

- `wx.qy.login`；
- FastAPI `/api/v1/auth/wecom`；
- `users.wecom_user_id` 身份映射登录；
- LoginService 退出；
- ChatService 短期 AI scoped token；
- 企业微信通讯录全量/增量同步；
- 企业微信真实应用测试。

因此功能16最终 E2E 不能继续使用 prototype/手机号登录作为生产发布证据。

## 5. 下一步测试顺序

1. 在 Python 3.12 + PostgreSQL 16 隔离环境升级空库到 `c2d3e4f5a6b7`。
2. 修复/同步剩余旧 PostgreSQL fixture，并跑 28 项真实 PG。
3. 重点验证 Outbox `SKIP LOCKED`，执行5项并发测试各20轮。
4. Python 3.12 环境跑 Ruff、pip check、完整非 PG 回归。
5. 恢复 Web 依赖后跑 Vitest、ESLint、build、Playwright。
6. 微信开发者工具用原始源码直接导入并执行真实编译/设备测试。
7. 实现企业微信正式登录和 LoginService 退出后，从企业微信身份重新跑 E2E-01～E2E-20。
8. 性能门禁：工作台/详情P95<2s、筛选P95<2.5s、高管聚合P95<4s。

## 6. 当前判定

`DEV-18 = IN_PROGRESS`。

当前不是发布成功状态。已经证明：企业微信部门外部ID迁移无非PG回归，小程序累计测试和配置问题已修复，Outbox并发缺陷已完成代码级修复；仍需真实 PostgreSQL、Python 3.12/Ruff、React Web、微信开发者工具和企业微信正式身份链路完成最终验收。

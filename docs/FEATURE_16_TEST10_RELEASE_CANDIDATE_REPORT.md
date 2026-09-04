# 功能16 / DEV-18 Test10 发布候选执行报告

> 日期：2026-09-04
> 基线：Test9 Release Candidate + 用户本地 Test9 实测报告
> 范围：只收口 Test9 剩余发布门禁，不新增产品功能。
> 当前状态：发布候选；当前容器无法执行 PostgreSQL、真实 Ruff、Python 3.12 与真实企业微信 E2E，因此不宣称最终发布成功。

## 1. 本轮目标

Test9 本地实测已经将失败收敛为两项核心门禁：

1. PostgreSQL 第一轮 28/28、第二轮同库 27/28，失败表现为状态日志总数仍为 13，但时间线中 version 13 出现在 version 12 之前。
2. Ruff 0.16.5 实跑仍有 31 个 I001 import block 错误。

此外，本地 Web 测试暴露 `@testing-library/dom` 未作为直接 devDependency 声明，首次干净安装场景不够可重复。

Test10 只修复以上工程质量问题；不改 Outbox、权限、available-actions 业务规则、任务状态机、自动归档语义、数据库结构或功能14/15。

## 2. PostgreSQL 第二轮失败根因修复

### 2.1 根因

`TaskStatusLogRepository` 原先按：

```text
created_at
status_log_id(UUID)
```

排序时间线。

完成验收时 `completion_approved`（task_version=12）与 `task_archived`（task_version=13）可在同一个事务中共享完全相同的 `created_at`。当时间戳相同时，随机 UUID 成为第二排序键，因此可能返回：

```text
... 11, 13, 12
```

而不是权威业务顺序：

```text
... 11, 12, 13
```

这与 Test9 本地失败“日志 total=13，但索引11实际13、期望12”一致。该问题是查询时间线的稳定排序缺陷，不需要改变 task_version 递增或自动归档状态机。

### 2.2 修复

`app/repositories/task_status_log.py`：

- `list_by_task_id()` 改为按 `task_version, created_at, status_log_id` 升序；
- `list_by_task_id_paginated()` 同样按 task_version 优先；
- `get_latest_for_task()` 改为 `task_version DESC, created_at DESC, status_log_id DESC`。

`task_version` 现在是任务状态时间线的第一权威排序键。

### 2.3 回归合同

新增/更新 Repository 与 Test10 静态合同，明确：

- 同一时间戳的 version 12/13 必须仍返回 12→13；
- latest 必须优先取最大 task_version；
- 不允许退回到 `created_at + UUID` 作为权威业务顺序。

## 3. PostgreSQL 多轮门禁增强

`scripts/run_postgresql_gate.sh` 新增：

```text
POSTGRES_GATE_PASSES
```

默认值为 2，且必须 >=2；同一数据库不清库连续执行 PostgreSQL 全量套件。

新增 `scripts/run_test10_release_gate.sh`，Test10 候选验证固定：

```text
POSTGRES_GATE_PASSES=3
```

开发候选期要求三轮连续通过，用于放大顺序依赖和 teardown 污染；普通发布 PG gate 仍至少两轮。

## 4. Ruff 收口

针对用户本地 Ruff 0.16.5 报告的 31 个 I001，本轮重新整理 `alembic/`、`app/`、`tests/`、`cloud-functions/`、`scripts/` 的 import block：

- 标准库 / 第三方 / first-party 分组；
- 同组成员按 Ruff/isort 约定整理；
- Alembic 中 `sqlalchemy` 与本项目 `alembic` package import 保持正确分组；
- 不改变 revision/down_revision、migration `upgrade/downgrade` 或业务逻辑。

当前执行容器没有 Ruff 二进制且无法联网安装，因此本报告**不宣称真实 `ruff check .` 已为 0**。正式结论仍必须由用户本地 Ruff 0.16.5/0.16.6 或 Test10 gate 实跑确认。

## 5. Web 干净安装依赖合同

本地 Test9 首次 Vitest 暴露 `@testing-library/dom` 缺失后才人工补装。

Test10 已将：

```text
@testing-library/dom ^10.4.1
```

显式加入 `web/package.json` 的 `devDependencies`，并同步 `package-lock.json`，避免依赖已有 node_modules 或间接 peer dependency。

当前容器成功执行离线 `npm install --package-lock-only` 验证 lock 合同；实际 `npm ci --offline` 因本容器缺少 `yocto-queue` npm 缓存包而 `ENOTCACHED`，因此没有在本容器重新宣称 Web lint/test/build 通过。用户 Test9 本地已有 Web lint 0、109/109、build PASS；Test10 最终仍必须用干净 `npm ci` 复验。

## 6. 当前容器实际执行证据

| 检查 | 结果 |
|---|---|
| Python | 3.13.5（项目要求 >=3.12,<3.13，正式门禁不匹配） |
| `compileall` | PASS |
| 后端非 PostgreSQL 全量 | **504 passed / 28 deselected** |
| Test10/Repository 定点合同 | PASS |
| 微信小程序累计测试 | **21/21 PASS** |
| 微信 JS `node --check` | PASS |
| ChatService task_intake/auth/config | PASS |
| Web package-lock 离线一致性 | PASS |
| Web `npm ci --offline` | BLOCKED：npm cache 缺包 `yocto-queue` |
| `bash -n` Test10/PG gate | PASS |
| PostgreSQL | 未执行：当前容器无 psycopg / PostgreSQL / Docker |
| Ruff | 未执行：当前容器无 Ruff 二进制 |
| Python 3.12正式 gate | 未执行：当前容器仅 Python 3.13.5 |
| 真实 WeCom E2E | BLOCKED：缺真实 AppID/凭据/HTTPS后端/fresh login code |

本轮非PG用例数由 Test9 的500增加至504，增加的是 Test10 发布合同/排序保护测试，不是新增产品功能。

## 7. 数据库与业务边界

本轮：

```text
新增业务表 = 0
新增字段 = 0
新增 Alembic migration = 0
```

明确未修改：

- Outbox `FOR UPDATE SKIP LOCKED`；
- notification 唯一约束；
- employee 权限边界；
- available-actions 稀疏节点合同；
- task_version 递增逻辑；
- completion review / 自动归档状态机；
- 功能14/15产品功能。

## 8. Test10 本地正式放行标准

用户本地/CI 应使用项目声明的 Python 3.12.x 并执行：

1. `ruff check .` → **0 error**；
2. 空 PostgreSQL 16 升级到唯一 head；
3. PG Pass1 → **28/28**；
4. 不清库 PG Pass2 → **28/28**；
5. Test10开发候选建议继续 Pass3 → **28/28**；
6. Outbox 5×20 → **100/100**；
7. 非PG → **504/504 或更多**；
8. Web 干净 `npm ci` → lint 0 → Vitest 109/109或更多 → build PASS；
9. 微信小程序 → 21/21或更多 + JS syntax PASS；
10. ChatService → PASS；
11. 最终 ZIP 解压到新目录后重复核心门禁。

真实企业微信 E2E 在真实 AppID、CorpID/AgentID/Secret、HTTPS 后端、测试员工和 fresh `wx.qy.login` code 到位后单独完成。

## 9. 当前结论

**Test10 已完成代码侧修复与当前环境可执行回归，但仍是 Release Candidate。**

在用户本地确认以下两项之前，不宣称 V1.1 最终发布成功：

```text
PostgreSQL 28/28 连续多轮
Ruff 0 error
```

随后再补 Python 3.12 正式 gate、Web 干净 npm ci 和真实 WeCom E2E。

## 10. 候选 ZIP 反向验收

生成候选 ZIP 后，已解压到全新 `/mnt/data/test10_reverse` 目录，不复用开发工作树，并执行：

```text
ZIP运行缓存检查                    PASS（无 __pycache__/.pyc/node_modules/.pytest_cache）
compileall                         PASS
后端非 PostgreSQL                 504 passed / 28 deselected
Repository + Test8/9/10合同        21 passed
Test10/PG gate bash -n             PASS
微信小程序累计                    21/21 PASS
微信全部 JS node --check           PASS
ChatService task_intake/auth/config 3/3 PASS
Web package-lock 离线一致性        PASS
```

反向验收与工作树结果一致。PostgreSQL、真实 Ruff、Python 3.12、干净 Web `npm ci`、真实 WeCom 仍受当前执行环境限制，未伪造 PASS。

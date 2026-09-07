# 旺序AI任务中枢｜Test15 端口区分与各端打开方式

> **Test15版本说明**：本次仅统一交付名称、解压目录和说明文档，不新增业务修改。
> 业务代码、测试脚本、配置模板、数据库模型和迁移均与Test14最后交付一致。
> 脚本、环境变量和库名示例中的 `test14` / `TEST14` 为保留的兼容标识，不要全局替换为Test15。
> 以前的测试结果属于Test14历史证据；Test15本次仅执行打包一致性和原修改范围检查，未重跑功能测试。
> **正式环境验收状态不变：仍为候选版本，未获生产放行。**

> 累计源码内 `docs/TEST14_*.md` 文件名为保持现有范围校验不变而保留；对外同步提供 `TEST15_*.md` 文档。


> 本文适用于Test15。端口不是版本号，也不表示“正式”。必须一起核对代码目录、进程、配置和数据库。  
> Test15累计包解压目录：smart-task-board-test15。本文不替换企业微信正式配置。

## 1. 分别从哪里打开

| 场景 | 打开方式 | 本地默认入口 | 数据与登录 |
|---|---|---|---|
| Web本地联调 | 电脑浏览器 | http://127.0.0.1:5174/login | 请求8001真实后端；prototype演示身份，不是生产SSO |
| FastAPI后端 | 浏览器检查或API客户端调用 | http://127.0.0.1:8001/health/ready；/docs | API服务，不是用户登录页面 |
| 小程序mock演示 | 微信开发者工具导入wechat-miniprogram | 无浏览器登录端口 | 模拟数据，不证明业务落库 |
| 小程序API联调 | 微信开发者工具导入专项联调副本 | config.js的apiBaseUrl指向隔离测试后端 | 必须确认mode=api；不能失败后以mock结果算通过 |
| 正式企业微信 | 员工从企业微信配置的应用入口进入 | 公司部署并配置的HTTPS入口 | 真实WeCom身份；最终域名和入口本次未验收 |

5173/8000是旧默认端口，不代表正式服务。Test13报告已出现打开旧目录Vite而误判版本的情况。5174/8001也可能被旧进程占用：不能只看地址判断Test15已生效。

5432、46479、46480是可能的PostgreSQL端口，不是登录页面。58805、9420等开发者工具自动化端口也不是用户登录入口。

手机中的127.0.0.1指手机自身，不是电脑。本文的回环地址供同机浏览器/开发工具使用；真机和正式企业微信需要合法且可访问的测试或正式域名，不能简单照搬。

## 2. 三种数据库用途要分开

| 用途 | 约定 | 保护 |
|---|---|---|
| 原有业务或demo库 | 用户现有实例，例如此前5432演示库 | 本轮不迁移、不seed、不清理 |
| 原技术门禁的全新测试库 | 原保护固定为127.0.0.1:46479/smarttaskboard_core_test | 必须是全新空库；原28项及新增4项在这里执行 |
| 本轮Web/HTTP联调库 | 新模板示例127.0.0.1:46480/smart_task_board_test14_test | 单独新建，用于保留本轮合成任务与浏览器复查 |

原有PG测试安全守卫绑定46479。本次没有修改这些守卫。该端口已被占用时，不得运行任何自动删除旧容器或清库命令；由操作者确认旧资源归属后自行安排空闲端口条件，或使用另一隔离运行环境。仅把环境变量改成另一个端口会被原门禁拒绝，不应以改代码绕过保护。

本轮门禁脚本不创建、删除容器或数据库。它只对操作者显式指定且通过原守卫的空测试库运行现有迁移和测试。32项×3轮使用同一个测试库，后续重跑整套空库门禁须另行准备新的空测试实例。

## 3. 启动Web联调

先准备项目原要求的Python3.12虚拟环境、原锁文件依赖，以及上述独立联调库。不要在仓库secrets/backend.env写prototype配置，也不要覆盖公司WeCom配置。

```bash
cd smart-task-board-test15
cp config-examples/test14-web.env.example /tmp/stb-test15-web.env
chmod 600 /tmp/stb-test15-web.env
```

在仓库外文件中填写新的测试数据库连接和随机JWT密钥，核对：

```text
APP_ENV=development
AUTH_MODE=prototype
PROTOTYPE_AUTH_ENABLED=true
ALLOW_TEST_EMPLOYEE_HEADER=false
PROTOTYPE_USER_EMPLOYEE_NOS=E-CREATOR,E-ASSIGNEE,E-REVIEWER,E-OBSERVER
CORS_ALLOWED_ORIGINS=http://127.0.0.1:5174,http://localhost:5174
```

仅当确认目标确为新建的smart_task_board_test14_test时，才执行初始化。以下不是日常启动步骤：

```bash
WANGXU_BACKEND_ENV_FILE=/tmp/stb-test15-web.env \
  .venv/bin/python -m alembic upgrade head

WANGXU_BACKEND_ENV_FILE=/tmp/stb-test15-web.env PYTHONPATH=. \
  .venv/bin/python scripts/seed_demo_data.py \
  --confirm-database-name smart_task_board_test14_test --dry-run

# 审核dry-run及连接目标后，显式应用测试员工数据：
WANGXU_BACKEND_ENV_FILE=/tmp/stb-test15-web.env PYTHONPATH=. \
  .venv/bin/python scripts/seed_demo_data.py \
  --confirm-database-name smart_task_board_test14_test --apply
```

在没有遗留AUTH_MODE/DATABASE_URL覆盖值的新终端中启动：

```bash
WANGXU_WEB_DEMO_ENV_FILE=/tmp/stb-test15-web.env \
  bash scripts/start-web-demo.sh
```

该已有启动入口默认使用5174/8001，拒绝端口被占用，不自动迁移或seed。核对终端打印的Project root、AUTH_MODE、Login URL，并保持进程运行。出现READY后，浏览器打开：

```text
http://127.0.0.1:5174/login
```

选择E-CREATOR。E-OBSERVER只能用于对照，不能代替有待接受任务的创建人验收。

## 4. 确认打开的是当前版本

macOS可先检查占用，再核对进程工作目录：

```bash
lsof -nP -iTCP:5174 -sTCP:LISTEN
lsof -nP -iTCP:8001 -sTCP:LISTEN
lsof -a -p <上一步取得的PID> -d cwd
```

两个进程目录必须属于本次smart-task-board-test15。占用未知时停止，不直接kill未知进程。不要运行脚本自动复用旧服务。

本机就绪检查按报告经验绕过代理：

```bash
curl --noproxy '*' -f http://127.0.0.1:8001/health/ready
curl --noproxy '*' -f http://127.0.0.1:8001/api/v1/auth/prototype-users
```

本轮F1不是继续修改CORS：它是含reassign_task的工作台响应校验错误。端口和进程已正确时，应检查接口状态与新的脱敏服务端诊断，不再通过更换空账号掩盖。

## 5. 执行正式技术门禁

先显式配置全新空PG门禁库的POSTGRES_TEST_DATABASE_URL；不要把包含密码的连接串发进报告。

```bash
PYTHON_BIN="$PWD/.venv/bin/python" \
  bash scripts/run_test14_technical_gate.sh
```

脚本只在自身子进程中隔离认证配置，使用原test_header测试模式，不修改正在运行的prototype或WeCom进程。会执行3.12检查、pip check、Ruff、scope、原PG门禁（本轮32项×3轮及原100次压力）、非PG、小程序、完整Web、ChatService。缺条件或任何失败都停止。

不要再直接运行会自动清理固定容器名的旧Test11默认创建分支。

## 6. 执行真实HTTP与浏览器门禁

先完成第3节的独立联调服务启动，确认它没有连接旧demo或业务库：

```bash
STB_TEST14_ALLOW_TEST_WRITES=1 \
PYTHON_BIN="$PWD/.venv/bin/python" \
STB_REAL_E2E_BROWSER_CHANNEL=chrome \
  bash scripts/run_test14_live_gate.sh
```

脚本不会自动启动、重启或复用未知后端。它在隔离库创建合成任务，不自动删除任务，便于复查；清理整个测试实例由操作者确认后进行。正式门禁只允许E-CREATOR或另一个明确创建人身份，不允许用观察者替代。

HTTP验证分别覆盖空、合法、非法周期；浏览器主动先发送真实任务，再登录创建人进入工作台、查看详情、返回、刷新与读取/me。现有登录用例和新增F1用例都连续3次。默认系统Chrome；缺浏览器须先安装，不能以跳过算通过。

脚本关闭新增用例的trace/video以免泄露令牌；原dev-18用例的失败trace仍可能含敏感信息，分享前必须脱敏。

## 7. 小程序真实页面验收

本轮小程序生产文件与Test13完全一致。须在专项副本检查mode=api和apiBaseUrl，并使用已有受控测试身份机制；不修改正式企业微信登录逻辑。

操作：录入任务并保留AI待确认提示 → 不回答AI → 手动补齐9项 → 来源留空 → 进入确认发送 → 发送 → 读详情及工作台。

记录任务ID、接口状态、数据库状态及通知接收人。验证没有提交AI回答请求，任务待接受、没有创建阶段节点，原有权限保持。不允许仅打开高管mock页面，就认定这条创建链路通过。

真实模型输出联通和正式企业微信SSO另列验收。本地fake或固定AI结果测试不能冒充真实Qwen验证。

## 8. 交付和替换注意

只导入小程序不能修复F1/F2：本轮必须部署/启动新累计包中的后端和Web；独立ChatService需要同步新的任务录入提示词。数据库结构不需要新增迁移。

任何上线结论以新解压目录的实际完整门禁结果为准。本容器执行结果与待执行项见TEST14_EXECUTION_REPORT.md。

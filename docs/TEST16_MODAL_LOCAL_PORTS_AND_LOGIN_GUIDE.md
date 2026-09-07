# Test16 弹窗修正版：端口区分、各端打开方式与复验步骤

> 根目录：`smart-task-board-test16`。先确认进程工作目录，再确认端口。
> 当前交付Test16-Modal-Hotfix：两处小程序弹窗已修复；原Test16后端幂等修复及数据库结构不变。
> 本文是打开与验收说明，不表示这些地址已经在你电脑上运行。

## 一、端口不是“演示/正式”身份

| 入口 | 怎么打开 | 含义 |
|---|---|---|
| Web本地真实接口联调 | 浏览器 `http://127.0.0.1:5174/login` | prototype演示身份，但实际访问后端与隔离PG，不是mock数据 |
| FastAPI后端 | `http://127.0.0.1:8001/health/ready`；接口文档 `/docs` | API服务，不是用户登录页 |
| 5173 / 8000 | 不作为本轮默认入口 | 可能是旧默认开发实例，不等于正式环境，不能盲目复用 |
| PG门禁库46479 | 数据库工具或测试脚本连接 | 原安全守卫只接受`smarttaskboard_core_test`；不是浏览器入口 |
| PG联调库46480 | 经确认的本地数据库连接 | 与门禁库分开。已有Test15现场数据应保留，不自动清空 |
| 小程序mock | 微信开发者工具导入 `wechat-miniprogram`，原mock配置 | 页面演示，不能作为真实保存/发送/权限验收 |
| 小程序API | 联调副本配置API模式和测试后端，在开发者工具打开 | 请求真实后端；必须验证没有自动回落mock |
| 正式企业微信 | 最终部署的企业微信应用入口和HTTPS域名 | 不是5174/8001；正式域名及SSO尚未由本轮验收确认 |

电脑的127.0.0.1指电脑本机，手机的127.0.0.1指手机本身。
上述回环地址用于电脑浏览器及相应本地工具，不可直接当作手机可访问地址。
真机API需要另行配置可达的测试HTTPS地址及平台要求，不修改生产域名来凑通本地测试。

## 二、先核对版本，避免旧进程

解压累计源码，进入：

```bash
cd /你的解压位置/smart-task-board-test16
.venv/bin/python scripts/verify-test16-modal-scope.py
```

尚未建立项目venv时，可以用明确可用的Python执行只读范围校验；正式门禁必须使用3.12。
本轮“接受任务无反应”修复在小程序，必须导入新的小程序目录并重新编译；只重启后端不能更新弹窗。尚未部署旧Test16后端幂等修复的环境，仍需同步更新后端。

macOS检查占用与工作目录：

```bash
lsof -nP -iTCP:5174 -sTCP:LISTEN
lsof -nP -iTCP:8001 -sTCP:LISTEN
lsof -a -p <你刚查到的PID> -d cwd
```

不要批量kill端口或清理其他开发者工具进程。
若仍占用，由操作者确认归属并正常关闭，不能把未知旧实例当作本轮服务。
仅改目录名不代表后端进程已经更新。

## 三、正式技术门禁：空门禁库与联调库不能混用

前置条件：Python3.12项目venv、项目依赖、Ruff、Node/npm及Web锁文件依赖、
实际PostgreSQL16测试实例、项目psycopg。

1. 保留Test15的46480问题复现现场，不自动删除。
2. 为本轮准备明确属于自己的、真正可销毁的空门禁库。
3. 原守卫要求目标为`127.0.0.1:46479/smarttaskboard_core_test`；不能换到业务库绕过。
4. 若46479有旧实例或表，停止，先由操作者确认所有权。脚本不提供清库命令。
5. 只需在门禁开始前为空。脚本迁移一次，三轮复用同一库验证隔离；不要每轮清库。

同一个终端内执行：

```bash
export PYTHON_BIN="$PWD/.venv/bin/python"
export POSTGRES_TEST_DATABASE_URL='postgresql+psycopg://测试账号:测试密码@127.0.0.1:46479/smarttaskboard_core_test'
bash scripts/run_test16_technical_gate.sh
```

占位账号和密码必须替换为本轮专用测试凭据，不使用生产凭据，不提交到源码。
脚本只对子进程设置test_header/fake AI等测试配置，不覆盖正在运行的prototype或WeCom服务。
本轮目标：40项PG×3轮全部通过、原Outbox100/100、完整非PG、小程序、Web、ChatService通过，
整体EXIT=0。日志中出现SKIP/deselected要按用例范围核对，不能把未执行项计为通过。

## 四、Web联调环境单独启动

沿用原启动入口和环境模板，不修改全局配置：

```bash
cp config-examples/test14-web.env.example /tmp/stb-test16-web.env
```

编辑临时环境文件，填写本轮隔离联调PG连接和随机JWT密钥；确认：
- `APP_ENV=development`
- `AUTH_MODE=prototype`
- `PROTOTYPE_AUTH_ENABLED=true`
- `ALLOW_TEST_EMPLOYEE_HEADER=false`
- 有实际存在、启用的演示员工白名单
- `CORS_ALLOWED_ORIGINS`精确包含实际5174来源
- 没有连接现有业务库或生产库

保留的`test14`模板文件名只是兼容标识，不要全局替换库名或环境变量。
启动脚本不会迁移、seed或清库。用户和数据库的初始化只能另行针对已确认测试目标执行。

```bash
WANGXU_WEB_DEMO_ENV_FILE=/tmp/stb-test16-web.env \
  bash scripts/start-web-demo.sh
```

保持该终端运行，出现`WEB DEMO READY`后打开：

`http://127.0.0.1:5174/login`

服务健康检查：

```bash
curl --noproxy '*' http://127.0.0.1:8001/health/ready
```

Ctrl+C正常关闭本次启动的服务。不要靠短命后台命令启动后立即退出终端。
本地代理探测只绕过回环请求，不全局关闭公司代理，也不改外部AI网络配置。

## 五、真实HTTP及浏览器验收

另开终端，仍进入同一Test16目录。确认8001后台连接的是允许写测试数据的隔离联调库后：

```bash
export PYTHON_BIN="$PWD/.venv/bin/python"
export STB_TEST16_ALLOW_TEST_WRITES=1
export PLAYWRIGHT_BASE_URL=http://127.0.0.1:5174
export STB_REAL_E2E_API_BASE_URL=http://127.0.0.1:8001
export STB_E2E_CREATOR=E-CREATOR
export STB_E2E_ASSIGNEE=E-ASSIGNEE
export STB_E2E_REVIEWER=E-REVIEWER
export STB_REAL_E2E_BROWSER_CHANNEL=chrome
bash scripts/run_test16_live_gate.sh
```

员工号按本轮实际测试数据替换。创建人不能换成观察者来避开数据触发条件。
该脚本复用原HTTP脚本、原dev-18/dev-19，并新增dev-20重放浏览器测试，重复执行三次。
内部仅对子进程开启旧`STB_TEST14_ALLOW_TEST_WRITES`兼容变量，不写回配置文件。

此门禁会写测试任务，保留任务ID供数据库核对，不自动清理任何业务数据。
同Key重放必须保留首次请求的`expected_task_version`，不能改用响应中的新版本掩盖问题。
数据库日志/通知去重以PG测试及专门核对为证据，浏览器测试本身不宣称检查了全部底层表。

## 六、小程序与正式企业微信另行验收

本轮小程序仅task-detail.acceptTask()和review.approve()修改。其余小程序逻辑与原Test16相同；累计为24个测试文件、53个JS文件。可复跑此前已通过的高管/员工双向门禁。
API模式需补录：不回答AI→手工补齐9项→来源留空→确认发送→详情/工作台，
并以真实请求和数据库结果确认；仅mock演示不算这一项通过。

游客AppID、本地模拟编译、prototype认证不等于正式企业微信SSO或真机上线验收。
本轮没有修改平台CLI、自动化SDK、组织授权或生产登录流程。

## 七、失败时保留哪些记录

提交本轮源码SHA-256、实际进程目录、环境版本、整体门禁出口、
完整失败用例名、第一次与重复请求的状态码、脱敏后的任务ID/版本、日志和通知核对结果。
不要提交JWT、密码、完整数据库URL、员工隐私或任务正文。

发现失败先保留现场，不先删任务、不先改状态、不换观察者账号。
正式结果写明“通过/失败/未执行”，不要沿用Test15结果作为Test16新证据。

## 八、本次最直接的打开步骤

1. 只体验弹窗修复：解压Test16-Modal-Hotfix-wechat-miniprogram.zip，在微信开发者工具中导入其中wechat-miniprogram目录并重新编译。此包仍保持原mode:"mock"默认配置；截图中的待接受示例可用于本地演示，不需要浏览器5174或后端8001。
2. 验证真实接口：从纯净交付目录复制一份单独的联调目录，在该副本config.js中使用mode:"api"、非空apiBaseUrl和经过确认的测试认证配置。电脑模拟器可连接本地8001；真机不可把127.0.0.1当作电脑地址，需可达测试HTTPS服务。本轮不替你配置公司域名或企业凭据。
3. 进入待接受任务，点击接受，原生确认按钮必须为“确认接受”；验收弹窗确认按钮必须为“确认通过”。没有变化先检查导入目录与缓存，不要删除任务、重置数据库或放开权限。
4. API联调要同时看Network中的accept/approve-completion请求和后端返回，不能只根据页面跳转判断成功。完整步骤见TEST16_MODAL_ACCEPTANCE_CHECKLIST.md。

范围校验请先对纯净交付副本执行；个人环境配置不写回发布包。无需清除现有任务、登录凭据或微信开发者工具的全局配置。本轮没有新增端口、云服务或数据库。

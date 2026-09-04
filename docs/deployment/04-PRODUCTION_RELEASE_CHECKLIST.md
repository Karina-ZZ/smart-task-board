# 旺序AI任务中枢｜生产发布检查单

发布版本：__________  日期：__________  发布负责人：__________

## A. 代码与自动化

- [ ] 发布版本冻结并记录SHA-256
- [ ] Ruff = 0 error
- [ ] Python compileall PASS
- [ ] Alembic只有一个head
- [ ] 空库 `alembic upgrade head` PASS
- [ ] 后端非PostgreSQL测试全部通过
- [ ] PostgreSQL专项全部通过并连续回归无退化
- [ ] Outbox并发回归通过，无重复发送
- [ ] Web lint/test/build通过（如发布Web）
- [ ] 小程序累计自动化通过
- [ ] 微信开发者工具使用正式AppID编译通过

## B. 生产安全

- [ ] `APP_ENV=production`
- [ ] `AUTH_MODE=wecom`
- [ ] `ALLOW_TEST_EMPLOYEE_HEADER=false`
- [ ] `PROTOTYPE_AUTH_ENABLED=false`
- [ ] `CHAT_REQUIRE_AUTH=true`
- [ ] Secret均未进入源码/ZIP/前端
- [ ] PostgreSQL未暴露公网端口
- [ ] HTTPS证书有效
- [ ] API域名和AI域名解析正确

## C. 企业微信

- [ ] CorpID正确
- [ ] AgentID正确
- [ ] Secret正确
- [ ] 正式AppID正确
- [ ] 应用可见范围正确
- [ ] active员工登录通过
- [ ] 高管登录和授权范围通过
- [ ] disabled员工拒绝
- [ ] 未绑定员工拒绝
- [ ] 真实 `wx.qy.login` E2E通过

## D. AI与通知

- [ ] Qwen真实调用通过
- [ ] FastAPI签发AI短Token通过
- [ ] ChatService拒绝无Token请求
- [ ] 企业微信真实任务通知发送通过
- [ ] 通知点击后重新鉴权通过
- [ ] 提醒调度Worker稳定运行

## E. 业务Smoke

- [ ] 创建任务
- [ ] 确认发送
- [ ] 主承办人接受
- [ ] AI拆解成功
- [ ] 协办节点承接
- [ ] 节点执行
- [ ] 进度汇报/卡点
- [ ] 提交完成
- [ ] 验收
- [ ] 自动归档
- [ ] 高管看板
- [ ] 员工任务联合筛选与返回恢复

## F. 数据与回滚

- [ ] 发布前数据库备份成功
- [ ] 备份SHA-256已记录
- [ ] 恢复演练已有有效证据
- [ ] 上一Release目录仍保留
- [ ] 代码回滚步骤确认
- [ ] 数据库迁移兼容性确认

## 发布结论

- [ ] GO
- [ ] BLOCKED
- [ ] ROLLBACK

阻塞/备注：

```text

```

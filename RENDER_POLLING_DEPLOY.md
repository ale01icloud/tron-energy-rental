# 🚀 Render.com 部署指南（Polling模式 - 推荐）

## 为什么使用Polling模式？

Webhook模式在Gunicorn环境下存在异步事件循环兼容性问题。**Polling模式更稳定可靠**！

---

## 📋 部署步骤

### 1. 在Render Dashboard中修改配置

进入您的服务设置页面：

#### ✅ 修改Start Command
```
python bot.py
```

#### ✅ 删除环境变量
删除 `USE_WEBHOOK` 环境变量（如果存在）

#### ✅ 保留的环境变量
- `TELEGRAM_BOT_TOKEN` = 您的bot token
- `OWNER_ID` = `7784416293`
- `DATABASE_URL` = 数据库连接URL（自动创建，见下方）

#### ✅ 配置PostgreSQL数据库

1. 在Render Dashboard中，点击 **New +** → **PostgreSQL**
2. 创建免费数据库实例：
   - **Name**: `telegram-finance-bot-db`（或任意名称）
   - **Database**: `financebot`
   - **User**: `financebot_user`
   - **Region**: 选择与Bot相同的区域
   - **PostgreSQL Version**: 16
   - **Instance Type**: Free

3. 创建后，复制 **Internal Database URL**

4. 回到Bot服务设置，添加环境变量：
   - **Key**: `DATABASE_URL`
   - **Value**: 粘贴刚才复制的Internal Database URL

### 2. 保存并重新部署

点击 **Manual Deploy** → **Deploy latest commit**

---

## ✅ 成功标志

部署成功后，日志显示：

```
🔄 使用 Polling 模式（本地开发）
✅ Bot 处理器已注册
🌐 启动 HTTP 保活服务器...
✅ HTTP 服务器已启动（后台运行）
🎉 机器人正在运行，等待消息...
```

---

## 🔄 防止休眠（重要！）

Render免费套餐15分钟无流量会休眠。解决方案：

### 方法1：UptimeRobot（推荐）

1. 注册 [UptimeRobot](https://uptimerobot.com)（免费）
2. 添加Monitor：
   - **Monitor Type**: HTTP(s)
   - **URL**: `https://你的服务名.onrender.com/health`
   - **Monitoring Interval**: 5 minutes
3. 完成！UptimeRobot会每5分钟ping一次保持服务活跃

### 方法2：Cron-job.org

1. 注册 [Cron-job.org](https://cron-job.org)
2. 创建任务访问 `/health` 端点
3. 设置间隔：5分钟

---

## 💾 数据持久化（重要！）

### ✅ 使用PostgreSQL数据库

从v2.0开始，bot使用PostgreSQL数据库存储：
- ✅ 群组费率和汇率设置
- ✅ 管理员列表
- ✅ 群组交易记录

**关键优势：**
1. **重新部署不丢失数据** - 费率/汇率设置永久保存
2. **自动备份** - Render数据库自动备份
3. **多实例共享** - 支持未来扩展

**注意：** 
- 日志文件（`data/logs/`）仍存储在本地临时文件系统
- 重新部署后日志会重置（不影响核心数据）

---

## 📊 优势对比

| 特性 | Polling模式 | Webhook模式 |
|------|------------|-------------|
| 稳定性 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| Gunicorn兼容 | ✅ 完美 | ❌ 有问题 |
| 配置复杂度 | ✅ 简单 | ⚠️ 复杂 |
| 需要外部保活 | ⚠️ 是 | ⚠️ 是 |
| 数据持久化 | ✅ PostgreSQL | ✅ PostgreSQL |

---

## 🛠️ 故障排查

### 问题：Bot不回复消息

**检查列表：**
1. ✅ 确认环境变量正确设置
2. ✅ 查看Render日志是否有错误
3. ✅ 确认bot token有效
4. ✅ 确认UptimeRobot正在运行

### 问题：服务频繁休眠

**解决：**
- 确保UptimeRobot或Cron-job正在工作
- 间隔设置为5分钟（不要超过10分钟）

---

## 💡 提示

- Polling模式不需要webhook URL配置
- HTTP服务器在5000端口（Render会自动映射到$PORT）
- 日志会显示所有消息处理情况
- 私聊消息会转发给OWNER_ID (7784416293)

---

**部署成功后，在Telegram中测试bot是否响应！** ✨

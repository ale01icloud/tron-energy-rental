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

## 📊 优势对比

| 特性 | Polling模式 | Webhook模式 |
|------|------------|-------------|
| 稳定性 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| Gunicorn兼容 | ✅ 完美 | ❌ 有问题 |
| 配置复杂度 | ✅ 简单 | ⚠️ 复杂 |
| 需要外部保活 | ⚠️ 是 | ⚠️ 是 |

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

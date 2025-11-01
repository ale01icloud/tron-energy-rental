# 📦 ClawCloud Run 部署指南

## 🌟 平台特点

ClawCloud Run 是一个轻量级云原生部署平台，提供：
- ✅ **$5/月免费额度**（GitHub账号>180天，终身有效）
- ✅ **无需信用卡**
- ✅ **Docker原生支持**
- ✅ **5分钟快速部署**
- ✅ **可视化管理**

**官方网站**：https://run.claw.cloud  
**控制台**：https://console.run.claw.cloud  
**文档**：https://docs.run.claw.cloud

---

## 🚀 快速部署步骤

### 📋 准备工作

1. **注册账号**
   - 访问：https://console.run.claw.cloud
   - 使用GitHub登录（账号需>180天可获取$5/月免费额度）
   - 验证账户余额（应显示$5赠金）

2. **准备Bot Token**
   - 打开Telegram搜索 `@BotFather`
   - 发送 `/newbot` 创建新bot
   - 保存Bot Token（格式：`123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`）

3. **获取您的Telegram ID**
   - 打开Telegram搜索 `@userinfobot`
   - 点击Start，获取您的User ID（如：`7784416293`）

---

## 🐳 方法1：使用Docker Hub部署（推荐）

### 步骤1：构建并推送Docker镜像

**在本地电脑上执行：**

```bash
# 1. 登录Docker Hub（需要先注册账号 hub.docker.com）
docker login

# 2. 构建镜像（替换 yourusername 为您的Docker Hub用户名）
docker build -t yourusername/telegram-finance-bot:latest .

# 3. 推送到Docker Hub
docker push yourusername/telegram-finance-bot:latest
```

### 步骤2：在ClawCloud部署

1. **打开控制台**：https://console.run.claw.cloud

2. **创建应用**
   - 点击左侧 **App Launchpad**
   - 点击 **Create App**

3. **配置应用**
   ```
   应用名称：telegram-finance-bot
   镜像名称：yourusername/telegram-finance-bot:latest
   部署模式：固定实例（Fixed Instances）
   实例数量：1
   ```

4. **配置资源**
   ```
   CPU：0.5 核
   内存：512 MB
   存储：1 GB
   ```

5. **网络配置**
   ```
   容器端口：10000
   启用外部访问：✅ 开启
   协议：HTTP
   ```

6. **环境变量**（点击 Environment Variables）
   ```
   TELEGRAM_BOT_TOKEN = 您的Bot Token
   OWNER_ID = 您的Telegram ID
   PORT = 10000
   ```

7. **点击右上角 Deploy 按钮**

8. **等待部署**
   - 状态变为 "Running" 即成功
   - 获取公网URL（如：`https://abc123.clawcloud.io`）

9. **验证部署**
   - 打开浏览器访问：`https://abc123.clawcloud.io/health`
   - 应显示：`{"status": "healthy", "mode": "Polling"}`
   - 在Telegram给您的bot发消息测试

---

## 📦 方法2：使用GitHub自动部署

### 步骤1：推送代码到GitHub

```bash
# 如果还没有GitHub仓库
git init
git add .
git commit -m "Deploy to ClawCloud"
git branch -M main
git remote add origin https://github.com/yourusername/telegram-finance-bot.git
git push -u origin main
```

### 步骤2：配置ClawCloud自动构建

1. **在ClawCloud控制台**
   - App Launchpad → Create App
   - 选择 **GitHub Integration**

2. **连接GitHub仓库**
   - 授权ClawCloud访问您的GitHub
   - 选择 `telegram-finance-bot` 仓库
   - 选择 `main` 分支

3. **构建配置**
   ```
   Dockerfile路径：./Dockerfile
   构建上下文：/
   ```

4. **其他配置同方法1**（端口、环境变量、资源等）

5. **启用自动部署**
   - 开启 "Auto Deploy on Push"
   - 以后每次推送代码，自动重新部署

---

## 🔧 高级配置

### 自定义域名（可选）

1. **在ClawCloud获取公网域名**
   - 部署成功后，查看应用详情
   - 记下ClawCloud分配的域名（如：`xyz.clawcloud.io`）

2. **配置DNS（在您的域名注册商）**
   ```
   类型：CNAME
   名称：bot（或其他子域名）
   目标：xyz.clawcloud.io
   ```

3. **在ClawCloud添加自定义域名**
   - 应用详情页 → Custom Domain
   - 输入：`bot.yourdomain.com`
   - ClawCloud自动签发免费SSL证书（3-5分钟）

### 持久化存储（重要！）

⚠️ **默认情况下，容器重启会丢失数据**

**解决方案**：挂载持久化卷

1. **在ClawCloud控制台**
   - 应用设置 → Volumes
   - 点击 Add Volume

2. **配置卷**
   ```
   卷名称：bot-data
   挂载路径：/app/data
   大小：1 GB
   ```

3. **重新部署**
   - 数据将永久保存在 `/app/data` 目录

### 查看日志

1. **在ClawCloud控制台**
   - 应用详情 → Logs 按钮
   - 实时查看bot运行日志

2. **进入容器终端**
   - 应用详情 → Terminal 按钮
   - 执行命令：`ls data/logs/`

---

## 💰 成本估算

**免费额度**：$5/月

**预计消耗**（0.5核CPU + 512MB内存，24/7运行）：
- CPU：0.5核 × 720小时 ≈ $2.50/月
- 内存：512MB × 720小时 ≈ $1.50/月
- 流量：可忽略
- **总计**：约$4/月

✅ **完全在免费额度内！**

---

## 🔍 故障排查

### Bot无响应

**检查步骤**：
1. **查看容器状态**
   - 确认状态为 "Running"
   - 如果是 "Failed"，点击 Logs 查看错误

2. **验证环境变量**
   - 确认 `TELEGRAM_BOT_TOKEN` 正确
   - 确认 `OWNER_ID` 是纯数字

3. **检查端口**
   - 容器端口必须是 `10000`
   - 协议选择 `HTTP`

### 数据丢失

**原因**：容器重启后数据被清空

**解决**：
1. 配置持久化卷（参考上面"持久化存储"）
2. 或使用 `重置默认值` 命令快速恢复设置

### 日志查看

```bash
# 在ClawCloud Terminal中
cd /app
ls data/logs/
tail -f data/logs/private_chats/user_*.log
```

---

## 📊 监控配置（可选）

### 健康检查

ClawCloud自动监控 `/health` 端点：
- 正常：返回200状态码
- 异常：自动重启容器

### 重启策略

默认配置：
- 失败自动重启
- 最大重试次数：3次
- 重启间隔：10秒

---

## 🎯 部署清单

- [ ] 注册ClawCloud账号（GitHub登录）
- [ ] 验证$5免费额度
- [ ] 准备Bot Token和OWNER_ID
- [ ] 构建Docker镜像（或连接GitHub）
- [ ] 创建应用并配置环境变量
- [ ] 配置资源（0.5核/512MB）
- [ ] 设置端口（10000）
- [ ] 启用外部访问
- [ ] 部署并验证（访问/health）
- [ ] 配置持久化卷（重要！）
- [ ] 在Telegram测试bot功能

---

## 🔗 相关链接

- **ClawCloud控制台**：https://console.run.claw.cloud
- **官方文档**：https://docs.run.claw.cloud
- **GitHub仓库**：https://github.com/lea499579-stack/telegram-finance-bot
- **本项目文档**：
  - [README.md](README.md) - 完整功能说明
  - [管理员指令大全.md](管理员指令大全.md) - 指令速查
  - [RENDER_POLLING_DEPLOY.md](RENDER_POLLING_DEPLOY.md) - Render部署（对比）

---

## 💡 ClawCloud vs Render对比

| 特性 | ClawCloud Run | Render |
|------|---------------|--------|
| **免费额度** | $5/月（永久） | 750小时/月 |
| **稳定性** | ⭐⭐⭐⭐ | ⭐⭐⭐（Web Service不稳定） |
| **部署方式** | Docker | 源代码/Docker |
| **数据持久化** | 需配置卷 | 重启丢失 |
| **健康检查** | 自动 | 需手动优化 |
| **适用场景** | 长期运行 | 短期测试 |

---

## 🎉 完成！

部署完成后：
1. ✅ Bot 24/7在线运行
2. ✅ 私聊消息自动转发
3. ✅ 群发功能可用
4. ✅ 多群组独立记账
5. ✅ 数据持久化保存

**祝您使用愉快！** 🚀

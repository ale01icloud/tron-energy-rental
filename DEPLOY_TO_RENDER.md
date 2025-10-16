# 🚀 部署Telegram记账机器人到Render

## 📋 准备工作

1. **注册Render账号**
   - 访问 https://render.com
   - 使用GitHub账号注册（推荐）或邮箱注册

2. **准备GitHub仓库**
   - 将此项目代码推送到GitHub（公开或私有仓库均可）

## 🔧 部署步骤

### 方法一：使用render.yaml自动部署（推荐）

1. **连接GitHub仓库**
   - 登录Render控制台
   - 点击 "New +" → "Blueprint"
   - 连接您的GitHub账号
   - 选择此项目的仓库

2. **配置环境变量**
   - Render会自动读取`render.yaml`配置
   - 系统会提示您输入环境变量：
     - `TELEGRAM_BOT_TOKEN`: 您的Telegram机器人Token
     - `SESSION_SECRET`: 随机字符串（可选）

3. **完成部署**
   - 点击"Apply"开始部署
   - 等待构建和部署完成（约2-5分钟）

### 方法二：手动创建Web Service

1. **创建新服务**
   - 登录Render控制台
   - 点击 "New +" → "Web Service"
   - 连接您的GitHub仓库

2. **配置服务**
   - **Name**: telegram-accounting-bot（或自定义名称）
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120 bot:app`

3. **设置环境变量**
   - 在"Environment"标签下添加：
     - Key: `TELEGRAM_BOT_TOKEN`
     - Value: 您的机器人Token（从@BotFather获取）
     - Key: `USE_WEBHOOK`
     - Value: `true`（启用Webhook模式，适用于Web Service）
   
4. **选择计划**
   - **Free Plan**: 适合测试，但会在15分钟无活动后休眠
   - **Starter Plan** ($7/月): 推荐，保持24/7运行

5. **部署**
   - 点击"Create Web Service"
   - 等待部署完成

## 🔄 更新现有服务到Gunicorn生产服务器

**重要**：如果您已经部署了服务且看到Flask开发服务器警告，需要手动更新启动命令：

### 步骤：

1. **登录Render Dashboard**
   - 访问 https://dashboard.render.com
   - 找到您的服务（telegram-accounting-bot）

2. **更新启动命令**
   - 点击服务名称进入详情页
   - 点击左侧 **"Settings"** 标签
   - 找到 **"Start Command"** 设置
   - 修改为以下命令：
     ```bash
     gunicorn --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120 bot:app
     ```
   - 点击 **"Save Changes"**

3. **重新部署**
   - 返回服务详情页
   - 点击右上角 **"Manual Deploy"** → **"Deploy latest commit"**
   - 等待部署完成

4. **验证成功**
   - 查看日志，应该看到：
     ```
     [INFO] Starting gunicorn 21.2.0
     [INFO] Listening at: http://0.0.0.0:10000
     ```
   - **不再显示Flask开发服务器警告**

---

## ⚙️ 重要配置说明

### 免费计划限制
- ⚠️ 免费计划会在15分钟无活动后自动休眠
- ⚠️ 机器人休眠期间无法接收消息
- 💡 建议：升级到Starter计划（$7/月）保持24/7运行

### 保持运行（使用免费计划）
✅ **已内置自动保活机制**
- 代码已自动集成每10分钟自我ping功能
- 无需额外配置，部署后自动防止休眠
- 在日志中可以看到"💓 保活ping成功"消息

**备用方案**（如内置保活失效）：
1. 使用UptimeRobot等服务每10分钟ping一次您的服务
2. URL: `https://your-app-name.onrender.com/health`

### 数据持久化
- ⚠️ Render免费计划不提供持久存储
- 💡 建议：使用Render的PostgreSQL数据库或外部数据库
- 当前数据存储在`data/`目录，服务重启会丢失

## 🔍 部署后检查

1. **查看日志**
   - 在Render控制台的"Logs"标签查看运行日志
   - 应该看到"机器人正在运行，等待消息..."

2. **测试机器人**
   - 在Telegram中向机器人发送消息
   - 检查是否正常响应

3. **监控状态**
   - 在Render控制台查看服务状态
   - 绿色"Live"表示运行正常

## 📝 故障排查

### 问题1: 机器人无响应
- 检查环境变量`TELEGRAM_BOT_TOKEN`是否正确设置
- 查看Render日志是否有错误信息
- 确认机器人Token有效（在@BotFather中检查）

### 问题2: 数据丢失
- 升级到付费计划使用持久磁盘
- 或配置外部数据库存储

### 问题3: 服务频繁休眠
- 升级到Starter计划（$7/月）
- 或使用外部服务定时ping

## 💰 费用说明

- **Free Plan**: $0/月（有休眠限制）
- **Starter Plan**: $7/月（推荐，24/7运行）
- **Standard Plan**: $25/月（更多资源）

## 🔗 有用链接

- Render文档: https://render.com/docs
- Telegram Bot文档: https://core.telegram.org/bots
- UptimeRobot（保活服务）: https://uptimerobot.com

## ✅ 部署完成

部署成功后，您的Telegram记账机器人将24/7运行（如使用付费计划），可以随时接收和处理消息！

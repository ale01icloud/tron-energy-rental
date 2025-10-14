# Telegram 机器人 🤖

这是一个简单的 Python Telegram 机器人项目。

## 📁 项目文件

- `bot.py` - Telegram 机器人主程序
- `main.py` - 简单的 Python 示例程序
- `requirements.txt` - Python 依赖包列表

## 🚀 如何运行机器人

### 方法 1：使用 Shell 命令
在 Shell 中运行：
```bash
python bot.py
```

### 方法 2：修改 Workflow
如果您想让机器人自动运行，可以在 Shell 中执行：
```bash
# 这会让机器人在后台运行
python bot.py
```

## 🤖 机器人功能

机器人支持以下命令：

- `/start` 或 `/hello` - 显示欢迎消息
- `/help` - 显示帮助信息
- `/info` - 显示你的用户信息

你也可以直接发送任何文本消息，机器人会回复你！

## 📦 安装依赖

如果需要安装或更新依赖包：
```bash
pip install -r requirements.txt
```

或者直接安装 Telegram bot 库：
```bash
pip install pyTelegramBotAPI
```

## 🔑 配置 Bot Token

Bot Token 已经配置在环境变量中（TELEGRAM_BOT_TOKEN）。

如果需要更改：
1. 打开 Replit 的 Secrets（工具面板）
2. 编辑 `TELEGRAM_BOT_TOKEN` 的值

## 💡 如何测试机器人

1. 运行 `python bot.py`
2. 在 Telegram 中找到你的机器人（使用你在 BotFather 中设置的用户名）
3. 发送 `/start` 命令
4. 尝试其他命令或发送消息

## 🛠️ 自定义机器人

编辑 `bot.py` 文件来添加新功能：

```python
@bot.message_handler(commands=['yourcommand'])
def your_function(message):
    bot.reply_to(message, "你的回复")
```

## 📚 更多信息

- [pyTelegramBotAPI 文档](https://pytba.readthedocs.org)
- [Telegram Bot API 文档](https://core.telegram.org/bots/api)

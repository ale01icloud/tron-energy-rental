#!/usr/bin/env python3
import os
import telebot

BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')

if not BOT_TOKEN:
    print("错误：未找到 TELEGRAM_BOT_TOKEN 环境变量")
    print("请在 Replit 中添加您的 Telegram Bot Token")
    exit(1)

bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start', 'hello'])
def send_welcome(message):
    """处理 /start 和 /hello 命令"""
    bot.reply_to(message, 
        "你好！我是你的 Telegram 机器人！👋\n\n"
        "可用命令：\n"
        "/start - 显示欢迎消息\n"
        "/help - 显示帮助信息\n"
        "/info - 显示你的信息"
    )

@bot.message_handler(commands=['help'])
def send_help(message):
    """处理 /help 命令"""
    help_text = """
📚 帮助信息

这是一个简单的 Telegram 机器人示例。

可用命令：
/start - 开始使用机器人
/hello - 打招呼
/help - 显示此帮助信息
/info - 显示你的用户信息

你也可以直接发送任何文本消息，我会回复你！
    """
    bot.reply_to(message, help_text)

@bot.message_handler(commands=['info'])
def send_user_info(message):
    """显示用户信息"""
    user_info = f"""
👤 你的信息：

名字: {message.from_user.first_name}
用户名: @{message.from_user.username if message.from_user.username else '未设置'}
用户ID: {message.from_user.id}
语言: {message.from_user.language_code if message.from_user.language_code else '未知'}
    """
    bot.reply_to(message, user_info)

@bot.message_handler(func=lambda msg: True)
def echo_all(message):
    """回复所有普通消息"""
    bot.reply_to(message, f"你说：{message.text}\n\n发送 /help 查看可用命令")

def main():
    print("🤖 Telegram 机器人已启动...")
    print("按 Ctrl+C 停止机器人")
    bot.infinity_polling()

if __name__ == '__main__':
    main()

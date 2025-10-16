# bot.py
import os, re, threading, json, math, datetime
from pathlib import Path
from flask import Flask, request
from dotenv import load_dotenv
import requests

# ========== 加载环境 ==========
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OWNER_ID  = os.getenv("OWNER_ID")  # 可选：你的 Telegram ID（字符串），拥有永久管理员权限

# ========== Flask应用（用于健康检查和Webhook）==========
app = Flask(__name__)

# 全局bot application对象（在webhook模式下会被设置）
class BotContainer:
    application = None
    loop = None
    init_started = False
    init_lock = threading.Lock()

@app.get("/")
def health_check():
    return "AA全球国际支付机器人正在运行", 200

@app.get("/health")
def health():
    return "ok", 200

@app.post("/<token>")
def webhook(token):
    """处理Telegram webhook请求"""
    if token != BOT_TOKEN:
        print(f"❌ Token不匹配: {token[:20]}...")
        return "Unauthorized", 401
    
    if not BotContainer.loop:
        print(f"⏳ Bot尚未初始化完成")
        return "Service Unavailable", 503
    
    try:
        from telegram import Update
        import asyncio
        
        # 获取更新数据
        update_data = request.get_json(force=True)
        update = Update.de_json(update_data, BotContainer.application.bot)
        
        # 将更新提交到bot的事件循环
        asyncio.run_coroutine_threadsafe(
            BotContainer.application.process_update(update),
            BotContainer.loop
        )
        
        return "ok", 200
    except Exception as e:
        print(f"❌ Webhook处理错误: {e}")
        import traceback
        traceback.print_exc()
        return "error", 500

# ========== 记账核心状态（多群组支持）==========
DATA_DIR = Path("./data")
GROUPS_DIR = DATA_DIR / "groups"
LOG_DIR  = DATA_DIR / "logs"
DATA_DIR.mkdir(parents=True, exist_ok=True)
GROUPS_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

ADMIN_FILE = DATA_DIR / "admins.json"

# 群组状态缓存 {chat_id: state_dict}
groups_state = {}

def get_default_state():
    """返回默认群组状态"""
    return {
        "defaults": {
            "in":  {"rate": 0.10, "fx": 153},
            "out": {"rate": -0.02, "fx": 137},
        },
        "countries": {},
        "precision": {"mode": "truncate", "digits": 2},
        "bot_name": "AA全球国际支付",
        "recent": {"in": [], "out": []},
        "summary": {"should_send_usdt": 0.0, "sent_usdt": 0.0},
        "last_date": ""
    }

def get_group_file(chat_id: int) -> Path:
    """获取群组数据文件路径"""
    return GROUPS_DIR / f"group_{chat_id}.json"

def load_group_state(chat_id: int) -> dict:
    """加载群组状态"""
    if chat_id in groups_state:
        return groups_state[chat_id]
    
    file = get_group_file(chat_id)
    if file.exists():
        try:
            state = json.loads(file.read_text(encoding="utf-8"))
            groups_state[chat_id] = state
            return state
        except Exception:
            pass
    
    # 创建新群组状态
    state = get_default_state()
    groups_state[chat_id] = state
    save_group_state(chat_id)
    return state

def save_group_state(chat_id: int):
    """保存群组状态"""
    if chat_id not in groups_state:
        return
    file = get_group_file(chat_id)
    file.write_text(json.dumps(groups_state[chat_id], ensure_ascii=False, indent=2), encoding="utf-8")

def load_admins():
    if not ADMIN_FILE.exists():
        default = []
        if OWNER_ID and OWNER_ID.isdigit():
            default = [int(OWNER_ID)]
        ADMIN_FILE.write_text(json.dumps(default, ensure_ascii=False, indent=2))
    try:
        return json.loads(ADMIN_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []

def save_admins(admin_list):
    ADMIN_FILE.write_text(json.dumps(admin_list, ensure_ascii=False, indent=2), encoding="utf-8")

admins_cache = load_admins()

# ========== 工具函数 ==========
def trunc2(x: float) -> float:
    # 先四舍五入到6位小数消除浮点误差，再截断到2位小数
    rounded = round(x, 6)
    return math.floor(rounded * 100.0) / 100.0

def fmt_usdt(x: float) -> str:
    return f"{x:.2f} USDT"

def now_ts():
    # 使用北京时间（UTC+8）
    beijing_tz = datetime.timezone(datetime.timedelta(hours=8))
    return datetime.datetime.now(beijing_tz).strftime("%H:%M")

def today_str():
    # 使用北京时间（UTC+8）
    beijing_tz = datetime.timezone(datetime.timedelta(hours=8))
    return datetime.datetime.now(beijing_tz).strftime("%Y-%m-%d")

def check_and_reset_daily(chat_id: int):
    """检查日期，如果日期变了（过了0点），清空账单"""
    state = load_group_state(chat_id)
    current_date = today_str()
    last_date = state.get("last_date", "")
    
    if last_date and last_date != current_date:
        # 日期变了，清空账单
        state["recent"]["in"] = []
        state["recent"]["out"] = []
        state["summary"]["should_send_usdt"] = 0.0
        state["summary"]["sent_usdt"] = 0.0
        state["last_date"] = current_date
        save_group_state(chat_id)
        return True  # 返回True表示已重置
    elif not last_date:
        # 首次运行，设置日期
        state["last_date"] = current_date
        save_group_state(chat_id)
    
    return False  # 返回False表示未重置

def log_path(chat_id: int, country: str|None, date_str: str) -> Path:
    folder = f"group_{chat_id}"
    if country:
        folder = f"{folder}/{country}"
    else:
        folder = f"{folder}/通用"
    p = LOG_DIR / folder
    p.mkdir(parents=True, exist_ok=True)
    return p / f"{date_str}.log"

def append_log(path: Path, text: str):
    with path.open("a", encoding="utf-8") as f:
        f.write(text.strip() + "\n")

def push_recent(chat_id: int, kind: str, item: dict):
    state = load_group_state(chat_id)
    arr = state["recent"][kind]
    arr.insert(0, item)
    save_group_state(chat_id)

def resolve_params(chat_id: int, direction: str, country: str|None) -> dict:
    state = load_group_state(chat_id)
    d = {"rate": None, "fx": None}
    countries = state["countries"]
    
    # 如果指定了国家，先查找该国家的专属设置
    if country and country in countries:
        if direction in countries[country]:
            d["rate"] = countries[country][direction].get("rate", None)
            d["fx"]   = countries[country][direction].get("fx", None)
    
    # 如果没有找到，使用默认值（不再回退到入金设置）
    if d["rate"] is None: 
        d["rate"] = state["defaults"][direction]["rate"]
    if d["fx"] is None: 
        d["fx"] = state["defaults"][direction]["fx"]
    
    return d

def parse_amount_and_country(text: str):
    m = re.match(r"^[\+\-]\s*([0-9]+(?:\.[0-9]+)?)", text.strip())
    if not m: return None, None
    amount = float(m.group(1))
    m2 = re.search(r"/\s*([^\s]+)$", text)
    country = m2.group(1) if m2 else None
    return amount, country

# ========== 管理员系统 ==========
def is_admin(user_id: int) -> bool:
    if OWNER_ID and OWNER_ID.isdigit() and int(OWNER_ID) == user_id:
        return True
    return user_id in admins_cache

def add_admin(user_id: int) -> bool:
    global admins_cache
    if user_id not in admins_cache:
        admins_cache.append(user_id)
        save_admins(admins_cache)
        return True
    return False

def remove_admin(user_id: int) -> bool:
    global admins_cache
    if user_id in admins_cache:
        admins_cache.remove(user_id)
        save_admins(admins_cache)
        return True
    return False

def list_admins():
    return admins_cache[:]

# ========== 群内汇总显示 ==========
def render_group_summary(chat_id: int) -> str:
    state = load_group_state(chat_id)
    bot = state["bot_name"]
    rec_in, rec_out = state["recent"]["in"], state["recent"]["out"]
    should, sent = trunc2(state["summary"]["should_send_usdt"]), trunc2(state["summary"]["sent_usdt"])
    diff = trunc2(should - sent)
    rin, fin = state["defaults"]["in"]["rate"], state["defaults"]["in"]["fx"]
    rout, fout = state["defaults"]["out"]["rate"], state["defaults"]["out"]["fx"]

    lines = []
    lines.append(f"📊【{bot} 账单汇总】\n")
    lines.append(f"📥 入金记录（最近5笔，共{len(rec_in)}笔）")
    
    # 入金记录：如果有国家，显示国家名（只取前2个字符）替换箭头
    in_lines = []
    for r in rec_in[:5]:
        country = r.get('country')
        if country:
            country_display = country[:2]  # 只显示前2个字符
            in_lines.append(f"🕐 {r['ts']}　+{r['raw']} {country_display} {fmt_usdt(trunc2(r['usdt']))}")
        else:
            in_lines.append(f"🕐 {r['ts']}　+{r['raw']} → {fmt_usdt(trunc2(r['usdt']))}")
    lines += in_lines or ["（暂无）"]
    
    lines.append("")
    lines.append(f"📤 出金记录（最近5笔，共{len(rec_out)}笔）")
    
    # 出金记录：同样处理国家显示
    out_lines = []
    for r in rec_out[:5]:
        if r.get('type') == '下发':
            out_lines.append(f"🕐 {r['ts']}　下发 {fmt_usdt(trunc2(r['usdt']))}")
        elif 'raw' in r:
            country = r.get('country')
            if country:
                country_display = country[:2]
                out_lines.append(f"🕐 {r['ts']}　-{r['raw']} {country_display} {fmt_usdt(trunc2(r['usdt']))}")
            else:
                out_lines.append(f"🕐 {r['ts']}　-{r['raw']} → {fmt_usdt(trunc2(r['usdt']))}")
        else:
            out_lines.append(f"🕐 {r['ts']}　{fmt_usdt(trunc2(r['usdt']))}")
    lines += out_lines or ["（暂无）"]
    lines.append("")
    lines.append("━━━━━━━━━━━━━━")
    lines.append(f"⚙️ 当前费率：入 {rin*100:.0f}% ⇄ 出 {rout*100:.0f}%")
    lines.append(f"💱 固定汇率：入 {fin} ⇄ 出 {fout}")
    lines.append(f"📊 应下发：{fmt_usdt(should)}")
    lines.append(f"📤 已下发：{fmt_usdt(sent)}")
    lines.append(f"{'❗' if diff != 0 else '✅'} 未下发：{fmt_usdt(diff)}")
    lines.append("━━━━━━━━━━━━━━")
    lines.append("📚 **查看更多记录**：发送「更多记录」")
    return "\n".join(lines)

def render_full_summary(chat_id: int) -> str:
    """显示当天所有记录"""
    state = load_group_state(chat_id)
    bot = state["bot_name"]
    rec_in, rec_out = state["recent"]["in"], state["recent"]["out"]
    should, sent = trunc2(state["summary"]["should_send_usdt"]), trunc2(state["summary"]["sent_usdt"])
    diff = trunc2(should - sent)
    rin, fin = state["defaults"]["in"]["rate"], state["defaults"]["in"]["fx"]
    rout, fout = state["defaults"]["out"]["rate"], state["defaults"]["out"]["fx"]

    lines = []
    lines.append(f"📊【{bot} 完整账单】\n")
    lines.append(f"📥 入金记录（共{len(rec_in)}笔）")
    if rec_in:
        for r in rec_in:
            country = r.get('country')
            if country:
                country_display = country[:2]
                lines.append(f"🕐 {r['ts']}　+{r['raw']} {country_display} {fmt_usdt(trunc2(r['usdt']))}")
            else:
                lines.append(f"🕐 {r['ts']}　+{r['raw']} → {fmt_usdt(trunc2(r['usdt']))}")
    else:
        lines.append("（暂无）")
    
    lines.append("")
    lines.append(f"📤 出金记录（共{len(rec_out)}笔）")
    if rec_out:
        for r in rec_out:
            if r.get('type') == '下发':
                lines.append(f"🕐 {r['ts']}　下发 {fmt_usdt(trunc2(r['usdt']))}")
            elif 'raw' in r:
                country = r.get('country')
                if country:
                    country_display = country[:2]
                    lines.append(f"🕐 {r['ts']}　-{r['raw']} {country_display} {fmt_usdt(trunc2(r['usdt']))}")
                else:
                    lines.append(f"🕐 {r['ts']}　-{r['raw']} → {fmt_usdt(trunc2(r['usdt']))}")
            else:
                lines.append(f"🕐 {r['ts']}　{fmt_usdt(trunc2(r['usdt']))}")
    else:
        lines.append("（暂无）")
    
    lines.append("")
    lines.append("━━━━━━━━━━━━━━")
    lines.append(f"⚙️ 当前费率：入 {rin*100:.0f}% ⇄ 出 {rout*100:.0f}%")
    lines.append(f"💱 固定汇率：入 {fin} ⇄ 出 {fout}")
    lines.append(f"📊 应下发：{fmt_usdt(should)}")
    lines.append(f"📤 已下发：{fmt_usdt(sent)}")
    lines.append(f"{'❗' if diff != 0 else '✅'} 未下发：{fmt_usdt(diff)}")
    lines.append("━━━━━━━━━━━━━━")
    return "\n".join(lines)

# ========== Telegram ==========
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes

async def is_group_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    """检查用户是否是群组管理员或群主"""
    chat = update.effective_chat
    if chat.type == "private":
        return False
    try:
        member = await context.bot.get_chat_member(chat.id, user_id)
        return member.status in ["creator", "administrator"]
    except Exception:
        return False

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    
    # 私聊模式
    if chat.type == "private":
        if is_admin(user.id):
            # 管理员私聊 - 显示完整操作说明
            await update.message.reply_text(
                "🤖 你好，我是财务记账机器人。\n\n"
                "📊 记账操作：\n"
                "  入金：+10000 或 +10000 / 日本\n"
                "  出金：-10000 或 -10000 / 日本\n"
                "  查看账单：+0 或 更多记录\n\n"
                "💰 USDT下发（仅管理员）：\n"
                "  下发35.04（记录下发并扣除应下发）\n"
                "  下发-35.04（撤销下发并增加应下发）\n\n"
                "🔄 撤销操作（仅管理员）：\n"
                "  回复账单消息 + 任意文字\n"
                "  系统会自动识别并撤销该笔记录\n\n"
                "⚙️ 快速设置（仅管理员）：\n"
                "  设置入金费率 10\n"
                "  设置入金汇率 153\n"
                "  设置出金费率 -2\n"
                "  设置出金汇率 137\n\n"
                "🔧 高级设置（指定国家）：\n"
                "  设置 日本 入 费率 8\n"
                "  设置 日本 入 汇率 127\n\n"
                "👥 管理员管理：\n"
                "  设置机器人管理员（回复消息）\n"
                "  删除机器人管理员（回复消息）\n"
                "  显示机器人管理员"
            )
        else:
            # 非管理员私聊 - 显示如何成为管理员的步骤
            await update.message.reply_text(
                "👋 你好！欢迎使用财务记账机器人\n\n"
                "💬 发送 /start 查看完整操作说明\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "📌 如何成为机器人管理员（详细步骤）：\n\n"
                "第1步：添加机器人到群组\n"
                "  • 点击机器人头像\n"
                "  • 选择「添加到群组或频道」\n"
                "  • 选择你的工作群组\n"
                "  • 确认添加\n\n"
                "第2步：在群里发送一条消息\n"
                "  • 进入群组聊天\n"
                "  • 发送任意消息（比如：\"申请管理员权限\"）\n"
                "  • 这样群管理员才能回复你的消息\n\n"
                "第3步：让群主/群管理员授权\n"
                "  • 群管理员点击「回复」你的消息\n"
                "  • 在回复框中输入：设置机器人管理员\n"
                "  • 发送后，你就获得了机器人管理员权限\n\n"
                "第4步：开始使用机器人\n"
                "  • 发送 /start 查看所有指令\n"
                "  • 或直接在群里发送：+10000（记录入金）\n\n"
                "✅ 成为管理员后你可以：\n"
                "  • 📊 记录入金/出金交易\n"
                "  • 📋 查看和管理账单\n"
                "  • 💰 记录USDT下发\n"
                "  • ⚙️ 设置费率和汇率\n"
                "  • 🔄 撤销错误操作\n"
                "  • 🌍 设置不同国家的费率\n\n"
                "💡 重要提示：\n"
                "  ⚠️ 只有机器人管理员的操作才会被响应\n"
                "  ⚠️ 普通成员的操作机器人不会回复\n"
                "  ⚠️ 只有群主/群管理员能设置机器人管理员\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "👉 再次发送 /start 查看完整功能列表"
            )
    else:
        # 群聊模式 - 显示完整操作说明
        await update.message.reply_text(
            "🤖 你好，我是财务记账机器人。\n\n"
            "📊 记账操作：\n"
            "  入金：+10000 或 +10000 / 日本\n"
            "  出金：-10000 或 -10000 / 日本\n"
            "  查看账单：+0 或 更多记录\n\n"
            "💰 USDT下发（仅管理员）：\n"
            "  下发35.04（记录下发并扣除应下发）\n"
            "  下发-35.04（撤销下发并增加应下发）\n\n"
            "🔄 撤销操作（仅管理员）：\n"
            "  回复账单消息 + 任意文字\n"
            "  系统会自动识别并撤销该笔记录\n\n"
            "⚙️ 快速设置（仅管理员）：\n"
            "  设置入金费率 10\n"
            "  设置入金汇率 153\n"
            "  设置出金费率 -2\n"
            "  设置出金汇率 137\n\n"
            "🔧 高级设置（指定国家）：\n"
            "  设置 日本 入 费率 8\n"
            "  设置 日本 入 汇率 127\n\n"
            "👥 管理员管理：\n"
            "  设置机器人管理员（回复消息）\n"
            "  删除机器人管理员（回复消息）\n"
            "  显示机器人管理员"
        )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    chat_id = chat.id
    text = (update.message.text or "").strip()
    ts, dstr = now_ts(), today_str()
    
    # ========== 私聊消息转发功能 ==========
    if chat.type == "private":
        # 记录私聊日志
        private_log_dir = LOG_DIR / "private_chats"
        private_log_dir.mkdir(exist_ok=True)
        user_log_file = private_log_dir / f"user_{user.id}.log"
        
        log_entry = f"[{ts}] {user.full_name} (@{user.username or 'N/A'}): {text}\n"
        with open(user_log_file, "a", encoding="utf-8") as f:
            f.write(log_entry)
        
        # 如果设置了OWNER_ID，且发送者不是OWNER，则转发给OWNER
        if OWNER_ID and OWNER_ID.isdigit():
            owner_id = int(OWNER_ID)
            
            if user.id != owner_id:
                # 非OWNER发送的私聊消息 - 转发给OWNER
                try:
                    user_info = f"👤 {user.full_name}"
                    if user.username:
                        user_info += f" (@{user.username})"
                    user_info += f"\n🆔 User ID: {user.id}"
                    
                    forward_msg = (
                        f"📨 收到私聊消息\n"
                        f"{user_info}\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"{text}\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"💡 回复此消息可直接回复用户"
                    )
                    
                    # 转发给OWNER并存储消息ID用于回复
                    sent_msg = await context.bot.send_message(
                        chat_id=owner_id,
                        text=forward_msg
                    )
                    
                    # 存储映射关系: OWNER收到的消息ID -> 原始用户ID
                    # 用于OWNER回复时知道发给谁
                    if 'private_msg_map' not in context.bot_data:
                        context.bot_data['private_msg_map'] = {}
                    context.bot_data['private_msg_map'][sent_msg.message_id] = user.id
                    
                    # 给用户回复确认消息
                    await update.message.reply_text(
                        "✅ 您的消息已发送给客服\n"
                        "⏳ 请耐心等待回复"
                    )
                    return
                    
                except Exception as e:
                    print(f"转发私聊消息失败: {e}")
                    # 继续处理，不影响后续逻辑
            else:
                # OWNER发送的私聊消息 - 检查是否是回复转发的消息
                if update.message.reply_to_message:
                    replied_msg_id = update.message.reply_to_message.message_id
                    
                    # 检查是否有映射关系
                    if 'private_msg_map' in context.bot_data:
                        target_user_id = context.bot_data['private_msg_map'].get(replied_msg_id)
                        
                        if target_user_id:
                            # OWNER正在回复某个用户的私聊
                            try:
                                await context.bot.send_message(
                                    chat_id=target_user_id,
                                    text=f"💬 客服回复：\n\n{text}"
                                )
                                await update.message.reply_text("✅ 回复已发送")
                                
                                # 记录回复日志到目标用户的日志文件
                                target_log_file = private_log_dir / f"user_{target_user_id}.log"
                                reply_log_entry = f"[{ts}] OWNER回复: {text}\n"
                                with open(target_log_file, "a", encoding="utf-8") as f:
                                    f.write(reply_log_entry)
                                
                                return
                            except Exception as e:
                                await update.message.reply_text(f"❌ 发送失败: {e}")
                                return
                
                # OWNER发送的非回复私聊消息 - 提示用法
                await update.message.reply_text(
                    "💡 使用提示：\n"
                    "• 回复转发的消息可以回复用户\n"
                    "• 在群组中使用记账功能"
                )
                return
    
    # ========== 群组消息处理 ==========
    # 检查日期并在需要时重置账单（每个群组独立）
    check_and_reset_daily(chat_id)
    
    # 获取当前群组状态
    state = load_group_state(chat_id)
    
    # 撤销操作（回复机器人消息 + 任意文本）
    if update.message.reply_to_message and update.message.reply_to_message.from_user.is_bot:
        if not is_admin(user.id):
            return  # 非管理员不回复
        
        # 获取被回复的消息内容
        replied_text = update.message.reply_to_message.text or ""
        
        # 尝试从消息中提取最近的入金或下发记录
        import re
        
        # 匹配所有入金记录: 🕐 14:30　+10000 → 58.82 USDT
        in_matches = re.findall(r'🕐\s*(\d+:\d+)\s*　\+(\d+(?:\.\d+)?)\s*→\s*(\d+(?:\.\d+)?)\s*USDT', replied_text)
        # 匹配所有下发记录: 🕐 14:30　35.04 USDT 或 🕐 14:30　-35.04 USDT
        out_matches = re.findall(r'🕐\s*(\d+:\d+)\s*　(-?\d+(?:\.\d+)?)\s*USDT', replied_text)
        
        # 取最后一笔（最新的）记录
        in_match = in_matches[-1] if in_matches else None
        out_match = out_matches[-1] if out_matches else None
        
        if in_match:
            # 撤销入金
            raw_amt = trunc2(float(in_match[1]))
            usdt_amt = trunc2(float(in_match[2]))
            
            # 反向操作：减少应下发
            state["summary"]["should_send_usdt"] = trunc2(state["summary"]["should_send_usdt"] - usdt_amt)
            save_group_state(chat_id)
            
            # 从最近记录中移除（如果存在）
            state["recent"]["in"] = [r for r in state["recent"]["in"] if not (r.get("raw") == raw_amt and r.get("usdt") == usdt_amt)]
            
            save_group_state(chat_id)
            append_log(log_path(chat_id, None, dstr), f"[撤销入金] 时间:{ts} 原金额:{raw_amt} USDT:{usdt_amt} 标记:无效操作")
            await update.message.reply_text(f"✅ 已撤销入金记录\n📊 原金额：+{raw_amt} → {usdt_amt} USDT")
            await update.message.reply_text(render_group_summary(chat_id))
            return
            
        elif out_match:
            # 撤销下发
            usdt_amt = trunc2(float(out_match[1]))
            
            # 反向操作：如果是正数下发，撤销后增加应下发；如果是负数，则减少应下发
            state["summary"]["should_send_usdt"] = trunc2(state["summary"]["should_send_usdt"] + usdt_amt)
            
            # 从最近记录中移除
            state["recent"]["out"] = [r for r in state["recent"]["out"] if r.get("usdt") != usdt_amt]
            
            save_group_state(chat_id)
            append_log(log_path(chat_id, None, dstr), f"[撤销下发] 时间:{ts} USDT:{usdt_amt} 标记:无效操作")
            await update.message.reply_text(f"✅ 已撤销下发记录\n📊 原金额：{usdt_amt} USDT")
            await update.message.reply_text(render_group_summary(chat_id))
            return
        else:
            await update.message.reply_text("❌ 无法识别要撤销的操作\n💡 请回复包含入金或下发记录的账单消息")
            return

    # 查看账单（+0 不记录）
    if text == "+0":
        await update.message.reply_text(render_group_summary(chat_id))
        return
    
    # 管理员管理命令
    if text.startswith(("设置机器人管理员", "删除机器人管理员", "显示机器人管理员")):
        lst = list_admins()
        if text.startswith("显示"):
            lines = ["👥 机器人管理员列表\n"]
            lines.append(f"⭐ 超级管理员：{OWNER_ID or '未设置'}\n")
            
            if lst:
                lines.append("📋 机器人管理员：")
                for admin_id in lst:
                    try:
                        # 尝试获取用户信息
                        chat_member = await context.bot.get_chat_member(update.effective_chat.id, admin_id)
                        user_info = chat_member.user
                        
                        # 构建显示信息
                        name = user_info.full_name
                        username = f"@{user_info.username}" if user_info.username else ""
                        
                        if username:
                            lines.append(f"• {name} ({username}) - ID: {admin_id}")
                        else:
                            lines.append(f"• {name} - ID: {admin_id}")
                    except Exception:
                        # 如果获取失败，只显示ID
                        lines.append(f"• ID: {admin_id}")
            else:
                lines.append("暂无机器人管理员")
            
            await update.message.reply_text("\n".join(lines))
            return
        
        # 检查权限：只有群组管理员/群主可以设置
        is_chat_admin = await is_group_admin(update, context, user.id)
        
        if not is_chat_admin:
            await update.message.reply_text("🚫 你没有权限设置机器人管理员。\n💡 只有群主/群管理员可以执行此操作。")
            return
        
        if not update.message.reply_to_message:
            await update.message.reply_text("请『回复』要授权或移除的用户消息再发送此命令。")
            return
        target = update.message.reply_to_message.from_user
        if text.startswith("设置"):
            add_admin(target.id)
            await update.message.reply_text(f"✅ 已将 {target.mention_html()} 设置为机器人管理员。", parse_mode="HTML")
        elif text.startswith("删除"):
            remove_admin(target.id)
            await update.message.reply_text(f"🗑️ 已移除 {target.mention_html()} 的机器人管理员权限。", parse_mode="HTML")
        return

    # 查询国家点位（费率/汇率）
    if text.endswith("当前点位"):
        if not is_admin(user.id):
            return  # 非管理员不回复
        
        # 提取国家名（去掉"当前点位"）
        country = text.replace("当前点位", "").strip()
        
        if not country:
            await update.message.reply_text("❌ 请指定国家名称\n例如：美国当前点位")
            return
        
        # 获取该国家的费率和汇率
        countries = state["countries"]
        defaults = state["defaults"]
        
        # 查询入金费率和汇率
        in_rate = None
        in_fx = None
        if country in countries and "in" in countries[country]:
            in_rate = countries[country]["in"].get("rate")
            in_fx = countries[country]["in"].get("fx")
        
        # 如果没有专属设置，使用默认值
        if in_rate is None:
            in_rate = defaults["in"]["rate"]
            in_rate_source = "默认"
        else:
            in_rate_source = f"{country}专属"
            
        if in_fx is None:
            in_fx = defaults["in"]["fx"]
            in_fx_source = "默认"
        else:
            in_fx_source = f"{country}专属"
        
        # 查询出金费率和汇率
        out_rate = None
        out_fx = None
        if country in countries and "out" in countries[country]:
            out_rate = countries[country]["out"].get("rate")
            out_fx = countries[country]["out"].get("fx")
        
        if out_rate is None:
            out_rate = defaults["out"]["rate"]
            out_rate_source = "默认"
        else:
            out_rate_source = f"{country}专属"
            
        if out_fx is None:
            out_fx = defaults["out"]["fx"]
            out_fx_source = "默认"
        else:
            out_fx_source = f"{country}专属"
        
        # 构建回复消息
        lines = [
            f"📍【{country} 当前点位】\n",
            f"📥 入金设置：",
            f"  • 费率：{in_rate*100:.0f}% ({in_rate_source})",
            f"  • 汇率：{in_fx} ({in_fx_source})\n",
            f"📤 出金设置：",
            f"  • 费率：{abs(out_rate)*100:.0f}% ({out_rate_source})",
            f"  • 汇率：{out_fx} ({out_fx_source})"
        ]
        
        await update.message.reply_text("\n".join(lines))
        return
    
    # 简化的设置命令
    if text.startswith(("设置入金费率", "设置入金汇率", "设置出金费率", "设置出金汇率")):
        if not is_admin(user.id):
            return  # 非管理员不回复
        try:
            direction = ""
            key = ""
            val = 0.0
            display_val = ""
            
            # 解析命令
            if "入金费率" in text:
                direction, key = "in", "rate"
                val = float(text.replace("设置入金费率", "").strip())
                val /= 100.0  # 转换为小数
                display_val = f"{val*100:.0f}%"
            elif "入金汇率" in text:
                direction, key = "in", "fx"
                val = float(text.replace("设置入金汇率", "").strip())
                display_val = str(val)
            elif "出金费率" in text:
                direction, key = "out", "rate"
                val = float(text.replace("设置出金费率", "").strip())
                val /= 100.0  # 转换为小数
                display_val = f"{val*100:.0f}%"
            elif "出金汇率" in text:
                direction, key = "out", "fx"
                val = float(text.replace("设置出金汇率", "").strip())
                display_val = str(val)
            
            # 更新默认设置
            state["defaults"][direction][key] = val
            save_group_state(chat_id)
            
            # 构建回复消息
            type_name = "费率" if key == "rate" else "汇率"
            dir_name = "入金" if direction == "in" else "出金"
            await update.message.reply_text(
                f"✅ 已设置默认{dir_name}{type_name}\n"
                f"📊 新值：{display_val}"
            )
        except ValueError:
            await update.message.reply_text("❌ 格式错误，请输入有效的数字\n例如：设置入金费率 10")
        return

    # 高级设置命令（指定国家）- 支持无空格格式
    if text.startswith("设置") and not text.startswith(("设置入金", "设置出金")):
        if not is_admin(user.id):
            return  # 非管理员不回复
        
        # 尝试匹配格式：设置 + 国家名 + 入/出 + 费率/汇率 + 数字
        # 例如：设置美国入费率7, 设置美国入汇率10
        import re
        pattern = r'^设置\s*(.+?)(入|出)(费率|汇率)\s*(\d+(?:\.\d+)?)\s*$'
        match = re.match(pattern, text)
        
        if match:
            scope = match.group(1).strip()  # 国家名
            direction = "in" if match.group(2) == "入" else "out"
            key = "rate" if match.group(3) == "费率" else "fx"
            try:
                val = float(match.group(4))
                if key == "rate": 
                    val /= 100.0  # 转换为小数
                
                if scope == "默认":
                    state["defaults"][direction][key] = val
                else:
                    state["countries"].setdefault(scope, {}).setdefault(direction, {})[key] = val
                
                save_group_state(chat_id)
                
                # 构建友好的回复消息
                type_name = "费率" if key == "rate" else "汇率"
                dir_name = "入金" if direction == "in" else "出金"
                display_val = f"{val*100:.0f}%" if key == "rate" else str(val)
                
                await update.message.reply_text(
                    f"✅ 已设置 {scope} {dir_name}{type_name}\n"
                    f"📊 新值：{display_val}"
                )
            except ValueError:
                await update.message.reply_text("❌ 数值格式错误")
            return
        else:
            # 尝试旧格式（有空格）：设置 国家 入 费率 值
            tokens = text.split()
            if len(tokens) >= 3:
                scope = tokens[1]
                direction = "in" if "入" in text else "out"
                key = "rate" if "费率" in text else "fx"
                try:
                    val = float(tokens[-1])
                    if key == "rate": val /= 100.0
                    if scope == "默认": 
                        state["defaults"][direction][key] = val
                    else:
                        state["countries"].setdefault(scope, {}).setdefault(direction, {})[key] = val
                    save_group_state(chat_id)
                    await update.message.reply_text(f"✅ 已设置 {scope} {direction} {key} = {val}")
                except ValueError:
                    return
                return

    # 入金
    if text.startswith("+"):
        if not is_admin(user.id):
            return  # 非管理员不回复
        amt, country = parse_amount_and_country(text)
        p = resolve_params(chat_id, "in", country)
        usdt = trunc2(amt * (1 - p["rate"]) / p["fx"])
        push_recent(chat_id, "in", {"ts": ts, "raw": amt, "usdt": usdt, "country": country})
        state["summary"]["should_send_usdt"] = trunc2(state["summary"]["should_send_usdt"] + usdt)
        save_group_state(chat_id)
        append_log(log_path(chat_id, country, dstr),
                   f"[入金] 时间:{ts} 国家:{country or '通用'} 原始:{amt} 汇率:{p['fx']} 费率:{p['rate']*100:.2f}% 结果:{usdt}")
        await update.message.reply_text(render_group_summary(chat_id))
        return

    # 出金
    if text.startswith("-"):
        if not is_admin(user.id):
            return  # 非管理员不回复
        amt, country = parse_amount_and_country(text)
        p = resolve_params(chat_id, "out", country)
        usdt = trunc2(amt * (1 + p["rate"]) / p["fx"])
        push_recent(chat_id, "out", {"ts": ts, "raw": amt, "usdt": usdt, "country": country})
        state["summary"]["sent_usdt"] = trunc2(state["summary"]["sent_usdt"] + usdt)
        save_group_state(chat_id)
        append_log(log_path(chat_id, country, dstr),
                   f"[出金] 时间:{ts} 国家:{country or '通用'} 原始:{amt} 汇率:{p['fx']} 费率:{p['rate']*100:.2f}% 下发:{usdt}")
        await update.message.reply_text(render_group_summary(chat_id))
        return

    # 下发USDT（仅管理员）
    if text.startswith("下发"):
        if not is_admin(user.id):
            return  # 非管理员不回复
        try:
            usdt_str = text.replace("下发", "").strip()
            usdt = trunc2(float(usdt_str))  # 对输入也进行精度截断
            
            if usdt > 0:
                # 正数：扣除应下发
                state["summary"]["should_send_usdt"] = trunc2(state["summary"]["should_send_usdt"] - usdt)
                push_recent(chat_id, "out", {"ts": ts, "usdt": usdt, "type": "下发"})
                append_log(log_path(chat_id, None, dstr), f"[下发USDT] 时间:{ts} 金额:{usdt} USDT")
            else:
                # 负数：增加应下发（撤销）
                usdt_abs = trunc2(abs(usdt))  # 对绝对值也进行精度截断
                state["summary"]["should_send_usdt"] = trunc2(state["summary"]["should_send_usdt"] + usdt_abs)
                push_recent(chat_id, "out", {"ts": ts, "usdt": usdt, "type": "下发"})
                append_log(log_path(chat_id, None, dstr), f"[撤销下发] 时间:{ts} 金额:{usdt_abs} USDT")
            
            save_group_state(chat_id)
            await update.message.reply_text(render_group_summary(chat_id))
        except ValueError:
            await update.message.reply_text("❌ 格式错误，请输入有效的数字\n例如：下发35.04 或 下发-35.04")
        return

    # 查看更多记录
    if text in ["更多记录", "查看更多记录", "更多账单", "显示历史账单"]:
        await update.message.reply_text(render_full_summary(chat_id))
        return

    # 无效操作不回复

# ========== 初始化函数（支持Gunicorn） ==========
def init_bot():
    """初始化Bot - 在Gunicorn启动时或直接运行时调用"""
    print("=" * 50)
    print("🚀 正在启动财务记账机器人...")
    print("=" * 50)
    
    if not BOT_TOKEN:
        print("❌ 错误：未找到 TELEGRAM_BOT_TOKEN 环境变量")
        exit(1)
    
    print("✅ Bot Token 已加载")
    print(f"📊 数据目录: {DATA_DIR}")
    print(f"👑 超级管理员: {OWNER_ID or '未设置'}")
    
    # 检查运行模式
    USE_WEBHOOK = os.getenv("USE_WEBHOOK", "false").lower() == "true"
    
    print("\n🤖 配置 Telegram Bot...")
    from telegram.ext import ApplicationBuilder
    
    if USE_WEBHOOK:
        # Webhook模式（Render Web Service）
        # 优先使用手动配置的WEBHOOK_URL，否则使用Render自动提供的RENDER_EXTERNAL_URL
        base_url = os.getenv("WEBHOOK_URL") or os.getenv("RENDER_EXTERNAL_URL")
        
        if not base_url:
            print("❌ 错误：Webhook模式需要设置以下环境变量之一：")
            print("   1. WEBHOOK_URL - 手动设置webhook地址（推荐）")
            print("   2. RENDER_EXTERNAL_URL - Render自动提供")
            print("\n请在Render Dashboard → Environment中添加：")
            print("   WEBHOOK_URL = https://你的服务名.onrender.com")
            exit(1)
        
        webhook_url = f"{base_url}/{BOT_TOKEN}"
        port = int(os.getenv("PORT", "10000"))  # Render默认端口
        
        # 验证webhook URL
        if not webhook_url.startswith("https://"):
            print(f"❌ 错误：Webhook URL必须使用HTTPS: {webhook_url}")
            print(f"   BASE_URL: {base_url}")
            exit(1)
        
        print(f"\n🌐 使用 Webhook 模式")
        print(f"📡 Webhook URL: {webhook_url}")
        print(f"🔌 监听端口: {port}")
        
        # 创建bot application
        BotContainer.application = ApplicationBuilder().token(BOT_TOKEN).build()
        BotContainer.application.add_handler(CommandHandler("start", cmd_start))
        BotContainer.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
        print("✅ Bot 处理器已注册")
        
        # 立即启动异步初始化（非daemon线程）
        def setup_webhook_async():
            import asyncio
            import time
            time.sleep(2)  # 等待Flask完全启动
            
            async def init():
                try:
                    async with BotContainer.application:
                        BotContainer.loop = asyncio.get_running_loop()
                        print("✅ Bot事件循环已创建")
                        
                        await BotContainer.application.bot.delete_webhook(drop_pending_updates=True)
                        print("🗑️ 已清除旧webhook")
                        
                        success = await BotContainer.application.bot.set_webhook(
                            url=webhook_url,
                            drop_pending_updates=False,
                            allowed_updates=["message"]
                        )
                        print(f"✅ Webhook设置{'成功' if success else '失败'}: {webhook_url}")
                        
                        await BotContainer.application.start()
                        print("✅ Bot application已启动")
                        
                        # 保持事件循环运行
                        await asyncio.Event().wait()
                except Exception as e:
                    print(f"❌ Webhook初始化错误: {e}")
                    import traceback
                    traceback.print_exc()
            
            asyncio.run(init())
        
        threading.Thread(target=setup_webhook_async, daemon=False).start()
        print("🔄 异步初始化线程已启动")
        
        # 自动保活机制 - 每5分钟ping一次自己防止Render休眠
        def keep_alive():
            import time
            time.sleep(30)  # 等待启动
            health_url = f"{base_url}/health"
            print(f"🔄 保活目标: {health_url}")
            
            while True:
                time.sleep(300)  # 每5分钟（Render免费套餐15分钟无流量会休眠）
                try:
                    response = requests.get(health_url, timeout=10)
                    if response.status_code == 200:
                        print(f"💓 保活成功: {datetime.datetime.now().strftime('%H:%M:%S')}")
                    else:
                        print(f"⚠️ 保活响应异常: {response.status_code}")
                except Exception as e:
                    print(f"❌ 保活失败: {e}")
        
        threading.Thread(target=keep_alive, daemon=True).start()
        print("✅ 自动保活机制已启动（每5分钟ping一次）")
        
        print(f"\n✅ Webhook模式初始化完成")
        print("=" * 50)
        # 注意：不调用app.run()，让Gunicorn管理Flask应用
        
    else:
        # Polling模式（本地开发/Replit）
        print("\n🔄 使用 Polling 模式（本地开发）")
        
        application = ApplicationBuilder().token(BOT_TOKEN).build()
        application.add_handler(CommandHandler("start", cmd_start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
        print("✅ Bot 处理器已注册")
        
        print("\n🌐 启动 HTTP 保活服务器...")
        def run_http():
            port = int(os.getenv("PORT", "5000"))
            app.run(host="0.0.0.0", port=port, use_reloader=False)
        threading.Thread(target=run_http, daemon=True).start()
        print("✅ HTTP 服务器已启动（后台运行）")
        print("\n🎉 机器人正在运行，等待消息...")
        print("=" * 50)
        application.run_polling()

# ========== Gunicorn入口：模块导入时初始化 ==========
# 当Gunicorn导入此模块时，自动初始化Bot（仅在Webhook模式）
if os.getenv("USE_WEBHOOK", "false").lower() == "true":
    init_bot()
    # 注意：不启动Flask，让Gunicorn管理app对象

# ========== 直接运行支持（仅用于本地开发/测试）==========
if __name__ == "__main__":
    # 直接运行python bot.py时（非Gunicorn）
    if os.getenv("USE_WEBHOOK", "false").lower() != "true":
        # Polling模式（本地开发）
        init_bot()
    else:
        # Webhook模式但直接运行（仅用于测试，生产环境用Gunicorn）
        print("⚠️ 警告：检测到Webhook模式但直接运行python bot.py")
        print("💡 生产环境请使用: gunicorn --bind 0.0.0.0:$PORT bot:app")
        print("🔧 如需测试，将继续使用Flask开发服务器...\n")
        port = int(os.getenv("PORT", "10000"))
        app.run(host="0.0.0.0", port=port, use_reloader=False, threaded=True)

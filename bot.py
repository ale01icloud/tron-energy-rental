# bot.py
import os, re, threading, json, math, datetime
from pathlib import Path
from flask import Flask
from dotenv import load_dotenv

# ========== 加载环境 ==========
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OWNER_ID  = os.getenv("OWNER_ID")  # 可选：你的 Telegram ID（字符串），拥有永久管理员权限

# ========== 保活HTTP ==========
app = Flask(__name__)
@app.get("/")
def ok():
    return "ok", 200

def run_http():
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, use_reloader=False)

# ========== 记账核心状态 ==========
DATA_DIR = Path("./data")
LOG_DIR  = DATA_DIR / "logs"
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

STATE_FILE = DATA_DIR / "state.json"
ADMIN_FILE = DATA_DIR / "admins.json"

# 初始化状态
state = {
    "defaults": {  # 通用设置
        "in":  {"rate": 0.10, "fx": 153},   # 入金：费率10%，汇率153
        "out": {"rate": -0.02, "fx": 137},  # 出金：费率-2%，汇率137
    },
    "countries": {},
    "precision": {"mode": "truncate", "digits": 2},
    "bot_name": "AA全球国际支付",
    "recent": {"in": [], "out": []},
    "summary": {"should_send_usdt": 0.0, "sent_usdt": 0.0},
    "last_date": ""  # 记录上次操作的日期，用于每日重置
}

def load_state():
    if STATE_FILE.exists():
        try:
            s = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            state.update(s)
        except Exception:
            pass

def save_state():
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

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

load_state()
admins_cache = load_admins()

# ========== 工具函数 ==========
def trunc2(x: float) -> float:
    return math.floor(x * 100.0) / 100.0  # 截断两位小数（不四舍五入）

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

def check_and_reset_daily():
    """检查日期，如果日期变了（过了0点），清空账单"""
    current_date = today_str()
    last_date = state.get("last_date", "")
    
    if last_date and last_date != current_date:
        # 日期变了，清空账单
        state["recent"]["in"] = []
        state["recent"]["out"] = []
        state["summary"]["should_send_usdt"] = 0.0
        state["summary"]["sent_usdt"] = 0.0
        state["last_date"] = current_date
        save_state()
        return True  # 返回True表示已重置
    elif not last_date:
        # 首次运行，设置日期
        state["last_date"] = current_date
        save_state()
    
    return False  # 返回False表示未重置

def log_path(country: str|None, date_str: str) -> Path:
    folder = country if country else "通用"
    p = LOG_DIR / folder
    p.mkdir(parents=True, exist_ok=True)
    return p / f"{date_str}.log"

def append_log(path: Path, text: str):
    with path.open("a", encoding="utf-8") as f:
        f.write(text.strip() + "\n")

def push_recent(kind: str, item: dict):
    arr = state["recent"][kind]
    arr.insert(0, item)
    # 不再限制记录数量，保存当天所有记录

def resolve_params(direction: str, country: str|None) -> dict:
    d = {"rate": None, "fx": None}
    countries = state["countries"]
    if country and country in countries:
        if direction in countries[country]:
            d["rate"] = countries[country][direction].get("rate", None)
            d["fx"]   = countries[country][direction].get("fx", None)
        if d["rate"] is None and "in" in countries[country]:
            d["rate"] = countries[country]["in"].get("rate", None)
        if d["fx"] is None and "in" in countries[country]:
            d["fx"]   = countries[country]["in"].get("fx", None)
    if d["rate"] is None: d["rate"] = state["defaults"][direction]["rate"]
    if d["fx"]   is None: d["fx"]   = state["defaults"][direction]["fx"]
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
def render_group_summary() -> str:
    bot = state["bot_name"]
    rec_in, rec_out = state["recent"]["in"], state["recent"]["out"]
    should, sent = trunc2(state["summary"]["should_send_usdt"]), trunc2(state["summary"]["sent_usdt"])
    diff = trunc2(should - sent)
    rin, fin = state["defaults"]["in"]["rate"], state["defaults"]["in"]["fx"]
    rout, fout = state["defaults"]["out"]["rate"], state["defaults"]["out"]["fx"]

    lines = []
    lines.append(f"📊【{bot} 账单汇总】\n")
    lines.append(f"📥 入金记录（最近5笔，共{len(rec_in)}笔）")
    lines += [f"🕐 {r['ts']}　+{r['raw']} → {fmt_usdt(trunc2(r['usdt']))}" for r in rec_in[:5]] or ["（暂无）"]
    lines.append("")
    lines.append(f"📤 出金记录（最近5笔，共{len(rec_out)}笔）")
    lines += [
        f"🕐 {r['ts']}　下发 {fmt_usdt(trunc2(r['usdt']))}" if r.get('type') == '下发' 
        else f"🕐 {r['ts']}　-{r.get('raw', 0)} → {fmt_usdt(trunc2(r['usdt']))}" if 'raw' in r 
        else f"🕐 {r['ts']}　{fmt_usdt(trunc2(r['usdt']))}" 
        for r in rec_out[:5]
    ] or ["（暂无）"]
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

def render_full_summary() -> str:
    """显示当天所有记录"""
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
        lines += [f"🕐 {r['ts']}　+{r['raw']} → {fmt_usdt(trunc2(r['usdt']))}" for r in rec_in]
    else:
        lines.append("（暂无）")
    
    lines.append("")
    lines.append(f"📤 出金记录（共{len(rec_out)}笔）")
    if rec_out:
        lines += [
            f"🕐 {r['ts']}　下发 {fmt_usdt(trunc2(r['usdt']))}" if r.get('type') == '下发' 
            else f"🕐 {r['ts']}　-{r.get('raw', 0)} → {fmt_usdt(trunc2(r['usdt']))}" if 'raw' in r 
            else f"🕐 {r['ts']}　{fmt_usdt(trunc2(r['usdt']))}" 
            for r in rec_out
        ]
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
                "  ⚠️ 只有群主/群管理员能设置机器人管理员"
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
    text = (update.message.text or "").strip()
    ts, dstr = now_ts(), today_str()
    
    # 检查日期并在需要时重置账单
    check_and_reset_daily()
    
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
            
            # 从最近记录中移除（如果存在）
            state["recent"]["in"] = [r for r in state["recent"]["in"] if not (r.get("raw") == raw_amt and r.get("usdt") == usdt_amt)]
            
            save_state()
            append_log(log_path(None, dstr), f"[撤销入金] 时间:{ts} 原金额:{raw_amt} USDT:{usdt_amt} 标记:无效操作")
            await update.message.reply_text(f"✅ 已撤销入金记录\n📊 原金额：+{raw_amt} → {usdt_amt} USDT")
            await update.message.reply_text(render_group_summary())
            return
            
        elif out_match:
            # 撤销下发
            usdt_amt = trunc2(float(out_match[1]))
            
            # 反向操作：如果是正数下发，撤销后增加应下发；如果是负数，则减少应下发
            state["summary"]["should_send_usdt"] = trunc2(state["summary"]["should_send_usdt"] + usdt_amt)
            
            # 从最近记录中移除
            state["recent"]["out"] = [r for r in state["recent"]["out"] if r.get("usdt") != usdt_amt]
            
            save_state()
            append_log(log_path(None, dstr), f"[撤销下发] 时间:{ts} USDT:{usdt_amt} 标记:无效操作")
            await update.message.reply_text(f"✅ 已撤销下发记录\n📊 原金额：{usdt_amt} USDT")
            await update.message.reply_text(render_group_summary())
            return
        else:
            await update.message.reply_text("❌ 无法识别要撤销的操作\n💡 请回复包含入金或下发记录的账单消息")
            return

    # 查看账单（+0 不记录）
    if text == "+0":
        await update.message.reply_text(render_group_summary())
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
            save_state()
            
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

    # 高级设置命令（指定国家）
    if text.startswith("设置"):
        if not is_admin(user.id):
            return  # 非管理员不回复
        tokens = text.split()
        scope = tokens[1]
        direction = "in" if "入" in text else "out"
        key = "rate" if "费率" in text else "fx"
        val = float(tokens[-1])
        if key == "rate": val /= 100.0
        if scope == "默认": state["defaults"][direction][key] = val
        else:
            state["countries"].setdefault(scope, {}).setdefault(direction, {})[key] = val
        save_state()
        await update.message.reply_text(f"✅ 已设置 {scope} {direction} {key} = {val}", parse_mode="Markdown")
        return

    # 入金
    if text.startswith("+"):
        if not is_admin(user.id):
            return  # 非管理员不回复
        amt, country = parse_amount_and_country(text)
        p = resolve_params("in", country)
        usdt = trunc2(amt * (1 - p["rate"]) / p["fx"])
        push_recent("in", {"ts": ts, "raw": amt, "usdt": usdt})
        state["summary"]["should_send_usdt"] = trunc2(state["summary"]["should_send_usdt"] + usdt)
        save_state()
        append_log(log_path(country, dstr),
                   f"[入金] 时间:{ts} 国家:{country or '通用'} 原始:{amt} 汇率:{p['fx']} 费率:{p['rate']*100:.2f}% 结果:{usdt}")
        await update.message.reply_text(render_group_summary())
        return

    # 出金
    if text.startswith("-"):
        if not is_admin(user.id):
            return  # 非管理员不回复
        amt, country = parse_amount_and_country(text)
        p = resolve_params("out", country)
        usdt = trunc2(amt * (1 + p["rate"]) / p["fx"])
        push_recent("out", {"ts": ts, "raw": amt, "usdt": usdt})
        state["summary"]["sent_usdt"] = trunc2(state["summary"]["sent_usdt"] + usdt)
        save_state()
        append_log(log_path(country, dstr),
                   f"[出金] 时间:{ts} 国家:{country or '通用'} 原始:{amt} 汇率:{p['fx']} 费率:{p['rate']*100:.2f}% 下发:{usdt}")
        await update.message.reply_text(render_group_summary())
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
                push_recent("out", {"ts": ts, "usdt": usdt, "type": "下发"})
                append_log(log_path(None, dstr), f"[下发USDT] 时间:{ts} 金额:{usdt} USDT")
            else:
                # 负数：增加应下发（撤销）
                usdt_abs = trunc2(abs(usdt))  # 对绝对值也进行精度截断
                state["summary"]["should_send_usdt"] = trunc2(state["summary"]["should_send_usdt"] + usdt_abs)
                push_recent("out", {"ts": ts, "usdt": usdt, "type": "下发"})
                append_log(log_path(None, dstr), f"[撤销下发] 时间:{ts} 金额:{usdt_abs} USDT")
            
            save_state()
            await update.message.reply_text(render_group_summary())
        except ValueError:
            await update.message.reply_text("❌ 格式错误，请输入有效的数字\n例如：下发35.04 或 下发-35.04")
        return

    # 查看更多记录
    if text in ["更多记录", "查看更多记录", "更多账单", "显示历史账单"]:
        await update.message.reply_text(render_full_summary())
        return

    # 无效操作不回复

# ========== 启动 ==========
if __name__ == "__main__":
    print("=" * 50)
    print("🚀 正在启动财务记账机器人...")
    print("=" * 50)
    
    if not BOT_TOKEN:
        print("❌ 错误：未找到 TELEGRAM_BOT_TOKEN 环境变量")
        exit(1)
    
    print("✅ Bot Token 已加载")
    print(f"📊 数据目录: {DATA_DIR}")
    print(f"👑 超级管理员: {OWNER_ID or '未设置'}")
    
    print("\n🌐 启动 HTTP 保活服务器...")
    threading.Thread(target=run_http, daemon=True).start()
    print("✅ HTTP 服务器已启动（后台运行）")
    
    print("\n🤖 启动 Telegram Bot...")
    from telegram.ext import ApplicationBuilder
    appbot = ApplicationBuilder().token(BOT_TOKEN).build()
    appbot.add_handler(CommandHandler("start", cmd_start))
    appbot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    print("✅ Bot 处理器已注册")
    print("\n🎉 机器人正在运行，等待消息...")
    print("=" * 50)
    appbot.run_polling()

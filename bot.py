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
    "bot_name": "@Finance_Bot",
    "recent": {"in": [], "out": []},
    "summary": {"should_send_usdt": 0.0, "sent_usdt": 0.0}
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
    return datetime.datetime.now().strftime("%H:%M")

def today_str():
    return datetime.datetime.now().strftime("%Y-%m-%d")

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
    if len(arr) > 5:
        arr.pop()

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
    lines.append("📥 入金记录（最近5笔）")
    lines += [f"🕐 {r['ts']}　+{r['raw']} → {fmt_usdt(r['usdt'])}" for r in rec_in[:5]] or ["（暂无）"]
    lines.append("")
    lines.append("📤 下发记录（最近5笔）")
    lines += [f"🕐 {r['ts']}　{fmt_usdt(r['usdt'])}" for r in rec_out[:5]] or ["（暂无）"]
    lines.append("")
    lines.append("━━━━━━━━━━━━━━")
    lines.append(f"⚙️ 当前费率：入 {rin*100:.0f}% ⇄ 出 {rout*100:.0f}%")
    lines.append(f"💱 固定汇率：入 {fin} ⇄ 出 {fout}")
    lines.append(f"📊 应下发：{fmt_usdt(should)}")
    lines.append(f"📤 已下发：{fmt_usdt(sent)}")
    lines.append(f"{'❗' if diff != 0 else '✅'} 未下发：{fmt_usdt(diff)}")
    lines.append("━━━━━━━━━━━━━━")
    lines.append("📚 **查看更多账单**：发送「更多账单」或「显示历史账单」")
    return "\n".join(lines)

# ========== Telegram ==========
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 你好，我是财务记账机器人。\n"
        "入金：+10000 或 +10000 / 日本\n"
        "出金：-10000 或 -10000 / 日本（法币→USDT）\n"
        "设置 示例：\n"
        "  设置 默认 入 费率 10\n"
        "  设置 日本 入 汇率 127\n"
        "管理员管理：\n"
        "  设置机器人管理员 @用户名\n"
        "  删除机器人管理员 @用户名\n"
        "  显示机器人管理员"
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (update.message.text or "").strip()
    ts, dstr = now_ts(), today_str()

    # 管理员管理命令
    if text.startswith(("设置机器人管理员", "删除机器人管理员", "显示机器人管理员")):
        lst = list_admins()
        if text.startswith("显示"):
            lines = [f"⭐ 超级管理员：{OWNER_ID or '未设置'}"]
            for a in lst: lines.append(f"- [ID {a}](tg://user?id={a})")
            await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
            return
        if not is_admin(user.id):
            await update.message.reply_text("🚫 你没有权限设置机器人管理员。")
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

    # 设置命令
    if text.startswith("设置"):
        if not is_admin(user.id):
            await update.message.reply_text("🚫 无权限执行此命令。")
            return
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
        amt, country = parse_amount_and_country(text)
        p = resolve_params("out", country)
        usdt = trunc2(amt * (1 + p["rate"]) / p["fx"])
        push_recent("out", {"ts": ts, "usdt": usdt})
        state["summary"]["sent_usdt"] = trunc2(state["summary"]["sent_usdt"] + usdt)
        save_state()
        append_log(log_path(country, dstr),
                   f"[出金] 时间:{ts} 国家:{country or '通用'} 原始:{amt} 汇率:{p['fx']} 费率:{p['rate']*100:.2f}% 下发:{usdt}")
        await update.message.reply_text(render_group_summary())
        return

    # 历史
    if text in ["更多账单", "显示历史账单"]:
        await update.message.reply_text(render_group_summary())
        return

    await update.message.reply_text("❓ 指令示例：+10000 / 日本 或 设置 默认 入 费率 10")

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

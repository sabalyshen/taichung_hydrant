# -*- coding: utf-8 -*-
"""指令處理器：/start /cancel /car /save /load /N"""
import os, logging, shutil
from datetime import datetime
from pathlib import Path
from telegram import Update, InputFile
from telegram.ext import ContextTypes

import map_bot
from state_manager import get_chat_data, load_state
from utils import BOT_TOKEN

OUTPUT_IMG = Path(map_bot.OUTPUT_IMG_DEFAULT)
OUTPUT_HTML = Path(map_bot.HTML_OUTPUT_DEFAULT)
SAVED_DIR = Path(map_bot._WRITE_DIR) / "saved_maps"
SAVED_DIR.mkdir(exist_ok=True)

logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚒 消防水源地圖 Bot\n\n"
        "1️⃣ 傳送地址 → 建立水源地圖\n"
        "2️⃣ 傳送位置＋消防車編號 → 記錄車輛\n"
        "3️⃣ /car → 標註所有車輛到地圖\n"
        "4️⃣ /save → 另存 HTML\n"
        "5️⃣ /load → 查看已存地圖\n"
        "6️⃣ /cancel → 清除狀態"
    )


async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cd = get_chat_data(context)
    cd.clear()
    p = Path(__file__).parent.parent / "chat_states" / f"{update.effective_chat.id}.json"
    if p.exists():
        p.unlink()
    await update.message.reply_text("✅ 已清除地圖狀態")


async def car_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cd = get_chat_data(context)
    chat_id = update.effective_chat.id

    if 'map_state' not in cd:
        saved = load_state(chat_id)
        if 'map_state' in saved:
            cd['map_state'] = saved['map_state']

    state = cd.get('map_state')
    trucks = cd.get('pending_trucks', [])

    if not state:
        await update.message.reply_text("⚠️ 尚未收到地址，請先傳送地址")
        return
    if not trucks:
        await update.message.reply_text("⚠️ 尚未收到任何消防車位置")
        return

    await update.message.reply_text(f"🗺️ 產生地圖中...（{len(trucks)} 台車）")
    try:
        result = map_bot.draw_map_with_trucks(
            state['center_lat'], state['center_lng'],
            state['label'], trucks, str(OUTPUT_IMG)
        )
        if result is None:
            await update.message.reply_text("地圖產生失敗")
            return

        with open(str(OUTPUT_IMG), 'rb') as f:
            names = ','.join(t['label'] for t in trucks)
            await update.message.reply_photo(photo=f, caption=f"📍 {state['label']}\n🚒 {names}")

        html_path, _ = map_bot.generate_interactive_map(
            state['center_lat'], state['center_lng'],
            state['label'], trucks, str(OUTPUT_HTML)
        )
        with open(html_path, 'rb') as f:
            await update.message.reply_document(
                document=InputFile(f, filename='消防水源地圖.html'),
                caption=f"🗺️ 互動地圖 | {len(trucks)} 台車 | 100 支消防栓"
            )

        await update.message.reply_text(f"✅ 地圖已產生（{len(trucks)} 台車），車輛清單保留中")
    except Exception as e:
        await update.message.reply_text("錯誤")
        logger.error(f"/car Error: {e}")


async def save_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not OUTPUT_HTML.exists():
        await update.message.reply_text("⚠️ 尚無地圖 HTML，請先產生地圖")
        return
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_name = f"map_{ts}.html"
    save_path = SAVED_DIR / save_name
    shutil.copy(str(OUTPUT_HTML), str(save_path))
    await update.message.reply_text(f"💾 已儲存：{save_name}")


async def load_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    files = sorted(SAVED_DIR.glob("map_*.html"), reverse=True)
    if not files:
        await update.message.reply_text("⚠️ 尚無已存地圖")
        return

    msg = "📂 已存地圖（輸入 /1~/10 取得）：\n\n"
    for i, f in enumerate(files[:10], 1):
        ts_str = f.stem.replace("map_", "")
        try:
            dt = datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
            ts_display = dt.strftime("%m/%d %H:%M")
        except ValueError:
            ts_display = ts_str
        size_kb = f.stat().st_size // 1024
        msg += f"/{i}. {ts_display} ({size_kb}KB)\n"

    cd = get_chat_data(context)
    cd['_load_list'] = [str(f) for f in files[:10]]
    await update.message.reply_text(msg)


async def handle_number_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cmd = update.message.text.strip().lstrip('/')
    if not cmd.isdigit():
        return
    idx = int(cmd) - 1
    cd = get_chat_data(context)
    files = cd.get('_load_list', [])
    if 0 <= idx < len(files):
        fpath = files[idx]
        with open(fpath, 'rb') as f:
            fname = Path(fpath).name
            await update.message.reply_document(
                document=InputFile(f, filename=fname),
                caption=f"📂 {fname}"
            )
    else:
        await update.message.reply_text("無效編號，請先輸入 /load 查看清單")

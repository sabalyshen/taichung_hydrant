# -*- coding: utf-8 -*-
"""文字訊息處理器：地址辨識、確認對話、車輛記錄"""
import os, logging
from pathlib import Path
from telegram import Update, InputFile
from telegram.ext import ContextTypes

import map_bot
from state_manager import get_chat_data, load_state, save_state
from utils import is_address

OUTPUT_IMG = Path(map_bot.OUTPUT_IMG_DEFAULT)
OUTPUT_HTML = Path(map_bot.HTML_OUTPUT_DEFAULT)

logger = logging.getLogger(__name__)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.is_bot:
        return

    text = update.message.text.strip()
    uid = update.message.from_user.id
    chat_id = update.effective_chat.id
    cd = get_chat_data(context)

    # 確認重複車輛移動 y/n
    if '_dup_truck' in cd:
        dup = cd.pop('_dup_truck')
        if text.lower() in ('y', 'yes', '是', 'Y'):
            cd['pending_trucks'] = [t for t in cd['pending_trucks'] if t['label'] != dup['label']]
            cd['pending_trucks'].append(dup)
            n = len(cd['pending_trucks'])
            await update.message.reply_text(f"🚒 {dup['label']} 位置已更新（共 {n} 台車）")
        else:
            await update.message.reply_text(f"❌ 已取消，{dup['label']} 維持原位置")
        return

    # 確認新地址 y/n
    if '_confirm_addr' in cd:
        addr = cd.pop('_confirm_addr')
        if text.lower() in ('y', 'yes', '是', 'Y'):
            cd.clear()
            await _new_address(update, context, addr)
        else:
            await update.message.reply_text("❌ 已取消，維持原地圖")
        return

    # 等待消防車編號（該用戶剛傳了位置）
    pending_key = f'_loc_{uid}'
    if pending_key in cd:
        lat, lng = cd.pop(pending_key)
        await _store_truck(update, context, lat, lng, text, uid)
        return

    if is_address(text):
        if 'map_state' not in cd:
            saved = load_state(chat_id)
            if 'map_state' in saved:
                cd['map_state'] = saved['map_state']

        if cd.get('map_state'):
            cd['_confirm_addr'] = text
            await update.message.reply_text(
                f"⚠️ 已有地圖「{cd['map_state']['label']}」，是否換成新地址？\n"
                "輸入 y（是）或 n（否）"
            )
        else:
            cd.clear()
            await _new_address(update, context, text)
        return


async def _store_truck(update: Update, context: ContextTypes.DEFAULT_TYPE,
                       lat: float, lng: float, label: str, uid: int):
    """記錄消防車位置，檢查重複名稱"""
    cd = get_chat_data(context)
    if 'pending_trucks' not in cd:
        cd['pending_trucks'] = []

    existing = [t for t in cd['pending_trucks'] if t['label'] == label]
    if existing:
        cd['_dup_truck'] = {'lat': lat, 'lng': lng, 'label': label, 'uid': uid}
        old = existing[0]
        await update.message.reply_text(
            f"⚠️ 車輛「{label}」已在清單中（位置: {old['lat']:.5f}, {old['lng']:.5f}）\n"
            f"是否移動車輛？\n輸入 y 覆蓋舊位置 / n 取消"
        )
        return

    cd['pending_trucks'].append({'lat': lat, 'lng': lng, 'label': label, 'uid': uid})
    n = len(cd['pending_trucks'])
    await update.message.reply_text(f"🚒 {label} 已記錄（共 {n} 台車），輸入 /car 產生地圖")


async def _new_address(update: Update, context: ContextTypes.DEFAULT_TYPE, address: str):
    """新地址 → 產生地圖"""
    chat_id = update.effective_chat.id
    await update.message.reply_text("🗺️ 查詢中...")
    try:
        result = map_bot.draw_map(address, str(OUTPUT_IMG))
        if result is None:
            await update.message.reply_text("❌ 找不到此地址")
            return

        _, nav_items = result

        lat, lng, _ = map_bot.geocode_address(address)
        if lat is None:
            await update.message.reply_text("定位失敗")
            return

        cd = get_chat_data(context)
        cd['map_state'] = {'center_lat': lat, 'center_lng': lng, 'label': address}
        cd['pending_trucks'] = []
        save_state(chat_id, cd)

        with open(str(OUTPUT_IMG), 'rb') as f:
            await update.message.reply_photo(photo=f, caption=f"📍 {address}")

        html_path, _ = map_bot.generate_interactive_map(lat, lng, address, [], str(OUTPUT_HTML))
        with open(html_path, 'rb') as f:
            await update.message.reply_document(
                document=InputFile(f, filename='消防水源地圖.html'),
                caption="🗺️ 互動地圖 | 100 支消防栓"
            )

        await update.message.reply_text("📌 請各車傳送「位置＋消防車編號」，完成後輸入 /car 產生完整地圖")

        if nav_items:
            msg = f"📍 {address}\n\n"
            for i, hid, dist, url in nav_items:
                msg += f"• 編號: {hid}\n• 距離: {dist}\n• {url}\n\n"
            await update.message.reply_text(msg.strip(), disable_web_page_preview=False)

    except Exception as e:
        await update.message.reply_text("錯誤")
        logger.error(f"_new_address Error: {e}")

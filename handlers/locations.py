# -*- coding: utf-8 -*-
"""位置訊息處理器"""
import logging
from telegram import Update
from telegram.ext import ContextTypes

from state_manager import get_chat_data, load_state
from handlers.messages import _store_truck

logger = logging.getLogger(__name__)


async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.is_bot:
        return

    loc = update.message.location
    caption = update.message.caption
    uid = update.message.from_user.id
    chat_id = update.effective_chat.id
    cd = get_chat_data(context)

    if 'map_state' not in cd:
        saved = load_state(chat_id)
        if 'map_state' in saved:
            cd['map_state'] = saved['map_state']

    if not cd.get('map_state'):
        await update.message.reply_text("⚠️ 請先傳送地址建立水源地圖")
        return

    if caption and caption.strip():
        await _store_truck(update, context, loc.latitude, loc.longitude, caption.strip(), uid)
    else:
        cd[f'_loc_{uid}'] = (loc.latitude, loc.longitude)
        await update.message.reply_text("📍 已收到位置！請輸入消防車編號（例如：大里91）")

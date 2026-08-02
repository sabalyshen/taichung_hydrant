# -*- coding: utf-8 -*-
"""共用工具函數"""
import re

# === 請更換為你的 Bot Token（從 @BotFather 取得）===
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"

def is_address(text: str) -> bool:
    """判斷是否為臺中市地址（可依需求修改正則表達式）"""
    if not text or len(text) < 4:
        return False
    if text.startswith('/') or text.startswith('📍') or text.startswith('🚒') or text.startswith('🗺️'):
        return False
    if not re.search(r'[臺台][中中南][市縣]', text):
        return False
    if not re.search(r'[路街大道]', text):
        return False
    return True

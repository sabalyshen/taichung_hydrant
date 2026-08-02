# -*- coding: utf-8 -*-
"""群組狀態管理：chat_data 存取 + JSON 持久化"""
import json
from pathlib import Path
from telegram.ext import ContextTypes

STATE_DIR = Path(__file__).parent / "chat_states"
STATE_DIR.mkdir(exist_ok=True)


def _state_path(chat_id: int) -> Path:
    return STATE_DIR / f"{chat_id}.json"


def load_state(chat_id: int) -> dict:
    """從磁碟載入持久化的地圖狀態"""
    p = _state_path(chat_id)
    if p.exists():
        with open(p, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_state(chat_id: int, chat_data: dict) -> None:
    """將 map_state 持久化到磁碟（過濾暫存 key）"""
    clean = {
        k: v for k, v in chat_data.items()
        if not k.startswith('_') and k != 'pending_trucks'
    }
    if 'map_state' in chat_data:
        clean['map_state'] = chat_data['map_state']
    with open(_state_path(chat_id), 'w', encoding='utf-8') as f:
        json.dump(clean, f, ensure_ascii=False)


def get_chat_data(context: ContextTypes.DEFAULT_TYPE) -> dict:
    """取得群組共享的 chat_data"""
    return context.chat_data

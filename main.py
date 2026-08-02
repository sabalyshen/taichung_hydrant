# -*- coding: utf-8 -*-
"""消防水源地圖 Telegram Bot — 主程式入口"""
import sys, os, logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# 確保可 import 上層的 map_bot
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils import BOT_TOKEN
from handlers.commands import (
    start, cancel_cmd, car_cmd, save_cmd, load_cmd, handle_number_command
)
from handlers.messages import handle_message
from handlers.locations import handle_location

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')


def main():
    app = Application.builder().token(BOT_TOKEN)\
        .read_timeout(60).write_timeout(60).connect_timeout(30)\
        .pool_timeout(60).build()

    # 指令
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel_cmd))
    app.add_handler(CommandHandler("car", car_cmd))
    app.add_handler(CommandHandler("save", save_cmd))
    app.add_handler(CommandHandler("load", load_cmd))
    # /1 ~ /10
    app.add_handler(MessageHandler(filters.COMMAND & filters.Regex(r'^/\d+$'), handle_number_command))
    # 位置
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    # 文字
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot 啟動完成")
    app.run_polling(drop_pending_updates=True, poll_interval=1.0, timeout=60)


if __name__ == '__main__':
    main()

import os, logging
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler,CallbackQueryHandler, filters
from .database import init_db
from .handlers import (
    cmd_help, cmd_start, 
    cmd_unknown, error_handler, cmd_reminders_btn,
    cmd_events_btn, cmd_birthdays_btn, cmd_settings_btn
)
from .conversations import remind_conversation, bday_conversation, reg_conversation
from .callbacks import handle_callback
from .scheduler import create_scheduler

load_dotenv()
logging.basicConfig(level=logging.INFO)

def main():
    init_db()
    token = os.environ['TELEGRAM_BOT_TOKEN']
    app = ApplicationBuilder().token(token).build()

    # Conversation handlers — must be registered before plain MessageHandlers
    app.add_handler(remind_conversation())
    app.add_handler(bday_conversation())
    app.add_handler(reg_conversation())

    # Inline button callbacks
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Commands
    app.add_handler(CommandHandler('start',      cmd_start))
    app.add_handler(CommandHandler('help',       cmd_help))
    app.add_handler(CommandHandler('settings',   cmd_settings_btn))
    app.add_handler(CommandHandler('events',     cmd_events_btn))
    app.add_handler(CommandHandler('reminders',  cmd_reminders_btn))
    app.add_handler(CommandHandler('birthdays',  cmd_birthdays_btn))

    # Reply keyboard button handlers
    app.add_handler(MessageHandler(filters.Regex('^🗓️ Events$'),    cmd_events_btn))
    app.add_handler(MessageHandler(filters.Regex('^🎂 Birthdays$'), cmd_birthdays_btn))
    app.add_handler(MessageHandler(filters.Regex('^⚙️ Settings$'),  cmd_settings_btn))
    app.add_handler(MessageHandler(filters.Regex('^📌 Reminders$'), cmd_reminders_btn))
    app.add_handler(MessageHandler(filters.Regex('^❓ Help$'),      cmd_help))
    
    # unknown command handler — always last
    app.add_handler(MessageHandler(filters.COMMAND, cmd_unknown))
    
    app.add_error_handler(error_handler)
    
    # Scheduler
    scheduler = create_scheduler(app.bot)
    scheduler.start()

    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
import os, logging
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from .database import init_db
from .handlers import cmd_register, cmd_events, cmd_remind, cmd_birthday, cmd_help, cmd_birthdays_list, cmd_start, cmd_birthday_delete, cmd_unknown, error_handler
from .scheduler import create_scheduler

load_dotenv()
logging.basicConfig(level=logging.INFO)

def main():
    init_db()
    token = os.environ['TELEGRAM_BOT_TOKEN']
    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler('register',     cmd_register))
    app.add_handler(CommandHandler('events',       cmd_events))
    app.add_handler(CommandHandler('remind',       cmd_remind))
    app.add_handler(CommandHandler('bday_add',     cmd_birthday))
    app.add_handler(CommandHandler('bdays',        cmd_birthdays_list))
    app.add_handler(CommandHandler('bdel',         cmd_birthday_delete))
    app.add_handler(CommandHandler('help',         cmd_help))
    app.add_handler(CommandHandler('start',        cmd_start))
    
    # unknown command handler — always last
    app.add_handler(MessageHandler(filters.COMMAND, cmd_unknown))
    
    app.add_error_handler(error_handler)
    
    scheduler = create_scheduler(app.bot)
    scheduler.start()

    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
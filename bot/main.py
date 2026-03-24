import os, logging
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, CommandHandler
from .database import init_db
from handlers import cmd_register, cmd_events, cmd_remind, cmd_birthday, cmd_help
from .scheduler import create_scheduler

load_dotenv()
logging.basicConfig(level=logging.INFO)

def main():
    init_db()
    token = os.environ['TELEGRAM_BOT_TOKEN']
    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler('register', cmd_register))
    app.add_handler(CommandHandler('events',   cmd_events))
    app.add_handler(CommandHandler('remind',   cmd_remind))
    app.add_handler(CommandHandler('birthday', cmd_birthday))
    app.add_handler(CommandHandler('help',     cmd_help))

    scheduler = create_scheduler(app.bot)
    scheduler.start()

    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
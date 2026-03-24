from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, date
from .database import get_conn
import os, logging

logger = logging.getLogger(__name__)

async def check_reminders(bot):
    now = datetime.now()
    with get_conn() as conn:
        rows = conn.execute(
            '''SELECT * FROM reminders WHERE sent=0
            AND remind_at <= ?''', (now.isoformat(),)
        ).fetchall()
        for row in rows:
            await bot.send_message(row['telegram_id'], row['message'])
            conn.execute(
                'UPDATE reminders SET sent=1 WHERE id=?', (row['id'],)
            )

async def check_birthdays(bot):
    today = date.today().strftime('%d-%m')
    with get_conn() as conn:
        rows = conn.execute(
            'SELECT * FROM birthdays WHERE birth_date=?', (today,)
        ).fetchall()
        # Notify all registered users
        users = conn.execute('SELECT * FROM user_calendars').fetchall()
        for bday in rows:
            for user in users:
                await bot.send_message(
                    user['telegram_id'],
                    f'U0001f382 Happy Birthday {bday["name"]}!'
                )

def create_scheduler(bot):
    scheduler = AsyncIOScheduler()
    interval = int(os.getenv('REMINDER_CHECK_INTERVAL_MINUTES', 5))
    hour = int(os.getenv('BIRTHDAY_CHECK_HOUR', 8))
    scheduler.add_job(check_reminders, 'interval',
                      minutes=interval, args=[bot])
    scheduler.add_job(check_birthdays, 'cron',
                      hour=hour, minute=0, args=[bot])
    return scheduler

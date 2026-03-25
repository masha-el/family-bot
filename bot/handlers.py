from telegram import Update
from telegram.ext import ContextTypes
from .database import get_conn
from .calendar_client import get_upcoming_events
from datetime import datetime

async def cmd_register(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    # /register <calendar_id><your name>
    args = ctx.args
    if len(args) < 2:
        await update.message.reply_text(
            'Usage: /register <calendar_id> <your name>'
        )
        return 
    cal_id, name = args[0], ' '.join(args[1:])
    with get_conn() as conn:
        conn.execute(
            'INSERT OR REPLACE INTO user_calendars VALUES (?,?,?)',
            (update.effective_user.id, name, cal_id)
        )
    await update.message.reply_text(f'Registered {name}!')

async def cmd_events(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    # events  -- shows your next 7 days
    uid = update.effective_user.id
    with get_conn() as conn:
        row = conn.execute(
            'SELECT * FROM user_calendars WHERE telegram_id=?', (uid,)
        ).fetchone()
    if not row:
        await update.message.reply_text(
            'Not registered. Use /register <calendar_id> <name>'
        )
        return
    events = get_upcoming_events(row['calendar_id'])
    if not events:
        await update.message.reply_text('No upcoming events this week.')
        return
    lines = []
    for e in events:
        start = e['start'].get('dateTime', e['start'].get('date'))
        lines.append(f"• {e['summary']} - {start[:16].replace('T', ' ')}")
    await update.message.reply_text('Your next 7 days: ' + ' '.join(lines))

async def cmd_remind(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    # /remind DD-MM-YYYY HH:MM <message>
    if len(ctx.args) < 3:
        await update.message.reply_text(
            'Usage: /remind DD-MM-YYYY HH:MM <message>'
        )
        return
    date_str = ctx.args[0] + ' ' + ctx.args[1]
    msg = ' '.join(ctx.args[2:])
    try:
        remind_at = datetime.strptime(date_str, '%d-%m-%Y %H:%M')
    except ValueError:
        await update.message.reply_text('Date format: DD-MM-YYYY HH:MM')
        return
    with get_conn() as conn:
        conn.execute(
            'INSERT INTO reminders (telegram_id,remind_at,message) VALUES (?,?,?)',
            (update.effective_user.id, remind_at.isoformat(), msg)
        )
    await update.message.reply_text(f'Reminder set for {date_str}')

async def cmd_birthday(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    # /birthday add <name> <DD-MM>
    if len(ctx.args) < 3 or ctx.args[0] != 'add':
        await update.message.reply_text(
            'Usage: /birthday add <name> <DD-MM>'
        )
        return
    name, date_str = ' '.join(ctx.args[1:-1]), ctx.args[-1]
    with get_conn() as conn:
        conn.execute(
            'INSERT INTO birthdays (added_by,name,birth_date) VALUES (?,?,?)',
            (update.effective_user.id, name, date_str)
        )
    await update.message.reply_text(f'Birthday added for {name} on {date_str}')

async def  cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (
        "🤖 *Family Bot Commands*\n"
        "───────────────────────\n\n"
        "\U0001f5d3 *Calendar*\n"
        "`/events` — your next 7 days\n\n"
        "⏰ *Reminders*\n"
        "`/remind DD\\-MM\\-YYYY HH:MM <message>`\n"
        "_Example: /remind 25\\-12\\-2025 09:00 Buy gifts_\n\n"
        "🎂 *Birthdays*\n"
        "`/birthday add <name> MM\\-DD`\n"
        "_Example: /birthday add Masha 03\\-15_\n\n"
        "⚙️ *Setup*\n"
        "`/register <calendar\\_id> <your name>`\n\n"
        "───────────────────────"
    )
    await update.message.reply_text(text, parse_mode="MarkdownV2")
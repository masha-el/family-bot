from telegram import Update
from telegram.ext import ContextTypes
from .database import get_conn
from .calendar_client import get_upcoming_events
from datetime import datetime
import re

def escape_md(text: str) -> str:
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', str(text))

async def cmd_register(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    # /register <calendar_id><your name>
    args = ctx.args
    if len(args) < 2:
        await update.message.reply_text(
            "⚙️ *Register Your Calendar*\n"
            "───────────────────────\n"
            "Usage: `/register <calendar\\_id> <your name>`\n"
            "_Your calendar ID is found in Google Calendar_\n"
            "_Settings \\> Integrate calendar_",
            parse_mode="MarkdownV2"
        )
        return 
    cal_id, name = args[0], ' '.join(args[1:])
    with get_conn() as conn:
        conn.execute(
            'INSERT OR REPLACE INTO user_calendars VALUES (?,?,?)',
            (update.effective_user.id, name, cal_id)
        )
    escaped_name = escape_md(name)
    await update.message.reply_text(
        "✅ *Registration complete\\!*\n"
        "───────────────────────\n"
        f"👤 *{escaped_name}*\n"
        "Your Google Calendar is now linked\\.\n"
        "Try `/events` to see your upcoming week\\.",
        parse_mode="MarkdownV2"
    )

async def cmd_events(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    # events  -- shows your next 7 days
    uid = update.effective_user.id
    with get_conn() as conn:
        row = conn.execute(
            'SELECT * FROM user_calendars WHERE telegram_id=?', (uid,)
        ).fetchone()
    if not row:
        await update.message.reply_text(
            "⚙️ You're not registered yet\\.\n"
            "Use `/register <calendar\\_id> <your name>` to get started\\.",
            parse_mode="MarkdownV2"
        )
        return
    events = get_upcoming_events(row['calendar_id'])
    if not events:
        await update.message.reply_text(
            "\U0001f5d3 *No upcoming events*\n"
            "Your calendar is clear for the next 7 days\\.",
            parse_mode="MarkdownV2"
        )
        return
    lines = ["\U0001f5d3 *Your next 7 days*\n───────────────────────"]
    for e in events:
        start = e['start'].get('dateTime', e['start'].get('date'))
        date_part = start[:10]
        time_part = start[11:16] if 'T' in start else 'All day'
        # convert date to DD-MM-YYYY for display
        d, m, y = date_part[8:], date_part[5:7], date_part[:4]
        display_date = f"{d}\\-{m}\\-{y}"
        display_time = time_part.replace(':', '\\:') if time_part != 'All day' else 'All day'
        summary = e['summary'].replace('-', '\\-').replace('.', '\\.').replace('!', '\\!')

        lines.append(f"📌 *{summary}*\n    🕐 {display_date} {display_time}")
        lines.append("───────────────────────")
    await update.message.reply_text('\n'.join(lines), parse_mode="MarkdownV2")

async def cmd_remind(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    # /remind DD-MM-YYYY HH:MM <message>
    if len(ctx.args) < 3:
        await update.message.reply_text(
            "⏰ *Set a Reminder*\n"
            "───────────────────────\n"
            "Usage: `/remind DD\\-MM\\-YYYY HH:MM <message>`\n"
            "_Example: /remind 25\\-12\\-2025 09:00 Buy gifts_",
            parse_mode="MarkdownV2"
        )
        return
    date_str = ctx.args[0] + ' ' + ctx.args[1]
    msg = ' '.join(ctx.args[2:])
    try:
        remind_at = datetime.strptime(date_str, '%d-%m-%Y %H:%M')
    except ValueError:
        await update.message.reply_text(
            "❌ *Invalid date format*\n"
            "Use: `DD\\-MM\\-YYYY HH:MM`\n"
            "_Example: 25\\-12\\-2025 09:00_",
            parse_mode="MarkdownV2"
        )
        return
    with get_conn() as conn:
        conn.execute(
            'INSERT INTO reminders (telegram_id,remind_at,message) VALUES (?,?,?)',
            (update.effective_user.id, remind_at.isoformat(), msg)
        )
    d, m, y = ctx.args[0].split('-')
    escaped_date = f"{d}\\-{m}\\-{y}"
    escaped_time = ctx.args[1].replace(':', '\\:')
    escaped_msg = escape_md(msg)
    await update.message.reply_text(
        "✅ *Reminder set\\!*\n"
        "───────────────────────\n"
        f"\U0001f5d3 {escaped_date} at {escaped_time}\n"
        f"💬 {escaped_msg}",
        parse_mode="MarkdownV2"
    )

async def cmd_birthday(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    # /birthday add <name> <DD-MM>
    if len(ctx.args) < 3 or ctx.args[0] != 'add':
        await update.message.reply_text(
            "🎂 *Add a Birthday*\n"
            "───────────────────────\n"
            "Usage: `/birthday add <name> MM\\-DD`\n"
            "_Example: /birthday add Masha 03\\-15_",
            parse_mode="MarkdownV2"
        )
        return
    name = ' '.join(ctx.args[1:-1])
    date_str = ctx.args[-1]
    with get_conn() as conn:
        conn.execute(
            'INSERT INTO birthdays (added_by,name,birth_date) VALUES (?,?,?)',
            (update.effective_user.id, name, date_str)
        )
    escaped_name = escape_md(name)
    m, d = date_str.split('-')
    escaped_date = f"{m}\\-{d}"
    await update.message.reply_text(
        "✅ *Birthday added\\!*\n"
        "───────────────────────\n"
        f"🎂 *{escaped_name}*\n"
        f"\U0001f5d3 Every year on {escaped_date}",
        parse_mode="MarkdownV2"
    )

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
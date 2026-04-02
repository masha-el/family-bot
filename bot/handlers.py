from telegram import Update
from telegram.ext import ContextTypes
from .database import get_conn
from .calendar_client import get_upcoming_events
from .keyboards import main_keyboard, events_keyboard, birthdays_keyboard, registration_keyboard
from datetime import datetime
import traceback
import re, os

def escape_md(text: str) -> str:
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', str(text))

async def cmd_events_btn(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    # events  -- shows your next 7 days
    uid = update.effective_user.id
    with get_conn() as conn:
        row = conn.execute(
            'SELECT * FROM user_calendars WHERE telegram_id=?', (uid,)
        ).fetchone()
    if not row:
        await update.message.reply_text(
            "⚙️ You're not registered yet\\.\n"
            "Tap ⚙️ Settings to link your Google Calendar\\.",            
            parse_mode="MarkdownV2",
            reply_markup=main_keyboard()
        )
        return
    events = get_upcoming_events(row['calendar_id'], days=7)
    if not events:
        await update.message.reply_text(
            "🗓️ *No upcoming events*\n"
            "Your calendar is clear for the next 7 days\\.",
            parse_mode="MarkdownV2",
            reply_markup=events_keyboard()
        )
        return
    lines = ["🗓️ *Your next 7 days*\n────────────────────"]
    for e in events:
        start = e['start'].get('dateTime', e['start'].get('date'))
        date_part = start[:10]
        time_part = start[11:16] if 'T' in start else 'All day'
        # convert date to DD-MM-YYYY for display
        d, m, y = date_part[8:], date_part[5:7], date_part[:4]
        lines.append(
            f"📌 *{escape_md(e['summary'])}*\n"
            f"↳ 🕐 {escape_md(f'{d}-{m}-{y}')} {escape_md(time_part)}"
        )
        lines.append("────────────────────")
    await update.message.reply_text(
        '\n'.join(lines), 
        parse_mode="MarkdownV2",
        reply_markup=events_keyboard()
        )

async def cmd_reminders_btn(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    with get_conn() as conn:
        rows = conn.execute(
            'SELECT id, remind_at, message FROM reminders WHERE telegram_id=? AND sent=0 ORDER BY remind_at',
            (uid,)
        ).fetchall()
    if not rows:
        await update.message.reply_text(
            "⏰ *No upcoming reminders*\n"
            "Tap ⏰ *Remind me* to add one\\.",
            parse_mode="MarkdownV2",
            reply_markup=main_keyboard()
        )
        return
    from .keyboards import reminders_keyboard
    reminder_ids = []
    lines = ["⏰ *Your reminders*\n────────────────────"]
    for row in rows:
        dt = datetime.fromisoformat(row['remind_at'])
        label = f"{dt.strftime('%d-%m-%Y %H:%M')} — {row['message'][:20]}"
        reminder_ids.append((row['id'], label))
        lines.append(f"📌 {escape_md(label)}")
    lines.append("────────────────────")
    await update.message.reply_text(
        '\n'.join(lines),
        parse_mode="MarkdownV2",
        reply_markup=reminders_keyboard(reminder_ids)
    )

async def  cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (
        "🤖 *Family Bot Commands*\n"
        "────────────────────\n\n"
        "\U0001f5d3 *Calendar*\n"
        "/events — your next 7 days\n\n"
        "⏰ *Reminders*\n"
        "/remind `<full-date> <time> <message>`\n"
        "_Example: `/remind` 25\\-12\\-2026 09:00 Buy gifts_\n\n"
        "🎂 *Birthdays commands:*\n"
        "/bday\\_add `<name> <day-month>`\n"
        "_Example: `/bday_add` Masha 10\\-01_\n\n"
        "/bdays — see all the birthdays you added\n\n"
        "/bdel — get numbered list, use `/bdel` with a number to delete\n"
        "_Example:`/bdel` 1 or `/bdel` 1 2_\n\n"
        "⚙️ *Setup*\n"
        "⚠️ Don't forget to share your calendar with the Bot Service Account\n"
        "/register `<calendar\\_id> <your name>`\n\n"
        "────────────────────"
    )
    await update.message.reply_text(text, parse_mode="MarkdownV2")

async def error_handler(update: object, ctx: ContextTypes.DEFAULT_TYPE):
    error_msg = ''.join(traceback.format_exception(
        type(ctx.error), ctx.error, ctx.error.__traceback__
    ))
    # truncate to Telegram's 4096 char limit
    if len(error_msg) > 3800:
        error_msg = error_msg[-3800:]
    
    text = (
        "❌ *Family Bot Error*\n"
        "────────────────────\n"
        f"`{escape_md(error_msg)}`"
    )
    await ctx.bot.send_message(
        chat_id=os.environ['ADMIN_TELEGRAM_ID'],
        text=text,
        parse_mode="MarkdownV2"
    )

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    name = escape_md(update.effective_user.first_name or "there")
    text = (
        f"👋 *Hello, {name}\\!*\n"
        "────────────────────\n"
        "I'm your *Family Bot* — here to keep everyone organized and on time\\.\n\n"
        "ℹ️ *What I can do:*\n"
        "• Sync with your personal Google Calendar\n"
        "• Send you reminders for events and appointments after you add them\n"
        "• Remind you of family or anyone's birthday\n\n"
        "Use the buttons below to get started\\."
    )
    await update.message.reply_text(
        text, parse_mode="MarkdownV2",
        reply_markup=main_keyboard()
        )

async def cmd_birthdays_btn(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    with get_conn() as conn:
        rows = conn.execute(
            'SELECT name, birth_date FROM birthdays WHERE added_by=?',(uid,)
        ).fetchall()
    if not rows:
        text = "🎂 *No birthdays added yet*"
    else:
        lines = ["🎂 *Birthdays*\n────────────────────"]
        for row in rows:
            lines.append(f"• {escape_md(row['name'])} — {escape_md(row['birth_date'])}")
        lines.append("────────────────────")
        text = '\n'.join(lines)
    await update.message.reply_text(
        text, parse_mode="MarkdownV2",
        reply_markup=birthdays_keyboard()
    )

async def cmd_unknown(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    command = update.message.text.split()[0].split('@')[0]
    await update.message.reply_text(
        f"❌ *Unknown command:* `{escape_md(command)}`\n"
        "Use /help to see all available commands\\.",
        parse_mode="MarkdownV2"
    )

async def cmd_settings_btn(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    import logging
    logging.info(f"Settings button pressed by uid: {uid}")

    with get_conn() as conn:
        row = conn.execute(
            'SELECT * FROM user_calendars WHERE telegram_id=?', (uid,)
        ).fetchone()
    if row:
        text = (
            "⚙️ *Your account*\n"
            "───────────────────────\n"
            f"👤 *{escape_md(row['name'])}*\n"
            f"\U0001f5d3 Calendar linked ✅\n\n"
            "To re\\-link a different calendar, tap the button below\\."
        )
    else:
        text = (
            "⚙️ *Setup*\n"
            "───────────────────────\n"
            "You haven't linked your Google Calendar yet\\.\n\n"
            "Tap the button below to get started\\."
        )
    await update.message.reply_text(
        text, parse_mode="MarkdownV2",
        reply_markup=registration_keyboard()
    )
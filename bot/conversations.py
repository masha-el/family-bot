from telegram import Update
from telegram.ext import (
    ContextTypes, ConversationHandler,
    MessageHandler, CallbackQueryHandler, filters
)
from .database import get_conn
from .calendar_client import add_birthday_event
from .keyboards import main_keyboard, cancel_keyboard
from .handlers import escape_md
from datetime import datetime
import logging

# Conversation states
REMIND_DATE, REMIND_TIME, REMIND_MSG = range(3)
BDAY_NAME, BDAY_DATE = range(3, 5)
REG_CALENDAR_ID, REG_NAME = range(5, 7)

# ─── /remind guided flow ─────────────────────────────────
async def remind_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⏰ *New Reminder*\n"
        "────────────────────\n"
        "Step 1 of 3 — Enter the date:\n"
        "_Format: DD\\-MM\\-YYYY_",
        parse_mode="MarkdownV2",
        reply_markup=cancel_keyboard()
    )
    return REMIND_DATE

async def remind_date(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.text == '❌ Cancel':
        return await _cancel(update, ctx)
    text = update.message.text.strip()
    parts = text.split('-')
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        await update.message.reply_text(
            "❌ Invalid format\\. Please enter the date as `DD\\-MM\\-YYYY`:",
            parse_mode="MarkdownV2"
        )
        return REMIND_DATE
    day, month, year = parts[0].zfill(2), parts[1].zfill(2), parts[2]
    if not (1 <= int(day) <= 31 and 1 <= int(month) <= 12):
        await update.message.reply_text(
            "❌ Invalid date\\. Try again:",
            parse_mode="MarkdownV2"
        )
        return REMIND_DATE
    ctx.user_data['remind_date'] = f"{day}-{month}-{year}"
    await update.message.reply_text(
        "Step 2 of 3 — Enter the time:\n"
        "_Format: HH:MM_",
        parse_mode="MarkdownV2",
        reply_markup=cancel_keyboard()
    )
    return REMIND_TIME

async def remind_time(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.text == '❌ Cancel':
        return await _cancel(update, ctx)
    text = update.message.text.strip()
    parts = text.split(':')
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        await update.message.reply_text(
            "❌ Invalid format\\. Please enter time as `HH:MM`:",
            parse_mode="MarkdownV2"
        )
        return REMIND_TIME
    hour, minute = int(parts[0]), int(parts[1])
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        await update.message.reply_text(
            "❌ Invalid time\\. Try again:",
            parse_mode="MarkdownV2"
        )
        return REMIND_TIME
    ctx.user_data['remind_time'] = text
    await update.message.reply_text(
        "Step 3 of 3 — Enter your reminder message:",
        reply_markup=cancel_keyboard()
    )
    return REMIND_MSG

async def remind_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.text == '❌ Cancel':
        return await _cancel(update, ctx)
    msg = update.message.text.strip()
    date_str = ctx.user_data['remind_date']
    time_str = ctx.user_data['remind_time']
    full_str = f"{date_str} {time_str}"
    # convert DD-MM-YYYY to datetime
    day, month, year = date_str.split('-')
    remind_at = datetime.strptime(f"{year}-{month}-{day} {time_str}", '%Y-%m-%d %H:%M')
    with get_conn() as conn:
        conn.execute(
            'INSERT INTO reminders (telegram_id, remind_at, message) VALUES (?,?,?)',
            (update.effective_user.id, remind_at.isoformat(), msg)
        )
    await update.message.reply_text(
        "✅ *Reminder set\\!*\n"
        "────────────────────\n"
        f"🗓️ {escape_md(date_str)} at {escape_md(time_str)}\n"
        f"💬 {escape_md(msg)}",
        parse_mode="MarkdownV2",
        reply_markup=main_keyboard()
    )
    ctx.user_data.clear()
    return ConversationHandler.END

# ─── /bday_add guided flow ─────────────────────
async def bday_add_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    # can be triggered by command or inline button
    if update.callback_query:
        await update.callback_query.answer()
        msg = update.callback_query.message
    else:
        msg = update.message
    await msg.reply_text(
        "🎂 *Add a Birthday*\n"
        "────────────────────\n"
        "Step 1 of 2 — Enter the person's name:",
        parse_mode="MarkdownV2",
        reply_markup=cancel_keyboard()
    )
    return BDAY_NAME

async def bday_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.text == '❌ Cancel':
        return await _cancel(update, ctx)
    ctx.user_data['bday_name'] = update.message.text.strip()
    await update.message.reply_text(
        "Step 2 of 2 — Enter their birthday:\n"
        "_Format: DD\\-MM_",
        parse_mode="MarkdownV2",
        reply_markup=cancel_keyboard() 
    )
    return BDAY_DATE

async def bday_date(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.text == '❌ Cancel':
        return await _cancel(update, ctx)
    text = update.message.text.strip()
    parts = text.split('-')
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        await update.message.reply_text(
            "❌ Invalid format\\. Please enter as `DD\\-MM`:",
            parse_mode="MarkdownV2"
        )
        return BDAY_DATE
    day, month = parts[0].zfill(2), parts[1].zfill(2)
    if not (1 <= int(day) <= 31 and 1 <= int(month) <= 12):
        await update.message.reply_text(
            "❌ Invalid date\\. Try again:",
            parse_mode="MarkdownV2"
        )
        return BDAY_DATE
    date_str = f"{day}-{month}"
    name = ctx.user_data['bday_name']

    calendar_event_id = None
    cal_status = ""
    with get_conn() as conn:
        row = conn.execute(
            'SELECT * FROM user_calendars WHERE telegram_id=?',
            (update.effective_user.id,)
        ).fetchone()
    if row:
        try:
            calendar_event_id = add_birthday_event(row['calendar_id'], name, date_str)
            cal_status = "\n🗓️ Added to your Google Calendar"
        except Exception as e:
            logging.error(f"Failed to add birthday to calendar: {e}", exc_info=True)
            cal_status = "\n⚠️ Saved locally but failed to add to Google Calendar"
    
    with get_conn() as conn:
        conn.execute(
            'INSERT INTO birthdays (added_by, name, birth_date, calendar_event_id) VALUES (?,?,?,?)',
            (update.effective_user.id, name, date_str, calendar_event_id)
        )
    await update.message.reply_text(
        "✅ *Birthday added\\!*\n"
        "────────────────────\n"
        f"🎂 *{escape_md(name)}*\n"
        f"\U0001f5d3 Every year on {escape_md(date_str)}"
        f"{escape_md(cal_status)}",
        parse_mode="MarkdownV2",
        reply_markup=main_keyboard()
    )
    ctx.user_data.clear()
    return ConversationHandler.END

# ─── Registration guided flow ───────────────

async def reg_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        msg = update.callback_query.message
    else:
        msg = update.message
    await msg.reply_text(
        "⚙️ *Link Your Google Calendar*\n"
        "────────────────────\n"
        "Step 1 of 2 — Paste your Calendar ID:\n\n"
        "_Found in Google Calendar \\> Settings \\> Settings for my calendar \\> Integrate calendar_",
        parse_mode="MarkdownV2",
        reply_markup=cancel_keyboard()
    )
    return REG_CALENDAR_ID

async def reg_calendar_id(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.text == '❌ Cancel':
        return await _cancel(update, ctx)
    ctx.user_data['calendar_id'] = update.message.text.strip()
    await update.message.reply_text(
        "Step 2 of 2 — What's your name?",
        reply_markup=cancel_keyboard()
    )
    return REG_NAME

async def reg_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.text == '❌ Cancel':
        return await _cancel(update, ctx)
    name = update.message.text.strip()
    cal_id = ctx.user_data['calendar_id']
    with get_conn() as conn:
        conn.execute(
            'INSERT OR REPLACE INTO user_calendars VALUES (?,?,?)',
            (update.effective_user.id, name, cal_id)
        )
    await update.message.reply_text(
       "✅ *Registration complete\\!*\n"
        "────────────────────\n"
        f"👤 *{escape_md(name)}*\n"
        "Your Google Calendar is now linked\\.\n"
        "Try 🗓️ Events to see your upcoming week\\.",
        parse_mode="MarkdownV2",
        reply_markup=main_keyboard() 
    )
    ctx.user_data.clear()
    return ConversationHandler.END

# ─── Shared cancel ───────────────────
async def _cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    await update.message.reply_text(
        "❌ Cancelled\\.",
        parse_mode="MarkdownV2",
        reply_markup=main_keyboard()
    )
    return ConversationHandler.END

# ─── ConversationHandler builders ────────────
def remind_conversation():
    return ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex('^⏰ Remind me$'), remind_start),
        ],
        states={
            REMIND_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, remind_date)],
            REMIND_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, remind_time)],
            REMIND_MSG:  [MessageHandler(filters.TEXT & ~filters.COMMAND, remind_message)],
        },
        fallbacks=[MessageHandler(filters.Regex('^❌ Cancel$'), _cancel)],
        per_user=True
    )

def bday_conversation():
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(bday_add_start, pattern='^bday_add_start$'),
        ],
        states={
            BDAY_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, bday_name)],
            BDAY_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, bday_date)],
        },
        fallbacks=[MessageHandler(filters.Regex('^❌ Cancel$'), _cancel)],
        per_user=True
    )

def reg_conversation():
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(reg_start, pattern='^reg_start$'),
            MessageHandler(filters.Regex('^⚙️ Settings$'), reg_start),
        ],
        states={
            REG_CALENDAR_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_calendar_id)],
            REG_NAME:        [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_name)], 
        },
        fallbacks=[MessageHandler(filters.Regex('^❌ Cancel$'), _cancel)],
        per_user=True
    )
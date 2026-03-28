from telegram import Update
from telegram.ext import ContextTypes
from .database import get_conn
from .calendar_client import get_upcoming_events, delete_birthday_event
from .keyboards import events_keyboard, birthdays_keyboard, reminders_keyboard
from .handlers import escape_md
from datetime import datetime
import logging

async def handle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == 'events_refresh':
        await _show_events(query, days=7)

    elif data == 'events_14':
        await _show_events(query, days=14)

    elif data == 'bday_del_start':
        await _show_bday_delete(query)

    elif data.startswith('bday_del_'):
        await _delete_birthday(query, int(data.replace('bday_del_', '')))

    elif data.startswith('rem_del_'):
        await _delete_reminder(query, int(data.replace('rem_del_', '')))
    
async def _show_events(query, days: int):
        uid = query.from_user.id
        with get_conn() as conn:
            row = conn.execute(
                'SELECT * FROM user_calendars WHERE telegram_id=?', (uid,)
            ).fetchone()
        if not row:
            await query.edit_message_text(
                "⚙️ You're not registered yet\\.\n"
                "Use ⚙️ Settings to link your calendar\\.",
                parse_mode="MarkdownV2" 
            )
            return
        events = get_upcoming_events(row['calendar_id'], days=days)
        if not events:
            await query.edit_message_text(
                f"🗓️ *No events in the next {days} days*",
                parse_mode="MarkdownV2",
                reply_markup=events_keyboard()
            )
            return
        lines = [f"🗓️ *Your next {days} days*\n────────────────────"]
        for e in events:
            start = e['start'].get('dateTime', e['start'].get('date'))
            date_part = start[:10]
            time_part = start[11:16] if 'T' in start else 'All day'
            d, m, y = date_part[8:], date_part[5:7], date_part[:4]
            lines.append(
                f"📌 *{escape_md(e['summary'])}*\n"
                f"↳ 🕐 {escape_md(f'{d}-{m}-{y}')} {escape_md(time_part)}"
            )
        lines.append("────────────────────")
        await query.edit_message_text(
            '\n'.join(lines),
            parse_mode="MarkdownV2",
            reply_markup=events_keyboard()
        )

async def _show_bday_delete(query):
    uid = query.from_user.id
    with get_conn() as conn:
        rows = conn.execute(
            'SELECT id, name, birth_date FROM birthdays WHERE added_by=?', (uid,)
        ).fetchall()
    if not rows:
        await query.edit_message_text(
            "🎂 *No birthdays to delete*",
            parse_mode="MarkdownV2",
            reply_markup=birthdays_keyboard()
        )
        return
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    buttons = [[InlineKeyboardButton(
        f"🗑️ {row['name']} — {row['birth_date']}",
        callback_data=f"bday_del_{row['id']}"
    )] for row in rows]
    buttons.append([InlineKeyboardButton("← Back", callback_data="bday_back")])
    await query.edit_message_reply_markup(
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def _delete_birthday(query, birthday_id: int):
    uid = query.from_user.id
    with get_conn() as conn:
        row = conn.execute(
            'SELECT * FROM birthdays WHERE id=? AND added_by=?',
            (birthday_id, uid)
        ).fetchone()
        if not row:
            await query.answer("Not found.")
            return
        conn.execute('DELETE FROM birthdays WHERE id=?', (birthday_id,))
        if row['calendar_event_id']:
            user_row = conn.execute(
                'SELECT calendar_id FROM user_calendars WHERE telegram_id=?', (uid,)
            ).fetchone()
            if user_row:
                try:
                    delete_birthday_event(user_row['calendar_id'], row['calendar_event_id'])
                except Exception as e:
                    logging.error(f"Failed to delete calendar event: {e}", exc_info=True)
    await query.answer(f"Deleted {row['name']}")
    await _show_bday_list(query)

async def _show_bday_list(query):
    uid = query.from_user.id
    with get_conn() as conn:
        rows = conn.execute(
            'SELECT id, name, birth_date FROM birthdays WHERE added_by=?', (uid,)
        ).fetchall()
    if not rows:
        text = "🎂 *No birthdays added yet*"
    else:
        lines = ["🎂 *Birthdays*\n────────────────────"]
        for row in rows:
            lines.append(f"• {escape_md(row['name'])} — {escape_md(row['birth_date'])}")
        lines.append("────────────────────")
        text = '\n'.join(lines)
    await query.edit_message_text(
        text, parse_mode="MarkdownV2",
        reply_markup=birthdays_keyboard()
    )

async def _delete_reminder(query, reminder_id: int):
    uid = query.from_user.id
    with get_conn() as conn:
        row = conn.execute(
            'SELECT * FROM reminders WHERE id=? AND telegram_id=?',
            (reminder_id, uid)
        ).fetchone()
        if not row:
            await query.answer("Not found.")
            return
        conn.execute('DELETE FROM reminders WHERE id=?', (reminder_id,))
    await query.answer("Reminder deleted")
    await _show_reminders(query)

async def _show_reminders(query):
    uid = query.from_user.id
    with get_conn() as conn:
        rows = conn.execute(
            'SELECT id, remind_at, message FROM reminders WHERE telegram_id=? AND sent=0 ORDER BY remind_at',
            (uid,)
        ).fetchall()
    if not rows:
        await query.edit_message_text(
            "⏰ *No upcoming reminders*",
            parse_mode="MarkdownV2"
        )
        return
    reminder_ids = []
    lines = ["⏰ *Your reminders*\n────────────────────"]
    for row in rows:
        dt = datetime.fromisoformat(row['remind_at'])
        label = f"{dt.strftime('%d-%m-%Y %H:%M')} — {row['message'][:20]}"
        reminder_ids.append((row['id'], label))
        lines.append(f"📌 {escape_md(label)}")
    lines.append("────────────────────")
    await query.edit_message_text(
        '\n'.join(lines),
        parse_mode="MarkdownV2",
        reply_markup=reminders_keyboard(reminder_ids)
    )
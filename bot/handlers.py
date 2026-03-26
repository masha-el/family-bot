from telegram import Update
from telegram.ext import ContextTypes
from .database import get_conn
from .calendar_client import get_upcoming_events, add_birthday_event, delete_birthday_event
from datetime import datetime
import traceback
import re, os
import logging

def escape_md(text: str) -> str:
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', str(text))

async def cmd_register(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    # /register <calendar_id><your name>
    args = ctx.args
    if len(args) < 2:
        await update.message.reply_text(
            "⚙️ *Register Your Calendar*\n"
            "────────────────────\n"
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
        "────────────────────\n"
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
    lines = ["\U0001f5d3 *Your next week*\n────────────────────"]
    for e in events:
        start = e['start'].get('dateTime', e['start'].get('date'))
        date_part = start[:10]
        time_part = start[11:16] if 'T' in start else 'All day'
        # convert date to DD-MM-YYYY for display
        d, m, y = date_part[8:], date_part[5:7], date_part[:4]
        display_date = escape_md(f"{d}-{m}-{y}")
        display_time = escape_md(time_part)
        summary = escape_md(e['summary'])

        lines.append(f"📌 *{summary}*\n↳ 🕐 {display_date} {display_time}\n")
        lines.append("────────────────────")
    await update.message.reply_text('\n'.join(lines), parse_mode="MarkdownV2")

async def cmd_remind(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    # /remind DD-MM-YYYY HH:MM <message>
    if len(ctx.args) < 3:
        await update.message.reply_text(
            "⏰ *Set a Reminder*\n"
            "────────────────────\n"
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
    escaped_date = escape_md(f"{d}-{m}-{y}")
    escaped_time = escape_md(ctx.args[1])
    escaped_msg = escape_md(msg)
    await update.message.reply_text(
        "✅ *Reminder set\\!*\n"
        "────────────────────\n"
        f"\U0001f5d3 {escaped_date} at {escaped_time}\n"
        f"💬 {escaped_msg}",
        parse_mode="MarkdownV2"
    )

async def cmd_birthday(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    # /bday add <name> <DD-MM>
    if len(ctx.args) < 3 or ctx.args[0] != 'add':
        await update.message.reply_text(
            "🎂 *Add a Birthday*\n"
            "────────────────────\n"
            "Usage: `/bday add <name> MM\\-DD`\n"
            "_Example: /bday add Masha 03\\-15_",
            parse_mode="MarkdownV2"
        )
        return
    name = ' '.join(ctx.args[1:-1])
    date_str = ctx.args[-1]
    # validation and zero-pad
    parts = date_str.split('-')
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        await update.message.reply_text(
            "❌ *Invalid date format*\n"
            "Use: `DD\\-MM`\n"
            "_Example: /bday add Masha 22\\-03_",
            parse_mode="MarkdownV2"
        )
        return
    day, month = parts[0].zfill(2), parts[1].zfill(2)
    if not (1 <= int(day) <= 31 and 1 <= int(month) <= 12):
        await update.message.reply_text(
            "❌ *Invalid date*\n"
            "Day must be 01\\-31, month must be 01\\-12\\.",
            parse_mode="MarkdownV2"
        )
        return
    date_str = f"{day}-{month}"  # normalized: always DD-MM zero-padded

    # add to the user's Google Calendar if they are registered
    with get_conn() as conn:
        row = conn.execute(
            'SELECT * FROM user_calendars WHERE telegram_id=?',
            (update.effective_user.id,)
        ).fetchone()
    
    cal_status = ""
    calendar_event_id = None
    if row:
        try:
            calendar_event_id = add_birthday_event(row['calendar_id'], name, date_str)
            cal_status = "\n🌐 Added to your Google Calendar"
        except Exception as e:
            logging.error(f"Failed to add birthday to calendar: {e}", exc_info=True)
            cal_status = "\n⚠️ Saved locally but failed to add to Google Calendar"
    
    with get_conn() as conn:
        conn.execute(
           'INSERT INTO birthdays (added_by, name, birth_date, calendar_event_id) VALUES (?,?,?,?)',
           (update.effective_user.id, name, date_str, calendar_event_id) 
        ) 

    escaped_name = escape_md(name)
    d, m = date_str.split('-')
    escaped_date = escape_md(f"{d}-{m}")
    await update.message.reply_text(
        "✅ *Birthday added\\!*\n"
        "────────────────────\n"
        f"🎉 *{escaped_name}*\n"
        f"🔄 Every year on {escaped_date}"
        f"{escape_md(cal_status)}",
        parse_mode="MarkdownV2"
    )

async def  cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (
        "🤖 *Family Bot Commands*\n"
        "────────────────────\n\n"
        "\U0001f5d3 *Calendar*\n"
        "/events — your next 7 days\n\n"
        "⏰ *Reminders*\n"
        "/remind DD\\-MM\\-YYYY HH:MM <message>\n"
        "_Example: `/remind` 25\\-12\\-2025 09:00 Buy gifts_\n\n"
        "🎂 *Birthdays commands:*\n"
        "/bday add <name> MM\\-DD\n"
        "_Example: `/bday` add Masha 01\\-10_\n\n"
        "`/bdays` — see all birthdays you added\n\n"
        "`/bdel` — get numbered lists of added birthdays\n"
        "_Example: use number to delete — `/bdel` 1 or `/bdel` 1 2_\n\n"
        "⚙️ *Setup*\n"
        "⚠️ Don't forget to share your calendar with the Bot Service Account  "
        "/register <calendar\\_id> <your name>\n\n"
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
        "\U0001f5d3 *What I can do:*\n"
        "• Sync with your personal Google Calendar\n"
        "• Send you reminders for events and appointments after you add them\n"
        "• Remind you of family or anyone's birthday\n\n"
        "⚙️ *Getting started:*\n"
        "1\\. Share your Google Calendar with the bot's service account\n"
        "2\\. Run `/register <calendar\\_id> <your name>`\n"
        "3\\. Try `/events` to see your upcoming week events\n"
        "────────────────────\n"
        "Type /help to see all available commands\\."
    )
    await update.message.reply_text(text, parse_mode="MarkdownV2")

async def cmd_birthdays_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    with get_conn() as conn:
        rows = conn.execute(
            'SELECT name, birth_date FROM birthdays WHERE added_by=?',(uid,)
        ).fetchall()
    if not rows:
        await update.message.reply_text(
            "📝 *No birthdays added yet*\n"
            "Use `/bday add <name> DD\\-MM` to add one\\.",
            parse_mode="MarkdownV2"
        )
        return
    lines = ["📝 *Birthdays you added:*\n────────────────────"]
    for row in rows:
        lines.append(f"• {escape_md(row['name'])} — {escape_md(row['birth_date'])}")
    lines.append("────────────────────")
    await update.message.reply_text('\n'.join(lines), parse_mode="MarkdownV2")

async def cmd_birthday_delete(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    #no argument - show numbered list
    if not ctx.args:
        with get_conn() as conn:
            rows = conn.execute(
                'SELECT id, name, birth_date, calendar_event_id FROM birthdays WHERE added_by=?', (uid,)
            ).fetchall()
        if not rows:
            await update.message.reply_text(
                "🎂 *No birthdays to delete*",
                parse_mode="MarkdownV2"
            )
            return
        lines = ["🎂 *Select number\\(s\\) to delete:*\n────────────────────"]
        for i, row in enumerate(rows, start=1):
            lines.append(f"{i}\\. {escape_md(row['name'])} — {escape_md(row['birth_date'])}")
        lines.append("────────────────────")
        lines.append("_Use /bdel 1 or /bdel 1 2 3 to delete multiple_")
        await update.message.reply_text('\n'.join(lines), parse_mode="MarkdownV2")
        return
    
    # validation for args that they are numbers
    if not all(arg.isdigit() for arg in ctx.args):
        await update.message.reply_text(
            "❌ Use numbers only\\. Use `/bdel` to see the list\\.",
            parse_mode="MarkdownV2"
        )
        return
    
    with get_conn() as conn:
        rows = conn.execute(
            'SELECT id, name, birth_date, calendar_event_id FROM birthdays WHERE added_by=?', (uid,)
        ).fetchall()
        # validation that all numbers are in range
        indices = [int(arg) - 1 for arg in ctx.args]
        invalid = [i + 1 for i in indices if i < 0 or i >= len(rows)]
        if invalid:
            invalid_str = escape_md(', '.join(str(n) for n in invalid))
            await update.message.reply_text(
               f"❌ *Invalid number\\(s\\):* {invalid_str}\\. Use `/bdel` to see the list\\.",
                parse_mode="MarkdownV2" 
            )
            return
        # delete all selected bdays
        deleted = []
        for i in sorted(set(indices)):  # sorted() handles duplicate entries
            row = rows[i]
            conn.execute('DELETE FROM birthdays WHERE id=?', (row['id'],))

            # delete from Google Calendar if event id exists
            if row['calendar_event_id']:
                user_row = conn.execute(
                    'SELECT calendar_id FROM user_calendars WHERE telegram_id=?',
                    (uid,)
                ).fetchone()
                if user_row:
                    try:
                        delete_birthday_event(user_row['calendar_id'], row['calendar_event_id'])
                    except Exception as e:
                        logging.error(f"Failed to delete calendar event: {e}", exc_info=True)

            deleted.append(f"🗑️ {escape_md(row['name'])} — {escape_md(row['birth_date'])}")
    lines = ["✅ *Deleted:*\n────────────────────"] + deleted + ["────────────────────"]
    await update.message.reply_text('\n'.join(lines), parse_mode="MarkdownV2")

async def cmd_unknown(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    command = update.message.text.split()[0]
    await update.message.reply_text(
        f"❌ *Unknown command:* `{escape_md(command)}`\n"
        "Use /help to see all available commands\\.",
        parse_mode="MarkdownV2"
    )
from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton

def main_keyboard():
    return ReplyKeyboardMarkup([
        ['🗓️ Events', '⏰ Remind me'],
        ['🎂 Birthdays', '⚙️ Settings']
    ], resize_keyboard=True)

def events_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton('➕ Add birthday', callback_data='bday_add_start'),
        InlineKeyboardButton('🗑️ Delete', callback_data='bday_del_start')
    ]])

def reminders_keyboard(reminder_ids: list):
    rows = []
    for rid, label in reminder_ids:
        rows.append([InlineKeyboardButton(
            f'🗑️ Delete — {label}', callback_data=f'rem_del_{rid}'
        )])
    return InlineKeyboardMarkup(rows)

def registration_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton('✅ Done — link my calendar', callback_data='reg_start')
    ]])

def cancel_keyboard():
    return ReplyKeyboardMarkup([['❌ Cancel']], resize_keyboard=True, one_time_keyboard=True)
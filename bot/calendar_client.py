from googleapiclient.discovery import build # type: ignore
from google.oauth2 import service_account # type: ignore
from datetime import datetime, timedelta, timezone
import os

SCOPES = ['https://www.googleapis.com/auth/calendar']
CREDS_PATH = os.getenv('GOOGLE_CREDENTIALS_PATH', '/app/credentials.json')

def get_service():
    creds = service_account.Credentials.from_service_account_file(
        CREDS_PATH, scopes=SCOPES)
    return build('calendar', 'v3', credentials=creds)

def get_upcoming_events(calendar_id: str, days: int = 7) -> list:
    service = get_service()
    now = datetime.now(timezone.utc)
    time_max = now + timedelta(days=days)
    result = service.events().list(
        calendarId=calendar_id,
        timeMin=now.isoformat(),
        timeMax=time_max.isoformat(),
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    return result.get('items', [])

def add_birthday_event(calendar_id: str, name: str, birth_date: str):
    # birth_date format: DD-MM
    import logging

    service = get_service()
    day, month = birth_date.split('-')
    month = month.zfill(2) # pad 3 -> 03
    day = day.zfill(2)
    current_year = datetime.now().year
    date_formatted = f'{current_year}-{month}-{day}'

    logging.info(f"Creating birthday event: name={name}, date={date_formatted}, calendar={calendar_id}")


    event = {
        'summary': f'🎂 {name}\'s Birthday',
        'start': {
            'date': date_formatted,
            'timeZone': 'Asia/Jerusalem'
        },
        'end': {
            'date': date_formatted,
            'timeZone': 'Asia/Jerusalem'
        },
        'recurrence': ['RRULE:FREQ=YEARLY'],
        'reminders': {
            'useDefault': False,
            'overrides': [
                {'method': 'popup', 'minutes': 1440},  # 1 day before
            ]
        }
    }
    logging.info(f"Event body: {event}")
    service.events().insert(calendarId=calendar_id, body=event).execute()

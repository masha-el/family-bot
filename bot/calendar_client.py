from googleapiclient.discovery import build 
from google.oauth2 import service_account 
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

def add_birthday_event(calendar_id: str, name: str, birth_date: str) -> str:
    # birth_date format: DD-MM
    service = get_service()
    day, month = birth_date.split('-')
    month = month.zfill(2) # pad 3 -> 03
    day = day.zfill(2)
    current_year = datetime.now().year
    date_formatted = f'{current_year}-{month}-{day}'

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
    result = service.events().insert(calendarId=calendar_id, body=event).execute()
    return result.get('id')
    
def delete_birthday_event(calendar_id: str, event_id: str):
    service = get_service()
    service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
from googleapiclient.discovery import build # type: ignore
from google.oauth2 import service_account # type: ignore
from datetime import datetime, timedelta, timezone
import os

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
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
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import os
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/calendar.events']
CREDENTIALS_FILE = 'client_secret.json'
TOKEN_FILE = 'token.json'

def get_calendar_service():
    """Get authenticated Google Calendar service."""
    creds = None
    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        except Exception as e:
            logger.error(f"Error loading token.json: {e}")
            os.remove(TOKEN_FILE)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                logger.error(f"Error refreshing token: {e}")
                os.remove(TOKEN_FILE)
                creds = None
        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
    return build('calendar', 'v3', credentials=creds)

def get_auth_url():
    """Get OAuth authorization URL."""
    try:
        if not os.path.exists(CREDENTIALS_FILE):
            raise FileNotFoundError(f"{CREDENTIALS_FILE} not found")
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
        flow.redirect_uri = 'http://localhost:5000/oauth2callback'
        auth_url, _ = flow.authorization_url(prompt='consent')
        logger.info(f"Generated auth URL: {auth_url}")
        return auth_url
    except Exception as e:
        logger.error(f"Error generating auth URL: {e}")
        raise

def handle_oauth_callback(authorization_response):
    """Handle OAuth callback."""
    try:
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
        flow.redirect_uri = 'http://localhost:5000/oauth2callback'
        flow.fetch_token(authorization_response=authorization_response)
        creds = flow.credential
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
    except Exception as e:
        logger.error(f"Error handling OAuth callback: {e}")
        raise

def create_calendar_event(event_summary):
    """Create a Google Calendar event."""
    try:
        service = get_calendar_service()
        event_time = datetime.now() + timedelta(days=1)
        event = {
            'summary': f'Prepare slides for {event_summary}',
            'description': 'Create presentation slides for the meeting.',
            'start': {'dateTime': event_time.isoformat(), 'timeZone': 'UTC'},
            'end': {'dateTime': (event_time + timedelta(hours=1)).isoformat(), 'timeZone': 'UTC'}
        }
        event_result = service.events().insert(calendarId='primary', body=event).execute()
        logger.info(f"Created Google Calendar event: {event_result.get('htmlLink')}")
        return {"action": "Scheduled meeting", "details": {"event_id": event_result.get('id'), "link": event_result.get('htmlLink')}}
    except Exception as e:
        logger.error(f"Error creating calendar event: {e}")
        raise
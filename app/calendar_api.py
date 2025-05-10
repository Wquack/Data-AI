from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import os
import logging
from datetime import datetime, timedelta, date
from googleapiclient.errors import HttpError

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
            logger.info("Loaded credentials from token.json")
        except Exception as e:
            logger.error(f"Error loading token.json: {e}")
            os.remove(TOKEN_FILE)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                logger.info("Refreshed credentials")
            except Exception as e:
                logger.error(f"Error refreshing token: {e}")
                os.remove(TOKEN_FILE)
                creds = None
        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
            logger.info("Authenticated via OAuth flow")
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
            logger.info("Saved credentials to token.json")
    return build('calendar', 'v3', credentials=creds)

def get_auth_url():
    """Get OAuth authorization URL."""
    try:
        if not os.path.exists(CREDENTIALS_FILE):
            raise FileNotFoundError(f"{CREDENTIALS_FILE} not found")
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
        flow.redirect_uri = 'http://localhost:5000/oauth2callback'
        auth_url, state = flow.authorization_url(prompt='consent', access_type='offline')
        logger.info(f"Generated auth URL: {auth_url}")
        return auth_url
    except Exception as e:
        logger.error(f"Error generating auth URL: {e}")
        raise

def handle_oauth_callback(authorization_response):
    """Handle OAuth callback."""
    try:
        if authorization_response.startswith('http://'):
            authorization_response = 'https://' + authorization_response[len('http://'):]
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
        flow.redirect_uri = 'http://localhost:5000/oauth2callback'
        logger.info(f"Handling OAuth callback with response: {authorization_response}")
        flow.fetch_token(authorization_response=authorization_response)
        creds = flow.credentials
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
        logger.info("OAuth callback successful, saved token.json")
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

def list_calendar_events():
    """List today's events from Google Calendar."""
    try:
        service = get_calendar_service()
        # Define the time range for today
        today = date.today()
        time_min = datetime.combine(today, datetime.min.time()).isoformat() + 'Z'
        time_max = datetime.combine(today, datetime.max.time()).isoformat() + 'Z'

        events_result = service.events().list(
            calendarId='primary',
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])
        event_list = []
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            summary = event.get('summary', 'No title')
            event_list.append({
                "id": event['id'],
                "summary": summary,
                "start": start,
                "link": event.get('htmlLink', '')
            })
        logger.info(f"Retrieved {len(event_list)} events for today")
        return event_list
    except HttpError as e:
        logger.error(f"Error fetching calendar events: {e}")
        raise
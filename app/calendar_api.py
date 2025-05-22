from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from googleapiclient.http import MediaFileUpload
import os
import logging
from datetime import datetime, timedelta, date
from googleapiclient.errors import HttpError
import base64
from email.mime.text import MIMEText
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

# Updated scopes to include Gmail access
SCOPES = [
    'https://www.googleapis.com/auth/calendar.events',
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/drive.file',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/userinfo.email',
    'openid'
]
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

def get_drive_service():
    """Get authenticated Google Drive service."""
    creds = None
    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
            logger.info("Loaded credentials from token.json for Drive")
        except Exception as e:
            logger.error(f"Error loading token.json for Drive: {e}")
            os.remove(TOKEN_FILE)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                logger.info("Refreshed credentials for Drive")
            except Exception as e:
                logger.error(f"Error refreshing token for Drive: {e}")
                os.remove(TOKEN_FILE)
                creds = None
        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
            logger.info("Authenticated via OAuth flow for Drive")
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
            logger.info("Saved credentials to token.json for Drive")
    return build('drive', 'v3', credentials=creds)

def get_gmail_service():
    """Get authenticated Gmail service."""
    creds = None
    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
            logger.info("Loaded credentials from token.json for Gmail")
        except Exception as e:
            logger.error(f"Error loading token.json for Gmail: {e}")
            os.remove(TOKEN_FILE)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                logger.info("Refreshed credentials for Gmail")
            except Exception as e:
                logger.error(f"Error refreshing token for Gmail: {e}")
                os.remove(TOKEN_FILE)
                creds = None
        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
            logger.info("Authenticated via OAuth flow for Gmail")
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
            logger.info("Saved credentials to token.json for Gmail")
    return build('gmail', 'v1', credentials=creds)

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
    try:
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
        flow.redirect_uri = 'http://localhost:5000/oauth2callback'
        flow.fetch_token(authorization_response=authorization_response)
        creds = flow.credentials

        # Save to token.json
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())

        # 🔍 Get user email using People API or Profile API
        service = build('oauth2', 'v2', credentials=creds)
        user_info = service.userinfo().get().execute()
        user_email = user_info.get("email", "unknown@example.com")

        return user_email
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

def upload_to_drive(file_path, file_name):
    """Upload a file to Google Drive and return a shareable link."""
    try:
        service = get_drive_service()
        file_metadata = {
            'name': file_name,
            'mimeType': 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
        }
        media = MediaFileUpload(file_path, mimetype='application/vnd.openxmlformats-officedocument.presentationml.presentation')
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink'
        ).execute()
        # Make the file shareable (retry on failure)
        try:
            service.permissions().create(
                fileId=file['id'],
                body={'type': 'anyone', 'role': 'reader'},
                fields='id'
            ).execute()
        except HttpError as e:
            logger.error(f"Failed to set sharing permissions: {e}")
            # Fallback: Set permissions using update (sometimes more reliable)
            service.permissions().update(
                fileId=file['id'],
                permissionId='anyoneWithLink',
                body={'type': 'anyone', 'role': 'reader'},
                fields='id'
            ).execute()
        logger.info(f"Uploaded file to Google Drive: {file.get('webViewLink')}")
        return file.get('webViewLink')
    except Exception as e:
        logger.error(f"Error uploading file to Google Drive: {e}")
        raise

def send_gmail(to, subject, body):
    """Send an email using the Gmail API."""
    try:
        service = get_gmail_service()
        message = MIMEText(body)
        message['to'] = to
        message['subject'] = subject
        message['from'] = 'me'
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        message = {'raw': raw_message}
        sent_message = service.users().messages().send(userId='me', body=message).execute()
        logger.info(f"Sent email via Gmail API: {sent_message['id']}")
        return {"action": "Email sent", "details": {"message_id": sent_message['id']}}
    except Exception as e:
        logger.error(f"Error sending email via Gmail API: {e}")
        raise

def create_calendar_event_with_zoom(topic, start_time, duration, zoom_link, user_id):
    try:
        # Load credentials from token.json or user store
        creds = Credentials.from_authorized_user_file("token.json")  # 🔁 Replace with DB-based loading if needed
        service = build("calendar", "v3", credentials=creds)

        # Parse start_time
        start_dt = datetime.fromisoformat(start_time)
        end_dt = start_dt + timedelta(minutes=duration)

        event = {
            "summary": topic,
            "description": f"Zoom Link: {zoom_link}",
            "start": {
                "dateTime": start_dt.isoformat(),
                "timeZone": "Asia/Kolkata"
            },
            "end": {
                "dateTime": end_dt.isoformat(),
                "timeZone": "Asia/Kolkata"
            }
        }

        created_event = service.events().insert(calendarId="primary", body=event).execute()
        return {
            "event_id": created_event["id"],
            "html_link": created_event["htmlLink"]
        }

    except Exception as e:
        raise Exception(f"Error creating Google Calendar event: {e}")


def list_calendar_events(start_date=None, end_date=None, event_type=None, attendees=None):
    """List events within a date range from Google Calendar with optional filters."""
    try:
        service = get_calendar_service()
        # Define the time range
        if start_date:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
        else:
            start = date.today()
        if end_date:
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
        else:
            end = start + timedelta(days=30)  # Default to 30 days from start date

        time_min = datetime.combine(start, datetime.min.time()).isoformat() + 'Z'
        time_max = datetime.combine(end, datetime.max.time()).isoformat() + 'Z'

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
            description = event.get('description', '')

            # Filter by event type (keyword in summary or description)
            if event_type:
                event_type_lower = event_type.lower()
                if not (summary.lower().find(event_type_lower) != -1 or (description and description.lower().find(event_type_lower) != -1)):
                    continue

            # Filter by attendees
            if attendees:
                attendee_emails = [attendee.get('email', '').lower() for attendee in event.get('attendees', [])]
                attendees_lower = [attendee.lower() for attendee in attendees.split(',')]
                if not any(attendee in attendee_emails for attendee in attendees_lower):
                    continue

            event_list.append({
                "id": event['id'],
                "summary": summary,
                "start": start,
                "link": event.get('htmlLink', '')
            })

        logger.info(f"Retrieved {len(event_list)} events from {start} to {end} with filters event_type={event_type}, attendees={attendees}")
        return event_list
    except HttpError as e:
        logger.error(f"Error fetching calendar events: {e}")
        raise
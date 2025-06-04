from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import os
import logging
from datetime import datetime, timedelta, date
from googleapiclient.errors import HttpError
import base64
from email.mime.text import MIMEText
from utils.token_store import load_tokens, save_tokens

logger = logging.getLogger(__name__)

# Updated scopes to include Gmail access
SCOPES = [
    'https://www.googleapis.com/auth/calendar.events',
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/drive.file',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.readonly',  # ← Add this for reading messages
    'https://www.googleapis.com/auth/userinfo.email',
    'openid'
]

# In app/calendar_api.py - Replace your get_calendar_service function

# In app/calendar_api.py - Replace your get_calendar_service function

# Replace get_calendar_service in app/calendar_api.py with this working version:

# Replace your get_calendar_service() function in app/calendar_api.py with this:

def get_calendar_service(user_id):
    """Get authenticated Google Calendar service."""
    tokens = load_tokens(user_id)
    google_tokens = tokens.get("google", {})
    
    if not google_tokens or "access_token" not in google_tokens:
        raise Exception("Google authentication required. Please authenticate via /auth/google")
    
    # ✅ CRITICAL FIX: Get OAuth credentials from environment
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        logger.error(f"Missing Google OAuth credentials - client_id: {bool(client_id)}, client_secret: {bool(client_secret)}")
        raise Exception("Google OAuth credentials not configured. Please check GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables.")
    
    logger.info(f"Creating Google credentials for user {user_id}")
    
    # ✅ CRITICAL FIX: Create credentials with ALL required fields
    creds = Credentials(
        token=google_tokens["access_token"],
        refresh_token=google_tokens.get("refresh_token"),  # This might be None - that's okay for now
        token_uri="https://oauth2.googleapis.com/token",   # ← REQUIRED
        client_id=client_id,                               # ← REQUIRED  
        client_secret=client_secret,                       # ← REQUIRED
        scopes=SCOPES
    )
    
    # Check if credentials are valid
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            try:
                logger.info(f"Refreshing Google credentials for user {user_id}")
                creds.refresh(Request())
                
                # Save refreshed tokens
                refreshed_tokens = {
                    "access_token": creds.token,
                    "refresh_token": creds.refresh_token,
                }
                
                if creds.expiry:
                    refreshed_tokens["expires_at"] = creds.expiry.isoformat()
                
                save_tokens(user_id, {"google": refreshed_tokens})
                logger.info(f"Successfully refreshed Google credentials for user {user_id}")
                
            except Exception as e:
                logger.error(f"Failed to refresh Google token for user {user_id}: {e}")
                raise Exception(f"Google token expired and refresh failed. Please re-authenticate via /auth/google")
        else:
            logger.warning(f"Google token expired and no refresh token available for user {user_id}")
            raise Exception("Google token expired. Please re-authenticate via /auth/google")
    
    try:
        service = build('calendar', 'v3', credentials=creds)
        logger.info(f"Successfully created Google Calendar service for user {user_id}")
        return service
    except Exception as e:
        logger.error(f"Failed to build Google Calendar service for user {user_id}: {e}")
        raise Exception(f"Failed to create Google Calendar service: {str(e)}")
    
def get_drive_service(user_id):
    """Get authenticated Google Drive service."""
    tokens = load_tokens(user_id)
    google_tokens = tokens.get("google", {})
    
    if not google_tokens or "access_token" not in google_tokens:
        raise Exception("Google authentication required. Please authenticate via /auth/google")
    
    # Get required OAuth credentials from environment
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        raise Exception("Google OAuth credentials not configured in environment")
    
    # Create credentials with all required fields
    creds = Credentials(
        token=google_tokens["access_token"],
        refresh_token=google_tokens.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES
    )
    
    # Check if credentials are valid or need refresh
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            try:
                logger.info(f"Refreshing Google credentials for Drive for user {user_id}")
                creds.refresh(Request())
                
                # Save the refreshed tokens back to storage
                refreshed_tokens = {
                    "access_token": creds.token,
                    "refresh_token": creds.refresh_token,
                }
                
                if creds.expiry:
                    refreshed_tokens["expires_at"] = creds.expiry.isoformat()
                
                save_tokens(user_id, {"google": refreshed_tokens})
                logger.info(f"Successfully refreshed and saved Google credentials for Drive for user {user_id}")
                
            except Exception as e:
                logger.error(f"Failed to refresh Google token for Drive for user {user_id}: {e}")
                raise Exception(f"Failed to refresh Google token. Please re-authenticate via /auth/google. Error: {str(e)}")
        else:
            logger.error(f"Google credentials invalid and no refresh token available for Drive for user {user_id}")
            raise Exception("Google credentials expired and no refresh token available. Please re-authenticate via /auth/google")
    
    try:
        service = build('drive', 'v3', credentials=creds)
        logger.info(f"Successfully created Google Drive service for user {user_id}")
        return service
    except Exception as e:
        logger.error(f"Failed to build Google Drive service for user {user_id}: {e}")
        raise Exception(f"Failed to create Google Drive service: {str(e)}")

def get_gmail_service(user_id):
    """Get authenticated Gmail service."""
    tokens = load_tokens(user_id)
    google_tokens = tokens.get("google", {})
    
    if not google_tokens or "access_token" not in google_tokens:
        raise Exception("Google authentication required. Please authenticate via /auth/google")
    
    # Get required OAuth credentials from environment
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        raise Exception("Google OAuth credentials not configured in environment")
    
    # Create credentials with all required fields
    creds = Credentials(
        token=google_tokens["access_token"],
        refresh_token=google_tokens.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES
    )
    
    # Check if credentials are valid or need refresh
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            try:
                logger.info(f"Refreshing Google credentials for Gmail for user {user_id}")
                creds.refresh(Request())
                
                # Save the refreshed tokens back to storage
                refreshed_tokens = {
                    "access_token": creds.token,
                    "refresh_token": creds.refresh_token,
                }
                
                if creds.expiry:
                    refreshed_tokens["expires_at"] = creds.expiry.isoformat()
                
                save_tokens(user_id, {"google": refreshed_tokens})
                logger.info(f"Successfully refreshed and saved Google credentials for Gmail for user {user_id}")
                
            except Exception as e:
                logger.error(f"Failed to refresh Google token for Gmail for user {user_id}: {e}")
                raise Exception(f"Failed to refresh Google token. Please re-authenticate via /auth/google. Error: {str(e)}")
        else:
            logger.error(f"Google credentials invalid and no refresh token available for Gmail for user {user_id}")
            raise Exception("Google credentials expired and no refresh token available. Please re-authenticate via /auth/google")
    
    try:
        service = build('gmail', 'v1', credentials=creds)
        logger.info(f"Successfully created Gmail service for user {user_id}")
        return service
    except Exception as e:
        logger.error(f"Failed to build Gmail service for user {user_id}: {e}")
        raise Exception(f"Failed to create Gmail service: {str(e)}")

def get_auth_url():
    """Get OAuth authorization URL."""
    # This function is no longer needed since /auth/google handles the OAuth flow
    raise NotImplementedError("Use /auth/google endpoint for Google OAuth flow")

def handle_oauth_callback(authorization_response):
    """Handle OAuth callback."""
    # This function is no longer needed since /auth/google/callback handles the OAuth flow
    raise NotImplementedError("Use /auth/google/callback endpoint for Google OAuth callback")

def create_calendar_event(event_summary, user_id):
    """Create a Google Calendar event."""
    try:
        service = get_calendar_service(user_id)
        event_time = datetime.now() + timedelta(days=1)
        event = {
            'summary': f'Prepare slides for {event_summary}',
            'description': 'Create presentation slides for the meeting.',
            'start': {'dateTime': event_time.isoformat(), 'timeZone': 'UTC'},
            'end': {'dateTime': (event_time + timedelta(hours=1)).isoformat(), 'timeZone': 'UTC'}
        }
        event_result = service.events().insert(calendarId='primary', body=event).execute()
        logger.info(f"Created Google Calendar event for user {user_id}: {event_result.get('htmlLink')}")
        return {"action": "Scheduled meeting", "details": {"event_id": event_result.get('id'), "link": event_result.get('htmlLink')}}
    except Exception as e:
        logger.error(f"Error creating calendar event for user {user_id}: {e}")
        raise

def upload_to_drive(file_path, file_name, user_id):
    """Upload a file to Google Drive and return a shareable link."""
    try:
        service = get_drive_service(user_id)
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
            logger.error(f"Failed to set sharing permissions for user {user_id}: {e}")
            # Fallback: Set permissions using update (sometimes more reliable)
            service.permissions().update(
                fileId=file['id'],
                permissionId='anyoneWithLink',
                body={'type': 'anyone', 'role': 'reader'},
                fields='id'
            ).execute()
        logger.info(f"Uploaded file to Google Drive for user {user_id}: {file.get('webViewLink')}")
        return file.get('webViewLink')
    except Exception as e:
        logger.error(f"Error uploading file to Google Drive for user {user_id}: {e}")
        raise

def send_gmail(to, subject, body, user_id):
    """Send an email using the Gmail API."""
    try:
        service = get_gmail_service(user_id)
        message = MIMEText(body)
        message['to'] = to
        message['subject'] = subject
        message['from'] = 'me'
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        message = {'raw': raw_message}
        sent_message = service.users().messages().send(userId='me', body=message).execute()
        logger.info(f"Sent email via Gmail API for user {user_id}: {sent_message['id']}")
        return {"action": "Email sent", "details": {"message_id": sent_message['id']}}
    except Exception as e:
        logger.error(f"Error sending email via Gmail API for user {user_id}: {e}")
        raise

def create_calendar_event_with_zoom(topic, start_time, duration, zoom_link, user_id):
    try:
        service = get_calendar_service(user_id)
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
        logger.info(f"Created Google Calendar event with Zoom link for user {user_id}: {created_event['htmlLink']}")
        return {
            "event_id": created_event["id"],
            "html_link": created_event["htmlLink"]
        }
    except Exception as e:
        logger.error(f"Error creating Google Calendar event for user {user_id}: {e}")
        raise

def list_calendar_events(user_id, start_date=None, end_date=None, event_type=None, attendees=None):
    """List events within a date range from Google Calendar with optional filters."""
    try:
        service = get_calendar_service(user_id)
        if start_date:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
        else:
            start = date.today()
        if end_date:
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
        else:
            end = start + timedelta(days=30)

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

            if event_type:
                event_type_lower = event_type.lower()
                if not (summary.lower().find(event_type_lower) != -1 or (description and description.lower().find(event_type_lower) != -1)):
                    continue

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

        logger.info(f"Retrieved {len(event_list)} events for user {user_id} from {start} to {end} with filters event_type={event_type}, attendees={attendees}")
        return event_list
    except Exception as e:
        logger.error(f"Error fetching calendar events for user {user_id}: {e}")
        raise

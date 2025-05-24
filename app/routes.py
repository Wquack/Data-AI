import sys
import requests
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
import mimetypes
from .recommendation import get_recommendation, process_user_message, chat_with_distilbert
from .calendar_api import create_calendar_event, get_auth_url, handle_oauth_callback, list_calendar_events, get_calendar_service, get_drive_service, upload_to_drive, send_gmail, create_calendar_event_with_zoom
from .encryption import encrypt_data
from .slack_oauth import get_slack_auth_url, handle_slack_callback, post_to_slack
from .zoom_oauth import get_zoom_auth_url, handle_zoom_callback, refresh_zoom_token
from utils.jwt_utils import generate_state_token, decode_state_token
from .notion_api import create_notion_page, list_notion_pages
from .powerpoint_api import create_powerpoint_slides
import logging
from utils.token_store import load_tokens
from datetime import date, datetime, timedelta
from urllib.parse import urlencode

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/ping")
def ping():
    return {"message": "pong"}

async def recommend_task_logic(request: Request):
    try:
        data = await request.json()
        if not data:
            logger.warning("No data received")
            raise HTTPException(status_code=400, detail='No data provided')
        event_summary = data.get('event_summary', '')
        if not isinstance(event_summary, str) or not event_summary.strip():
            logger.warning("Invalid event summary")
            raise HTTPException(status_code=400, detail='Event summary must be a non-empty string')

        logger.info(f"Received event summary: {event_summary}")
        encrypted_summary = encrypt_data(event_summary)
        logger.info("Input encrypted")

        recommendation = get_recommendation(event_summary)
        return {'recommendation': recommendation}
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post('/recommend')
async def recommend_task(request: Request):
    return await recommend_task_logic(request)

async def chat_endpoint_logic(request: Request):
    try:
        data = await request.json()
        if not data:
            logger.warning("No data received")
            raise HTTPException(status_code=400, detail='No data provided')
        message = data.get('message', '')
        if not isinstance(message, str) or not message.strip():
            logger.warning("Invalid message")
            raise HTTPException(status_code=400, detail='Message must be a non-empty string')

        logger.info(f"Received user message: {message}")
        result = process_user_message(message)
        logger.info(f"Chat endpoint response: {result}")
        return result
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post('/chat')
async def chat_endpoint(request: Request):
    return await chat_endpoint_logic(request)

async def chat_with_distilbert_endpoint_logic(request: Request):
    try:
        data = await request.json()
        if not data:
            logger.warning("No data received")
            raise HTTPException(status_code=400, detail='No data provided')
        message = data.get('message', '')
        if not isinstance(message, str) or not message.strip():
            logger.warning("Invalid message")
            raise HTTPException(status_code=400, detail='Message must be a non-empty string')

        logger.info(f"Received user message for DistilBERT: {message}")
        result = chat_with_distilbert(message)
        logger.info(f"DistilBERT response: {result}")
        return result
    except Exception as e:
        logger.error(f"Error in chat_with_distilbert endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post('/chat_with_distilbert')
async def chat_with_distilbert_endpoint(request: Request):
    return await chat_with_distilbert_endpoint_logic(request)

def create_zoom_meeting_logic(data, user_id):
    topic = data.get('topic', 'AI Meeting')
    start_time = data.get('start_time')  # ISO 8601 format: "2025-05-21T15:00:00"
    duration = data.get('duration', 30)  # in minutes

    if not user_id:
        raise HTTPException(status_code=400, detail="Missing X-User-ID")

    tokens = load_tokens(user_id)
    if not tokens:
        raise HTTPException(status_code=401, detail="Tokens not found for this user")
    access_token = tokens.get("zoom", {}).get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="Zoom token not found for this user")

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    meeting_data = {
        "topic": topic,
        "type": 2,  # Scheduled meeting
        "start_time": start_time,
        "duration": duration,
        "timezone": "Asia/Kolkata",
        "settings": {
            "join_before_host": True,
            "waiting_room": False
        }
    }

    # First attempt to create the meeting
    response = requests.post(
        "https://api.zoom.us/v2/users/me/meetings",
        headers=headers,
        json=meeting_data
    )

    # 🔁 If token is expired, refresh_zoom_token and retry once
    if response.status_code == 401 and response.json().get("code") == 124:
        access_token = refresh_zoom_token(user_id)
        headers["Authorization"] = f"Bearer {access_token}"
        response = requests.post(
            "https://api.zoom.us/v2/users/me/meetings",
            headers=headers,
            json=meeting_data
        )

    if response.status_code != 201:
        raise HTTPException(status_code=500, detail={"error": "Zoom API error", "details": response.json()})

    result = response.json()
    return {
        "message": "Meeting created",
        "zoom_link": result["join_url"],
        "meeting_id": result["id"],
        "start_time": result["start_time"]
    }

@router.post('/create_zoom_meeting')
async def create_zoom_meeting(request: Request):
    try:
        data = await request.json()
        user_id = request.headers.get("X-User-ID")
        return create_zoom_meeting_logic(data, user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def list_notion_pages_endpoint_logic():
    try:
        pages = list_notion_pages()
        return {'pages': pages}
    except Exception as e:
        logger.error(f"Error listing Notion pages: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get('/list_notion_pages')
async def list_notion_pages_endpoint():
    return await list_notion_pages_endpoint_logic()

async def list_calendar_events_endpoint_logic(request: Request):
    try:
        if not os.path.exists('token.json'):
            try:
                auth_url = get_auth_url()
                raise HTTPException(status_code=401, detail={'action': 'Requires authentication', 'auth_url': auth_url})
            except Exception as e:
                logger.error(f"Failed to generate auth URL: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to initiate authentication: {str(e)}")

        start_date = end_date = event_type = attendees = date_param = None

        if request.method == 'GET':
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date')
            event_type = request.query_params.get('event_type')
            attendees = request.query_params.get('attendees')
            date_param = request.query_params.get('date')
        else:
            data = await request.json()
            start_date = data.get('start_date', request.query_params.get('start_date'))
            end_date = data.get('end_date', request.query_params.get('end_date'))
            event_type = data.get('event_type', request.query_params.get('event_type'))
            attendees = data.get('attendees', request.query_params.get('attendees'))
            date_param = data.get('date', request.query_params.get('date'))

        if not start_date and date_param:
            start_date = end_date = date_param

        events = list_calendar_events(start_date, end_date, event_type, attendees)
        return {'events': events}
    except Exception as e:
        logger.error(f"Error listing calendar events: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get('/list_calendar_events')
@router.post('/list_calendar_events')
async def list_calendar_events_endpoint(request: Request):
    return await list_calendar_events_endpoint_logic(request)

async def execute_task_endpoint_logic(request: Request):
    try:
        data = await request.json()
        action = data.get('action', '') # type: ignore
        event_summary = data.get('event_summary', '') or data.get('topic', 'AI Meeting')   # type: ignore[attr-defined]
        parent_page_id = data.get('parent_page_id') # type: ignore[attr-defined]
        recipient = data.get('recipient', '') # type: ignore[attr-defined]
        slack_channel = data.get('slack_channel') # type: ignore[attr-defined]
        start_time = data.get('start_time')  # "2025-05-21T15:00:00" # type: ignore[attr-defined]
        duration = data.get('duration', 30) # type: ignore[attr-defined]
        user_id = request.headers.get("X-User-ID")

        if not user_id:
            raise HTTPException(status_code=400, detail="Missing X-User-ID")
        if not action.strip() or not event_summary.strip():
            raise HTTPException(status_code=400, detail='Action and event summary must be non-empty strings')

        logger.info(f"Executing action: {action} for user: {user_id}")

        # === 🔹 Setup full Zoom meeting + Calendar ===
        if action == "Setup full Zoom meeting":
            # Zoom meeting
            tokens = load_tokens(user_id)
            if not tokens:
                raise HTTPException(status_code=401, detail="Tokens not found")
            access_token = tokens.get("zoom", {}).get("access_token")
            if not access_token:
                raise HTTPException(status_code=401, detail="Zoom token not found")

            meeting_payload = {
                "topic": event_summary,
                "type": 2,
                "start_time": start_time,
                "duration": duration,
                "timezone": "Asia/Kolkata",
                "settings": {
                    "join_before_host": True,
                    "waiting_room": False
                }
            }

            if not access_token:
                raise HTTPException(status_code=401, detail="Access token is missing")

            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }

            if not meeting_payload:
                raise HTTPException(status_code=400, detail="Meeting payload is missing")

            zoom_response = requests.post(
                "https://api.zoom.us/v2/users/me/meetings",
                headers=headers,
                json=meeting_payload
            )

            if zoom_response.status_code == 401 and zoom_response.json().get("code") == 124:
                access_token = refresh_zoom_token(user_id)
                headers["Authorization"] = f"Bearer {access_token}"
                zoom_response = requests.post(
                    "https://api.zoom.us/v2/users/me/meetings",
                    headers=headers,
                    json=meeting_payload
                )

            if zoom_response.status_code != 201:
                raise HTTPException(status_code=500, detail={"error": "Zoom API error", "details": zoom_response.json()})

            zoom_data = zoom_response.json()
            zoom_link = zoom_data["join_url"]

            calendar_result = create_calendar_event_with_zoom(
                topic=event_summary,
                start_time=start_time,
                duration=duration,
                zoom_link=zoom_link,
                user_id=user_id
            )

            return {
                "message": "Zoom + Calendar setup complete",
                "zoom_link": zoom_link,
                "calendar_event": calendar_result
            }

        # === 📊 Prepare slides workflow ===
        elif action == "Prepare slides":
            if not os.path.exists('token.json'):
                raise HTTPException(status_code=401, detail={'action': 'Requires authentication', 'auth_url': get_auth_url()})

            calendar_result = create_calendar_event(event_summary)
            ppt_result = create_powerpoint_slides(event_summary)
            drive_link = upload_to_drive(ppt_result["details"]["file_path"], f"slides_{event_summary}.pptx")
            notion_result = create_notion_page(f"Slides for {event_summary}", parent_page_id, drive_link=drive_link)
            notion_result["details"]["slides_drive_link"] = drive_link

            service = get_calendar_service()
            event_id = calendar_result["details"]["event_id"]
            event = service.events().get(calendarId='primary', eventId=event_id).execute()
            event['description'] = (event.get('description', '') +
                                    f"\n\nGoogle Drive Link: {drive_link}\nNotion Page: {notion_result['details']['url']}")
            service.events().update(calendarId='primary', eventId=event_id, body=event).execute()

            return {
                "action": "Completed multiple tasks",
                "details": {
                    "calendar": calendar_result["details"],
                    "drive_link": drive_link,
                    "notion": notion_result["details"]
                }
            }

        # === 📒 Notion note creation ===
        elif action == "Write important notes in Notion":
            zoom_link = data.get("zoom_link")
            calendar_link = data.get("calendar_link")

            extra_text = ""
            if zoom_link:
                extra_text += f"Zoom Meeting: {zoom_link}\n"
            if calendar_link:
                extra_text += f"Google Calendar: {calendar_link}\n"

            notion_result = create_notion_page(
            event_summary,
            parent_page_id=parent_page_id,
            extra_text=extra_text if extra_text else None
)

            return {
                "message": "Notion page created",
                "redirect_url": notion_result["details"]["url"]
            }

        # === 📩 Gmail meeting email ===
        elif action == "Write up an email for the meeting to a colleague":
            zoom_link = data.get("zoom_link")
            calendar_link = data.get("calendar_link")

            subject = f"Meeting: {event_summary}"
            body = f"Hi,\n\nI wanted to discuss our meeting scheduled for {event_summary}..."

            if zoom_link:
                body += f"\n\nZoom Link: {zoom_link}"
            if calendar_link:
                body += f"\nCalendar Event: {calendar_link}"

            body += "\n\nBest,\n[Your Name]"

            if not recipient:
                # Redirect to Gmail compose with prefilled content
                email_url = f"https://mail.google.com/mail/?view=cm&fs=1&{urlencode({'to': '', 'subject': subject, 'body': body})}"
                return {"action": "Redirect to Gmail", "redirect_url": email_url}
            else:
                # Send email via Gmail API
                return send_gmail(recipient, subject, body)


        # === 📅 Follow-up meeting (Google Calendar) ===
        elif action == "Send an email to discuss concerns":
            subject = f"Concerns about {event_summary}"
            body = (
                f"Hi,\n\nI wanted to discuss some concerns I have about {event_summary}.\n"
                "Could we set up a time to talk?\n\nBest,\n[Your Name]"
            )

            if not recipient:
                email_url = f"https://mail.google.com/mail/?view=cm&fs=1&{urlencode({'to': '', 'subject': subject, 'body': body})}"
                return {"action": "Redirect to Gmail", "redirect_url": email_url}
            else:
                return send_gmail(recipient, subject, body)


        # === 📬 Slack notification ===
        elif action == "Plan schedule":
            result = post_to_slack(f"Planning schedule for {event_summary}.", user_id=user_id)
            return result

        else:
            return {"action": "No action taken", "details": {}}

    except Exception as e:
        logger.error(f"Error in execute_task: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post('/execute_task')
async def execute_task_endpoint(request: Request):
    return await execute_task_endpoint_logic(request)

@router.get('/download_slides/{filename}')
async def download_slides(filename: str):
    try:
        directory = os.path.join(os.getcwd(), "presentations")
        mimetype_guess = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        return FileResponse(path=os.path.join(directory, filename), media_type=mimetype_guess, filename=filename)
    except Exception as e:
        logger.error(f"Error downloading slides: {e}")
        raise HTTPException(status_code=404, detail=str(e))

@router.get('/oauth2callback')
async def oauth2callback(request: Request):
    try:
        # Extract the full URL from the request
        full_url = str(request.url)
        user_email = handle_oauth_callback(full_url)
        # For now, show the email (in production, store in session or JWT)
        return {"message": "Google authenticated", "email": user_email}
    except Exception as e:
        logger.error(f"Error in OAuth callback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/auth/slack/callback")
async def auth_slack_callback(request: Request):
    code = request.query_params.get("code")
    user_id = request.headers.get("X-User-ID")

    if not code or not user_id:
        raise HTTPException(status_code=400, detail="Missing authorization code or user ID")

    if user_id is None:
        raise HTTPException(status_code=400, detail="Missing user ID")

    if code and user_id:
        try:
            token_data = handle_slack_callback(code, user_id)  # 👈 pass to backend logic
            return {"message": "Slack authenticated successfully", "details": token_data}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    else:
        raise HTTPException(status_code=400, detail="Missing authorization code or user ID")
    


@router.get("/auth/zoom")
async def auth_zoom(request: Request):
    user_id = request.headers.get("X-User-ID")
    if not user_id:
        raise HTTPException(status_code=400, detail="Missing X-User-ID")

    # 🔐 Generate secure state token (JWT)
    state_token = generate_state_token(user_id)

    # 🔁 Pass tokenized state to Zoom
    return redirect(get_zoom_auth_url() + f"&state={state_token}")


@router.get("/auth/zoom/callback")
async def auth_zoom_callback(request: Request):
    code = request.query_params.get("code")
    state_token = request.query_params.get("state")
    if not code or not state_token:
        raise HTTPException(status_code=400, detail="Missing code or state token")
    try:
        data = decode_state_token(state_token)
        user_id = data["user_id"]
        tokens = handle_zoom_callback(code, user_id)
        return {"message": "Zoom authenticated", "tokens": tokens}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

import sys
import requests
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse as redirect
import mimetypes
from .recommendation import get_recommendation, process_user_message, chat_with_distilbert
from .calendar_api import create_calendar_event, list_calendar_events, upload_to_drive, send_gmail, create_calendar_event_with_zoom
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
from fastapi import Depends
from auth.auth_routes import get_current_user
from pydantic import BaseModel
from typing import List
from fastapi import Body
from sqlalchemy.orm import Session
from models.user import User
from utils.db import get_db

class ChatMessage(BaseModel):
    message: str

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
        logger.error(f"Error processing recommend task request: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")

@router.post('/recommend')
async def recommend_task(request: Request):
    return await recommend_task_logic(request)

async def chat_endpoint_logic(request: Request, user_id: str):
    try:
        data = await request.json()
        if not data:
            logger.warning("No data received")
            raise HTTPException(status_code=400, detail='No data provided')
        message = data.get('message', '')
        if not isinstance(message, str) or not message.strip():
            logger.warning("Invalid message")
            raise HTTPException(status_code=400, detail='Message must be a non-empty string')

        logger.info(f"Received user message for user {user_id}: {message}")
        result = process_user_message(message, user_id)
        logger.info(f"Chat endpoint response for user {user_id}: {result}")
        return result
    except Exception as e:
        logger.error(f"Error in chat endpoint for user {user_id}: {str(e)}")
        if "Google authentication required" in str(e):
            raise HTTPException(status_code=401, detail={'action': 'Requires authentication', 'auth_url': f"{os.getenv('BASE_URL', 'http://localhost:5000')}/auth/google"})
        raise HTTPException(status_code=500, detail=f"Error processing chat request: {str(e)}")

@router.post('/chat')
async def chat_endpoint(request: Request, current_user: User = Depends(get_current_user)):
    return await chat_endpoint_logic(request, str(current_user.id))

async def chat_with_distilbert_endpoint_logic(request: Request, user_id: str):
    try:
        data = await request.json()
        if not data:
            logger.warning("No data received")
            raise HTTPException(status_code=400, detail='No data provided')
        message = data.get('message', '')
        if not isinstance(message, str) or not message.strip():
            logger.warning("Invalid message")
            raise HTTPException(status_code=400, detail='Message must be a non-empty string')

        logger.info(f"Received user message for Mistral for user {user_id}: {message}")
        result = chat_with_distilbert(message, user_id)
        logger.info(f"Mistral response for user {user_id}: {result}")
        return result
    except Exception as e:
        logger.error(f"Error in chat_with_distilbert endpoint for user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing Mistral chat request: {str(e)}")

@router.post('/chat_with_distilbert')
async def chat_with_distilbert_endpoint(request: Request, current_user: User = Depends(get_current_user)):
    return await chat_with_distilbert_endpoint_logic(request, str(current_user.id))

def create_zoom_meeting_logic(data, user_id):
    topic = data.get('topic', 'AI Meeting')
    start_time = data.get('start_time')  # ISO 8601 format: "2025-05-21T15:00:00"
    duration = data.get('duration', 30)  # in minutes

    if not user_id:
        raise HTTPException(status_code=400, detail="Missing user ID")

    tokens = load_tokens(user_id)
    if not tokens:
        raise HTTPException(status_code=401, detail="Tokens not found for this user")
    access_token = tokens.get("zoom", {}).get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="Zoom token not found for this user. Please authenticate via /auth/zoom.")

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

    try:
        response = requests.post(
            "https://api.zoom.us/v2/users/me/meetings",
            headers=headers,
            json=meeting_data
        )

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
    except Exception as e:
        logger.error(f"Error creating Zoom meeting for user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating Zoom meeting: {str(e)}")

@router.post('/create_zoom_meeting')
async def create_zoom_meeting(request: Request, current_user: User = Depends(get_current_user)):
    try:
        data = await request.json()
        user_id = str(current_user.id)
        return create_zoom_meeting_logic(data, user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def list_notion_pages_endpoint_logic(user_id: str):
    try:
        pages = list_notion_pages(user_id)
        return {'pages': pages}
    except Exception as e:
        logger.error(f"Error listing Notion pages for user {user_id}: {str(e)}")
        if "Notion token not found" in str(e):
            raise HTTPException(status_code=401, detail={'action': 'Requires authentication', 'auth_url': f"{os.getenv('BASE_URL', 'http://localhost:5000')}/auth/notion"})
        raise HTTPException(status_code=500, detail=str(e))

@router.get('/list_notion_pages')
async def list_notion_pages_endpoint(current_user: User = Depends(get_current_user)):
    return await list_notion_pages_endpoint_logic(str(current_user.id))

async def list_calendar_events_endpoint_logic(request: Request, user_id: str):
    try:
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

        events = list_calendar_events(user_id, start_date, end_date, event_type, attendees)
        return {'events': events}
    except Exception as e:
        logger.error(f"Error listing calendar events for user {user_id}: {str(e)}")
        if "Google authentication required" in str(e):
            raise HTTPException(status_code=401, detail={'action': 'Requires authentication', 'auth_url': f"{os.getenv('BASE_URL', 'http://localhost:5000')}/auth/google"})
        raise HTTPException(status_code=500, detail=f"Error listing calendar events: {str(e)}")

@router.get('/list_calendar_events')
@router.post('/list_calendar_events')
async def list_calendar_events_endpoint(request: Request, current_user: User = Depends(get_current_user)):
    return await list_calendar_events_endpoint_logic(request, str(current_user.id))

@router.get('/download_slides/{filename}')
async def download_slides(filename: str):
    try:
        directory = os.path.join(os.getcwd(), "presentations")
        mimetype_guess = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        return FileResponse(path=os.path.join(directory, filename), media_type=mimetype_guess, filename=filename)
    except Exception as e:
        logger.error(f"Error downloading slides: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))

@router.get('/oauth2callback')
async def oauth2callback(request: Request):
    raise HTTPException(status_code=400, detail="This endpoint is deprecated. Use /auth/google/callback instead.")

@router.get("/auth/slack/callback")
async def auth_slack_callback(request: Request):
    code = request.query_params.get("code")
    user_id = request.headers.get("X-User-ID")

    if not code or not user_id:
        raise HTTPException(status_code=400, detail="Missing authorization code or user ID")

    try:
        token_data = handle_slack_callback(code, user_id)
        return {"message": "Slack authenticated successfully", "details": token_data}
    except Exception as e:
        logger.error(f"Error in Slack auth callback for user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/auth/zoom")
async def auth_zoom(request: Request):
    user_id = request.headers.get("X-User-ID")
    if not user_id:
        raise HTTPException(status_code=400, detail="Missing X-User-ID")

    state_token = generate_state_token(user_id)
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
        logger.error(f"Error in Zoom auth callback: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/execute_task")
def execute_task_endpoint(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    body: dict = Body(...)
):
    user_id = str(current_user.id)
    action = body.get("action", "")
    event_summary = body.get("event_summary", "")
    parent_page_id = body.get("parent_page_id", None)
    start_time = body.get("start_time", None)
    duration = body.get("duration", 30)
    recipient = body.get("recipient", "")
    slack_channel = body.get("slack_channel", "")

    if not action or not event_summary:
        raise HTTPException(status_code=400, detail="Missing action or event summary")

    # Validate environment variables only for relevant actions
    if action in ["Setup full Zoom meeting", "Create a Zoom Meeting", "Add a Reminder to Zoom"]:
        if not all([os.getenv('ZOOM_CLIENT_ID'), os.getenv('ZOOM_REDIRECT_URI'), os.getenv('ZOOM_BASIC_AUTH')]):
            raise HTTPException(status_code=500, detail="Zoom environment variables not configured")
    if action in ["Post update on Slack", "Send a Slack Reminder"]:
        if not all([os.getenv('SLACK_CLIENT_ID'), os.getenv('SLACK_CLIENT_SECRET'), os.getenv('SLACK_REDIRECT_URI')]):
            raise HTTPException(status_code=500, detail="Slack environment variables not configured")
    if action in ["Write email to colleague"]:
        if not all([os.getenv('GOOGLE_CLIENT_ID'), os.getenv('GOOGLE_CLIENT_SECRET'), os.getenv('GOOGLE_REDIRECT_URI')]):
            raise HTTPException(status_code=500, detail="Google environment variables not configured")
    if action in ["Write important notes in Notion"]:
        if not all([os.getenv('NOTION_CLIENT_ID'), os.getenv('NOTION_CLIENT_SECRET'), os.getenv('NOTION_REDIRECT_URI')]):
            raise HTTPException(status_code=500, detail="Notion environment variables not configured")

    tokens = load_tokens(user_id)

    try:
        if action == "Write important notes in Notion":
            result = create_notion_page(event_summary, parent_page_id, user_id=user_id)
            return {"message": "Notion page created", "notion": result}

        elif action == "Setup full Zoom meeting" or action == "Create a Zoom Meeting":
            if not tokens.get("zoom"):
                raise HTTPException(status_code=401, detail="Zoom not connected. Please authenticate via /auth/zoom.")
            zoom_data = create_zoom_meeting_logic({
                "topic": event_summary,
                "start_time": start_time if start_time else datetime.now().isoformat(),
                "duration": duration
            }, user_id)
            calendar_event = create_calendar_event_with_zoom(
                topic=event_summary,
                start_time=start_time if start_time else datetime.now().isoformat(),
                duration=duration,
                zoom_link=zoom_data["zoom_link"],
                user_id=user_id
            )
            return {"message": "Zoom meeting and calendar event created", "zoom": zoom_data, "calendar_event": calendar_event}

        elif action == "Add a Reminder to Zoom":
            if not tokens.get("zoom"):
                raise HTTPException(status_code=401, detail="Zoom not connected. Please authenticate via /auth/zoom.")
            zoom_data = create_zoom_meeting_logic({
                "topic": event_summary,
                "start_time": start_time if start_time else datetime.now().isoformat(),
                "duration": duration
            }, user_id)
            calendar_event = create_calendar_event_with_zoom(
                topic=event_summary,
                start_time=start_time if start_time else datetime.now().isoformat(),
                duration=duration,
                zoom_link=zoom_data["zoom_link"],
                user_id=user_id
            )
            slack_result = post_to_slack(
                f"Reminder: {event_summary} on {start_time if start_time else datetime.now().isoformat()} via Zoom: {zoom_data['zoom_link']}",
                user_id=user_id
            )
            return {
                "message": "Zoom reminder added",
                "zoom": zoom_data,
                "calendar_event": calendar_event,
                "slack": slack_result
            }

        elif action == "Write email to colleague":
            if not tokens.get("google"):
                raise HTTPException(status_code=401, detail="Google not connected. Please authenticate via /auth/google.")
            email_body = f"Meeting scheduled: {event_summary}"
            return send_gmail(recipient, f"Regarding: {event_summary}", email_body, user_id)

        elif action in ["Post update on Slack", "Send a Slack Reminder"]:
            if not tokens.get("slack"):
                raise HTTPException(status_code=401, detail="Slack not connected. Please authenticate via /auth/slack.")
            return post_to_slack(f"Update: {event_summary}", user_id=user_id)

        else:
            return {"message": f"No handler implemented for action '{action}'"}
    except Exception as e:
        logger.error(f"Error executing task for user {user_id}: {str(e)}")
        if "Google authentication required" in str(e):
            raise HTTPException(status_code=401, detail={'action': 'Requires authentication', 'auth_url': f"{os.getenv('BASE_URL', 'http://localhost:5000')}/auth/google"})
        if "Notion token not found" in str(e):
            raise HTTPException(status_code=401, detail={'action': 'Requires authentication', 'auth_url': f"{os.getenv('BASE_URL', 'http://localhost:5000')}/auth/notion"})
        raise HTTPException(status_code=500, detail=str(e))
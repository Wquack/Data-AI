import sys
import os
import json
import logging
import mimetypes
import traceback
from datetime import datetime, timedelta
from urllib.parse import urlencode
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from fastapi import APIRouter, Request, HTTPException, Depends, Body
from fastapi.responses import RedirectResponse, FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from models.user import User
from utils.db import get_db
from utils.token_store import load_tokens
from auth.auth_routes import get_current_user
from utils.jwt_utils import generate_state_token, decode_state_token
from .recommendation import process_user_message, chat_with_mistral
from .calendar_api import create_calendar_event, list_calendar_events, upload_to_drive, send_gmail, create_calendar_event_with_zoom
from .encryption import encrypt_data
from .mistral_api import call_mistral_api
from .slack_oauth import get_slack_auth_url, handle_slack_callback, post_to_slack
from .zoom_oauth import get_zoom_auth_url, handle_zoom_callback, refresh_zoom_token
from .notion_api import create_notion_page, list_notion_pages
from .powerpoint_api import create_powerpoint_slides
import requests
# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

router = APIRouter()

class ChatMessage(BaseModel):
    message: str

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

        # Note: get_recommendation was removed in recommendation.py; this endpoint may need reimplementation
        raise HTTPException(status_code=501, detail="Recommendation functionality is not implemented")
    except Exception as e:
        logger.error(f"Error processing recommend task request: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")

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

        current_user: User = Depends(get_current_user)
        user_id = str(current_user.id)

        logger.info(f"Received user message for user {user_id}: {message}")
        response = await call_mistral_api(message, user_id)
        logger.info(f"Chat endpoint response for user {user_id}: {json.dumps(response, indent=2)}")
        if response is not None:
            return {
                "response": response.get("response"),
                "suggestions": response.get("suggestions", [])
            }
        else:
            return {"response": None, "suggestions": []}
    except Exception as e:
        logger.error(f"Error in chat endpoint for user {user_id}: {str(e)}\n{traceback.format_exc()}")
        if "google authentication required" in str(e).lower():
            raise HTTPException(status_code=401, detail={'action': 'Requires authentication', 'auth_url': f"{os.getenv('BASE_URL', 'http://localhost:5000')}/auth/google"})
        raise HTTPException(status_code=500, detail=f"Error processing chat request: {str(e)}")

@router.post('/chat')
async def chat_endpoint(request: Request, current_user: User = Depends(get_current_user)):
    return await chat_endpoint_logic(request, str(current_user.id))

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
        result = await process_user_message(message, user_id)
        logger.info(f"Chat endpoint response for user {user_id}: {json.dumps(result, indent=2)}")

        if result:
            current_hour = datetime.now().hour
            if 5 <= current_hour < 12:
                greeting = "Good morning!"
            elif 12 <= current_hour < 17:
                greeting = "Good afternoon!"
            elif 17 <= current_hour < 22:
                greeting = "Good evening!"
            else:
                greeting = "Good night!"
            result["response"] = f"{greeting} {result['response']}"

        return result
    except Exception as e:
        logger.error(f"Error in chat endpoint for user {user_id}: {str(e)}\n{traceback.format_exc()}")
        if "google authentication required" in str(e).lower():
            raise HTTPException(status_code=401, detail={'action': 'Requires authentication', 'auth_url': f"{os.getenv('BASE_URL', 'http://localhost:5000')}/auth/google"})
        raise HTTPException(status_code=500, detail=f"Error processing chat request: {str(e)}")
    
@router.post('/chat_with_mistral')
async def chat_with_mistral_endpoint(request: Request, current_user: User = Depends(get_current_user)):
    return await chat_with_mistral_endpoint_logic(request, str(current_user.id))

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
        logger.error(f"Error creating Zoom meeting for user {user_id}: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error creating Zoom meeting: {str(e)}")

@router.post('/create_zoom_meeting')
async def create_zoom_meeting(request: Request, current_user: User = Depends(get_current_user)):
    try:
        data = await request.json()
        user_id = str(current_user.id)
        return create_zoom_meeting_logic(data, user_id)
    except Exception as e:
        logger.error(f"Error in create_zoom_meeting endpoint for user {user_id}: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

async def list_notion_pages_endpoint_logic(user_id: str):
    try:
        pages = list_notion_pages(user_id)
        return {'pages': pages}
    except Exception as e:
        logger.error(f"Error listing Notion pages for user {user_id}: {str(e)}\n{traceback.format_exc()}")
        if "notion token not found" in str(e).lower():
            raise HTTPException(status_code=401, detail={'action': 'Requires authentication', 'auth_url': f"{os.getenv('BASE_URL', 'http://localhost:5000')}/auth/notion"})
        raise HTTPException(status_code=500, detail=str(e))

@router.get('/list_notion_pages')
async def list_notion_pages_endpoint(current_user: User = Depends(get_current_user)):
    return await list_notion_pages_endpoint_logic(str(current_user.id))

@router.get('/list_notion_tasks')
async def list_notion_tasks_endpoint(current_user: User = Depends(get_current_user)):
    try:
        # Fetch tasks from Notion (simplified example)
        tasks = [
            {"title": "updating the company's mission statement", "section": "Projects"}
        ]
        return {"tasks": tasks}
    except Exception as e:
        logger.error(f"Error listing Notion tasks for user {current_user.id}: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get('/list_drive_deadlines')
async def list_drive_deadlines_endpoint(request: Request, current_user: User = Depends(get_current_user)):
    try:
        # Fetch deadlines from Google Drive (simplified example)
        deadlines = [
            {"title": "the quarterly report", "folder": "Quarterly Reports"}
        ]
        return {"deadlines": deadlines}
    except Exception as e:
        logger.error(f"Error listing Google Drive deadlines for user {current_user.id}: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

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
        logger.error(f"Error listing calendar events for user {user_id}: {str(e)}\n{traceback.format_exc()}")
        if "google authentication required" in str(e).lower():
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
        logger.error(f"Error downloading slides: {str(e)}\n{traceback.format_exc()}")
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
        logger.error(f"Error in Slack auth callback for user {user_id}: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/auth/zoom")
async def auth_zoom(request: Request):
    user_id = request.headers.get("X-User-ID")
    if not user_id:
        raise HTTPException(status_code=400, detail="Missing X-User-ID")

    state_token = generate_state_token(user_id)
    return RedirectResponse(get_zoom_auth_url() + f"&state={state_token}")

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
        logger.error(f"Error in Zoom auth callback: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/execute_task")
def execute_task_endpoint(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    body: dict = Body(...)
):
    action = body.get("action", "")
    event_summary = body.get("event_summary", "")
    parent_page_id = body.get("parent_page_id", None)
    start_time = body.get("start_time", None)
    duration = body.get("duration", 30)
    recipient = body.get("recipient", "")
    slack_channel = body.get("slack_channel", "")

    user_id = str(current_user.id)

    tokens = load_tokens(user_id)

    try:
        if action == "Write important notes in Notion":
            result = create_notion_page(event_summary, parent_page_id, user_id)
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
                message=f"Reminder: {event_summary} on {start_time if start_time else datetime.now().isoformat()} via Zoom: {zoom_data['zoom_link']}",
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
        logger.error(f"Error executing task for user {user_id}: {str(e)}\n{traceback.format_exc()}")
        if "google authentication required" in str(e).lower():
            raise HTTPException(status_code=401, detail={'action': 'Requires authentication', 'auth_url': f"{os.getenv('BASE_URL', 'http://localhost:5000')}/auth/google"})
        if "notion token not found" in str(e).lower():
            raise HTTPException(status_code=401, detail={'action': 'Requires authentication', 'auth_url': f"{os.getenv('BASE_URL', 'http://localhost:5000')}/auth/notion"})
        raise HTTPException(status_code=500, detail=str(e))

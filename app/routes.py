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
import re
from typing import Dict, List, Any, Optional
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
    context: Optional[str] = None  # Optional conversation context

class Suggestion(BaseModel):
    action: str
    service: str
    description: str
    priority: int  # 1-5, where 5 is highest priority

class ChatResponse(BaseModel):
    message: str
    intent: str
    confidence: float
    response: str
    suggestions: List[Suggestion]
    follow_up_questions: List[str]
    notion_pages: List[Dict[str, Any]]


def get_user_services_context(user_tokens: Dict) -> Dict[str, bool]:
    """Get available services for the user"""
    return {
        "google_calendar": "google" in user_tokens and "access_token" in user_tokens.get("google", {}),
        "gmail": "google" in user_tokens and "access_token" in user_tokens.get("google", {}),
        "slack": "slack" in user_tokens and "access_token" in user_tokens.get("slack", {}),
        "zoom": "zoom" in user_tokens and "access_token" in user_tokens.get("zoom", {}),
        "notion": "notion" in user_tokens and "access_token" in user_tokens.get("notion", {})
    }

def analyze_user_intent(message: str) -> Dict[str, Any]:
    """Enhanced intent detection using keywords and patterns"""
    message_lower = message.lower()
    
    # Define intent patterns with confidence scores
    intent_patterns = {
        "schedule_meeting": {
            "keywords": ["schedule", "meeting", "event", "appointment", "calendar", "book", "arrange"],
            "patterns": [r"schedule.*meeting", r"book.*appointment", r"arrange.*call"],
            "confidence_base": 0.8
        },
        "send_email": {
            "keywords": ["email", "send", "message", "notify", "inform"],
            "patterns": [r"send.*email", r"email.*about", r"notify.*team"],
            "confidence_base": 0.7
        },
        "create_document": {
            "keywords": ["create", "document", "note", "write", "draft"],
            "patterns": [r"create.*document", r"write.*note", r"draft.*proposal"],
            "confidence_base": 0.7
        },
        "search_information": {
            "keywords": ["find", "search", "look", "information", "data"],
            "patterns": [r"find.*information", r"search.*for", r"look.*up"],
            "confidence_base": 0.6
        },
        "status_update": {
            "keywords": ["status", "update", "progress", "report"],
            "patterns": [r"status.*update", r"progress.*report", r"how.*going"],
            "confidence_base": 0.6
        },
        "general_question": {
            "keywords": ["help", "how", "what", "why", "when", "where"],
            "patterns": [r"how.*do", r"what.*is", r"help.*with"],
            "confidence_base": 0.5
        }
    }
    
    best_intent = "general_question"
    best_confidence = 0.3
    
    for intent, config in intent_patterns.items():
        confidence = 0
        
        # Check keywords
        keyword_matches = sum(1 for keyword in config["keywords"] if keyword in message_lower)
        confidence += (keyword_matches / len(config["keywords"])) * config["confidence_base"]
        
        # Check patterns
        pattern_matches = sum(1 for pattern in config["patterns"] if re.search(pattern, message_lower))
        if pattern_matches > 0:
            confidence += 0.2
        
        if confidence > best_confidence:
            best_intent = intent
            best_confidence = confidence
    
    return {
        "intent": best_intent,
        "confidence": min(best_confidence, 1.0)
    }

def generate_intelligent_response(message: str, intent: str, services: Dict[str, bool]) -> str:
    """Generate contextual response using Mistral with better prompting"""
    
    available_services = [service for service, available in services.items() if available]
    services_text = ", ".join(available_services) if available_services else "none"
    
    # Create a more sophisticated prompt
    system_prompt = f"""You are an intelligent assistant that helps users manage their productivity across various platforms. 
    
Available services for this user: {services_text}
Detected intent: {intent}

Provide a helpful, specific response that:
1. Directly addresses their request
2. Suggests actionable next steps using their available services
3. Is concise but informative
4. Avoids generic positive/negative sentiment responses

Focus on practical solutions and specific actions they can take."""

    try:
        # Use your existing Mistral API call but with better prompting
        mistral_api_key = os.getenv("MISTRAL_API_KEY")
        if not mistral_api_key:
            return "I'm here to help you manage your tasks and productivity. What would you like to accomplish?"

        headers = {
            "Authorization": f"Bearer {mistral_api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "mistral-small-latest",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ],
            "temperature": 0.7,
            "max_tokens": 300
        }
        
        response = requests.post("https://api.mistral.ai/v1/chat/completions", headers=headers, json=payload)
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        else:
            logger.error(f"Mistral API error: {response.status_code} {response.text}")
            return "I'm here to help you manage your tasks and productivity. What would you like to accomplish?"
    except Exception as e:
        logger.error(f"Error calling Mistral API: {str(e)}")
        return "I'm here to help you manage your tasks and productivity. What would you like to accomplish?"

def generate_smart_suggestions(intent: str, message: str, services: Dict[str, bool]) -> List[Dict]:
    """Generate contextual suggestions based on intent and available services"""
    suggestions = []
    
    if intent == "schedule_meeting" and services.get("google_calendar"):
        suggestions.append({
            "action": "Create calendar event",
            "service": "google_calendar",
            "description": "Schedule this meeting on your Google Calendar",
            "priority": 5
        })
        if services.get("gmail"):
            suggestions.append({
                "action": "Send meeting invite",
                "service": "gmail",
                "description": "Send email invitations to participants",
                "priority": 4
            })
        if services.get("zoom"):
            suggestions.append({
                "action": "Create Zoom meeting",
                "service": "zoom",
                "description": "Generate Zoom link for the meeting",
                "priority": 4
            })
    
    elif intent == "send_email" and services.get("gmail"):
        suggestions.append({
            "action": "Compose email",
            "service": "gmail",
            "description": "Draft and send your email",
            "priority": 5
        })
    
    elif intent == "create_document" and services.get("notion"):
        suggestions.append({
            "action": "Create Notion page",
            "service": "notion",
            "description": "Start a new document in Notion",
            "priority": 5
        })
    
    elif intent == "status_update":
        if services.get("slack"):
            suggestions.append({
                "action": "Post to Slack",
                "service": "slack",
                "description": "Share your status update with your team",
                "priority": 4
            })
        if services.get("gmail"):
            suggestions.append({
                "action": "Send status email",
                "service": "gmail",
                "description": "Email a detailed status report",
                "priority": 3
            })
    
    elif intent == "search_information" and services.get("notion"):
        suggestions.append({
            "action": "Search Notion",
            "service": "notion",
            "description": "Look for relevant information in your Notion workspace",
            "priority": 4
        })
    
    # Always provide a general help suggestion if no specific actions are available
    if not suggestions:
        if services.get("google_calendar"):
            suggestions.append({
                "action": "Check calendar",
                "service": "google_calendar",
                "description": "Review your upcoming events and schedule",
                "priority": 2
            })
        if services.get("notion"):
            suggestions.append({
                "action": "Browse Notion",
                "service": "notion",
                "description": "Explore your Notion workspace for inspiration",
                "priority": 2
            })
    
    # Sort by priority
    suggestions.sort(key=lambda x: x["priority"], reverse=True)
    return suggestions[:3]  # Return top 3 suggestions

def generate_follow_up_questions(intent: str, message: str) -> List[str]:
    """Generate relevant follow-up questions to continue the conversation"""
    questions = []
    
    if intent == "schedule_meeting":
        questions = [
            "What time works best for this meeting?",
            "Who should be invited to this meeting?",
            "How long should the meeting be?"
        ]
    elif intent == "send_email":
        questions = [
            "Who should receive this email?",
            "What's the main topic or subject?",
            "Is this urgent or can it wait?"
        ]
    elif intent == "create_document":
        questions = [
            "What type of document are you creating?",
            "What's the main purpose of this document?",
            "Do you need to collaborate with others on this?"
        ]
    elif intent == "general_question":
        questions = [
            "What specific task would you like help with?",
            "Are you looking to schedule something or send a message?",
            "What's your main goal right now?"
        ]
    else:
        questions = [
            "Would you like me to help you get started?",
            "Do you need any additional information?",
            "Is there anything else I can assist you with?"
        ]
    
    return questions[:2]  # Return up to 2 follow-up questions


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
        response = await call_mistral_api(message, str(user_id))
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

@router.post("/chat")
async def chat_endpoint(request: Request, current_user: User = Depends(get_current_user)):
    user_id = None
    try:
        user_id = current_user.id
        data = await request.json()
        message = data.get("message", "")

        if not isinstance(message, str) or not message.strip():
            raise HTTPException(status_code=400, detail="Invalid message")

        logger.info(f"Received user message for user {user_id}: {message}")

        # Step 1: Analyze user intent
        intent_analysis = analyze_user_intent(message)
        
        # Step 2: Get user's available services
        user_tokens = load_tokens(str(user_id))
        services = get_user_services_context(user_tokens or {})
        
        # Step 3: Generate intelligent response
        response_text = generate_intelligent_response(
            message, 
            intent_analysis["intent"], 
            services
        )
        
        # Step 4: Generate smart suggestions
        suggestions = generate_smart_suggestions(
            intent_analysis["intent"], 
            message, 
            services
        )
        
        # Step 5: Generate follow-up questions
        follow_up_questions = generate_follow_up_questions(
            intent_analysis["intent"], 
            message
        )
        
        logger.info(f"Chat processed for user {user_id}: intent={intent_analysis['intent']}, confidence={intent_analysis['confidence']}")
        
        return {
            "message": message,
            "intent": intent_analysis["intent"],
            "confidence": intent_analysis["confidence"],
            "response": response_text,
            "suggestions": suggestions,
            "follow_up_questions": follow_up_questions,
            "notion_pages": []  # Keep this for compatibility
        }
        
    except Exception as e:
        logger.error(f"Error in chat processing for user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="An error occurred while processing your request")



async def chat_with_mistral_endpoint_logic(request: Request, user_id: str):
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
        response = await chat_with_mistral(message, user_id)
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
        user_id = decode_state_token(state_token)
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

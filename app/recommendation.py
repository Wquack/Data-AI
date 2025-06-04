# app/recommendation.py - Fixed and enhanced version

import logging
import aiohttp
import asyncio
import traceback
import re
from datetime import date, timedelta
from typing import Dict, List, Any, Optional
from .mistral_api import call_mistral_api
from cachetools import TTLCache

logger = logging.getLogger(__name__)

notion_pages_cache = TTLCache(maxsize=100, ttl=300)

# Enhanced context-aware additions
PRODUCTIVITY_KEYWORDS = [
    "meeting", "schedule", "calendar", "email", "task", "project", "deadline", 
    "work", "office", "team", "collaboration", "planning", "organize", "remind",
    "appointment", "event", "zoom", "slack", "notion", "document", "note",
    "productivity", "manage", "time", "busy", "focus", "goal", "priority"
]

# FIXED: Added missing comma after "inappropriate"
INAPPROPRIATE_KEYWORDS = [
    "sex", "dating", "relationship", "love", "personal", "private", "intimate",
    "nsfw", "adult", "inappropriate", "orgy", "lesbian"
]

REJECTION_PATTERNS = [
    r"i don't want", r"no thanks", r"not interested", r"don't need",
    r"already did", r"not now", r"maybe later", r"skip", r"pass"
]

class ConversationContext:
    """Track conversation context to avoid repetitive suggestions"""
    
    def __init__(self):
        self.rejected_services = set()
        self.suggested_actions = set()
        self.conversation_count = 0
        self.last_intent = None
    
    def add_rejection(self, service: str):
        """Mark a service as rejected by the user"""
        self.rejected_services.add(service.lower())
    
    def add_suggested_action(self, action: str):
        """Track what we've already suggested"""
        self.suggested_actions.add(action.lower())
    
    def is_rejected(self, service: str) -> bool:
        """Check if user has rejected this service"""
        return service.lower() in self.rejected_services
    
    def already_suggested(self, action: str) -> bool:
        """Check if we've already suggested this action"""
        return action.lower() in self.suggested_actions

# Store context per user (in production, use Redis or database)
user_contexts: Dict[str, ConversationContext] = {}

def get_user_context(user_id: str) -> ConversationContext:
    """Get or create conversation context for user"""
    if user_id not in user_contexts:
        user_contexts[user_id] = ConversationContext()
    return user_contexts[user_id]

def is_productivity_related(message: str) -> bool:
    """Check if message is related to productivity/work"""
    message_lower = message.lower()
    
    # Check for inappropriate content first
    for keyword in INAPPROPRIATE_KEYWORDS:
        if keyword in message_lower:
            return False
    
    # Check for productivity keywords
    for keyword in PRODUCTIVITY_KEYWORDS:
        if keyword in message_lower:
            return True
    
    # Check for common productivity phrases
    productivity_phrases = [
        "what should i do", "help me with", "how to", "need to",
        "have to", "should i", "can you help", "assist me", "updates", "events"
    ]
    
    return any(phrase in message_lower for phrase in productivity_phrases)

def detect_rejection(message: str) -> bool:
    """Detect if user is rejecting suggestions"""
    message_lower = message.lower()
    
    # Check explicit rejection patterns
    for pattern in REJECTION_PATTERNS:
        if re.search(pattern, message_lower):
            return True
    
    # Check for negative sentiment words
    negative_words = ["no", "nope", "nah", "never", "stop", "enough", "annoying"]
    return any(word in message_lower for word in negative_words)

def extract_rejected_service(message: str) -> Optional[str]:
    """Extract which service the user is rejecting"""
    message_lower = message.lower()
    services = ["notion", "calendar", "slack", "zoom", "email", "gmail"]
    
    for service in services:
        if service in message_lower:
            return service
    return None

# === EXISTING FUNCTIONS PRESERVED ===

# Define positive and negative keywords for sentiment detection
POSITIVE_KEYWORDS = ["good", "great", "fantastic", "amazing", "success", "achieve", "milestone", "celebrate", "happy", "awesome", "excellent", "wonderful"]
NEGATIVE_KEYWORDS = ["bad", "terrible", "fail", "overwhelm", "stress", "problem", "issue", "difficult", "sad", "frustrate", "struggle", "delay"]

async def fetch_calendar_events(start_date=None, end_date=None, user_id=None, timeout=10):
    try:
        url = "https://backend.data-ai.co/list_calendar_events"
        params = {}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date

        async with aiohttp.ClientSession() as session:
            start_time = asyncio.get_event_loop().time()
            async with session.get(url, params=params, timeout=timeout) as response:
                response.raise_for_status()
                events = await response.json()
                end_time = asyncio.get_event_loop().time()
                logger.info(f"fetch_calendar_events took {end_time - start_time:.2f} seconds for user {user_id}")
                return events.get("events", [])
    except aiohttp.ClientResponseError as e:
        if e.status == 401 and 'action' in e.message and 'Requires authentication' in e.message:
            return {"requires_auth": True, "auth_url": e.message.get("auth_url", "https://backend.data-ai.co/auth/google")}
        logger.error(f"HTTP error fetching calendar events for user {user_id}: {str(e)}\n{traceback.format_exc()}")
        raise Exception(f"Failed to fetch calendar events: HTTP error {str(e)}")
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        logger.error(f"Network error fetching calendar events for user {user_id}: {str(e)}\n{traceback.format_exc()}")
        raise Exception(f"Failed to fetch calendar events: Network error {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error fetching calendar events for user {user_id}: {str(e)}\n{traceback.format_exc()}")
        raise Exception(f"Failed to fetch calendar events: {str(e)}")

async def fetch_notion_pages(user_id=None, timeout=10):
    cache_key = f"notion_pages_{user_id}"
    if cache_key in notion_pages_cache:
        logger.info(f"Returning cached Notion pages for user {user_id}")
        return notion_pages_cache[cache_key]

    try:
        async with aiohttp.ClientSession() as session:
            start_time = asyncio.get_event_loop().time()
            async with session.get("https://backend.data-ai.co/list_notion_pages", timeout=timeout) as response:
                response.raise_for_status()
                pages = await response.json()
                pages = pages.get("pages", [])
                end_time = asyncio.get_event_loop().time()
                logger.info(f"fetch_notion_pages took {end_time - start_time:.2f} seconds for user {user_id}")
                notion_pages_cache[cache_key] = pages
                return pages
    except Exception as e:
        logger.error(f"Error fetching Notion pages for user {user_id}: {str(e)}\n{traceback.format_exc()}")
        return []

async def fetch_notion_tasks(user_id=None, timeout=10):
    try:
        async with aiohttp.ClientSession() as session:
            start_time = asyncio.get_event_loop().time()
            async with session.get("https://backend.data-ai.co/list_notion_tasks", timeout=timeout) as response:
                response.raise_for_status()
                tasks = await response.json()
                tasks = tasks.get("tasks", [])
                end_time = asyncio.get_event_loop().time()
                logger.info(f"fetch_notion_tasks took {end_time - start_time:.2f} seconds for user {user_id}")
                return tasks
    except Exception as e:
        logger.error(f"Error fetching Notion tasks for user {user_id}: {str(e)}\n{traceback.format_exc()}")
        return []

async def fetch_drive_deadlines(user_id=None, timeout=10):
    try:
        async with aiohttp.ClientSession() as session:
            start_time = asyncio.get_event_loop().time()
            async with session.get("https://backend.data-ai.co/list_drive_deadlines", timeout=timeout) as response:
                response.raise_for_status()
                deadlines = await response.json()
                deadlines = deadlines.get("deadlines", [])
                end_time = asyncio.get_event_loop().time()
                logger.info(f"fetch_drive_deadlines took {end_time - start_time:.2f} seconds for user {user_id}")
                return deadlines
    except Exception as e:
        logger.error(f"Error fetching Google Drive deadlines for user {user_id}: {str(e)}\n{traceback.format_exc()}")
        return []

def generate_action_suggestions(message, mistral_response=""):
    message_lower = message.lower()
    mistral_lower = mistral_response.lower()
    suggestions = []

    if 'meeting' in message_lower or 'conference' in message_lower or 'meeting' in mistral_lower:
        suggestions.append({
            "action": "Write important notes in Notion",
            "service": "notion",
            "description": "Create a Notion page to jot down key points for the meeting."
        })
        suggestions.append({
            "action": "Write up an email for the meeting to a colleague",
            "service": "gmail",
            "description": "Draft an email to a colleague about the meeting details."
        })
        suggestions.append({
            "action": "Add a Reminder to Zoom",
            "service": "zoom",
            "description": "Create a Zoom meeting and add it to the calendar as a reminder."
        })
    elif 'deadline' in message_lower or 'project' in message_lower or 'deadline' in mistral_lower:
        suggestions.append({
            "action": "Break down tasks in Notion",
            "service": "notion",
            "description": "Create a Notion page to outline tasks for the project or deadline."
        })
        suggestions.append({
            "action": "Set a calendar reminder",
            "service": "calendar",
            "description": "Add a reminder to Google Calendar for the deadline."
        })
    elif 'appointment' in message_lower or 'doctor' in message_lower or 'appointment' in mistral_lower:
        suggestions.append({
            "action": "Send a reminder email",
            "service": "gmail",
            "description": "Draft an email reminder to bring documents for the appointment."
        })
        suggestions.append({
            "action": "Add to calendar",
            "service": "calendar",
            "description": "Add the appointment to your Google Calendar."
        })
    elif 'celebrate' in message_lower or 'milestone' in message_lower or 'success' in mistral_lower:
        suggestions.append({
            "action": "Schedule a team celebration meeting",
            "service": "calendar",
            "description": "Schedule a meeting on Google Calendar to celebrate with your team."
        })
        suggestions.append({
            "action": "Share achievement on Slack",
            "service": "slack",
            "description": "Post a message on Slack to share your milestone with the team."
        })
    elif 'overwhelmed' in message_lower or 'stress' in message_lower or 'overwhelmed' in mistral_lower:
        suggestions.append({
            "action": "Organize thoughts in Notion",
            "service": "notion",
            "description": "Create a Notion page to organize your thoughts and reduce stress."
        })
        suggestions.append({
            "action": "Request support via email",
            "service": "gmail",
            "description": "Draft an email to a colleague to request support or assistance."
        })
    else:
        suggestions.append({
            "action": "Plan your day",
            "service": "calendar",
            "description": "Schedule your tasks for the day on Google Calendar to stay organized."
        })

    return suggestions

def generate_sentiment_based_suggestions(message, sentiment, mistral_response=""):
    message_lower = message.lower()
    mistral_lower = mistral_response.lower()
    suggestions = []

    if sentiment == "positive":
        if 'celebrate' in message_lower or 'milestone' in message_lower or 'success' in mistral_lower:
            suggestions.append({
                "action": "Schedule a team celebration meeting",
                "service": "calendar",
                "description": "Schedule a meeting on Google Calendar to celebrate with your team."
            })
            suggestions.append({
                "action": "Share achievement on Slack",
                "service": "slack",
                "description": "Post a message on Slack to share your milestone with the team."
            })
        elif 'project' in message_lower or 'progress' in mistral_lower:
            suggestions.append({
                "action": "Document progress in Notion",
                "service": "notion",
                "description": "Create a Notion page to document your project progress."
            })
            suggestions.append({
                "action": "Schedule a follow-up meeting",
                "service": "calendar",
                "description": "Schedule a follow-up meeting on Google Calendar to keep the momentum going."
            })
        else:
            suggestions.append({
                "action": "Celebrate with a team email",
                "service": "gmail",
                "description": "Send an email to your team to celebrate your positive mood."
            })
    else:
        if 'project' in message_lower or 'deadline' in mistral_lower:
            suggestions.append({
                "action": "Break down tasks in Notion",
                "service": "notion",
                "description": "Create a Notion page to outline tasks for the project or deadline."
            })
            suggestions.append({
                "action": "Set a calendar reminder",
                "service": "calendar",
                "description": "Add a reminder to Google Calendar for the deadline."
            })
        elif 'overwhelmed' in message_lower or 'stress' in message_lower or 'overwhelmed' in mistral_lower:
            suggestions.append({
                "action": "Organize thoughts in Notion",
                "service": "notion",
                "description": "Create a Notion page to organize your thoughts and reduce stress."
            })
            suggestions.append({
                "action": "Request support via email",
                "service": "gmail",
                "description": "Draft an email to a colleague to request support or assistance."
            })
        else:
            suggestions.append({
                "action": "Schedule a break",
                "service": "calendar",
                "description": "Add a break to your Google Calendar to take some time off."
            })
            suggestions.append({
                "action": "Discuss concerns on Slack",
                "service": "slack",
                "description": "Share your challenges with your team on Slack to get support."
            })

    return suggestions

def detect_sentiment(message, mistral_response=""):
    message_lower = message.lower()
    mistral_lower = mistral_response.lower()

    if "positive" in mistral_lower:
        return "positive"
    if "negative" in mistral_lower:
        return "negative"

    positive_score = sum(1 for keyword in POSITIVE_KEYWORDS if keyword in message_lower or keyword in mistral_lower)
    negative_score = sum(1 for keyword in NEGATIVE_KEYWORDS if keyword in message_lower or keyword in mistral_lower)

    if positive_score > negative_score:
        return "positive"
    elif negative_score > positive_score:
        return "negative"
    else:
        return "positive"

def extract_crisp_response(mistral_response, sentiment):
    """Extract the first sentence from Mistral's response as a crisp line."""
    try:
        sentences = mistral_response.split('.')
        crisp_response = sentences[0].strip()
        if crisp_response and not crisp_response.endswith('!'):
            crisp_response += '!'
        return crisp_response
    except Exception as e:
        logger.error(f"Error extracting crisp response: {str(e)}\n{traceback.format_exc()}")
        if sentiment == "positive":
            return "Congratulations on your achievement!"
        else:
            return "Sorry to hear you're facing challenges!"

def generate_contextual_response(message_lower, suggestions, sentiment):
    """Generate a contextual follow-up based on the sentiment, suggestions, and message context."""
    if not suggestions:
        return "Consider planning your next steps to stay on track."

    primary_suggestion = suggestions[0]
    action = primary_suggestion["action"]
    service = primary_suggestion["service"]

    is_celebratory = any(keyword in message_lower for keyword in ["celebrate", "milestone", "success", "achieve"])

    action_lower = action.lower()
    if service.lower() in action_lower:
        action_phrase = action_lower.replace(service.lower(), "").strip()
    else:
        action_phrase = action_lower

    if sentiment == "positive":
        if is_celebratory:
            return f"To celebrate, try to {action_phrase} using {service.capitalize()}."
        else:
            return f"To stay on track, try to {action_phrase} using {service.capitalize()}."
    else:
        return f"To manage this, try to {action_phrase} using {service.capitalize()}."

# === NEW ENHANCED FUNCTIONS ===

def generate_contextual_response_enhanced(
    message: str, 
    user_id: str, 
    services: Dict[str, bool]
) -> Dict[str, Any]:
    """Enhanced response generation with conversation context"""
    
    context = get_user_context(user_id)
    context.conversation_count += 1
    message_lower = message.lower()
    
    # 1. Check if message is inappropriate or off-topic
    if not is_productivity_related(message):
        return {
            "response": "I'm here to help with your productivity and work tasks. How can I assist you with scheduling, organizing, or managing your work?",
            "suggestions": [],
            "follow_up_questions": ["What work task can I help you with?"],
            "intent": "off_topic",
            "confidence": 0.9
        }
    
    # 2. Handle rejections
    if detect_rejection(message):
        rejected_service = extract_rejected_service(message)
        if rejected_service:
            context.add_rejection(rejected_service)
        
        return {
            "response": "Got it! What else can I help you with today?",
            "suggestions": generate_fresh_suggestions(services, context),
            "follow_up_questions": ["Is there anything specific you'd like to work on?"],
            "intent": "rejection_handled",
            "confidence": 0.9
        }
    
    # 3. Handle greetings without overwhelming suggestions
    greeting_words = ["hi", "hello", "hey", "good morning", "good afternoon"]
    if any(word in message_lower for word in greeting_words) and len(message.split()) <= 3:
        return {
            "response": "Hi! I'm here to help with your work and productivity. What would you like to focus on today?",
            "suggestions": generate_minimal_suggestions(services, context),
            "follow_up_questions": ["What's your main priority right now?"],
            "intent": "greeting",
            "confidence": 0.9
        }
    
    # 4. Handle specific productivity requests
    if "meeting" in message_lower or "schedule" in message_lower:
        context.last_intent = "schedule_meeting"
        return handle_scheduling_request(message, services, context)
    
    elif any(phrase in message_lower for phrase in ["email", "gmail", "inbox", "messages"]):
        context.last_intent = "email_management"
        return handle_email_management_request(message, services, context)
    
    elif "note" in message_lower or "document" in message_lower:
        context.last_intent = "create_document"
        return handle_document_request(message, services, context)
    
    # 5. Handle Notion pages requests
    elif any(phrase in message_lower for phrase in ["list notion pages", "show notion pages", "notion pages", "my notion pages", "view notion"]):
        context.last_intent = "list_notion_pages"
        return handle_notion_pages_request(message, services, context)
    
    # 6. Handle calendar events requests  
    elif any(phrase in message_lower for phrase in ["list calendar", "show calendar", "calendar events", "my events", "check calendar"]):
        context.last_intent = "list_calendar_events"
        return handle_calendar_events_request(message, services, context)
    
    # 7. Handle Slack requests
    elif any(phrase in message_lower for phrase in ["slack", "channels", "team chat", "post message"]):
        context.last_intent = "slack_management"
        return handle_slack_management_request(message, services, context)
    
    # 8. Default helpful response
    return {
        "response": "I can help you with scheduling meetings, sending emails, creating documents, or organizing your tasks. What would you like to work on?",
        "suggestions": generate_fresh_suggestions(services, context, max_suggestions=2),
        "follow_up_questions": ["What's the most important task on your agenda?"],
        "intent": "general_help",
        "confidence": 0.7
    }

def generate_fresh_suggestions(
    services: Dict[str, bool], 
    context: ConversationContext,
    max_suggestions: int = 2
) -> List[Dict]:
    """Generate suggestions that haven't been rejected or repeated - UPDATED"""
    
    suggestions = []
    
    # Calendar suggestions
    if services.get("google_calendar") and not context.is_rejected("calendar"):
        if not context.already_suggested("check calendar"):
            suggestions.append({
                "action": "Check calendar",
                "service": "google_calendar",
                "description": "Review your upcoming events",
                "priority": 5
            })
            context.add_suggested_action("check calendar")
    
    # Gmail suggestions  
    if services.get("gmail") and not context.is_rejected("email"):
        if not context.already_suggested("list gmail messages"):
            suggestions.append({
                "action": "List Gmail messages", 
                "service": "gmail",
                "description": "Check your recent emails",
                "priority": 4
            })
            context.add_suggested_action("list gmail messages")
    
    # Notion suggestions
    if services.get("notion") and not context.is_rejected("notion"):
        if not context.already_suggested("list notion pages"):
            suggestions.append({
                "action": "List Notion pages",
                "service": "notion", 
                "description": "View your Notion workspace",
                "priority": 3
            })
            context.add_suggested_action("list notion pages")
    
    # Slack suggestions
    if services.get("slack") and not context.is_rejected("slack"):
        if not context.already_suggested("list slack channels"):
            suggestions.append({
                "action": "List Slack channels",
                "service": "slack",
                "description": "View your team channels", 
                "priority": 3
            })
            context.add_suggested_action("list slack channels")
    
    # Limit suggestions and prioritize
    return sorted(suggestions, key=lambda x: x["priority"], reverse=True)[:max_suggestions]

def generate_minimal_suggestions(
    services: Dict[str, bool], 
    context: ConversationContext
) -> List[Dict]:
    """Generate only 1-2 most relevant suggestions"""
    return generate_fresh_suggestions(services, context, max_suggestions=1)

def handle_scheduling_request(message: str, services: Dict[str, bool], context: ConversationContext) -> Dict:
    """Handle meeting/scheduling requests specifically"""
    if services.get("google_calendar"):
        return {
            "response": "I can help you schedule that meeting! Let me show you your calendar first.",
            "suggestions": [{
                "action": "Check calendar",
                "service": "google_calendar", 
                "description": "View available time slots",
                "priority": 5
            }],
            "follow_up_questions": ["What time works best for your meeting?"],
            "intent": "schedule_meeting",
            "confidence": 0.9
        }
    else:
        return {
            "response": "To help with scheduling, I'll need access to your Google Calendar.",
            "suggestions": [{
                "action": "Connect Google Calendar",
                "service": "google_calendar",
                "description": "Enable calendar integration", 
                "priority": 5
            }],
            "follow_up_questions": [],
            "intent": "schedule_meeting",
            "confidence": 0.9
        }

def handle_email_management_request(message: str, services: Dict[str, bool], context: ConversationContext) -> Dict:
    """Handle email management requests with new Gmail APIs"""
    message_lower = message.lower()
    
    if services.get("gmail"):
        # Determine specific email action
        if any(phrase in message_lower for phrase in ["list", "show", "inbox", "messages"]):
            return {
                "response": "I'll show you your recent Gmail messages!",
                "suggestions": [{
                    "action": "List Gmail messages",
                    "service": "gmail",
                    "description": "View your recent emails",
                    "priority": 5
                }],
                "follow_up_questions": ["Would you like to compose a new email?"],
                "intent": "list_gmail_messages",
                "confidence": 0.9
            }
        elif any(phrase in message_lower for phrase in ["compose", "write", "send", "new email"]):
            return {
                "response": "I can help you compose an email!",
                "suggestions": [{
                    "action": "Compose email",
                    "service": "gmail",
                    "description": "Create a new email draft",
                    "priority": 5
                }],
                "follow_up_questions": ["Who would you like to send this email to?"],
                "intent": "compose_email",
                "confidence": 0.9
            }
        else:
            return {
                "response": "I can help you with your Gmail! What would you like to do?",
                "suggestions": [
                    {
                        "action": "List Gmail messages",
                        "service": "gmail",
                        "description": "View your recent emails",
                        "priority": 5
                    },
                    {
                        "action": "Compose email",
                        "service": "gmail", 
                        "description": "Create a new email",
                        "priority": 4
                    }
                ],
                "follow_up_questions": ["Would you like to check your inbox or compose a new email?"],
                "intent": "email_management",
                "confidence": 0.9
            }
    else:
        return {
            "response": "To help with emails, please connect your Gmail account first.",
            "suggestions": [{
                "action": "Connect Gmail",
                "service": "gmail",
                "description": "Enable Gmail integration",
                "priority": 5
            }],
            "follow_up_questions": [],
            "intent": "email_management",
            "confidence": 0.9
        }

def handle_slack_management_request(message: str, services: Dict[str, bool], context: ConversationContext) -> Dict:
    """Handle Slack management requests with new Slack APIs"""
    message_lower = message.lower()
    
    if services.get("slack"):
        if any(phrase in message_lower for phrase in ["channels", "list", "show"]):
            return {
                "response": "I'll show you your Slack channels!",
                "suggestions": [{
                    "action": "List Slack channels",
                    "service": "slack",
                    "description": "View your Slack channels",
                    "priority": 5
                }],
                "follow_up_questions": ["Which channel would you like to post to?"],
                "intent": "list_slack_channels",
                "confidence": 0.9
            }
        elif any(phrase in message_lower for phrase in ["post", "send", "message"]):
            return {
                "response": "I can help you post a message to Slack!",
                "suggestions": [{
                    "action": "Post to Slack",
                    "service": "slack",
                    "description": "Send a message to a channel",
                    "priority": 5
                }],
                "follow_up_questions": ["What message would you like to send?"],
                "intent": "post_slack_message",
                "confidence": 0.9
            }
        else:
            return {
                "response": "I can help you with Slack! What would you like to do?",
                "suggestions": [
                    {
                        "action": "List Slack channels",
                        "service": "slack",
                        "description": "View your channels",
                        "priority": 5
                    },
                    {
                        "action": "Post to Slack",
                        "service": "slack",
                        "description": "Send a message",
                        "priority": 4
                    }
                ],
                "follow_up_questions": ["Would you like to see your channels or post a message?"],
                "intent": "slack_management", 
                "confidence": 0.9
            }
    else:
        return {
            "response": "To help with Slack, please connect your Slack workspace first.",
            "suggestions": [{
                "action": "Connect Slack",
                "service": "slack",
                "description": "Enable Slack integration",
                "priority": 5
            }],
            "follow_up_questions": [],
            "intent": "slack_management",
            "confidence": 0.9
        }

def handle_email_request(message: str, services: Dict[str, bool], context: ConversationContext) -> Dict:
    """Handle email-related requests (LEGACY - kept for compatibility)"""
    if services.get("gmail"):
        return {
            "response": "I can help you with that email!",
            "suggestions": [{
                "action": "Compose email",
                "service": "gmail",
                "description": "Draft your message",
                "priority": 5
            }],
            "follow_up_questions": ["Who are you sending this email to?"],
            "intent": "send_email", 
            "confidence": 0.9
        }
    else:
        return {
            "response": "To help with emails, please connect your Gmail account first.",
            "suggestions": [{
                "action": "Connect Gmail",
                "service": "gmail",
                "description": "Enable email integration",
                "priority": 5
            }],
            "follow_up_questions": [],
            "intent": "send_email",
            "confidence": 0.9
        }

def handle_document_request(message: str, services: Dict[str, bool], context: ConversationContext) -> Dict:
    """Handle document/note creation requests"""
    if services.get("notion"):
        return {
            "response": "I can help you create that document in Notion!",
            "suggestions": [{
                "action": "Create Notion page",
                "service": "notion",
                "description": "Start a new document",
                "priority": 5
            }],
            "follow_up_questions": ["What's the document about?"],
            "intent": "create_document",
            "confidence": 0.9
        }
    else:
        return {
            "response": "To create documents, please connect your Notion workspace first.",
            "suggestions": [{
                "action": "Connect Notion", 
                "service": "notion",
                "description": "Enable document creation",
                "priority": 5
            }],
            "follow_up_questions": [],
            "intent": "create_document",
            "confidence": 0.9
        }

def handle_notion_pages_request(message: str, services: Dict[str, bool], context: ConversationContext) -> Dict:
    """Handle Notion pages listing requests specifically"""
    if services.get("notion"):
        return {
            "response": "I'll show you your Notion pages right away!",
            "suggestions": [{
                "action": "List Notion pages",
                "service": "notion", 
                "description": "View all your Notion pages",
                "priority": 5
            }],
            "follow_up_questions": ["Which page would you like to work on?"],
            "intent": "list_notion_pages",
            "confidence": 0.9
        }
    else:
        return {
            "response": "To view your Notion pages, I'll need access to your Notion workspace first.",
            "suggestions": [{
                "action": "Connect Notion",
                "service": "notion",
                "description": "Enable Notion integration to view your pages", 
                "priority": 5
            }],
            "follow_up_questions": [],
            "intent": "list_notion_pages",
            "confidence": 0.9
        }

def handle_calendar_events_request(message: str, services: Dict[str, bool], context: ConversationContext) -> Dict:
    """Handle calendar events listing requests specifically"""
    if services.get("google_calendar"):
        return {
            "response": "Let me fetch your calendar events for you!",
            "suggestions": [{
                "action": "Check calendar",
                "service": "google_calendar", 
                "description": "View your upcoming events",
                "priority": 5
            }],
            "follow_up_questions": ["Would you like to see events for a specific date range?"],
            "intent": "list_calendar_events",
            "confidence": 0.9
        }
    else:
        return {
            "response": "To view your calendar events, I'll need access to your Google Calendar first.",
            "suggestions": [{
                "action": "Connect Google Calendar",
                "service": "google_calendar",
                "description": "Enable Google Calendar integration", 
                "priority": 5
            }],
            "follow_up_questions": [],
            "intent": "list_calendar_events",
            "confidence": 0.9
        }

# === PRESERVED EXISTING CHAT FUNCTIONS ===

async def chat_with_mistral(message, user_id):
    # Your existing chat_with_mistral function remains unchanged
    response = None
    mistral_response = "I couldn't process the request due to an error."
    suggestions = []
    notion_pages = []
    message_lower = message.lower()

    try:
        messages = [
            {"role": "system", "content": "You are a helpful productivity assistant. Analyze the user's message, determine their sentiment (positive or negative), and provide a conversational response with actionable suggestions to improve their productivity. Suggestions should involve services like Google Calendar, Notion, Gmail, or Slack."},
            {"role": "user", "content": message}
        ]

        start_time = asyncio.get_event_loop().time()

        try:
            suggestions = generate_action_suggestions(message)
        except Exception as e:
            logger.error(f"Error generating initial suggestions for user {user_id}: {str(e)}\n{traceback.format_exc()}")
            suggestions = []

        try:
            mistral_task = asyncio.create_task(call_mistral_api(messages))
        except Exception as e:
            logger.error(f"Error creating Mistral API task for user {user_id}: {str(e)}\n{traceback.format_exc()}")
            mistral_task = asyncio.create_task(asyncio.sleep(0))
            mistral_response = "Failed to initiate Mistral API request."

        try:
            notion_task = asyncio.create_task(fetch_notion_pages(user_id=user_id)) if any(s["service"] == "notion" for s in suggestions) else asyncio.ensure_future(asyncio.sleep(0))
        except Exception as e:
            logger.error(f"Error creating Notion pages task for user {user_id}: {str(e)}\n{traceback.format_exc()}")
            notion_task = asyncio.ensure_future(asyncio.sleep(0))

        try:
            response, notion_pages = await asyncio.gather(mistral_task, notion_task, return_exceptions=True)
        except Exception as e:
            logger.error(f"Error gathering async tasks for user {user_id}: {str(e)}\n{traceback.format_exc()}")
            response = None

        if isinstance(response, Exception):
            logger.error(f"Mistral API task failed for user {user_id}: {str(response)}\n{traceback.format_exc()}")
            mistral_response = "I couldn't process the request due to a server error."
        else:
            try:
                if response is None:
                    logger.error(f"Mistral API response is None for user {user_id}")
                    mistral_response = "Mistral API returned no response."
                else:
                    mistral_response = response["choices"][0]["message"]["content"]
                    if not isinstance(mistral_response, str):
                        logger.error(f"Mistral response content is not a string for user {user_id}: {mistral_response}")
                        mistral_response = "I couldn't process the response from the assistant."
            except (KeyError, TypeError, IndexError) as e:
                logger.error(f"Error parsing Mistral API response for user {user_id}: {str(e)}\n{traceback.format_exc()}")
                mistral_response = "I couldn't process the response from the assistant."

        end_time = asyncio.get_event_loop().time()
        logger.info(f"chat_with_mistral parallel tasks completed in {end_time - start_time:.2f} seconds for user {user_id}")

        sentiment = detect_sentiment(message, mistral_response)
        confidence = 0.9

        try:
            suggestions = generate_sentiment_based_suggestions(message, sentiment, mistral_response)
        except Exception as e:
            logger.error(f"Error generating sentiment-based suggestions for user {user_id}: {str(e)}\n{traceback.format_exc()}")

        if any(s["service"] == "notion" for s in suggestions) and not isinstance(notion_task, asyncio.Future):
            try:
                notion_pages = await fetch_notion_pages(user_id=user_id)
            except Exception as e:
                logger.error(f"Error fetching Notion pages after suggestions refined for user {user_id}: {str(e)}\n{traceback.format_exc()}")
                notion_pages = []

        if not isinstance(notion_pages, list):
            logger.warning(f"notion_pages is not a list for user {user_id}: {notion_pages}")
            notion_pages = []
        notion_page_options = [{"id": page["id"], "title": page["title"]} for page in notion_pages]

        crisp_response = extract_crisp_response(mistral_response, sentiment)
        contextual_response = generate_contextual_response(message_lower, suggestions, sentiment)
        final_response = f"{crisp_response} {contextual_response}"

        return {
            "message": message,
            "sentiment": sentiment,
            "confidence": confidence,
            "response": final_response,
            "suggestions": suggestions,
            "notion_pages": notion_page_options
        }
    except Exception as e:
        logger.error(f"Error in chat_with_mistral for user {user_id}: {str(e)}\n{traceback.format_exc()}")
        # Fallback logic
        suggestions = generate_action_suggestions(message)
        try:
            notion_pages = await fetch_notion_pages(user_id=user_id) if any(s["service"] == "notion" for s in suggestions) else []
        except Exception as e:
            logger.error(f"Error fetching Notion pages in fallback for user {user_id}: {str(e)}\n{traceback.format_exc()}")
            notion_pages = []

        if not isinstance(notion_pages, list):
            logger.warning(f"notion_pages is not a list in fallback for user {user_id}: {notion_pages}")
            notion_pages = []
        notion_page_options = [{"id": page["id"], "title": page["title"]} for page in notion_pages]

        sentiment = detect_sentiment(message)
        confidence = 0.9

        try:
            suggestions = generate_sentiment_based_suggestions(message, sentiment)
        except Exception as e:
            logger.error(f"Error generating sentiment-based suggestions in fallback for user {user_id}: {str(e)}\n{traceback.format_exc()}")

        crisp_response = extract_crisp_response("Sorry, I couldn't process your request right now.", sentiment)
        contextual_response = generate_contextual_response(message_lower, suggestions, sentiment)
        final_response = f"{crisp_response} {contextual_response}"

        return {
            "message": message,
            "sentiment": sentiment,
            "confidence": confidence,
            "response": final_response,
            "suggestions": suggestions,
            "notion_pages": notion_page_options
        }

async def process_user_message(message, user_id):
    """Process user message and return structured response (PRESERVED FUNCTION)"""
    try:
        message_lower = message.lower()
        updates = []

        start_date = None
        end_date = None
        if "today's events" in message_lower or "what are my events today" in message_lower:
            start_date = date.today().strftime('%Y-%m-%d')
            end_date = start_date
            date_range = "today"
        elif "tomorrow" in message_lower:
            tomorrow = date.today() + timedelta(days=1)
            start_date = tomorrow.strftime('%Y-%m-%d')
            end_date = start_date
            date_range = "tomorrow"
        elif "all the available events" in message_lower:
            start_date = date.today().strftime('%Y-%m-%d')
            end_date = (date.today() + timedelta(days=30)).strftime('%Y-%m-%d')
            date_range = "the next 30 days"
        else:
            date_range = "tomorrow"

        if "updates" in message_lower or "events" in message_lower:
            start_time = asyncio.get_event_loop().time()
            events_result = await fetch_calendar_events(start_date, end_date, user_id=user_id)
            end_time = asyncio.get_event_loop().time()
            logger.info(f"fetch_calendar_events completed in {end_time - start_time:.2f} seconds for user {user_id}")

            if isinstance(events_result, dict) and events_result.get("requires_auth"):
                return {
                    "response": "Authentication required to access Google Calendar.",
                    "requires_auth": True,
                    "auth_url": events_result["auth_url"]
                }
            events = events_result
            suggestions = []
            if events:
                response = f"Here's a summary of your updates for {date_range}:\n\n"
                for idx, event in enumerate(events, 1):
                    event_summary = event["summary"].strip()
                    start_time = event["start"]
                    updates.append(f"{idx}. Meeting: {event_summary} at {start_time}. You can join the meeting via this Zoom link.")
                    event_suggestions = generate_action_suggestions(event_summary)
                    for suggestion in event_suggestions:
                        suggestion["event_summary"] = event_summary
                        suggestion["calendar_link"] = event["link"]
                    suggestions.extend(event_suggestions)
            else:
                updates.append(f"No calendar events found for {date_range}.")

            start_time = asyncio.get_event_loop().time()
            notion_tasks = await fetch_notion_tasks(user_id=user_id)
            end_time = asyncio.get_event_loop().time()
            logger.info(f"fetch_notion_tasks completed in {end_time - start_time:.2f} seconds for user {user_id}")

            if notion_tasks:
                for idx, task in enumerate(notion_tasks, len(updates) + 1):
                    updates.append(f"{idx}. In Notion, there's a task assigned to you for {task['title']}. You can find the details in the \"{task['section']}\" section.")

            start_time = asyncio.get_event_loop().time()
            drive_deadlines = await fetch_drive_deadlines(user_id=user_id)
            end_time = asyncio.get_event_loop().time()
            logger.info(f"fetch_drive_deadlines completed in {end_time - start_time:.2f} seconds for user {user_id}")

            if drive_deadlines:
                for idx, deadline in enumerate(drive_deadlines, len(updates) + 1):
                    updates.append(f"{idx}. Don't forget about the deadline for {deadline['title']}. You can work on it in the Google Drive folder labeled '{deadline['folder']}'.")

            if updates:
                response = "\n\n".join(updates)
                response += "\n\nRemember, it's always a good idea to check your Gmail inbox for any last-minute updates or changes. If you need help managing your tasks or scheduling, feel free to ask. I'm here to assist you!"
            else:
                response = f"No updates found for {date_range}."

            notion_pages = await fetch_notion_pages(user_id=user_id) if any(s["service"] == "notion" for s in suggestions) else []
            if not isinstance(notion_pages, list):
                logger.warning(f"notion_pages is not a list in process_user_message for user {user_id}: {notion_pages}")
                notion_pages = []
            notion_page_options = [{"id": page["id"], "title": page["title"]} for page in notion_pages]

            return {
                "response": response.strip(),
                "suggestions": suggestions,
                "notion_pages": notion_page_options if suggestions else []
            }

        else:
            return await chat_with_mistral(message, user_id)
    except Exception as e:
        logger.error(f"Error processing user message for user {user_id}: {str(e)}\n{traceback.format_exc()}")
        raise
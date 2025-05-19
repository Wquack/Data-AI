from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
import logging
import requests
from datetime import date, timedelta, datetime

logger = logging.getLogger(__name__)

# Load model and tokenizer
MODEL_NAME = "distilbert-base-uncased-finetuned-sst-2-english"
try:
    logger.info("Loading model and tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
    logger.info("Model and tokenizer loaded successfully")
except Exception as e:
    logger.error(f"Failed to load model: {e}")
    raise

def fetch_calendar_events(start_date=None, end_date=None):
    """Fetch events for a specific date range from the backend API."""
    try:
        url = "http://localhost:5000/list_calendar_events"
        params = {}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        response = requests.get(url, params=params)
        response.raise_for_status()
        events = response.json().get("events", [])
        return events
    except requests.exceptions.HTTPError as e:
        if response.status_code == 401 and 'action' in response.json() and response.json()['action'] == 'Requires authentication':
            return {"requires_auth": True, "auth_url": response.json().get("auth_url")}
        logger.error(f"Error fetching calendar events: {e}")
        raise
    except Exception as e:
        logger.error(f"Error fetching calendar events: {e}")
        raise

def fetch_notion_pages():
    """Fetch accessible Notion pages from the backend API."""
    try:
        response = requests.get("http://localhost:5000/list_notion_pages")
        response.raise_for_status()
        pages = response.json().get("pages", [])
        return pages
    except Exception as e:
        logger.error(f"Error fetching Notion pages: {e}")
        return []

def generate_action_suggestions(event_summary):
    """Generate multiple context-aware action suggestions based on the event summary."""
    event_summary = event_summary.lower()
    suggestions = []

    # Base suggestion logic on event keywords
    if 'meeting' in event_summary or 'conference' in event_summary:
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
    elif 'deadline' in event_summary or 'project' in event_summary:
        suggestions.append({
            "action": "Write important notes in Notion",
            "service": "notion",
            "description": "Create a Notion page to outline tasks for the deadline."
        })
        suggestions.append({
            "action": "Plan schedule",
            "service": "slack",
            "description": "Post a message in Slack to plan the schedule."
        })
    elif 'appointment' in event_summary or 'doctor' in event_summary:
        suggestions.append({
            "action": "Bring documents",
            "service": "gmail",
            "description": "Draft an email reminder to bring documents for the appointment."
        })
    else:
        suggestions.append({
            "action": "Plan schedule",
            "service": "slack",
            "description": "Post a message in Slack to plan the schedule."
        })

    return suggestions

def generate_sentiment_based_suggestions(message, sentiment):
    """Generate action suggestions based on sentiment predicted by DistilBERT."""
    suggestions = []
    message_lower = message.lower()

    if sentiment == "positive":
        # Positive sentiment: Suggest proactive actions
        suggestions.append({
            "action": "Schedule a follow-up meeting",
            "service": "calendar",
            "description": "Schedule a follow-up meeting on Google Calendar to keep the momentum going."
        })
        suggestions.append({
            "action": "Write important notes in Notion",
            "service": "notion",
            "description": "Create a Notion page to outline your next steps."
        })
    else:
        # Negative sentiment: Suggest reflective or planning actions
        suggestions.append({
            "action": "Write important notes in Notion",
            "service": "notion",
            "description": "Create a Notion page to jot down your concerns or ideas."
        })
        suggestions.append({
            "action": "Send an email to discuss concerns",
            "service": "gmail",
            "description": "Draft an email to a colleague to discuss your concerns."
        })

    return suggestions

def get_recommendation(event_summary):
    """Generate a single task recommendation using DistilBERT (for backward compatibility)."""
    inputs = tokenizer(event_summary, return_tensors="pt", padding=True, truncation=True)
    logger.info(f"Tokenized input: {inputs['input_ids']}")
    with torch.no_grad():
        outputs = model(**inputs)
    logits = outputs.logits
    predicted_class = torch.argmax(logits, dim=1).item()
    logger.info(f"Predicted class: {predicted_class}")
    suggestions = generate_action_suggestions(event_summary)
    return suggestions[0]["action"] if suggestions else "No task recommended"

def chat_with_distilbert(message):
    """Directly interact with DistilBERT to classify sentiment and return a response with actionable suggestions."""
    try:
        inputs = tokenizer(message, return_tensors="pt", padding=True, truncation=True)
        logger.info(f"Tokenized input: {inputs['input_ids']}")
        with torch.no_grad():
            outputs = model(**inputs)
        logits = outputs.logits
        predicted_class = torch.argmax(logits, dim=1).item()
        logger.info(f"Predicted class for message '{message}': {predicted_class}")
        
        # Map the predicted class to a sentiment label
        sentiment = "positive" if predicted_class == 1 else "negative"
        confidence = float(torch.softmax(logits, dim=1)[0][predicted_class])
        
        # Generate actionable suggestions based on sentiment
        suggestions = generate_sentiment_based_suggestions(message, sentiment)
        
        # Fetch Notion pages for Notion-related actions
        notion_pages = fetch_notion_pages() if any(s["service"] == "notion" for s in suggestions) else []
        notion_page_options = [{"id": page["id"], "title": page["title"]} for page in notion_pages]

        response = {
            "message": message,
            "sentiment": sentiment,
            "confidence": confidence,
            "conversational_response": "Looks like you're feeling positive! Let's take some actions to keep the momentum going." if predicted_class == 1 else "Seems like you're feeling a bit negative. Let's take some actions to help you reflect.",
            "suggestions": suggestions,
            "notion_pages": notion_page_options
        }
        return response
    except Exception as e:
        logger.error(f"Error in chat_with_distilbert: {e}")
        raise

def process_user_message(message):
    """Process a user message and return a response with multiple suggested actions."""
    try:
        message_lower = message.lower()
        
        # Determine the target date range
        start_date = None
        end_date = None
        if "today's events" in message_lower or "what are my events today" in message_lower:
            start_date = date.today().strftime('%Y-%m-%d')
            end_date = start_date
        elif "tomorrow" in message_lower:
            tomorrow = date.today() + timedelta(days=1)
            start_date = tomorrow.strftime('%Y-%m-%d')
            end_date = start_date
        elif "all the available events" in message_lower:
            start_date = date.today().strftime('%Y-%m-%d')
            end_date = (date.today() + timedelta(days=30)).strftime('%Y-%m-%d')
        
        # Intent: Fetch events
        if "events" in message_lower:
            events_result = fetch_calendar_events(start_date, end_date)
            # Check if authentication is required
            if isinstance(events_result, dict) and events_result.get("requires_auth"):
                return {
                    "response": "Authentication required to access Google Calendar.",
                    "requires_auth": True,
                    "auth_url": events_result["auth_url"]
                }
            events = events_result
            if not events:
                date_range = "today" if "today" in message_lower else "tomorrow" if "tomorrow" in message_lower else "the next 30 days"
                return {"response": f"I couldn't find any events for {date_range}."}
            
            date_range = "today" if "today" in message_lower else "tomorrow" if "tomorrow" in message_lower else "the next 30 days"
            response = f"Here are your events for {date_range}:\n"
            suggestions = []
            for event in events:
                event_summary = event["summary"].strip()  # Remove extra spaces
                start_time = event["start"]
                response += f"- {event_summary} at {start_time}\n"
                # Generate multiple action suggestions for each event
                event_suggestions = generate_action_suggestions(event_summary)
                for suggestion in event_suggestions:
                    suggestion["event_summary"] = event_summary
                    suggestion["calendar_link"] = event["link"]
                suggestions.extend(event_suggestions)
            
            # Fetch Notion pages for suggestions involving Notion
            notion_pages = fetch_notion_pages()
            notion_page_options = [{"id": page["id"], "title": page["title"]} for page in notion_pages]
            
            return {
                "response": response.strip(),
                "suggestions": suggestions,
                "notion_pages": notion_page_options if suggestions else []
            }
        
        # Intent: General recommendation based on user input
        else:
            suggestions = generate_action_suggestions(message)
            if not suggestions:
                return {"response": "I don't have any specific recommendations for that. Try asking about your events!"}
            
            notion_pages = fetch_notion_pages() if any(s["service"] == "notion" for s in suggestions) else []
            notion_page_options = [{"id": page["id"], "title": page["title"]} for page in notion_pages]
            
            return {
                "response": f"I have some suggestions for '{message}':",
                "suggestions": [{"event_summary": message, **s} for s in suggestions],
                "notion_pages": notion_page_options
            }
    except Exception as e:
        logger.error(f"Error processing user message: {e}")
        return {"response": "Sorry, I encountered an error. Please try again."}
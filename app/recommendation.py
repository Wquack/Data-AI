from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
import logging
import requests

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

def fetch_calendar_events():
    """Fetch today's events from the backend API."""
    try:
        response = requests.get("http://localhost:5000/list_calendar_events")
        response.raise_for_status()
        events = response.json().get("events", [])
        return events
    except Exception as e:
        logger.error(f"Error fetching calendar events: {e}")
        return []

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

def select_task(event_summary, predicted_class):
    """Select task based on event summary keywords and model prediction."""
    event_summary = event_summary.lower()
    if 'meeting' in event_summary or 'conference' in event_summary:
        return "Prepare slides"
    elif 'deadline' in event_summary or 'project' in event_summary:
        return "Review notes"
    elif 'appointment' in event_summary or 'doctor' in event_summary:
        return "Bring documents"
    else:
        return "Plan schedule" if predicted_class == 1 else "No task recommended"

def get_recommendation(event_summary):
    """Generate task recommendation using DistilBERT."""
    inputs = tokenizer(event_summary, return_tensors="pt", padding=True, truncation=True)
    logger.info(f"Tokenized input: {inputs['input_ids']}")
    with torch.no_grad():
        outputs = model(**inputs)
    logits = outputs.logits
    predicted_class = torch.argmax(logits, dim=1).item()
    logger.info(f"Predicted class: {predicted_class}")
    return select_task(event_summary, predicted_class)

def process_user_message(message):
    """Process a user message and return a response with suggested actions."""
    try:
        message_lower = message.lower()
        
        # Intent: Fetch today's events
        if "today's events" in message_lower or "what are my events" in message_lower:
            events = fetch_calendar_events()
            if not events:
                return {"response": "I couldn't find any events for today."}
            
            response = "Here are your events for today:\n"
            suggestions = []
            for event in events:
                event_summary = event["summary"]
                start_time = event["start"]
                response += f"- {event_summary} at {start_time}\n"
                # Suggest an action for each event
                recommendation = get_recommendation(event_summary)
                if recommendation != "No task recommended":
                    suggestions.append({
                        "event_summary": event_summary,
                        "recommendation": recommendation,
                        "prompt": f"{recommendation} for '{event_summary}'"
                    })
            
            # Fetch Notion pages for suggestions involving Notion (e.g., "Review notes")
            notion_pages = fetch_notion_pages()
            notion_page_options = [{"id": page["id"], "title": page["title"]} for page in notion_pages]
            
            return {
                "response": response.strip(),
                "suggestions": suggestions,
                "notion_pages": notion_page_options if suggestions else []
            }
        
        # Intent: General recommendation based on user input
        else:
            recommendation = get_recommendation(message)
            if recommendation == "No task recommended":
                return {"response": "I don't have a specific recommendation for that. Try asking about your events!"}
            
            notion_pages = fetch_notion_pages() if recommendation == "Review notes" else []
            notion_page_options = [{"id": page["id"], "title": page["title"]} for page in notion_pages]
            
            return {
                "response": f"I suggest: {recommendation} for '{message}'.",
                "suggestions": [{
                    "event_summary": message,
                    "recommendation": recommendation,
                    "prompt": f"{recommendation} for '{message}'"
                }],
                "notion_pages": notion_page_options
            }
    except Exception as e:
        logger.error(f"Error processing user message: {e}")
        return {"response": "Sorry, I encountered an error. Please try again."}
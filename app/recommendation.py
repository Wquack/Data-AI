import logging
import aiohttp
import asyncio
import traceback
from datetime import date, timedelta
from .mistral_api import call_mistral_api
from cachetools import TTLCache

logger = logging.getLogger(__name__)

notion_pages_cache = TTLCache(maxsize=100, ttl=300)

async def fetch_calendar_events(start_date=None, end_date=None, user_id=None, timeout=10):
    try:
        url = "http://localhost:5000/list_calendar_events"
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
            return {"requires_auth": True, "auth_url": e.message.get("auth_url", "http://localhost:5000/auth/google")}
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
            async with session.get("http://localhost:5000/list_notion_pages", timeout=timeout) as response:
                response.raise_for_status()
                pages = await response.json()
                pages = pages.get("pages", [])
                end_time = asyncio.get_event_loop().time()
                logger.info(f"fetch_notion_pages took {end_time - start_time:.2f} seconds for user {user_id}")
                notion_pages_cache[cache_key] = pages
                return pages
    except Exception as e:
        logger.error(f"Error fetching Notion pages for user {user_id}: {str(e)}\n{traceback.format_exc()}")
        return []  # Ensure we return an empty list on failure

async def fetch_notion_tasks(user_id=None, timeout=10):
    try:
        async with aiohttp.ClientSession() as session:
            start_time = asyncio.get_event_loop().time()
            async with session.get("http://localhost:5000/list_notion_tasks", timeout=timeout) as response:
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
            async with session.get("http://localhost:5000/list_drive_deadlines", timeout=timeout) as response:
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
    suggestions = []
    message_lower = message.lower()
    mistral_lower = mistral_response.lower()

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
        if 'overwhelmed' in message_lower or 'stress' in message_lower or 'overwhelmed' in mistral_lower:
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
        elif 'project' in message_lower or 'deadline' in mistral_lower:
            suggestions.append({
                "action": "Break down tasks in Notion",
                "service": "notion",
                "description": "Create a Notion page to break down your project tasks."
            })
            suggestions.append({
                "action": "Ask for an extension via email",
                "service": "gmail",
                "description": "Draft an email to request a deadline extension."
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

async def chat_with_mistral(message, user_id):
    # Define default values for variables used in all paths
    mistral_response = "I couldn't process the request due to an error."
    suggestions = []
    notion_pages = []

    try:
        messages = [
            {"role": "system", "content": "You are a helpful productivity assistant. Analyze the user's message, determine their sentiment (positive or negative), and provide a conversational response with actionable suggestions to improve their productivity. Suggestions should involve services like Google Calendar, Notion, Gmail, or Slack."},
            {"role": "user", "content": message}
        ]

        start_time = asyncio.get_event_loop().time()

        # Generate suggestions based on message content immediately
        try:
            suggestions = generate_action_suggestions(message)
        except Exception as e:
            logger.error(f"Error generating initial suggestions for user {user_id}: {str(e)}\n{traceback.format_exc()}")
            suggestions = []

        # Fetch Mistral response and Notion pages in parallel
        try:
            mistral_task = asyncio.create_task(call_mistral_api(messages))
        except Exception as e:
            logger.error(f"Error creating Mistral API task for user {user_id}: {str(e)}\n{traceback.format_exc()}")
            mistral_task = asyncio.create_task(asyncio.sleep(0))

        try:
            notion_task = asyncio.create_task(fetch_notion_pages(user_id=user_id)) if any(s["service"] == "notion" for s in suggestions) else asyncio.ensure_future(asyncio.sleep(0))
        except Exception as e:
            logger.error(f"Error creating Notion pages task for user {user_id}: {str(e)}\n{traceback.format_exc()}")
            notion_task = asyncio.ensure_future(asyncio.sleep(0))

        # Wait for both tasks to complete
        try:
            response, notion_pages = await asyncio.gather(mistral_task, notion_task, return_exceptions=True)
        except Exception as e:
            logger.error(f"Error gathering async tasks for user {user_id}: {str(e)}\n{traceback.format_exc()}")
            response = None

        # Check for errors in the tasks
        if isinstance(response, Exception):
            logger.error(f"Mistral API task failed for user {user_id}: {str(response)}\n{traceback.format_exc()}")
            mistral_response = "I couldn't process the request due to a server error."
        else:
            try:
                if response is None:
                    raise ValueError("Mistral API response is None")
                mistral_response = response["choices"][0]["message"]["content"] 
                if not isinstance(mistral_response, str):
                    logger.error(f"Mistral response content is not a string for user {user_id}: {mistral_response}")
                    mistral_response = "I couldn't process the response from the assistant."
            except (KeyError, TypeError, IndexError, ValueError) as e:
                logger.error(f"Error parsing Mistral API response for user {user_id}: {str(e)}\n{traceback.format_exc()}")
                mistral_response = "I couldn't process the response from the assistant."

        end_time = asyncio.get_event_loop().time()
        logger.info(f"chat_with_mistral parallel tasks completed in {end_time - start_time:.2f} seconds for user {user_id}")

        sentiment = "positive" if "positive" in mistral_response.lower() else "negative"
        confidence = 0.9

        # Refine suggestions with sentiment and Mistral response
        try:
            refined_suggestions = generate_sentiment_based_suggestions(message, sentiment, mistral_response)
            if refined_suggestions:
                suggestions = refined_suggestions
            else:
                suggestions = generate_action_suggestions(message, mistral_response)
        except Exception as e:
            logger.error(f"Error refining suggestions for user {user_id}: {str(e)}\n{traceback.format_exc()}")

        # If suggestions changed and we need Notion pages but haven't fetched them yet
        if any(s["service"] == "notion" for s in suggestions) and not isinstance(notion_task, asyncio.Future):
            try:
                notion_pages = await fetch_notion_pages(user_id=user_id)
            except Exception as e:
                logger.error(f"Error fetching Notion pages after suggestions refined for user {user_id}: {str(e)}\n{traceback.format_exc()}")
                notion_pages = []

        # Ensure notion_pages is a list before iterating
        if not isinstance(notion_pages, list):
            logger.warning(f"notion_pages is not a list for user {user_id}: {notion_pages}")
            notion_pages = []
        notion_page_options = [{"id": page["id"], "title": page["title"]} for page in notion_pages]

        return {
            "message": message,
            "sentiment": sentiment,
            "confidence": confidence,
            "response": mistral_response,
            "suggestions": suggestions,
            "notion_pages": notion_page_options
        }
    except Exception as e:
        logger.error(f"Error in chat_with_mistral for user {user_id}: {str(e)}\n{traceback.format_exc()}")
        # Fallback response if Mistral fails
        suggestions = generate_action_suggestions(message)
        try:
            notion_pages = await fetch_notion_pages(user_id=user_id) if any(s["service"] == "notion" for s in suggestions) else []
        except Exception as e:
            logger.error(f"Error fetching Notion pages in fallback for user {user_id}: {str(e)}\n{traceback.format_exc()}")
            notion_pages = []

        # Ensure notion_pages is a list before iterating
        if not isinstance(notion_pages, list):
            logger.warning(f"notion_pages is not a list in fallback for user {user_id}: {notion_pages}")
            notion_pages = []
        notion_page_options = [{"id": page["id"], "title": page["title"]} for page in notion_pages]

        return {
            "message": message,
            "sentiment": "unknown",
            "confidence": 0.0,
            "response": "Sorry, I couldn't process your request right now. Let's plan your next steps instead.",
            "suggestions": suggestions,
            "notion_pages": notion_page_options
        }

async def process_user_message(message, user_id):
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
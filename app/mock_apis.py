import requests
import logging

logger = logging.getLogger(__name__)
MOCK_API_URL = "https://httpbin.org/post"

def mock_notion_create_page(event_summary):
    """Mock Notion createPage."""
    response = requests.post(MOCK_API_URL, json={
        "title": f"Notes for {event_summary}",
        "body": "Review relevant project notes.",
        "userId": 1
    })
    logger.info(f"Mock Notion API response: {response.status_code}")
    return {"action": "Created note", "details": response.json()}

def mock_gmail_send(event_summary):
    """Mock Gmail users.messages.send."""
    response = requests.post(MOCK_API_URL, json={
        "title": f"Documents for {event_summary}",
        "body": "Reminder: Gather required documents.",
        "userId": 1
    })
    logger.info(f"Mock Gmail API response: {response.status_code}")
    return {"action": "Sent email reminder", "details": response.json()}

def mock_slack_post(event_summary):
    """Mock Slack chat.postMessage."""
    response = requests.post(MOCK_API_URL, json={
        "title": f"Schedule for {event_summary}",
        "body": "Plan the event schedule.",
        "userId": 1
    })
    logger.info(f"Mock Slack API response: {response.status_code}")
    return {"action": "Sent Slack message", "details": response.json()}
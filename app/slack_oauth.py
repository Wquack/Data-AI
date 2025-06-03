# slack_oauth.py

import os
import requests
from dotenv import load_dotenv
from utils.token_store import save_tokens, load_tokens  # ✅ Import both functions

# # TEMP: remove once user_id is dynamically resolved from session or Google profile
# DUMMY_USER_ID = "shrey@gmail.com"

load_dotenv()

SLACK_CLIENT_ID = os.getenv("SLACK_CLIENT_ID")
SLACK_CLIENT_SECRET = os.getenv("SLACK_CLIENT_SECRET")
SLACK_REDIRECT_URI = "https://backend.chat-ai.co/auth/slack/callback"
def get_slack_auth_url():
    return (
        f"https://slack.com/oauth/v2/authorize"
        f"?client_id={SLACK_CLIENT_ID}"
        f"&scope=chat:write,users:read"
        f"&redirect_uri={SLACK_REDIRECT_URI}"
    )

def handle_slack_callback(code, user_id):
    url = "https://slack.com/api/oauth.v2.access"
    data = {
        "client_id": SLACK_CLIENT_ID,
        "client_secret": SLACK_CLIENT_SECRET,
        "code": code,
        "redirect_uri": SLACK_REDIRECT_URI
    }
    response = requests.post(url, data=data).json()
    if not response.get("ok"):
        raise Exception(f"Slack auth failed: {response.get('error')}")

    save_tokens(user_id, {
        "slack": {
            "access_token": response["access_token"],
            "team": response["team"]["name"],
            "user_id": response["authed_user"]["id"]
        }
    })

    return {
        "access_token": response["access_token"],
        "user_id": response["authed_user"]["id"],
        "team": response["team"]["name"]
    }


    save_tokens(user_id, {
        "slack": {
            "access_token": response["access_token"],
            "team": response["team"]["name"],
            "user_id": response["authed_user"]["id"]
        }
    })

    return {
        "access_token": response["access_token"],
        "user_id": response["authed_user"]["id"],
        "team": response["team"]["name"]
    }


def post_to_slack(message, user_id=None):
    try:
        if user_id is None:
            raise Exception("User ID is required to post to Slack.")
        tokens = load_tokens(user_id)
        slack_token = tokens.get("slack", {}).get("access_token")
        if not slack_token:
            raise Exception("Slack token not found for this user.")

        headers = {
            "Authorization": f"Bearer {slack_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "channel": "#general",
            "text": message
        }
        response = requests.post("https://slack.com/api/chat.postMessage", json=payload, headers=headers)
        response.raise_for_status()
        result = response.json()
        if not result.get("ok"):
            raise Exception(f"Slack API error: {result.get('error')}")
        return {"action": "Posted to Slack", "details": {"ts": result["ts"]}}
    except Exception as e:
        raise Exception(f"Error posting to Slack: {e}")

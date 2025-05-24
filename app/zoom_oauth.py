import os
import requests
from dotenv import load_dotenv
from utils.token_store import save_tokens

load_dotenv()

ZOOM_CLIENT_ID = os.getenv("ZOOM_CLIENT_ID")
ZOOM_CLIENT_SECRET = os.getenv("ZOOM_CLIENT_SECRET")
ZOOM_REDIRECT_URI = "http://localhost:5000/auth/zoom/callback"

def get_zoom_auth_url():
    return (
        "https://zoom.us/oauth/authorize"
        f"?response_type=code"
        f"&client_id={ZOOM_CLIENT_ID}"
        f"&redirect_uri={ZOOM_REDIRECT_URI}"
    )

def handle_zoom_callback(code, user_id):
    url = "https://zoom.us/oauth/token"
    
    if not ZOOM_CLIENT_ID or not ZOOM_CLIENT_SECRET:
        raise Exception("ZOOM_CLIENT_ID or ZOOM_CLIENT_SECRET not set")

    # Use proper tuple-based basic auth instead of manually building headers
    auth = (str(ZOOM_CLIENT_ID), str(ZOOM_CLIENT_SECRET)) if ZOOM_CLIENT_ID and ZOOM_CLIENT_SECRET else None

    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": ZOOM_REDIRECT_URI
    }

    # Debug info (optional)
    print("Requesting Zoom token exchange with:")
    print(f"  client_id: {ZOOM_CLIENT_ID}")
    print(f"  redirect_uri: {ZOOM_REDIRECT_URI}")
    print(f"  code: {code}")

    response = requests.post(url, data=data, auth=auth)

    if response.status_code != 200:
        print("Zoom token response error:", response.text)
        raise Exception(f"Zoom token error: {response.json()}")

    zoom_tokens = response.json()

    save_tokens(user_id, {
        "zoom": {
            "access_token": zoom_tokens.get("access_token"),
            "refresh_token": zoom_tokens.get("refresh_token")
        }
    })
def refresh_zoom_token(user_id):
    from utils.token_store import load_tokens, save_tokens

    tokens = load_tokens(user_id)
    refresh_token = tokens.get("zoom", {}).get("refresh_token")
    if not refresh_token:
        raise Exception("No refresh token found for user.")

    url = "https://zoom.us/oauth/token"
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }
    if ZOOM_CLIENT_ID and ZOOM_CLIENT_SECRET:
        auth = (str(ZOOM_CLIENT_ID), str(ZOOM_CLIENT_SECRET))
        response = requests.post(url, data=data, auth=auth)
    else:
        response = requests.post(url, data=data)
    if response.status_code != 200:
        raise Exception(f"Failed to refresh Zoom token: {response.json()}")

    new_tokens = response.json()
    save_tokens(user_id, {
        "zoom": {
            "access_token": new_tokens["access_token"],
            "refresh_token": new_tokens["refresh_token"]
        }
    })

    return new_tokens["access_token"]


    return zoom_tokens

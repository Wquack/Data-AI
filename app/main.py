import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from flask import request, jsonify, redirect, url_for, send_from_directory
from . import create_app
from .recommendation import get_recommendation, process_user_message, chat_with_distilbert
from .calendar_api import create_calendar_event, get_auth_url, handle_oauth_callback, list_calendar_events, get_calendar_service, get_drive_service, upload_to_drive, send_gmail, create_calendar_event_with_zoom
from .encryption import encrypt_data
from .slack_oauth import get_slack_auth_url, handle_slack_callback, post_to_slack
from .zoom_oauth import get_zoom_auth_url, handle_zoom_callback
from .notion_api import create_notion_page, list_notion_pages
from .powerpoint_api import create_powerpoint_slides
import logging
from utils.token_store import load_tokens
import requests
from datetime import date, datetime, timedelta
from urllib.parse import urlencode
from utils.token_store import load_tokens
from .zoom_oauth import refresh_zoom_token  
import requests
from datetime import datetime, timedelta

app = create_app()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.route('/recommend', methods=['POST'])
def recommend_task():
    try:
        data = request.json
        event_summary = data.get('event_summary', '')
        if not isinstance(event_summary, str) or not event_summary.strip():
            logger.warning("Invalid event summary")
            return jsonify({'error': 'Event summary must be a non-empty string'}), 400

        logger.info(f"Received event summary: {event_summary}")
        encrypted_summary = encrypt_data(event_summary)
        logger.info("Input encrypted")

        recommendation = get_recommendation(event_summary)
        return jsonify({'recommendation': recommendation})
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/chat', methods=['POST'])
def chat_endpoint():
    try:
        data = request.json
        message = data.get('message', '')
        if not isinstance(message, str) or not message.strip():
            logger.warning("Invalid message")
            return jsonify({'error': 'Message must be a non-empty string'}), 400

        logger.info(f"Received user message: {message}")
        result = process_user_message(message)
        logger.info(f"Chat endpoint response: {result}")
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/chat_with_distilbert', methods=['POST'])
def chat_with_distilbert_endpoint():
    try:
        data = request.json
        message = data.get('message', '')
        if not isinstance(message, str) or not message.strip():
            logger.warning("Invalid message")
            return jsonify({'error': 'Message must be a non-empty string'}), 400

        logger.info(f"Received user message for DistilBERT: {message}")
        result = chat_with_distilbert(message)
        logger.info(f"DistilBERT response: {result}")
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in chat_with_distilbert endpoint: {e}")
        return jsonify({'error': str(e)}), 500

# ✅ make sure this import exists

@app.route('/create_zoom_meeting', methods=['POST'])
def create_zoom_meeting():
    try:
        data = request.json
        topic = data.get('topic', 'AI Meeting')
        start_time = data.get('start_time')  # ISO 8601 format: "2025-05-21T15:00:00"
        duration = data.get('duration', 30)  # in minutes

        user_id = request.headers.get("X-User-ID")
        if not user_id:
            return jsonify({"error": "Missing X-User-ID"}), 400

        tokens = load_tokens(user_id)
        access_token = tokens.get("zoom", {}).get("access_token")
        if not access_token:
            return jsonify({"error": "Zoom token not found for this user"}), 401

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

        # First attempt to create the meeting
        response = requests.post(
            "https://api.zoom.us/v2/users/me/meetings",
            headers=headers,
            json=meeting_data
        )

        # 🔁 If token is expired, refresh and retry once
        if response.status_code == 401 and response.json().get("code") == 124:
            access_token = refresh_zoom_token(user_id)
            headers["Authorization"] = f"Bearer {access_token}"
            response = requests.post(
                "https://api.zoom.us/v2/users/me/meetings",
                headers=headers,
                json=meeting_data
            )

        if response.status_code != 201:
            return jsonify({"error": "Zoom API error", "details": response.json()}), 500

        result = response.json()
        return jsonify({
            "message": "Meeting created",
            "zoom_link": result["join_url"],
            "meeting_id": result["id"],
            "start_time": result["start_time"]
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route('/list_notion_pages', methods=['GET'])
def list_notion_pages_endpoint():
    try:
        pages = list_notion_pages()
        return jsonify({'pages': pages})
    except Exception as e:
        logger.error(f"Error listing Notion pages: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/list_calendar_events', methods=['GET', 'POST'])
def list_calendar_events_endpoint():
    try:
        if not os.path.exists('token.json'):
            try:
                auth_url = get_auth_url()
                return jsonify({'action': 'Requires authentication', 'auth_url': auth_url}), 401
            except Exception as e:
                logger.error(f"Failed to generate auth URL: {e}")
                return jsonify({'error': f"Failed to initiate authentication: {str(e)}"}), 500

        start_date = end_date = event_type = attendees = date_param = None

        if request.method == 'GET':
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            event_type = request.args.get('event_type')
            attendees = request.args.get('attendees')
            date_param = request.args.get('date')
        else:
            data = request.get_json(silent=True) or {}
            start_date = data.get('start_date', request.args.get('start_date'))
            end_date = data.get('end_date', request.args.get('end_date'))
            event_type = data.get('event_type', request.args.get('event_type'))
            attendees = data.get('attendees', request.args.get('attendees'))
            date_param = data.get('date', request.args.get('date'))

        if not start_date and date_param:
            start_date = end_date = date_param

        events = list_calendar_events(start_date, end_date, event_type, attendees)
        return jsonify({'events': events})
    except Exception as e:
        logger.error(f"Error listing calendar events: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/execute_task', methods=['POST'])
def execute_task_endpoint():
    try:
        data = request.json
        action = data.get('action', '')
        event_summary = data.get('event_summary', '') or data.get('topic', 'AI Meeting')
        parent_page_id = data.get('parent_page_id')
        recipient = data.get('recipient', '')
        slack_channel = data.get('slack_channel')
        start_time = data.get('start_time')  # "2025-05-21T15:00:00"
        duration = data.get('duration', 30)
        user_id = request.headers.get("X-User-ID")

        if not user_id:
            return jsonify({"error": "Missing X-User-ID"}), 400
        if not action.strip() or not event_summary.strip():
            return jsonify({'error': 'Action and event summary must be non-empty strings'}), 400

        logger.info(f"Executing action: {action} for user: {user_id}")

        # === 🔹 Setup full Zoom meeting + Calendar ===
        if action == "Setup full Zoom meeting":
            # Zoom meeting
            tokens = load_tokens(user_id)
            access_token = tokens.get("zoom", {}).get("access_token")
            if not access_token:
                return jsonify({"error": "Zoom token not found"}), 401

            meeting_payload = {
                "topic": event_summary,
                "type": 2,
                "start_time": start_time,
                "duration": duration,
                "timezone": "Asia/Kolkata",
                "settings": {
                    "join_before_host": True,
                    "waiting_room": False
                }
            }

            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }

            zoom_response = requests.post(
                "https://api.zoom.us/v2/users/me/meetings",
                headers=headers,
                json=meeting_payload
            )

            if zoom_response.status_code == 401 and zoom_response.json().get("code") == 124:
                access_token = refresh_zoom_token(user_id)
                headers["Authorization"] = f"Bearer {access_token}"
                zoom_response = requests.post(
                    "https://api.zoom.us/v2/users/me/meetings",
                    headers=headers,
                    json=meeting_payload
                )

            if zoom_response.status_code != 201:
                return jsonify({"error": "Zoom API error", "details": zoom_response.json()}), 500

            zoom_data = zoom_response.json()
            zoom_link = zoom_data["join_url"]

            calendar_result = create_calendar_event_with_zoom(
                topic=event_summary,
                start_time=start_time,
                duration=duration,
                zoom_link=zoom_link,
                user_id=user_id
            )

            return jsonify({
                "message": "Zoom + Calendar setup complete",
                "zoom_link": zoom_link,
                "calendar_event": calendar_result
            })

        # === 📊 Prepare slides workflow ===
        elif action == "Prepare slides":
            if not os.path.exists('token.json'):
                return jsonify({'action': 'Requires authentication', 'auth_url': get_auth_url()}), 401

            calendar_result = create_calendar_event(event_summary)
            ppt_result = create_powerpoint_slides(event_summary)
            drive_link = upload_to_drive(ppt_result["details"]["file_path"], f"slides_{event_summary}.pptx")
            notion_result = create_notion_page(f"Slides for {event_summary}", parent_page_id, drive_link=drive_link)
            notion_result["details"]["slides_drive_link"] = drive_link

            service = get_calendar_service()
            event_id = calendar_result["details"]["event_id"]
            event = service.events().get(calendarId='primary', eventId=event_id).execute()
            event['description'] = (event.get('description', '') +
                                    f"\n\nGoogle Drive Link: {drive_link}\nNotion Page: {notion_result['details']['url']}")
            service.events().update(calendarId='primary', eventId=event_id, body=event).execute()

            return jsonify({
                "action": "Completed multiple tasks",
                "details": {
                    "calendar": calendar_result["details"],
                    "drive_link": drive_link,
                    "notion": notion_result["details"]
                }
            })

        # === 📒 Notion note creation ===
        elif action == "Write important notes in Notion":
            zoom_link = data.get("zoom_link")
            calendar_link = data.get("calendar_link")

            extra_text = ""
            if zoom_link:
                extra_text += f"Zoom Meeting: {zoom_link}\n"
            if calendar_link:
                extra_text += f"Google Calendar: {calendar_link}\n"

            notion_result = create_notion_page(
            event_summary,
            parent_page_id=parent_page_id,
            extra_text=extra_text if extra_text else None
)

            return jsonify({
                "message": "Notion page created",
                "redirect_url": notion_result["details"]["url"]
            })

        # === 📩 Gmail meeting email ===
        elif action == "Write up an email for the meeting to a colleague":
            zoom_link = data.get("zoom_link")
            calendar_link = data.get("calendar_link")

            subject = f"Meeting: {event_summary}"
            body = f"Hi,\n\nI wanted to discuss our meeting scheduled for {event_summary}..."

            if zoom_link:
                body += f"\n\nZoom Link: {zoom_link}"
            if calendar_link:
                body += f"\nCalendar Event: {calendar_link}"

            body += "\n\nBest,\n[Your Name]"

            if not recipient:
                # Redirect to Gmail compose with prefilled content
                email_url = f"https://mail.google.com/mail/?view=cm&fs=1&{urlencode({'to': '', 'subject': subject, 'body': body})}"
                return jsonify({"action": "Redirect to Gmail", "redirect_url": email_url})
            else:
                # Send email via Gmail API
                return jsonify(send_gmail(recipient, subject, body))


        # === 📅 Follow-up meeting (Google Calendar) ===
        elif action == "Send an email to discuss concerns":
            subject = f"Concerns about {event_summary}"
            body = (
                f"Hi,\n\nI wanted to discuss some concerns I have about {event_summary}.\n"
                "Could we set up a time to talk?\n\nBest,\n[Your Name]"
            )

            if not recipient:
                email_url = f"https://mail.google.com/mail/?view=cm&fs=1&{urlencode({'to': '', 'subject': subject, 'body': body})}"
                return jsonify({"action": "Redirect to Gmail", "redirect_url": email_url})
            else:
                return jsonify(send_gmail(recipient, subject, body))


        # === 📬 Slack notification ===
        elif action == "Plan schedule":
            result = post_to_slack(f"Planning schedule for {event_summary}.", user_id=user_id)
            return jsonify(result)

        else:
            return jsonify({"action": "No action taken", "details": {}})

    except Exception as e:
        logger.error(f"Error in execute_task: {e}")
        return jsonify({'error': str(e)}), 500



@app.route('/download_slides/<path:filename>', methods=['GET'])
def download_slides(filename):
    try:
        directory = os.path.join(os.getcwd(), "presentations")
        return send_from_directory(directory, filename, as_attachment=True)
    except Exception as e:
        logger.error(f"Error downloading slides: {e}")
        return jsonify({'error': str(e)}), 404

@app.route('/oauth2callback')
def oauth2callback():
    try:
        user_email = handle_oauth_callback(request.url)
        # For now, show the email (in production, store in session or JWT)
        return jsonify({"message": "Google authenticated", "email": user_email})
    except Exception as e:
        logger.error(f"Error in OAuth callback: {e}")
        return jsonify({'error': str(e)}), 500


@app.route("/auth/slack/callback", methods=["GET"])
def auth_slack_callback():
    code = request.args.get("code")
    user_id = request.headers.get("X-User-ID")  # ✅ Real Google user email

    if not code or not user_id:
        return jsonify({"error": "Missing authorization code or user ID"}), 400

    try:
        token_data = handle_slack_callback(code, user_id)  # 👈 pass to backend logic
        return jsonify({"message": "Slack authenticated successfully", "details": token_data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

@app.route("/auth/zoom", methods=["GET"])
def auth_zoom():
    user_id = request.headers.get("X-User-ID")
    if not user_id:
        return jsonify({"error": "Missing X-User-ID"}), 400
    return redirect(get_zoom_auth_url(user_id))

@app.route("/auth/zoom/callback", methods=["GET"])
def auth_zoom_callback():
    code = request.args.get("code")
    user_id = request.args.get("state")  # pulled from get_zoom_auth_url
    if not code or not user_id:
        return jsonify({"error": "Missing code or user ID"}), 400
    try:
        tokens = handle_zoom_callback(code, user_id)
        return jsonify({"message": "Zoom authenticated", "tokens": tokens})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

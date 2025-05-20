import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from flask import request, jsonify, redirect, url_for, send_from_directory
from . import create_app
from .recommendation import get_recommendation, process_user_message, chat_with_distilbert
from .calendar_api import create_calendar_event, get_auth_url, handle_oauth_callback, list_calendar_events, get_calendar_service, get_drive_service, upload_to_drive, send_gmail
from .encryption import encrypt_data
from .slack_oauth import get_slack_auth_url, handle_slack_callback, post_to_slack
from .notion_api import create_notion_page, list_notion_pages
from .powerpoint_api import create_powerpoint_slides
import logging
from datetime import date, datetime, timedelta
from urllib.parse import urlencode

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
        event_summary = data.get('event_summary', '')
        parent_page_id = data.get('parent_page_id')
        recipient = data.get('recipient', '')
        slack_channel = data.get('slack_channel')

        if not action.strip() or not event_summary.strip():
            logger.warning("Invalid action or event summary")
            return jsonify({'error': 'Action and event summary must be non-empty strings'}), 400

        logger.info(f"Executing task for action: {action}, event: {event_summary}")
        
        if action == "Prepare slides":
            if not os.path.exists('token.json'):
                try:
                    auth_url = get_auth_url()
                    return jsonify({'action': 'Requires authentication', 'auth_url': auth_url}), 401
                except Exception as e:
                    logger.error(f"Failed to generate auth URL: {e}")
                    return jsonify({'error': f"Failed to initiate authentication: {str(e)}"}), 500

            calendar_result = create_calendar_event(event_summary)
            ppt_result = create_powerpoint_slides(event_summary)
            drive_link = upload_to_drive(ppt_result["details"]["file_path"], f"slides_{event_summary}.pptx")
            notion_result = create_notion_page(f"Slides for {event_summary}", parent_page_id, drive_link=drive_link)
            notion_result["details"]["slides_drive_link"] = drive_link

            service = get_calendar_service()
            event_id = calendar_result["details"]["event_id"]
            event = service.events().get(calendarId='primary', eventId=event_id).execute()
            event['description'] = (event.get('description', '') + f"\n\nGoogle Drive Link: {drive_link}\nNotion Page: {notion_result['details']['url']}")
            service.events().update(calendarId='primary', eventId=event_id, body=event).execute()
            logger.info(f"Updated Calendar event {event_id} with Google Drive link and Notion page URL")

            result = {
                "action": "Completed multiple tasks",
                "details": {
                    "calendar": calendar_result["details"],
                    "drive_link": drive_link,
                    "notion": notion_result["details"]
                }
            }

        elif action == "Write important notes in Notion":
            notion_result = create_notion_page(event_summary, parent_page_id)
            return jsonify({
                "action": "Redirect to Notion",
                "redirect_url": notion_result["details"]["url"]
            })

        elif action == "Write up an email for the meeting to a colleague":
            if not recipient:
                email_body = "Hi,\n\nI wanted to discuss our meeting...\n\nBest,\n[Your Name]"
                encoded_body = urlencode({'body': email_body})
                url_params = f"to=&subject=Meeting: {event_summary}&{encoded_body}"
                email_url = "https://mail.google.com/mail/?view=cm&fs=1&" + url_params
                return jsonify({"action": "Redirect to Gmail", "redirect_url": email_url})
            else:
                try:
                    result = send_gmail(recipient, f"Meeting: {event_summary}", f"Hi,\n\nI wanted to discuss our meeting scheduled for {event_summary}...\n\nBest,\n[Your Name]")
                except Exception as e:
                    logger.error(f"Error sending email: {e}")
                    return jsonify({'error': str(e)}), 500

        elif action == "Send an email to discuss concerns":
            if not recipient:
                email_params = {
                                    "to": "",
                                    "subject": f"Concerns about {event_summary}",
                                    "body": "Hi,\n\nI wanted to discuss concerns...\n\nBest,\n[Your Name]"
                                }
                email_url = "https://mail.google.com/mail/?view=cm&fs=1&" + urlencode(email_params)
                return jsonify({"action": "Redirect to Gmail", "redirect_url": email_url})
            else:
                result = send_gmail(recipient, f"Concerns about {event_summary}", f"Hi,\n\nI wanted to discuss concerns about {event_summary}...\n\nBest,\n[Your Name]")

        elif action == "Schedule a follow-up meeting":
            if not os.path.exists('token.json'):
                try:
                    auth_url = get_auth_url()
                    return jsonify({'action': 'Requires authentication', 'auth_url': auth_url}), 401
                except Exception as e:
                    return jsonify({'error': f"Failed to initiate authentication: {str(e)}"}), 500
            calendar_result = create_calendar_event(event_summary)
            return jsonify({"action": "Scheduled meeting", "details": calendar_result["details"]})

        elif action == "Bring documents":
            if not recipient:
                email_params = {
                                    "to": "",
                                    "subject": f"Concerns about {event_summary}",
                                    "body": "Hi,\n\nI wanted to discuss concerns...\n\nBest,\n[Your Name]"
                                }
                email_url = "https://mail.google.com/mail/?view=cm&fs=1&" + urlencode(email_params)
                
               
                return jsonify({"action": "Redirect to Gmail", "redirect_url": email_url})
            else:
                result = send_gmail(recipient, f"Reminder: Bring documents for {event_summary}", f"Hi,\n\nThis is a reminder to bring documents for {event_summary}.\n\nBest,\n[Your Name]")

        elif action == "Plan schedule":
            result = post_to_slack(f"Planning schedule for {event_summary}.")

        else:
            result = {"action": "No action taken", "details": {}}

        return jsonify(result)

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


# 🔐 Slack OAuth routes
@app.route("/auth/slack", methods=["GET"])
def auth_slack():
    return redirect(get_slack_auth_url())

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



if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

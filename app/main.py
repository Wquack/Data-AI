import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from flask import request, jsonify, redirect, url_for, send_from_directory
from . import create_app
from .recommendation import get_recommendation, process_user_message, chat_with_distilbert
from .calendar_api import create_calendar_event, get_auth_url, handle_oauth_callback, list_calendar_events, get_calendar_service
from .encryption import encrypt_data
from .mock_apis import mock_gmail_send, mock_slack_post
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
    """Endpoint to directly interact with DistilBERT for sentiment analysis."""
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

@app.route('/list_calendar_events', methods=['GET'])
def list_calendar_events_endpoint():
    try:
        if not os.path.exists('token.json'):
            try:
                auth_url = get_auth_url()
                return jsonify({'action': 'Requires authentication', 'auth_url': auth_url}), 401
            except Exception as e:
                logger.error(f"Failed to generate auth URL: {e}")
                return jsonify({'error': f"Failed to initiate authentication: {str(e)}"}), 500
        # Get the date range parameters from the query string
        start_date = request.args.get('start_date', None)
        end_date = request.args.get('end_date', None)
        # Backward compatibility: if only 'date' is provided, use it as start_date
        if not start_date and request.args.get('date', None):
            start_date = request.args.get('date')
            end_date = start_date
        events = list_calendar_events(start_date, end_date)
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
        parent_page_id = data.get('parent_page_id', None)
        if not isinstance(action, str) or not action.strip() or not isinstance(event_summary, str) or not event_summary.strip():
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
            # Create calendar event
            calendar_result = create_calendar_event(event_summary)
            # Create PowerPoint slides
            ppt_result = create_powerpoint_slides(event_summary)
            # Create a Notion page to link the slides
            notion_result = create_notion_page(f"Slides for {event_summary}", parent_page_id)
            notion_result["details"]["slides_path"] = ppt_result["details"]["file_path"]
            # Update Calendar event with PowerPoint file path and Notion page URL
            service = get_calendar_service()
            event_id = calendar_result["details"]["event_id"]
            event = service.events().get(calendarId='primary', eventId=event_id).execute()
            event['description'] = (event.get('description', '') + f"\n\nPowerPoint Slides: {ppt_result['details']['file_path']}\nNotion Page: {notion_result['details']['url']}")
            service.events().update(calendarId='primary', eventId=event_id, body=event).execute()
            logger.info(f"Updated Calendar event {event_id} with PowerPoint file path and Notion page URL")
            # Combine results
            result = {
                "action": "Completed multiple tasks",
                "details": {
                    "calendar": calendar_result["details"],
                    "powerpoint": ppt_result["details"],
                    "notion": notion_result["details"]
                }
            }
        elif action == "Write important notes in Notion":
            # Create Notion page
            notion_result = create_notion_page(event_summary, parent_page_id)
            # Redirect to the Notion page URL
            return jsonify({
                "action": "Redirect to Notion",
                "redirect_url": notion_result["details"]["url"]
            })
        elif action == "Write up an email for the meeting to a colleague":
            # Redirect to Gmail compose with pre-filled details
            email_params = {
                "to": "",  # Let the user fill in the recipient
                "subject": f"Meeting: {event_summary}",
                "body": f"Hi,\n\nI wanted to discuss our meeting scheduled for {event_summary}. Here are some details...\n\nBest,\n[Your Name]"
            }
            email_url = f"https://mail.google.com/mail/?view=cm&fs=1&{urlencode(email_params)}"
            return jsonify({
                "action": "Redirect to Gmail",
                "redirect_url": email_url
            })
        elif action == "Send an email to discuss concerns":
            # Redirect to Gmail compose with pre-filled details
            email_params = {
                "to": "",  # Let the user fill in the recipient
                "subject": f"Concerns about {event_summary}",
                "body": f"Hi,\n\nI wanted to discuss some concerns I have about {event_summary}. Could we set up a time to talk?\n\nBest,\n[Your Name]"
            }
            email_url = f"https://mail.google.com/mail/?view=cm&fs=1&{urlencode(email_params)}"
            return jsonify({
                "action": "Redirect to Gmail",
                "redirect_url": email_url
            })
        elif action == "Schedule a follow-up meeting":
            if not os.path.exists('token.json'):
                try:
                    auth_url = get_auth_url()
                    return jsonify({'action': 'Requires authentication', 'auth_url': auth_url}), 401
                except Exception as e:
                    logger.error(f"Failed to generate auth URL: {e}")
                    return jsonify({'error': f"Failed to initiate authentication: {str(e)}"}), 500
            # Create calendar event
            calendar_result = create_calendar_event(event_summary)
            return jsonify({
                "action": "Scheduled meeting",
                "details": calendar_result["details"]
            })
        elif action == "Bring documents":
            result = mock_gmail_send(event_summary)
        elif action == "Plan schedule":
            result = mock_slack_post(event_summary)
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
        handle_oauth_callback(request.url)
        return redirect(url_for('execute_task_endpoint'))
    except Exception as e:
        logger.error(f"Error in OAuth callback: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
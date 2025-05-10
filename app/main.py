import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from flask import request, jsonify, redirect, url_for, send_from_directory
from . import create_app
from .recommendation import get_recommendation, process_user_message
from .calendar_api import create_calendar_event, get_auth_url, handle_oauth_callback, list_calendar_events
from .encryption import encrypt_data
from .mock_apis import mock_gmail_send, mock_slack_post
from .notion_api import create_notion_page, list_notion_pages
from .powerpoint_api import create_powerpoint_slides
import logging

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

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
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
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
        events = list_calendar_events()
        return jsonify({'events': events})
    except Exception as e:
        logger.error(f"Error listing calendar events: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/execute_task', methods=['POST'])
def execute_task_endpoint():
    try:
        data = request.json
        recommendation = data.get('recommendation', '')
        event_summary = data.get('event_summary', '')
        parent_page_id = data.get('parent_page_id', None)
        if not isinstance(recommendation, str) or not recommendation.strip() or not isinstance(event_summary, str) or not event_summary.strip():
            logger.warning("Invalid recommendation or event summary")
            return jsonify({'error': 'Recommendation and event summary must be non-empty strings'}), 400

        logger.info(f"Executing task for recommendation: {recommendation}, event: {event_summary}")
        
        if recommendation == "Prepare slides":
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
            # Combine results
            result = {
                "action": "Completed multiple tasks",
                "details": {
                    "calendar": calendar_result["details"],
                    "powerpoint": ppt_result["details"]
                }
            }
        elif recommendation == "Review notes":
            result = create_notion_page(event_summary, parent_page_id)
        elif recommendation == "Bring documents":
            result = mock_gmail_send(event_summary)
        elif recommendation == "Plan schedule":
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
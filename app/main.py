import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from flask import request, jsonify, redirect, url_for
from . import create_app
from .recommendation import get_recommendation
from .calendar_api import create_calendar_event, get_auth_url, handle_oauth_callback
from .encryption import encrypt_data
from .mock_apis import mock_notion_create_page, mock_gmail_send, mock_slack_post
import logging

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

@app.route('/execute_task', methods=['POST'])
def execute_task_endpoint():
    try:
        data = request.json
        recommendation = data.get('recommendation', '')
        event_summary = data.get('event_summary', '')
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
            result = create_calendar_event(event_summary)
        elif recommendation == "Review notes":
            result = mock_notion_create_page(event_summary)
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
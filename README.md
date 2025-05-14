Recommendation Model Backend
Backend for a PIN AI-inspired PoC, generating task recommendations and executing web-based actions.
Setup

Install Python 3.9.
Create virtual environment:python -m venv venv
.\venv\Scripts\activate


Install dependencies:pip install flask==2.3.3 flask-cors==5.0.0 transformers==4.35.2 torch==2.3.0 pycryptodome==3.20.0 requests==2.31.0


Run:python recommendation_model.py



API Endpoints

POST /recommend
Input: {"event_summary": "string"}
Output: {"recommendation": "string"}
Example: {"event_summary": "Team meeting at 2 PM"} → {"recommendation": "Prepare slides"}


POST /execute_task
Input: {"recommendation": "string", "event_summary": "string"}
Output: {"action": "string", "details": "object"}
Example: {"recommendation": "Prepare slides", "event_summary": "Team meeting at 2 PM"} → {"action": "Scheduled meeting", "details": {...}}



Mock APIs

Google Calendar: createEvent (Prepare slides)
Notion: createPage (Review notes)
Gmail: users.messages.send (Bring documents)
Slack: chat.postMessage (Plan schedule)

Notes

Uses httpbin.org/post for mock API responses.
Phase 2: Implement real APIs (Google, Notion, Zoom, Slack).
Privacy: Inputs encrypted, mock APIs send minimal data.

hello
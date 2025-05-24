# Recommendation Model Backend

## Introduction

This project is a backend service that provides task recommendations based on user input, integrates with various APIs (Google Calendar, Zoom, Slack, Notion, Gmail, PowerPoint), and offers user authentication.

## Installation

1.  Clone the repository:

    ```bash
    git clone [repository_url]
    cd Recommendation_Model_Backend
    ```
2.  Install the dependencies:

    ```bash
    pip install -r requirements.txt
    ```
3.  Configure environment variables:

    *   Create a `.env` file in the root directory.
    *   Add the following environment variables:

        ```
        # Add your environment variables here
        ```

## Usage

The backend provides several API endpoints for different functionalities. Below are the details of each endpoint.

## API Endpoints

### 1. Ping

*   Endpoint: `/ping`
*   Method: GET
*   Description: Checks if the server is running.
*   Response:

    ```json
    {
        "message": "pong"
    }
    ```

### 2. Recommend Task

*   Endpoint: `/recommend`
*   Method: POST
*   Description: Recommends a task based on the provided event summary.
*   Request Body:

    ```json
    {
        "event_summary": "string"
    }
    ```
*   Response:

    ```json
    {
        "recommendation": "string"
    }
    ```

### 3. Chat Endpoint

*   Endpoint: `/chat`
*   Method: POST
*   Description: Processes a user message and returns a response.
*   Request Body:

    ```json
    {
        "message": "string"
    }
    ```
*   Response:

    ```json
    {
        # Response structure depends on the message
    }
    ```

### 4. Chat with DistilBERT Endpoint

*   Endpoint: `/chat_with_distilbert`
*   Method: POST
*   Description: Processes a user message using the DistilBERT model and returns a response.
*   Request Body:

    ```json
    {
        "message": "string"
    }
    ```
*   Response:

    ```json
    {
        # Response structure depends on the message
    }
    ```

### 5. Create Zoom Meeting

*   Endpoint: `/create_zoom_meeting`
*   Method: POST
*   Description: Creates a Zoom meeting. Requires a valid Zoom access token.
*   Headers:
    *   `X-User-ID`: User ID
*   Request Body:

    ```json
    {
        "topic": "string",
        "start_time": "string (ISO 8601 format: YYYY-MM-DDTHH:MM:SS)",
        "duration": "integer (minutes)"
    }
    ```
*   Response:

    ```json
    {
        "message": "Meeting created",
        "zoom_link": "string",
        "meeting_id": "string",
        "start_time": "string"
    }
    ```

### 6. List Notion Pages

*   Endpoint: `/list_notion_pages`
*   Method: GET
*   Description: Lists Notion pages.
*   Response:

    ```json
    {
        "pages": "list of pages"
    }
    ```

### 7. List Calendar Events

*   Endpoint: `/list_calendar_events`
*   Method: GET, POST
*   Description: Lists calendar events.
*   Request Parameters:
    *   `start_date` (optional): Start date for filtering events.
    *   `end_date` (optional): End date for filtering events.
    *   `event_type` (optional): Event type for filtering events.
    *   `attendees` (optional): Attendees for filtering events.
    *   `date` (optional): Shorthand for setting both start_date and end_date to the same value.
*   Response:

    ```json
    {
        "events": "list of events"
    }
    ```

### 8. Execute Task

*   Endpoint: `/execute_task`
*   Method: POST
*   Description: Executes a specific task based on the provided action.
*   Headers:
    *   `X-User-ID`: User ID
*   Request Body:

    ```json
    {
        "action": "string",
        "event_summary": "string",
        "parent_page_id": "string",
        "recipient": "string",
        "slack_channel": "string",
        "start_time": "string (ISO 8601 format: YYYY-MM-DDTHH:MM:SS)",
        "duration": "integer (minutes)",
        "zoom_link": "string",
        "calendar_link": "string"
    }
    ```
*   Response:

    ```json
    {
        # Response structure depends on the action
    }
    ```

### 9. Download Slides

*   Endpoint: `/download_slides/{filename}`
*   Method: GET
*   Description: Downloads slides with the given filename.
*   Response: File download

### 10. OAuth2 Callback

*   Endpoint: `/oauth2callback`
*   Method: GET
*   Description: Handles the OAuth2 callback from Google.
*   Response:

    ```json
    {
        "message": "Google authenticated",
        "email": "user email"
    }
    ```

### 11. Slack Auth Callback

*   Endpoint: `/auth/slack/callback`
*   Method: GET
*   Description: Handles the Slack authentication callback.
*   Request Parameters:
    *   `code`: Authorization code
*   Headers:
    *   `X-User-ID`: User ID
*   Response:

    ```json
    {
        "message": "Slack authenticated successfully",
        "details": {
            # Token details
        }
    }
    ```

### 12. Zoom Auth

*   Endpoint: `/auth/zoom`
*   Method: GET
*   Description: Redirects to the Zoom authentication page.
*   Headers:
    *   `X-User-ID`: User ID
*   Response: Redirect to Zoom authentication

### 13. Zoom Auth Callback

*   Endpoint: `/auth/zoom/callback`
*   Method: GET
*   Description: Handles the Zoom authentication callback.
*   Request Parameters:
    *   `code`: Authorization code
    *   `state`: State token
*   Response:

    ```json
    {
        "message": "Zoom authenticated",
        "tokens": {
            # Token details
        }
    }
    ```

## Models

### 1. User

*   Description: Represents a user in the system.
*   Attributes:
    *   `id` (Integer): Primary key, unique identifier for the user.
    *   `email` (String): Unique email address of the user.
    *   `password_hash` (String): Hashed password for the user.

### 2. UserToken

*   Description: Stores user tokens for different services.
*   Attributes:
    *   `user_id` (String): User ID associated with the token.
    *   `service` (String): Service name (e.g., Google, Zoom, Slack).
    *   `access_token` (String): Access token for the service.
    *   `refresh_token` (String, optional): Refresh token for the service.
    *   `expires_at` (DateTime, optional): Expiration timestamp of the access token.

## Utilities

### 1. db.py

*   Description: Handles database connection and session management using SQLAlchemy.
*   Functions:
    *   `DATABASE_URL`: Environment variable for the database URL.
    *   `engine`: SQLAlchemy engine for connecting to the database.
    *   `SessionLocal`: Session maker for creating database sessions.
    *   `Base`: Base class for declarative models.

### 2. jwt_utils.py

*   Description: Provides utilities for creating and decoding JWT (JSON Web Tokens).
*   Functions:
    *   `create_access_token(data: dict, expires_delta: int)`: Creates a new access token with the given data and expiration time.
    *   `decode_access_token(token: str)`: Decodes an access token and returns the payload.
    *   `generate_state_token(user_id: str)`: Generates a state token for OAuth flow.
    *   `decode_state_token(token: str)`: Decodes a state token.

### 3. token_store.py

*   Description: Manages the storage and retrieval of user tokens for different services.
*   Functions:
    *   `save_tokens(user_id, token_data: dict)`: Saves tokens for multiple services.
    *   `load_tokens(user_id: str) -> dict`: Loads all tokens for a user.

## Authentication

The backend uses JWT (JSON Web Tokens) for authentication and supports OAuth 2.0 for Google, Zoom, and Slack.

### 1. JWT Authentication

*   **Register User**:
    *   Endpoint: `/auth/register`
    *   Method: POST
    *   Description: Registers a new user.
    *   Request Body:

        ```json
        {
            "email": "string (email format)",
            "password": "string"
        }
        ```
    *   Response:

        ```json
        {
            "message": "User registered successfully",
            "user_id": "integer"
        }
        ```

*   **Login User**:
    *   Endpoint: `/auth/login`
    *   Method: POST
    *   Description: Logs in an existing user and returns an access token.
    *   Request Body:

        ```json
        {
            "email": "string (email format)",
            "password": "string"
        }
        ```
    *   Response:

        ```json
        {
            "access_token": "string",
            "token_type": "bearer"
        }
        ```

*   **Get Logged-in User**:
    *   Endpoint: `/auth/me`
    *   Method: GET
    *   Description: Retrieves the current logged-in user's information.
    *   Headers:
        *   `Authorization`: `Bearer <access_token>`
    *   Response:

        ```json
        {
            "id": "integer",
            "email": "string (email format)"
        }
        ```

*   **Logout User**:
    *   Endpoint: `/auth/logout`
    *   Method: POST
    *   Description: Logs out the current user.
    *   Response:

        ```json
        {
            "message": "Successfully logged out"
        }
        ```

### 2. OAuth 2.0 Authentication

*   **Google OAuth**:
    *   Endpoint: `/auth/google`
    *   Method: GET
    *   Description: Redirects to the Google OAuth 2.0 authentication page.
    *   Callback Endpoint: `/auth/google/callback`

*   **Zoom OAuth**:
    *   Endpoint: `/auth/zoom`
    *   Method: GET
    *   Description: Redirects to the Zoom OAuth 2.0 authentication page.
    *   Callback Endpoint: `/auth/zoom/callback`

*   **Slack OAuth**:
    *   Endpoint: `/auth/slack`
    *   Method: GET
    *   Description: Redirects to the Slack OAuth 2.0 authentication page.
    *   Callback Endpoint: `/auth/slack/callback`

### 3. Token Management

*   **View Tokens**:
    *   Endpoint: `/auth/tokens`
    *   Method: GET
    *   Description: Retrieves the tokens for the current user.
    *   Headers:
        *   `Authorization`: `Bearer <access_token>`
    *   Response:

        ```json
        {
            "tokens": {
                "google": {
                    "access_token": "string",
                    "refresh_token": "string",
                    "expires_at": "datetime"
                },
                "zoom": {
                    "access_token": "string",
                    "refresh_token": "string",
                    "expires_at": "datetime"
                },
                "slack": {
                    "access_token": "string",
                    "refresh_token": "string",
                    "expires_at": "datetime"
                }
            }
        }
        ```

## Environment Variables

*   `SLACK_CLIENT_SECRET`: Slack client secret.
*   `SLACK_CLIENT_ID`: Slack client ID.
*   `SLACK_REDIRECT_URI`: Slack redirect URI.
*   `ZOOM_CLIENT_ID`: Zoom client ID.
*   `ZOOM_CLIENT_SECRET`: Zoom client secret.
*   `DATABASE_URL`: Database connection URL.
*   `JWT_SECRET`: Secret key for JWT encoding.
*   `JWT_EXPIRY_SECONDS`: JWT expiry time in seconds.
*   `GOOGLE_CLIENT_ID`: Google client ID.
*   `GOOGLE_CLIENT_SECRET`: Google client secret.
*   `GOOGLE_REDIRECT_URI`: Google redirect URI.

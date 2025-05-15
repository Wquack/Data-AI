
Recommendation Model Backend
Backend for a AI-inspired PoC, generating task recommendations and executing web-based actions.
Setup

This document describes the files in the project as of Phase I.

## .gitignore

This file specifies intentionally untracked files that Git should ignore. It prevents sensitive information and build artifacts from being committed to the repository.

## README.md

This file provides a high-level overview of the project, including its purpose, usage instructions, and development information.

## requirements.txt

This file lists the Python packages required to run the project. It is used to install the dependencies using `pip install -r requirements.txt`.

## token.json

This file stores the user's authentication token for the Google Calendar API. It is generated after the user authorizes the application to access their calendar.

## app/

This directory contains the main application code.

### app/__init__.py

This file initializes the `app` package and creates the Flask application instance.

### app/calendar_api.py

This file contains functions for interacting with the Google Calendar API, such as creating and listing calendar events.

### app/encryption.py

This file provides functions for encrypting and decrypting sensitive data, such as the user's Google Calendar API token.

<<<<<<< HEAD
hello
=======
### app/main.py

This file contains the main application logic, including the Flask routes and the task recommendation engine.

### app/mock_apis.py

This file contains mock implementations of external APIs, such as Notion, Gmail, and Slack. These are used for testing purposes.

### app/notion_api.py

This file contains functions for interacting with the Notion API, such as creating and listing pages.

### app/powerpoint_api.py

This file contains functions for creating PowerPoint slides from event summaries.

### app/recommendation.py

This file contains the logic for recommending tasks based on the user's calendar events and Notion pages.

hel
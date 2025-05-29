import os
import requests
from dotenv import load_dotenv
import logging
from requests.exceptions import RequestException
import  time

load_dotenv()

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"

logger = logging.getLogger(__name__)

def call_mistral_api(messages, model="mistral-tiny"):
    if not MISTRAL_API_KEY:
        raise Exception("MISTRAL_API_KEY not set in environment variables")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {MISTRAL_API_KEY}"
    }

    payload = {
        "model": model,
        "messages": messages
    }

    try:
        response = requests.post(MISTRAL_API_URL, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error calling Mistral API: {e}")
        raise Exception(f"Failed to call Mistral API: {str(e)}")
    
def call_mistral_api(messages, model="mistral-tiny", retries=3, delay=1):
    for attempt in range(retries):
        try:
            response = requests.post(MISTRAL_API_URL, json={"model": model, "messages": messages}, headers=headers)
            response.raise_for_status()
            return response.json()
        except RequestException as e:
            if attempt == retries - 1:
                logger.error(f"Error calling Mistral API after {retries} attempts: {e}")
                raise Exception(f"Failed to call Mistral API: {str(e)}")
            logger.warning(f"Attempt {attempt + 1} failed, retrying in {delay} seconds...")
            time.sleep(delay)
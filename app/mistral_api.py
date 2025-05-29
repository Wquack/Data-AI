# mistral_api.py
import os
import aiohttp
import asyncio
from dotenv import load_dotenv
import logging
import traceback
from cachetools import TTLCache
from transformers import pipeline

load_dotenv()

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"

logger = logging.getLogger(__name__)

mistral_cache = TTLCache(maxsize=1000, ttl=3600)  # Cache for 1 hour

async def call_mistral_api(messages, model="mistral-tiny", timeout=30, retries=3, retry_delay=2):
    if not MISTRAL_API_KEY:
        raise Exception("MISTRAL_API_KEY not set in environment variables")

    cache_key = f"{model}:{str(messages)}"
    if cache_key in mistral_cache:
        logger.info("Returning cached Mistral response")
        return mistral_cache[cache_key]

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {MISTRAL_API_KEY}"
    }

    payload = {
        "model": model,
        "messages": messages
    }

    async with aiohttp.ClientSession() as session:
        for attempt in range(retries):
            try:
                start_time = asyncio.get_event_loop().time()
                async with session.post(MISTRAL_API_URL, json=payload, headers=headers, timeout=timeout) as response:
                    response.raise_for_status()
                    result = await response.json()
                    end_time = asyncio.get_event_loop().time()
                    logger.info(f"Mistral API call took {end_time - start_time:.2f} seconds")
                    mistral_cache[cache_key] = result
                    return result
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                if attempt == retries - 1:
                    logger.warning(f"Mistral API failed after {retries} attempts, falling back to local model: {str(e)}")
                    # Fallback to local model
                    local_model = pipeline("text-generation", model="distilgpt2")
                    prompt = f"{messages[0]['content']}\nUser: {messages[1]['content']}"
                    result = local_model(prompt, max_length=100, num_return_sequences=1)
                    fallback_response = {"choices": [{"message": {"content": result[0]["generated_text"]}}]}
                    mistral_cache[cache_key] = fallback_response
                    return fallback_response
                logger.warning(f"Mistral API attempt {attempt + 1} failed, retrying in {retry_delay} seconds: {str(e)}")
                await asyncio.sleep(retry_delay)
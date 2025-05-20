# utils/token_store.py
import json
import os

TOKEN_FILE = "tokens.json"

def load_tokens(user_id):
    if not os.path.exists(TOKEN_FILE):
        return {}
    with open(TOKEN_FILE, "r") as f:
        all_tokens = json.load(f)
    return all_tokens.get(user_id, {})

def save_tokens(user_id, new_tokens):
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            all_tokens = json.load(f)
    else:
        all_tokens = {}

    if user_id not in all_tokens:
        all_tokens[user_id] = {}

    all_tokens[user_id].update(new_tokens)

    with open(TOKEN_FILE, "w") as f:
        json.dump(all_tokens, f, indent=2)

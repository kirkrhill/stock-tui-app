import os
import json
import logging

CONFIG_PATH = os.path.expanduser("~/.stock_tui_config.json")

def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Failed to load config: {e}")
    return {"history": [], "pinned": []}

def save_config(config):
    # Merge with existing config
    current = load_config()
    current.update(config)
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(current, f)
    except Exception as e:
        logging.error(f"Failed to save config: {e}")

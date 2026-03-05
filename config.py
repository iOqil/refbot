import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

ADMIN_IDS = set(
    int(x.strip())
    for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
)

REQUIRED_CHANNELS = [
    x.strip()
    for x in os.getenv("REQUIRED_CHANNELS", "").split(",")
    if x.strip()
]

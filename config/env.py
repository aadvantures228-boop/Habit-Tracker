import os
from dotenv import load_dotenv
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
WEATHER_TOKEN = os.getenv('WEATHER_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))
# Optional reusable keys for compatibility with the weather bot.
ADV_ACTIVATION_KEYS = frozenset(k.strip().upper() for k in os.getenv('ADV_ACTIVATION_KEYS', '').split(',') if k.strip())
DATA_PATH = os.getenv('DATA_PATH', 'bot_data.pkl')
# If set, use durable PostgreSQL instead of the local pickle file.
DATABASE_URL = os.getenv('DATABASE_URL', '')

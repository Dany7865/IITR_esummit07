import os
import json as _json
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root if present
env_path = Path(__file__).parent.joinpath('.env')
if env_path.exists():
	load_dotenv(env_path)
else:
	load_dotenv()  # fallback to environment

# Database - default to sqlite file for local/dev. Set MYSQL_* in env to use MySQL elsewhere.
DATABASE_PATH = os.getenv('DATABASE_PATH', 'leads.db')

MYSQL_HOST = os.getenv('MYSQL_HOST', 'localhost')
MYSQL_USER = os.getenv('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', '')
MYSQL_DB = os.getenv('MYSQL_DB', 'hpcl_leads')

# API / Integration keys (do NOT check these into source control)
WHATSAPP_TOKEN = os.getenv('WHATSAPP_TOKEN', '')
PHONE_ID = os.getenv('PHONE_ID', '')
FCM_SERVER_KEY = os.getenv('FCM_SERVER_KEY', '')
SECRET_KEY = os.getenv('SECRET_KEY', 'replace-me')

# Source feeds (defaults empty)
NEWS_RSS_URL = os.getenv('NEWS_RSS_URL', '')
TENDER_RSS_URL = os.getenv('TENDER_RSS_URL', '')
GEM_RSS_URL = os.getenv('GEM_RSS_URL', '')
TENDERS24_URL = os.getenv('TENDERS24_URL', '')

# Admin credentials for basic login (dev only)
ADMIN_USER = os.getenv('ADMIN_USER', 'admin')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'password')

# WhatsApp webhook verify token
WHATSAPP_VERIFY_TOKEN = os.getenv('WHATSAPP_VERIFY_TOKEN', '')

# Other defaults
BASE_URL = os.getenv('BASE_URL', 'http://127.0.0.1:5000')
MIN_CONFIDENCE_TO_NOTIFY = int(os.getenv('MIN_CONFIDENCE_TO_NOTIFY', '50'))
# Priority thresholds for scoring
HIGH_PRIORITY_THRESHOLD = int(os.getenv('HIGH_PRIORITY_THRESHOLD', '75'))
MEDIUM_PRIORITY_THRESHOLD = int(os.getenv('MEDIUM_PRIORITY_THRESHOLD', '50'))
# Notifications defaults
DEFAULT_SALES_NUMBER = os.getenv('SALES_NUMBER', '')
NOTIFY_ON_NEW_LEAD = os.getenv('NOTIFY_ON_NEW_LEAD', 'true').lower() in ('1', 'true', 'yes')
NOTIFY_ON_ASSIGN = os.getenv('NOTIFY_ON_ASSIGN', 'true').lower() in ('1', 'true', 'yes')
MAX_WHATSAPP_BODY = int(os.getenv('MAX_WHATSAPP_BODY', '1000'))
# SMTP / Email settings (optional)
SMTP_HOST = os.getenv('SMTP_HOST', '')
SMTP_PORT = int(os.getenv('SMTP_PORT', os.getenv('SMTP_PORT', '587') or '587'))
SMTP_USER = os.getenv('SMTP_USER', '')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
SMTP_FROM = os.getenv('SMTP_FROM', 'no-reply@example.com')

# Admin contact for notifications
ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', '')
API_KEY = os.getenv('API_KEY', '')
# Comma-separated list of allowed CORS origins. Examples: 'http://localhost:5000,http://127.0.0.1:8000'
ALLOWED_ORIGINS = [o.strip() for o in os.getenv('ALLOWED_ORIGINS', 'http://127.0.0.1:5000').split(',') if o.strip()]
API_KEYS_FILE = os.getenv('API_KEYS_FILE', str(Path(__file__).parent.joinpath('.api_keys.json')))

# Load API_KEYS from JSON file when present (preferred), otherwise allow `API_KEYS` env JSON or single API_KEY env fallback.
def _load_api_keys():
	# 1) file
	try:
		p = Path(API_KEYS_FILE)
		if p.exists():
			with p.open('r', encoding='utf-8') as fh:
				return _json.load(fh)
	except Exception:
		pass
	# 2) env JSON
	try:
		raw = os.getenv('API_KEYS', '')
		if raw:
			return _json.loads(raw)
	except Exception:
		pass
	# 3) fallback single API_KEY env
	if API_KEY:
		return {API_KEY: {"role": "admin"}}
	return {}


API_KEYS = _load_api_keys()


def get_api_role(api_key: str):
	"""Return dict for api_key or empty dict when not found."""
	if not api_key:
		return {}
	return API_KEYS.get(api_key, {})

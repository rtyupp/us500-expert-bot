"""إعدادات بوت US500 (S&P 500) والتداول عبر Capital.com."""
import os
from pathlib import Path

_ENV_FILE = Path(__file__).with_name(".env")

def _load_env_file() -> None:
    if not _ENV_FILE.exists():
        return
    for raw in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip().strip('"').strip("'")

_load_env_file()

# تيليجرام
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8934702570:AAF8zX_iErjTlhws86a4CUj4a24fIOeJ6-w")
ADMIN_CHAT_ID = int(os.environ.get("ADMIN_CHAT_ID", "1819077477"))
DAILY_CHAT_ID = int(os.environ.get("DAILY_CHAT_ID", "1819077477"))
CHANNEL_ID = os.environ.get("CHANNEL_ID", "-1002567371754")

# Capital.com API
CAPITAL_EMAIL = os.environ.get("CAPITAL_EMAIL", "lsyry3247@gmail.com")
CAPITAL_API_KEY = os.environ.get("CAPITAL_API_KEY", "Iw25M1vmcgxt487o")
CAPITAL_API_PASSWORD = os.environ.get("CAPITAL_API_PASSWORD", "Ali1213141516.")
CAPITAL_ENV = os.environ.get("CAPITAL_ENV", "demo").lower()  # demo | live
AUTO_TRADE = os.environ.get("CAPITAL_AUTO_TRADE", "0") == "1"

# إدارة الصفقات
EPIC = "US500"
ASSET_NAME = "US 500 (S&P 500)"
DEFAULT_RISK_PCT = float(os.environ.get("DEFAULT_RISK_PCT", "1.0"))  # 1% لكل صفقة
MAX_OPEN_POSITIONS = int(os.environ.get("MAX_OPEN_POSITIONS", "1"))
TRAILING_STOP_ATR_MULT = float(os.environ.get("TRAILING_STOP_ATR_MULT", "2.0"))

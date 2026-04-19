import os

from dotenv import load_dotenv

load_dotenv()


def _get_required_str(key: str) -> str:
    value = os.getenv(key, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return value


def _get_required_int(key: str) -> int:
    raw = os.getenv(key, "").strip()
    if not raw:
        raise RuntimeError(f"Missing required environment variable: {key}")
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"Environment variable {key} must be an integer") from exc


def _get_optional_int(key: str, default: int) -> int:
    raw = os.getenv(key)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"Environment variable {key} must be an integer") from exc


def _get_optional_str(key: str, default: str) -> str:
    raw = os.getenv(key)
    if raw is None:
        return default
    value = raw.strip()
    return value or default


BOT_TOKEN = _get_required_str("BOT_TOKEN")
API_ID = _get_required_int("API_ID")
API_HASH = _get_required_str("API_HASH")
OWNER_ID = _get_required_int("OWNER_ID")

PRICE_STARS = _get_optional_int("PRICE_STARS", 1)
PASSCODES_FILE = _get_optional_str("PASSCODES_FILE", "passcodes.txt")
ADMINS_FILE = _get_optional_str("ADMINS_FILE", "admins.txt")

import os
import secrets
from pathlib import Path

API_DIR = Path(__file__).resolve().parent.parent
DB_PATH = API_DIR / "governance.db"
API_PREFIX = "/api/v1"
SECRET_KEY_PATH = API_DIR / ".secret_key"
CHAT_MODEL = os.environ.get("CHAT_MODEL", "claude-sonnet-4-6")


def load_secret_key() -> bytes:
    env = os.environ.get("GOV_PORTAL_SECRET_KEY")
    if env:
        return env.encode()
    try:
        fd = os.open(SECRET_KEY_PATH, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(secrets.token_bytes(32))
    except FileExistsError:
        pass
    return SECRET_KEY_PATH.read_bytes()

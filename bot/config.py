import os
import shutil
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
FILES_DIR = BASE_DIR / "files"

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DATABASE_PATH = DATA_DIR / "bot.db"
MAP_FILE_NAME = "karta_sostoyaniy.pdf"

_admin_raw = os.getenv("ADMIN_IDS", "")
ADMIN_IDS: set[int] = {
    int(item.strip())
    for item in _admin_raw.split(",")
    if item.strip().isdigit()
}


def get_map_file_path() -> Path:
    """Возвращает путь к PDF с латинским именем (надёжнее на Windows)."""
    FILES_DIR.mkdir(parents=True, exist_ok=True)
    safe_path = FILES_DIR / MAP_FILE_NAME

    if safe_path.exists():
        return safe_path

    pdfs = sorted(FILES_DIR.glob("*.pdf"))
    if pdfs:
        shutil.copy2(pdfs[0], safe_path)
        return safe_path

    return safe_path

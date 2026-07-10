"""
Dunju AI — Central Configuration
All settings live here. Change once, applies everywhere.
v2.5.0
"""

from pathlib import Path

# ── Paths ──
BASE_DIR = Path(__file__).parent.parent
DB_PATH  = BASE_DIR / "dunju_ai_memory.db"

# ── Ollama ──
OLLAMA_URL    = "http://localhost:11434"
DEFAULT_MODEL = "dunju-ai:latest"

# ── Server ──
HOST = "0.0.0.0"
PORT = 8000

# ── Document Engine ──
MAX_PAGES     = 20      # max PDF pages to extract
MAX_CHARS     = 15000   # max characters sent to LLM per document

# ── App ──
APP_NAME    = "Dunju AI Backend"
APP_VERSION = "2.6.0"
APP_BUILD   = "260"
PHILOSOPHY  = "Build. Automate. Scale."

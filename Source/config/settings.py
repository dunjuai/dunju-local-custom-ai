"""
Dunju AI — Central Configuration
All settings live here. Change once, applies everywhere.
"""

import os
from pathlib import Path

# ── Paths ──
BASE_DIR = Path(__file__).parent.parent
# DUNJU_DB_PATH lets tests (or power users) point at a different database file.
DB_PATH  = Path(os.environ.get("DUNJU_DB_PATH") or (BASE_DIR / "dunju_ai_memory.db"))
FRONTEND_DIR = BASE_DIR / "frontend"

# ── Ollama ──
OLLAMA_URL    = "http://localhost:11434"
DEFAULT_MODEL = "dunju-ai:latest"

# ── Server ──
# 127.0.0.1 = only this computer can reach the backend (recommended).
# To share on your LAN, set the DUNJU_HOST environment variable to 0.0.0.0 AND list
# the hostnames/IPs people will use in DUNJU_ALLOWED_HOSTS (comma-separated).
# Note: anyone who can open the page on your LAN can then use the app.
HOST = os.environ.get("DUNJU_HOST", "127.0.0.1")
PORT = int(os.environ.get("DUNJU_PORT", "8000"))
ALLOWED_HOSTS = ["127.0.0.1", "localhost"] + [
    h.strip() for h in os.environ.get("DUNJU_ALLOWED_HOSTS", "").split(",") if h.strip()
]

# ── Document Engine ──
MAX_UPLOAD_MB = 20      # default upload size limit (overridable in Settings > Documents)
MAX_PAGES     = 20      # max PDF pages for the inline preview path (non-RAG)
MAX_CHARS     = 15000   # max characters for the inline preview path (non-RAG)

# ── RAG (Retrieval-Augmented Generation) ──
# When RAG is on, the whole document is indexed (not truncated), so these
# caps are large safety limits rather than the real ceiling.
EMBED_MODEL    = "nomic-embed-text"   # local Ollama embedding model (ollama pull nomic-embed-text)
CHUNK_SIZE     = 1000                 # target characters per chunk
CHUNK_OVERLAP  = 150                  # character overlap between adjacent chunks
RAG_TOP_K      = 6                    # chunks retrieved and injected per question
SUMMARY_CHUNKS = 8                    # representative chunks used for "summarize" requests
MAX_CONTEXT_CHARS = 9000              # hard cap on retrieved text injected per turn
                                      # (keeps the prompt within the model's context
                                      #  window so there is always room to generate)
MAX_PAGES_RAG  = 500                  # safety cap on pages indexed
MAX_CHARS_RAG  = 500000               # safety cap on characters indexed

# ── App ──
APP_NAME    = "Dunju AI Backend"
APP_VERSION = "1.0.1"
APP_BUILD   = "101"
PHILOSOPHY  = "Build. Automate. Scale."

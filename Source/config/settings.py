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
APP_VERSION = "1.0.0"
APP_BUILD   = "100"
PHILOSOPHY  = "Build. Automate. Scale."

"""
Dunju AI — Main Backend Entry Point
Clean modular architecture. Each module has one responsibility.
Build. Automate. Scale.
v2.5.0 — Removed projects, knowledge base, activity log
"""

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
import httpx
import json
import traceback
from datetime import datetime

# ── Internal modules ──
from config.settings import OLLAMA_URL, DEFAULT_MODEL, HOST, PORT, APP_NAME, APP_VERSION, APP_BUILD, PHILOSOPHY, DB_PATH
from database.db import init_db, migrate_db
from ai.experts import seed_default_experts, get_all_experts, get_expert_by_name, create_expert, update_expert, delete_expert
from ai.prompts import build_system_prompt
from document.engine import process_file
from document.classifier import classify_document, detect_language
from document.context_builder import build_context
from memory.chat_memory import (
    list_chats, create_chat, get_chat, save_message,
    rename_chat, delete_chat, delete_all_chats, duplicate_chat
)
from settings_engine import (
    seed_default_settings, get_all_settings, get_setting,
    set_setting, update_settings, get_db_stats
)

# ── Startup / shutdown (FastAPI lifespan style) ──
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    migrate_db()
    seed_default_experts()
    seed_default_settings()
    yield

# ── App setup ──
app = FastAPI(title=APP_NAME, version=APP_VERSION, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ════════════════════════════════════════════
#  PYDANTIC MODELS
# ════════════════════════════════════════════

class ChatMessage(BaseModel):
    role: str
    content: str
    display_content: Optional[str] = None
    file_names: Optional[List[str]] = None


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    system_prompt: Optional[str] = None
    model: Optional[str] = DEFAULT_MODEL
    stream: Optional[bool] = True
    chat_id: Optional[str] = None
    skill: Optional[str] = "General"


class CreateChatRequest(BaseModel):
    title: Optional[str] = "New Chat"
    skill: Optional[str] = "General"


class SaveMessageRequest(BaseModel):
    chat_id: str
    role: str
    content: str
    display_content: Optional[str] = None
    file_names: Optional[List[str]] = None


class RenameChatRequest(BaseModel):
    title: str


class CreateExpertRequest(BaseModel):
    name: str
    emoji: Optional[str] = "🤖"
    color: Optional[str] = "#a855f7"
    system_prompt: str
    suggested_actions: Optional[list] = []
    default_questions: Optional[list] = []


class UpdateExpertRequest(BaseModel):
    name: Optional[str] = None
    emoji: Optional[str] = None
    color: Optional[str] = None
    system_prompt: Optional[str] = None
    suggested_actions: Optional[list] = None
    default_questions: Optional[list] = None


class UpdateSettingsRequest(BaseModel):
    settings: dict


# ════════════════════════════════════════════
#  CORE ENDPOINTS
# ════════════════════════════════════════════

@app.get("/")
async def root():
    return {
        "service": APP_NAME, "version": APP_VERSION, "build": APP_BUILD,
        "philosophy": PHILOSOPHY, "ai_engine": "Ollama", "model": DEFAULT_MODEL,
        "backend": "FastAPI", "database": "SQLite",
        "document_engine": "v1", "memory_engine": "v1"
    }


@app.get("/health")
async def health():
    db_status = "ready" if DB_PATH.exists() else "initializing"
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            res = await client.get(f"{OLLAMA_URL}/api/tags")
            if res.status_code == 200:
                models = [m["name"] for m in res.json().get("models", [])]
                return {"status": "healthy", "ollama": "connected", "models": models, "memory_db": db_status}
            # Ollama responded but not with 200 — backend itself is still up
            return {"status": "degraded", "ollama": "error", "ollama_http": res.status_code, "memory_db": db_status}
    except Exception as e:
        return {"status": "degraded", "ollama": "offline", "error": str(e), "memory_db": db_status}


# ════════════════════════════════════════════
#  DOCUMENT ENDPOINTS
# ════════════════════════════════════════════

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        file_bytes = await file.read()
        filename = file.filename
        print(f"Processing: {filename} ({len(file_bytes)} bytes)")
        result = process_file(file_bytes, filename)
        doc_type = classify_document(result["text"])
        language = detect_language(result["text"])
        return {
            "filename": filename,
            "size": len(file_bytes),
            "extracted_text": result["text"],
            "char_count": result.get("char_count"),
            "word_count": result.get("word_count"),
            "pages": result.get("pages"),
            "tables": result.get("tables"),
            "images": result.get("images"),
            "language": language,
            "doc_type": doc_type,
            "processing_time": result.get("processing_time"),
            "status": "success"
        }
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


# ════════════════════════════════════════════
#  CHAT ENDPOINTS
# ════════════════════════════════════════════

@app.get("/chats")
async def api_list_chats():
    return {"chats": list_chats()}


@app.post("/chats")
async def api_create_chat(request: CreateChatRequest):
    return create_chat(request.title, request.skill)


@app.get("/chats/{chat_id}")
async def api_get_chat(chat_id: str):
    chat = get_chat(chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    return chat


@app.post("/chats/{chat_id}/messages")
async def api_save_message(chat_id: str, request: SaveMessageRequest):
    save_message(chat_id, request.role, request.content, request.display_content, request.file_names)
    return {"status": "saved"}


@app.put("/chats/{chat_id}/rename")
async def api_rename_chat(chat_id: str, request: RenameChatRequest):
    rename_chat(chat_id, request.title)
    return {"status": "renamed"}


@app.delete("/chats/{chat_id}")
async def api_delete_chat(chat_id: str):
    delete_chat(chat_id)
    return {"status": "deleted"}


@app.delete("/chats")
async def api_delete_all_chats():
    delete_all_chats()
    return {"status": "all_cleared"}


@app.post("/chats/{chat_id}/duplicate")
async def api_duplicate_chat(chat_id: str):
    chat = duplicate_chat(chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    return chat


# ════════════════════════════════════════════
#  AI EXPERT ENDPOINTS
# ════════════════════════════════════════════

@app.get("/experts")
async def api_list_experts():
    return {"experts": get_all_experts()}


@app.post("/experts")
async def api_create_expert(request: CreateExpertRequest):
    expert = create_expert(
        request.name, request.emoji, request.color,
        request.system_prompt, request.suggested_actions, request.default_questions
    )
    return expert


@app.put("/experts/{expert_id}")
async def api_update_expert(expert_id: str, request: UpdateExpertRequest):
    fields = {k: v for k, v in request.dict().items() if v is not None}
    update_expert(expert_id, **fields)
    return {"status": "updated"}


@app.delete("/experts/{expert_id}")
async def api_delete_expert(expert_id: str):
    ok = delete_expert(expert_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Expert not found")
    return {"status": "deleted"}


# ════════════════════════════════════════════
#  SETTINGS ENDPOINTS
# ════════════════════════════════════════════

@app.get("/settings")
async def api_get_settings():
    return get_all_settings()


@app.put("/settings")
async def api_update_settings(request: UpdateSettingsRequest):
    update_settings(request.settings)
    return {"status": "updated"}


@app.get("/settings/database")
async def api_database_stats():
    return get_db_stats()


# ════════════════════════════════════════════
#  DATABASE BACKUP / RESTORE
# ════════════════════════════════════════════

BACKUP_DIR = DB_PATH.parent.parent / "Backups"


@app.post("/database/backup")
async def api_backup_database():
    import shutil
    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = BACKUP_DIR / f"dunju_ai_memory_{stamp}.db"
        shutil.copy2(DB_PATH, dest)
        set_setting("last_backup", datetime.now().isoformat())
        return {"status": "backed_up", "path": str(dest)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/database/restore")
async def api_restore_database(file: UploadFile = File(...)):
    import shutil
    try:
        content = await file.read()
        # Validate it's a real SQLite database before touching anything
        if not content.startswith(b"SQLite format 3\x00"):
            raise HTTPException(status_code=400, detail="Not a valid SQLite database file")
        # Safety net: back up the current DB first
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy2(DB_PATH, BACKUP_DIR / f"pre_restore_{stamp}.db")
        # Replace the live DB
        with open(DB_PATH, "wb") as f:
            f.write(content)
        return {"status": "restored", "safety_backup": f"pre_restore_{stamp}.db"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ════════════════════════════════════════════
#  LLM STREAMING CHAT
# ════════════════════════════════════════════

@app.post("/chat")
async def chat(request: ChatRequest):
    system_prompt = request.system_prompt or build_system_prompt(request.skill or "General")

    messages = [{"role": "system", "content": system_prompt}]
    messages += [{"role": m.role, "content": m.content} for m in request.messages]

    # Model options from settings (Settings > AI)
    try:
        temperature = float(get_setting("temperature", "0.7"))
    except (TypeError, ValueError):
        temperature = 0.7
    try:
        max_tokens = int(get_setting("max_tokens", "2048"))
    except (TypeError, ValueError):
        max_tokens = 2048

    async def stream_response():
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                async with client.stream(
                    "POST", f"{OLLAMA_URL}/api/chat",
                    json={
                        "model": request.model or DEFAULT_MODEL,
                        "messages": messages,
                        "stream": True,
                        "think": False,
                        "options": {
                            "temperature": temperature,
                            "num_predict": max_tokens
                        }
                    }
                ) as response:
                    async for chunk in response.aiter_text():
                        yield chunk
        except Exception as e:
            yield json.dumps({"error": str(e)})

    return StreamingResponse(stream_response(), media_type="application/x-ndjson")


# ════════════════════════════════════════════
#  LAUNCHER
# ════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*52)
    print(f"  {APP_NAME} v{APP_VERSION}")
    print(f"  {PHILOSOPHY}")
    print("="*52)
    print(f"  API:      http://localhost:{PORT}")
    print(f"  Health:   http://localhost:{PORT}/health")
    print(f"  Experts:  http://localhost:{PORT}/experts")
    print(f"  Ollama:   {OLLAMA_URL}")
    print(f"  Database: {DB_PATH}")
    print("="*52 + "\n")
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)

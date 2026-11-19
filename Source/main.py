"""
Dunju AI — Main Backend Entry Point
Clean modular architecture. Each module has one responsibility.
Build. Automate. Scale.

Security model: the backend listens on 127.0.0.1 only, serves the UI itself
(same origin, so no CORS is needed), rejects requests whose Host header is not
an allowed local name (blocks DNS-rebinding), and requires a per-launch access
token on every API call. The token is embedded in the page served at "/".
"""

import os
import secrets
from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Request
from fastapi.responses import StreamingResponse, Response, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel
from typing import List, Optional
import httpx
import json
import uuid
import traceback
from datetime import datetime

# ── Internal modules ──
from config.settings import (
    OLLAMA_URL, DEFAULT_MODEL, HOST, PORT, ALLOWED_HOSTS, APP_NAME, APP_VERSION, APP_BUILD,
    PHILOSOPHY, DB_PATH, MAX_CHARS, MAX_UPLOAD_MB, FRONTEND_DIR,
)
from database.db import init_db, migrate_db
from ai.experts import seed_default_experts, get_all_experts, get_expert_by_name, create_expert, update_expert, delete_expert
from ai.prompts import build_system_prompt
from document.engine import process_file, legacy_format_message
from document.classifier import classify_document, detect_language, DOC_TYPE_LABELS
from document.context_builder import build_context
from document.generator import generate as generate_document
from document.batch import scan_folder, extract_file_text
from memory.crypto import encrypt_bytes, decrypt_bytes
from memory.activity import log_activity, recent_activity, clear_activity
from document.rag import (
    rag_enabled, index_document, retrieve, retrieve_summary, is_summary_query,
    build_rag_context, delete_doc_chunks, delete_chunks_for_chat, cleanup_orphan_chunks,
)
from memory.chat_memory import (
    list_chats, create_chat, get_chat, save_message,
    rename_chat, delete_chat, delete_all_chats, duplicate_chat, set_chat_docs,
    truncate_chat, branch_chat
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
    try:
        removed = cleanup_orphan_chunks()
        if removed:
            print(f"  RAG: removed {removed} orphaned document chunks")
    except Exception as e:
        print(f"  RAG cleanup skipped: {e}")
    yield

# ── App setup ──
app = FastAPI(title=APP_NAME, version=APP_VERSION, lifespan=lifespan,
              docs_url=None, redoc_url=None, openapi_url=None)

# Per-launch access token. Set DUNJU_TOKEN to pin it (e.g. for scripts/tests).
API_TOKEN = os.environ.get("DUNJU_TOKEN") or secrets.token_urlsafe(32)
TOKEN_HEADER = "x-dunju-token"
INDEX_FILE = FRONTEND_DIR / "DunjuAI_Chat.html"
ASSETS_DIR = FRONTEND_DIR / "assets"


@app.middleware("http")
async def require_token(request: Request, call_next):
    """Every API call must carry the token. Only the page itself, /health and the
    static assets are public (the page is what hands the token to the browser; other
    websites cannot read it because there is no CORS)."""
    path = request.url.path
    # /health is public too: it only reports up/down + model names, and support
    # needs to open it directly in a browser when debugging.
    if request.method == "GET" and (path in ("/", "/health", "/favicon.ico") or path.startswith("/assets/")):
        return await call_next(request)
    supplied = request.headers.get(TOKEN_HEADER, "")
    if not secrets.compare_digest(supplied, API_TOKEN):
        return JSONResponse(
            {"detail": f"Missing or invalid access token. Open the app at http://127.0.0.1:{PORT} and reload the page."},
            status_code=401,
        )
    return await call_next(request)


# Added last = runs first: reject unexpected Host headers before anything else.
app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)

if ASSETS_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")

_CSP = ("default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; "
        "object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")


def _max_upload_bytes() -> int:
    try:
        mb = float(get_setting("max_upload_mb", str(MAX_UPLOAD_MB)) or MAX_UPLOAD_MB)
    except (TypeError, ValueError):
        mb = MAX_UPLOAD_MB
    return int(max(1, mb) * 1024 * 1024)


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
    doc_ids: Optional[List[str]] = None


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


class KeepRequest(BaseModel):
    keep: int = 0


class GenerateRequest(BaseModel):
    content: str
    format: str = "docx"
    title: Optional[str] = "Dunju AI Export"


class BatchScanRequest(BaseModel):
    folder: str
    recursive: bool = False


class BatchRunRequest(BaseModel):
    folder: str
    recursive: bool = False
    action: str = "summarize"
    prompt: Optional[str] = ""
    files: Optional[List[str]] = None


class CreateExpertRequest(BaseModel):
    name: str
    emoji: Optional[str] = "🤖"
    color: Optional[str] = "#a855f7"
    system_prompt: str
    suggested_actions: Optional[list] = []
    default_questions: Optional[list] = []
    model: Optional[str] = ""


class UpdateExpertRequest(BaseModel):
    name: Optional[str] = None
    emoji: Optional[str] = None
    color: Optional[str] = None
    system_prompt: Optional[str] = None
    suggested_actions: Optional[list] = None
    default_questions: Optional[list] = None
    model: Optional[str] = None


class UpdateSettingsRequest(BaseModel):
    settings: dict


class EncBackupRequest(BaseModel):
    password: str


class ActivityRequest(BaseModel):
    event: str
    detail: Optional[str] = ""


# ════════════════════════════════════════════
#  CORE ENDPOINTS
# ════════════════════════════════════════════

@app.get("/", include_in_schema=False)
async def index():
    """Serve the app UI with this launch's access token embedded."""
    if not INDEX_FILE.exists():
        raise HTTPException(status_code=404, detail="Frontend file not found")
    html = INDEX_FILE.read_text(encoding="utf-8").replace("__DUNJU_TOKEN__", API_TOKEN)
    return HTMLResponse(html, headers={
        "Cache-Control": "no-store",
        "Content-Security-Policy": _CSP,
        "X-Frame-Options": "DENY",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer",
    })


@app.get("/info")
async def info():
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
async def upload_file(file: UploadFile = File(...), chat_id: Optional[str] = None):
    try:
        filename = file.filename or "upload"
        legacy = legacy_format_message(filename)
        if legacy:
            raise HTTPException(status_code=415, detail=legacy)
        limit = _max_upload_bytes()
        file_bytes = await file.read(limit + 1)
        if len(file_bytes) > limit:
            raise HTTPException(
                status_code=413,
                detail=f"File is larger than the {limit // (1024 * 1024)} MB upload limit (Settings > Documents).",
            )
        print(f"Processing: {filename} ({len(file_bytes)} bytes)")

        # Extract the FULL document (RAG caps) so nothing is lost to indexing.
        result = process_file(file_bytes, filename, full=True)
        full_text = result["text"]
        doc_type = classify_document(full_text)
        language = detect_language(full_text)

        # Try to index for RAG. On any failure, degrade gracefully to the
        # classic inline path (frontend will send the preview text instead).
        doc_id = None
        indexed = False
        chunk_count = 0
        if rag_enabled():
            try:
                doc_id = str(uuid.uuid4())
                stats = await index_document(doc_id, filename, full_text, chat_id)
                indexed = stats.get("indexed", False)
                chunk_count = stats.get("chunks", 0)
                if not indexed:
                    doc_id = None
            except Exception as e:
                print(f"  RAG indexing failed ({filename}): {e} — falling back to inline text")
                doc_id = None
                indexed = False

        # The response carries a TRUNCATED preview for the UI / inline fallback.
        preview = full_text[:MAX_CHARS]
        log_activity("Document uploaded", filename)
        return {
            "filename": filename,
            "size": len(file_bytes),
            "extracted_text": preview,
            "char_count": len(full_text),
            "word_count": result.get("word_count"),
            "pages": result.get("pages"),
            "tables": result.get("tables"),
            "images": result.get("images"),
            "language": language,
            "doc_type": doc_type,
            "processing_time": result.get("processing_time"),
            "doc_id": doc_id,
            "indexed": indexed,
            "chunk_count": chunk_count,
            "status": "success"
        }
    except HTTPException:
        raise
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/documents/{doc_id}")
async def api_delete_document(doc_id: str):
    removed = delete_doc_chunks(doc_id)
    return {"status": "deleted", "chunks_removed": removed}


# ── Activity log ──
@app.get("/activity")
async def api_activity(limit: int = 50):
    return {"activity": recent_activity(limit)}


@app.post("/activity")
async def api_log_activity(request: ActivityRequest):
    log_activity(request.event, request.detail or "")
    return {"status": "logged"}


@app.delete("/activity")
async def api_clear_activity():
    clear_activity()
    return {"status": "cleared"}


@app.post("/generate")
async def api_generate(request: GenerateRequest):
    """Turn chat content (markdown) into a downloadable .docx/.pdf/.pptx/.xlsx."""
    fmt = (request.format or "docx").lower()
    try:
        data, media = generate_document(request.content or "", fmt, request.title or "Dunju AI Export")
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"Missing library for .{fmt}: {e}. Try: pip install reportlab")
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
    fname = f"dunju-export.{fmt}"
    return Response(content=data, media_type=media,
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})


# ── Batch / folder automation ──
async def _llm_once(prompt: str, max_tokens: int = 512) -> str:
    sysp = build_system_prompt("General") + "\n\n/no_think"
    async with httpx.AsyncClient(timeout=180) as client:
        r = await client.post(f"{OLLAMA_URL}/api/chat", json={
            "model": DEFAULT_MODEL, "stream": False, "think": False,
            "messages": [{"role": "system", "content": sysp},
                         {"role": "user", "content": prompt}],
            "options": {"temperature": 0.3, "num_predict": max_tokens},
        })
        r.raise_for_status()
        return ((r.json().get("message") or {}).get("content") or "").strip()


@app.post("/batch/scan")
async def api_batch_scan(request: BatchScanRequest):
    files = scan_folder(request.folder, request.recursive)
    if files is None:
        raise HTTPException(status_code=400, detail="Folder not found or not a directory")
    return {"folder": request.folder, "count": len(files), "files": files}


@app.post("/batch/run")
async def api_batch_run(request: BatchRunRequest):
    import os as _os
    scanned = scan_folder(request.folder, request.recursive)
    if scanned is None:
        raise HTTPException(status_code=400, detail="Folder not found or not a directory")
    allowed = [f["path"] for f in scanned]
    if request.files:
        # Only files that were found inside the chosen folder may be processed.
        allowed_set = set(allowed)
        rejected = [p for p in request.files if p not in allowed_set]
        if rejected:
            raise HTTPException(status_code=400, detail="Some files are not inside the selected folder")
        paths = list(request.files)
    else:
        paths = allowed
    action = (request.action or "summarize").lower()
    prompts = {
        "summarize": "Summarize this document in 4-6 concise bullet points, focusing on the most important information.",
        "extract": "Extract the key data points — figures, names, dates, totals — from this document as a short structured list.",
        "custom": request.prompt or "Summarize this document.",
    }

    async def stream():
        yield json.dumps({"type": "start", "total": len(paths)}) + "\n"
        for i, path in enumerate(paths):
            name = _os.path.basename(path)
            try:
                text = extract_file_text(path)
                doc_type = classify_document(text)
                if action == "classify":
                    result = DOC_TYPE_LABELS.get(doc_type, doc_type.title())
                else:
                    pr = prompts.get(action, prompts["summarize"])
                    result = await _llm_once(f"{pr}\n\nDOCUMENT: {name}\n\n{text[:12000]}")
                yield json.dumps({"type": "file", "index": i, "name": name,
                                  "doc_type": DOC_TYPE_LABELS.get(doc_type, doc_type),
                                  "result": result}) + "\n"
            except Exception as e:
                yield json.dumps({"type": "file", "index": i, "name": name, "error": str(e)}) + "\n"
        yield json.dumps({"type": "done"}) + "\n"

    return StreamingResponse(stream(), media_type="application/x-ndjson")


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
    log_activity("Memory saved", f"{request.role} message")
    return {"status": "saved"}


@app.put("/chats/{chat_id}/rename")
async def api_rename_chat(chat_id: str, request: RenameChatRequest):
    rename_chat(chat_id, request.title)
    log_activity("Chat renamed", request.title)
    return {"status": "renamed"}


@app.delete("/chats/{chat_id}")
async def api_delete_chat(chat_id: str):
    # Remove this chat's RAG vectors first (needs the chat row to find its docs);
    # documents still used by a branch/duplicate of this chat are kept.
    delete_chunks_for_chat(chat_id)
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


@app.post("/chats/{chat_id}/truncate")
async def api_truncate_chat(chat_id: str, request: KeepRequest):
    truncate_chat(chat_id, request.keep)
    return {"status": "truncated", "keep": request.keep}


@app.post("/chats/{chat_id}/branch")
async def api_branch_chat(chat_id: str, request: KeepRequest):
    chat = branch_chat(chat_id, request.keep)
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
        request.system_prompt, request.suggested_actions, request.default_questions,
        request.model
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
        log_activity("Backup created", dest.name)
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


@app.post("/database/backup/encrypted")
async def api_backup_encrypted(request: EncBackupRequest):
    if not request.password or len(request.password) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters")
    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        enc = encrypt_bytes(DB_PATH.read_bytes(), request.password)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = BACKUP_DIR / f"dunju_ai_backup_{stamp}.dunjuenc"
        dest.write_bytes(enc)
        set_setting("last_backup", datetime.now().isoformat())
        log_activity("Encrypted backup created", dest.name)
        return {"status": "backed_up", "path": str(dest), "encrypted": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/database/restore/encrypted")
async def api_restore_encrypted(file: UploadFile = File(...), password: str = Form(...)):
    import shutil
    try:
        content = await file.read()
        try:
            raw = decrypt_bytes(content, password)
        except ValueError:
            raise HTTPException(status_code=400, detail="Not a Dunju encrypted backup (.dunjuenc)")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=400, detail="Wrong password — could not decrypt the backup")
        if not raw.startswith(b"SQLite format 3\x00"):
            raise HTTPException(status_code=400, detail="Decrypted file is not a valid database")
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy2(DB_PATH, BACKUP_DIR / f"pre_restore_{stamp}.db")
        with open(DB_PATH, "wb") as f:
            f.write(raw)
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
    # Enforce the Language setting (stored but previously unused)
    _lang = (get_setting("language", "English") or "English").strip()
    if _lang and _lang.lower() != "english":
        system_prompt = system_prompt.rstrip() + f"\n\nAlways write your response in {_lang}, regardless of the language of the question or the documents."

    # Reasoning mode (Settings > AI): off = keep Qwen reasoning off so tokens go to
    # the answer; on = let the model think (surfaced in the UI).
    reasoning = (get_setting("reasoning_mode", "false") or "false").lower() == "true"
    if not reasoning:
        system_prompt = system_prompt.rstrip() + "\n\n/no_think"

    # Per-expert model override — an expert can pin its own Ollama model.
    chat_model = request.model or DEFAULT_MODEL
    try:
        _exp = get_expert_by_name(request.skill or "General")
        if _exp and (_exp.get("model") or "").strip():
            chat_model = _exp["model"].strip()
    except Exception:
        pass

    messages = [{"role": "system", "content": system_prompt}]

    # ── RAG: retrieve relevant document chunks for THIS turn ──
    # Uses the latest user message as the query and injects only the
    # top-matching excerpts, so document size stays decoupled from context.
    summary = False
    rag_n = 0
    rag_sources = []
    if request.doc_ids and rag_enabled():
        try:
            last_user = next(
                (m.content for m in reversed(request.messages) if m.role == "user"),
                ""
            )
            # Summary/overview requests get a representative cross-section (incl.
            # the document opening); specific questions use similarity top-k.
            summary = is_summary_query(last_user)
            if summary:
                chunks = await retrieve_summary(request.doc_ids)
            else:
                chunks = await retrieve(last_user, request.doc_ids)
            rag_n = len(chunks)
            rag_block, rag_sources = build_rag_context(chunks, summary=summary)
            if rag_block:
                messages.append({"role": "system", "content": rag_block})
            # Remember which docs belong to this chat (for reload / follow-ups)
            if request.chat_id:
                set_chat_docs(request.chat_id, request.doc_ids)
        except Exception as e:
            print(f"  RAG retrieval failed: {e} — answering without retrieved context")

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

    ctx_chars = sum(len(m["content"]) for m in messages)
    print(f"[chat] docs={len(request.doc_ids or [])} summary={summary} rag_chunks={rag_n} "
          f"messages={len(messages)} ctx_chars={ctx_chars} max_tokens={max_tokens}")

    async def stream_response():
        content_chars = 0
        thinking_buf = []
        done_reason = err = None
        try:
            if rag_sources:
                yield json.dumps({"sources": rag_sources}) + "\n"
            async with httpx.AsyncClient(timeout=180) as client:
                async with client.stream(
                    "POST", f"{OLLAMA_URL}/api/chat",
                    json={
                        "model": chat_model,
                        "messages": messages,
                        "stream": True,
                        "think": reasoning,
                        "options": {
                            "temperature": temperature,
                            "num_predict": max_tokens
                        }
                    }
                ) as response:
                    if response.status_code != 200:
                        body = (await response.aread()).decode("utf-8", "ignore")
                        print(f"[chat] Ollama HTTP {response.status_code}: {body[:300]}")
                        yield json.dumps({"error": f"Ollama {response.status_code}: {body[:200]}"})
                        return
                    async for chunk in response.aiter_text():
                        # Inspect (for diagnostics + empty-answer recovery) then pass through
                        for line in chunk.splitlines():
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                d = json.loads(line)
                            except Exception:
                                continue
                            msg = d.get("message") or {}
                            if msg.get("content"):
                                content_chars += len(msg["content"])
                            if msg.get("thinking"):
                                thinking_buf.append(msg["thinking"])
                            if d.get("done"):
                                done_reason = d.get("done_reason")
                            if d.get("error"):
                                err = d.get("error")
                        yield chunk
                    # Recovery: never leave the user with a blank bubble
                    if content_chars == 0:
                        if thinking_buf:
                            recovered = "".join(thinking_buf).strip()
                            print(f"[chat] content empty; recovered {len(recovered)}ch from thinking")
                        else:
                            recovered = ("I could not generate a response for this request. "
                                         "If it was a large summary, try again or ask a more specific "
                                         "question; you can also raise Max Tokens in Settings > AI.")
                            print("[chat] content empty and no thinking -> sent fallback message")
                        if recovered:
                            yield "\n" + json.dumps(
                                {"message": {"role": "assistant", "content": recovered}, "done": True}
                            )
        except Exception as e:
            err = str(e)
            yield json.dumps({"error": str(e)})
        finally:
            print(f"[chat] stream end: content={content_chars}ch "
                  f"thinking={sum(len(t) for t in thinking_buf)}ch "
                  f"done_reason={done_reason} err={err}")

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
    print(f"  Open the app:  http://127.0.0.1:{PORT}")
    print(f"  Listening on:  {HOST}:{PORT}")
    print(f"  Ollama:        {OLLAMA_URL}")
    print(f"  Database:      {DB_PATH}")
    if HOST not in ("127.0.0.1", "localhost"):
        print("  WARNING: listening beyond this computer. Anyone who can open the")
        print("           page on your network can use the app and read your chats.")
    print("="*52 + "\n")
    uvicorn.run(app, host=HOST, port=PORT, reload=False)

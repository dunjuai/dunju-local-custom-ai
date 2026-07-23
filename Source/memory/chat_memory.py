"""
Dunju AI — Chat Memory Engine
All chat and message CRUD operations against SQLite.
v2.5.0 — Removed project_id, activity log, dashboard stats
"""

import json
import uuid
from datetime import datetime
from database.db import get_db


def list_chats() -> list:
    conn = get_db()
    rows = conn.execute("""
        SELECT c.*,
               EXISTS(
                   SELECT 1 FROM messages m
                   WHERE m.chat_id = c.id
                     AND m.file_names IS NOT NULL
                     AND m.file_names != '' AND m.file_names != '[]'
               ) AS has_files
        FROM chats c ORDER BY c.updated_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def duplicate_chat(chat_id: str) -> dict | None:
    """Create a full copy of a chat (messages included)."""
    conn = get_db()
    src = conn.execute("SELECT * FROM chats WHERE id = ?", (chat_id,)).fetchone()
    if not src:
        conn.close()
        return None
    now = datetime.now().isoformat()
    new_id = str(uuid.uuid4())
    new_title = "Copy of " + src["title"]
    conn.execute(
        "INSERT INTO chats (id, title, skill, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (new_id, new_title, src["skill"], now, now)
    )
    conn.execute("""
        INSERT INTO messages (chat_id, role, content, display_content, file_names, created_at)
        SELECT ?, role, content, display_content, file_names, created_at
        FROM messages WHERE chat_id = ? ORDER BY id ASC
    """, (new_id, chat_id))
    conn.commit()
    conn.close()
    return {"id": new_id, "title": new_title, "skill": src["skill"], "created_at": now, "updated_at": now}


def truncate_chat(chat_id: str, keep: int) -> bool:
    """Delete all messages in a chat beyond the first `keep` (by id order)."""
    conn = get_db()
    ids = [r["id"] for r in conn.execute(
        "SELECT id FROM messages WHERE chat_id = ? ORDER BY id ASC", (chat_id,)).fetchall()]
    for mid in ids[max(0, keep):]:
        conn.execute("DELETE FROM messages WHERE id = ?", (mid,))
    conn.execute("UPDATE chats SET updated_at = ? WHERE id = ?",
                 (datetime.now().isoformat(), chat_id))
    conn.commit()
    conn.close()
    return True


def branch_chat(chat_id: str, keep: int) -> dict | None:
    """Create a new chat containing a copy of the first `keep` messages."""
    conn = get_db()
    src = conn.execute("SELECT * FROM chats WHERE id = ?", (chat_id,)).fetchone()
    if not src:
        conn.close()
        return None
    now = datetime.now().isoformat()
    new_id = str(uuid.uuid4())
    new_title = "Branch of " + src["title"]
    doc_ids = src["doc_ids"] if "doc_ids" in src.keys() else "[]"
    conn.execute(
        "INSERT INTO chats (id, title, skill, doc_ids, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (new_id, new_title, src["skill"], doc_ids, now, now)
    )
    ids = [r["id"] for r in conn.execute(
        "SELECT id FROM messages WHERE chat_id = ? ORDER BY id ASC", (chat_id,)).fetchall()]
    keep_ids = ids[:max(0, keep)]
    if keep_ids:
        ph = ",".join("?" for _ in keep_ids)
        conn.execute(f"""
            INSERT INTO messages (chat_id, role, content, display_content, file_names, created_at)
            SELECT ?, role, content, display_content, file_names, created_at
            FROM messages WHERE id IN ({ph}) ORDER BY id ASC
        """, (new_id, *keep_ids))
    conn.commit()
    conn.close()
    return {"id": new_id, "title": new_title, "skill": src["skill"], "created_at": now, "updated_at": now}


def create_chat(title: str = "New Chat", skill: str = "General") -> dict:
    conn = get_db()
    now = datetime.now().isoformat()
    chat_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO chats (id, title, skill, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (chat_id, title, skill, now, now)
    )
    conn.commit()
    conn.close()
    return {"id": chat_id, "title": title, "skill": skill, "created_at": now, "updated_at": now}


def get_chat(chat_id: str) -> dict | None:
    conn = get_db()
    chat = conn.execute("SELECT * FROM chats WHERE id = ?", (chat_id,)).fetchone()
    if not chat:
        conn.close()
        return None
    messages = conn.execute(
        "SELECT role, content, display_content, file_names, created_at FROM messages WHERE chat_id = ? ORDER BY id ASC",
        (chat_id,)
    ).fetchall()
    conn.close()
    msg_list = []
    for m in messages:
        msg_list.append({
            "role": m["role"],
            "content": m["content"],
            "display_content": m["display_content"],
            "file_names": json.loads(m["file_names"]) if m["file_names"] else [],
            "created_at": m["created_at"]
        })
    chat_dict = dict(chat)
    # doc_ids is stored as a JSON string — hand the frontend a real list
    try:
        chat_dict["doc_ids"] = json.loads(chat_dict.get("doc_ids") or "[]")
    except (TypeError, ValueError):
        chat_dict["doc_ids"] = []
    return {**chat_dict, "messages": msg_list}


def set_chat_docs(chat_id: str, doc_ids: list) -> bool:
    """Persist the set of RAG document ids attached to a chat."""
    conn = get_db()
    conn.execute(
        "UPDATE chats SET doc_ids = ? WHERE id = ?",
        (json.dumps(doc_ids or []), chat_id)
    )
    conn.commit()
    conn.close()
    return True


def save_message(chat_id: str, role: str, content: str,
                 display_content: str = None, file_names: list = None) -> bool:
    conn = get_db()
    now = datetime.now().isoformat()
    conn.execute(
        "INSERT INTO messages (chat_id, role, content, display_content, file_names, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (chat_id, role, content, display_content, json.dumps(file_names or []), now)
    )
    # Auto-title from first user message
    chat = conn.execute("SELECT title FROM chats WHERE id = ?", (chat_id,)).fetchone()
    if chat and chat["title"] == "New Chat" and role == "user":
        text = (display_content or content).strip()
        new_title = text[:40] + ("..." if len(text) > 40 else "")
        conn.execute("UPDATE chats SET title = ?, updated_at = ? WHERE id = ?", (new_title, now, chat_id))
    else:
        conn.execute("UPDATE chats SET updated_at = ? WHERE id = ?", (now, chat_id))
    conn.commit()
    conn.close()
    return True


def rename_chat(chat_id: str, title: str) -> bool:
    conn = get_db()
    conn.execute("UPDATE chats SET title = ?, updated_at = ? WHERE id = ?",
                 (title, datetime.now().isoformat(), chat_id))
    conn.commit()
    conn.close()
    return True


def delete_chat(chat_id: str) -> bool:
    conn = get_db()
    conn.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
    conn.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
    conn.commit()
    conn.close()
    return True


def delete_all_chats() -> bool:
    conn = get_db()
    conn.execute("DELETE FROM messages")
    conn.execute("DELETE FROM chats")
    # also clear the RAG vector store — orphaned chunks serve no purpose
    try:
        conn.execute("DELETE FROM doc_chunks")
    except Exception:
        pass
    conn.commit()
    conn.close()
    return True

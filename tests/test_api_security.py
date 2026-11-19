"""The backend must only be usable by the page it serves."""
import json
from datetime import datetime, timedelta

from conftest import AUTH, TOKEN


def test_index_serves_page_with_token_and_csp(client):
    r = client.get("/")
    assert r.status_code == 200
    assert TOKEN in r.text
    assert "__DUNJU_TOKEN__" not in r.text
    assert "connect-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["x-frame-options"] == "DENY"


def test_api_requires_token(client):
    assert client.get("/chats").status_code == 401
    assert client.get("/chats", headers={"X-Dunju-Token": "wrong"}).status_code == 401
    assert client.delete("/chats").status_code == 401
    assert client.get("/chats", headers=AUTH).status_code == 200


def test_unknown_host_rejected(client):
    r = client.get("/", headers={"Host": "evil.example.com"})
    assert r.status_code == 400


def test_no_cors_headers_for_other_sites(client):
    r = client.get("/chats", headers={**AUTH, "Origin": "https://evil.example.com"})
    assert "access-control-allow-origin" not in r.headers


def test_upload_rejects_legacy_format(client):
    r = client.post("/upload", headers=AUTH, files={"file": ("old.doc", b"x" * 10)})
    assert r.status_code == 415
    assert ".docx" in r.json()["detail"]


def test_upload_size_limit_enforced_on_server(client):
    client.put("/settings", headers=AUTH, json={"settings": {"max_upload_mb": "1", "rag_enabled": "false"}})
    try:
        big = b"a" * (1024 * 1024 + 10)
        r = client.post("/upload", headers=AUTH, files={"file": ("big.txt", big)})
        assert r.status_code == 413
        r = client.post("/upload", headers=AUTH, files={"file": ("small.txt", b"hello world")})
        assert r.status_code == 200
    finally:
        client.put("/settings", headers=AUTH, json={"settings": {"max_upload_mb": "20", "rag_enabled": "true"}})


def test_batch_only_processes_files_inside_folder(client, tmp_path):
    (tmp_path / "a.txt").write_text("hello")
    outside = tmp_path.parent / "outside-secret.txt"
    outside.write_text("secret")
    r = client.post("/batch/run", headers=AUTH, json={
        "folder": str(tmp_path), "action": "classify", "files": [str(outside)]})
    assert r.status_code == 400
    r = client.post("/batch/run", headers=AUTH, json={
        "folder": str(tmp_path), "action": "classify"})
    assert r.status_code == 200
    lines = [json.loads(l) for l in r.text.splitlines() if l.strip()]
    assert [l["name"] for l in lines if l["type"] == "file"] == ["a.txt"]


def _add_chunk(doc_id, created_at=None):
    from database.db import get_db
    conn = get_db()
    conn.execute(
        "INSERT INTO doc_chunks (doc_id, chat_id, source_name, chunk_index, content, embedding, created_at) "
        "VALUES (?, NULL, 'f.txt', 0, 'text', ?, ?)",
        (doc_id, b"\x00" * 4, created_at or datetime.now().isoformat()))
    conn.commit()
    conn.close()


def _chunk_count(doc_id):
    from database.db import get_db
    conn = get_db()
    n = conn.execute("SELECT COUNT(*) FROM doc_chunks WHERE doc_id = ?", (doc_id,)).fetchone()[0]
    conn.close()
    return n


def test_deleting_chat_keeps_docs_used_by_branch(client):
    from memory.chat_memory import set_chat_docs
    chat = client.post("/chats", headers=AUTH, json={"title": "t"}).json()
    _add_chunk("doc-shared")
    set_chat_docs(chat["id"], ["doc-shared"])
    branch = client.post(f"/chats/{chat['id']}/branch", headers=AUTH, json={"keep": 0}).json()
    dup = client.post(f"/chats/{chat['id']}/duplicate", headers=AUTH).json()

    client.delete(f"/chats/{chat['id']}", headers=AUTH)
    assert _chunk_count("doc-shared") == 1          # branch + duplicate still use it
    client.delete(f"/chats/{branch['id']}", headers=AUTH)
    assert _chunk_count("doc-shared") == 1          # duplicate still uses it
    client.delete(f"/chats/{dup['id']}", headers=AUTH)
    assert _chunk_count("doc-shared") == 0          # last user gone -> cleaned up


def test_cleanup_removes_only_old_unattached_docs(client):
    from document.rag import cleanup_orphan_chunks
    old = (datetime.now() - timedelta(days=3)).isoformat()
    _add_chunk("doc-old-orphan", old)
    _add_chunk("doc-new-orphan")
    cleanup_orphan_chunks()
    assert _chunk_count("doc-old-orphan") == 0
    assert _chunk_count("doc-new-orphan") == 1


def test_health_is_public(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert "status" in r.json()


def test_assets_are_public(client):
    r = client.get("/assets/dunju-logo.jpg")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/jpeg"

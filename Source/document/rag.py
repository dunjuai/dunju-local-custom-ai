"""
Dunju AI — RAG Engine (Retrieval-Augmented Generation)

Makes document size effectively unlimited on modest hardware.
Pipeline:  full text -> chunks -> embeddings (local Ollama model)
           -> SQLite vector store -> cosine top-k retrieval per question.

No external vector database: a brute-force cosine over stored float32
vectors is instant for local, single-user use and fits the existing
SQLite architecture. Everything degrades gracefully — if the embedding
model is missing or Ollama is offline, callers fall back to the classic
inline-text behaviour instead of erroring.
"""

import re
import json
import httpx
import numpy as np
from datetime import datetime, timedelta

from database.db import get_db
from config.settings import (
    OLLAMA_URL, EMBED_MODEL, CHUNK_SIZE, CHUNK_OVERLAP, RAG_TOP_K, SUMMARY_CHUNKS,
    MAX_CONTEXT_CHARS,
)
from settings_engine import get_setting


# ── Settings helpers (DB overrides config defaults) ──────────────────
def _embed_model() -> str:
    return get_setting("embedding_model", EMBED_MODEL) or EMBED_MODEL


def rag_enabled() -> bool:
    return (get_setting("rag_enabled", "true") or "true").lower() != "false"


def _top_k() -> int:
    try:
        return int(get_setting("rag_top_k", str(RAG_TOP_K)) or RAG_TOP_K)
    except (TypeError, ValueError):
        return RAG_TOP_K


# ── Chunking ─────────────────────────────────────────────────────────
def chunk_text(text: str, size: int = None, overlap: int = None) -> list:
    """Pack the document into ~size-char chunks with char overlap.

    Splits on line breaks first (keeps paragraphs/rows intact where
    possible), then hard-splits any single block longer than `size`.
    """
    size = size or CHUNK_SIZE
    overlap = overlap or CHUNK_OVERLAP
    text = (text or "").strip()
    if not text:
        return []

    blocks = [b.strip() for b in text.split("\n") if b.strip()]
    chunks, cur = [], ""
    for b in blocks:
        # a single oversized block: flush current, then hard-split it
        if len(b) > size:
            if cur:
                chunks.append(cur)
                cur = ""
            step = max(1, size - overlap)
            for i in range(0, len(b), step):
                chunks.append(b[i:i + size])
            continue
        if len(cur) + len(b) + 1 <= size:
            cur = (cur + "\n" + b).strip()
        else:
            if cur:
                chunks.append(cur)
            cur = b
    if cur:
        chunks.append(cur)

    # prepend a short tail of the previous chunk for context continuity
    if overlap > 0 and len(chunks) > 1:
        stitched = [chunks[0]]
        for i in range(1, len(chunks)):
            tail = chunks[i - 1][-overlap:]
            stitched.append((tail + "\n" + chunks[i]).strip())
        chunks = stitched

    return chunks


# ── Embeddings (via Ollama) ──────────────────────────────────────────
async def embed_texts(texts: list) -> list:
    """Return a list of embedding vectors for `texts`.

    Tries the batch /api/embed endpoint first, falls back to the legacy
    per-item /api/embeddings endpoint. Raises on hard failure so the
    caller can fall back to inline text.
    """
    if not texts:
        return []
    model = _embed_model()
    async with httpx.AsyncClient(timeout=180) as client:
        # Preferred: batch endpoint (newer Ollama)
        try:
            res = await client.post(
                f"{OLLAMA_URL}/api/embed",
                json={"model": model, "input": texts},
            )
            if res.status_code == 200:
                embs = res.json().get("embeddings")
                if embs and len(embs) == len(texts):
                    return embs
        except Exception:
            pass
        # Fallback: legacy single-prompt endpoint
        vectors = []
        for t in texts:
            res = await client.post(
                f"{OLLAMA_URL}/api/embeddings",
                json={"model": model, "prompt": t},
            )
            res.raise_for_status()
            vectors.append(res.json()["embedding"])
        return vectors


# ── Indexing ─────────────────────────────────────────────────────────
async def index_document(doc_id: str, source_name: str,
                         full_text: str, chat_id: str = None) -> dict:
    """Chunk + embed + store a document. Returns index stats."""
    chunks = chunk_text(full_text)
    if not chunks:
        return {"doc_id": doc_id, "chunks": 0, "indexed": False}

    vectors = await embed_texts(chunks)
    if len(vectors) != len(chunks):
        return {"doc_id": doc_id, "chunks": 0, "indexed": False}

    now = datetime.now().isoformat()
    conn = get_db()
    # Re-index safety: clear any prior chunks for this doc_id
    conn.execute("DELETE FROM doc_chunks WHERE doc_id = ?", (doc_id,))
    for i, (content, vec) in enumerate(zip(chunks, vectors)):
        blob = np.asarray(vec, dtype=np.float32).tobytes()
        conn.execute(
            "INSERT INTO doc_chunks "
            "(doc_id, chat_id, source_name, chunk_index, content, embedding, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (doc_id, chat_id, source_name, i, content, blob, now),
        )
    conn.commit()
    conn.close()
    return {"doc_id": doc_id, "chunks": len(chunks), "indexed": True}


# ── Keyword scoring (BM25) + rank fusion for hybrid retrieval ─────────
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(t: str) -> list:
    return _TOKEN_RE.findall((t or "").lower())


def _hybrid_enabled() -> bool:
    return (get_setting("rag_hybrid", "true") or "true").lower() != "false"


def _bm25_scores(query, docs_tokens, k1=1.5, b=0.75):
    import math
    from collections import Counter
    n = len(docs_tokens)
    if n == 0:
        return []
    avgdl = (sum(len(d) for d in docs_tokens) / n) or 1.0
    df = Counter()
    doc_tf = []
    for d in docs_tokens:
        tf = Counter(d)
        doc_tf.append(tf)
        for term in tf:
            df[term] += 1
    qterms = set(_tokenize(query))
    idf = {t: math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5)) for t in qterms if df.get(t)}
    scores = []
    for tf in doc_tf:
        dl = sum(tf.values()) or 1
        s = 0.0
        for t in qterms:
            f = tf.get(t, 0)
            if not f or t not in idf:
                continue
            s += idf[t] * (f * (k1 + 1)) / (f + k1 * (1 - b + b * dl / avgdl))
        scores.append(s)
    return scores


def _rrf(rank_lists, k=60, weights=None):
    weights = weights or [1.0] * len(rank_lists)
    scores = {}
    for rl, w in zip(rank_lists, weights):
        for rank, idx in enumerate(rl):
            scores[idx] = scores.get(idx, 0.0) + w / (k + rank + 1)
    return scores


# ── Retrieval (hybrid: keyword BM25 + vector cosine, fused with RRF) ──
async def retrieve(query: str, doc_ids: list, top_k: int = None) -> list:
    """Return the top-k most relevant chunks. Hybrid keyword+vector when
    rag_hybrid is on (better for exact names/numbers/IDs), else pure cosine."""
    if not doc_ids:
        return []
    top_k = top_k or _top_k()

    conn = get_db()
    placeholders = ",".join("?" for _ in doc_ids)
    rows = conn.execute(
        f"SELECT source_name, content, embedding, chunk_index FROM doc_chunks "
        f"WHERE doc_id IN ({placeholders})",
        tuple(doc_ids),
    ).fetchall()
    conn.close()
    if not rows:
        return []

    contents = [r["content"] for r in rows]

    # vector (cosine) scores — 0.0 where embeddings are missing/unavailable
    cos = [0.0] * len(rows)
    try:
        qvec = await embed_texts([query or ""])
    except Exception:
        qvec = []
    if qvec:
        q = np.asarray(qvec[0], dtype=np.float32)
        qn = q / (np.linalg.norm(q) + 1e-8)
        for i, r in enumerate(rows):
            v = np.frombuffer(r["embedding"], dtype=np.float32)
            if v.shape == q.shape:
                cos[i] = float(np.dot(qn, v / (np.linalg.norm(v) + 1e-8)))

    hybrid = _hybrid_enabled() and bool((query or "").strip())
    if hybrid:
        bm = _bm25_scores(query, [_tokenize(c) for c in contents])
        vec_rank = sorted(range(len(rows)), key=lambda i: cos[i], reverse=True)
        kw_rank = sorted(range(len(rows)), key=lambda i: bm[i], reverse=True)
        fused = _rrf([vec_rank, kw_rank], weights=[1.0, 1.6])  # boost keyword for exact matches
        order = sorted(range(len(rows)), key=lambda i: fused.get(i, 0.0), reverse=True)
        score_of = lambda i: fused.get(i, 0.0)
    else:
        if not qvec:
            return []
        order = sorted(range(len(rows)), key=lambda i: cos[i], reverse=True)
        score_of = lambda i: cos[i]

    return [
        {"score": round(float(score_of(i)), 4),
         "source": rows[i]["source_name"],
         "content": rows[i]["content"],
         "chunk_index": rows[i]["chunk_index"]}
        for i in order[:top_k]
    ]


# ── Summary-aware retrieval ──────────────────────────────────────────
# "Summarize the whole document" is a vague query: plain cosine top-k tends
# to grab a few similar (often number-dense) chunks and miss the opening /
# executive summary, producing a skewed or hallucinated summary. For summary
# intent we instead return a REPRESENTATIVE cross-section: the opening chunks
# (where abstracts/exec summaries live) plus an even spread across the document.
# Word-boundary matching (not naive substring) so short tokens like "gist"
# never match inside words like "register" or "logistics".
_SUMMARY_RE = re.compile(
    r"\b("
    r"summar\w*|overview|tl;?dr|the gist|high[- ]level|"
    r"key (?:points|takeaways)|main points|brief\w*|"
    r"whole (?:document|report)|entire (?:document|report)|"
    r"what(?:'s| is) this (?:document|report)"
    r")\b",
    re.IGNORECASE,
)


def is_summary_query(q: str) -> bool:
    """True for broad summary/overview requests (or an empty/default prompt)."""
    ql = (q or "").strip()
    if not ql:
        return True
    return bool(_SUMMARY_RE.search(ql))


async def retrieve_summary(doc_ids: list, budget: int = None) -> list:
    """Return a representative cross-section of the document(s) for summaries.

    Structural, not similarity-based: always includes the opening chunks
    (exec summary / abstract) plus an even spread across the rest, so a
    summary can never miss the document's headline.
    """
    if not doc_ids:
        return []
    budget = budget or SUMMARY_CHUNKS

    conn = get_db()
    ph = ",".join("?" for _ in doc_ids)
    rows = conn.execute(
        f"SELECT doc_id, source_name, content, chunk_index FROM doc_chunks "
        f"WHERE doc_id IN ({ph}) ORDER BY doc_id, chunk_index",
        tuple(doc_ids),
    ).fetchall()
    conn.close()
    if not rows:
        return []

    from collections import OrderedDict
    bydoc = OrderedDict()
    for r in rows:
        bydoc.setdefault(r["doc_id"], []).append(r)

    per_doc = max(4, budget // len(bydoc))
    selected = []
    for chs in bydoc.values():
        n = len(chs)
        lead_n = min(3, n)                 # opening: title + exec summary
        lead = chs[:lead_n]
        rest = chs[lead_n:]
        want = max(0, per_doc - lead_n)
        spread = []
        if rest and want > 0:
            step = max(1, len(rest) // want)
            spread = rest[::step][:want]
        selected.extend(lead + spread)

    # De-dupe, keep document order
    seen, out = set(), []
    for r in sorted(selected, key=lambda r: (r["doc_id"], r["chunk_index"])):
        key = (r["doc_id"], r["chunk_index"])
        if key in seen:
            continue
        seen.add(key)
        out.append({"score": None, "source": r["source_name"], "content": r["content"], "chunk_index": r["chunk_index"]})
    return out


def _fit_context(chunks: list, max_chars: int, summary: bool) -> list:
    """Bound the total injected text so the prompt always leaves room for the
    model to generate (an over-full context window yields an empty reply).

    - Specific questions: chunks are score-sorted, so keep the highest-ranked
      ones that fit (drop the weakest).
    - Summaries: keep an even spread (including first and last) so document
      coverage is preserved rather than truncating the tail.
    """
    if not chunks:
        return chunks
    total = sum(len(c["content"]) for c in chunks)
    if total <= max_chars:
        return chunks
    if not summary:
        out, used = [], 0
        for c in chunks:
            L = len(c["content"])
            if out and used + L > max_chars:
                break
            out.append(c); used += L
        return out
    avg = total / len(chunks)
    keep = max(2, int(max_chars / avg))
    if keep >= len(chunks):
        return chunks
    idx = sorted({round(i * (len(chunks) - 1) / (keep - 1)) for i in range(keep)})
    return [chunks[i] for i in idx]


def build_rag_context(chunks: list, summary: bool = False):
    """Assemble retrieved chunks into a NUMBERED system-message context block
    (with strict grounding + citation rules). Returns (context_str, sources)
    where sources is the ordered list the frontend renders as citations."""
    if not chunks:
        return None, []
    chunks = _fit_context(chunks, MAX_CONTEXT_CHARS, summary)
    blocks = "\n\n".join(
        f"[{i + 1}] (from {c['source']})\n{c['content']}" for i, c in enumerate(chunks)
    )
    scope = (
        "Write a clear, structured summary of the document using the excerpts "
        "below, which are a representative cross-section including the opening "
        "section. Cover the main sections and the most important figures.\n"
        if summary else
        "The excerpts below were retrieved from the uploaded document(s) as the "
        "most relevant to the user's question.\n"
    )
    rules = (
        "Answer using ONLY these excerpts. Follow these rules strictly:\n"
        "- Quote numbers, names, dates and currency signs EXACTLY as written. "
        "Never invent, estimate, round, or change a value or its sign (do not turn a positive into a loss).\n"
        "- Report only figures that appear verbatim in the excerpts. Do NOT add up, "
        "total, average, or otherwise compute any number that is not written explicitly; "
        "if a total is not given, do not state one.\n"
        "- Do not infer trends, causes, growth, or losses from isolated figures unless the document states them explicitly.\n"
        "- If the figures look inconsistent, placeholder, or like test data, say so plainly rather than building a narrative around them.\n"
        "- Cite the excerpts you rely on using their bracket number, e.g. [1] or [2], right after the statement they support.\n"
        "- If the answer, or enough context, is not present in the excerpts, say so directly instead of guessing.\n"
    )
    if summary:
        rules += "- This summary is based on a sample of the document; note that it may be partial.\n"
    sources = [
        {"n": i + 1,
         "source": c["source"],
         "chunk": c.get("chunk_index"),
         "snippet": " ".join((c["content"] or "").split())[:200]}
        for i, c in enumerate(chunks)
    ]
    return f"{scope}{rules}\n{blocks}", sources


# ── Cleanup ──────────────────────────────────────────────────────────
def delete_doc_chunks(doc_id: str) -> int:
    conn = get_db()
    cur = conn.execute("DELETE FROM doc_chunks WHERE doc_id = ?", (doc_id,))
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    return deleted


def _doc_ids_in_chats(conn, exclude_chat_id: str = None) -> set:
    """All document ids referenced by chats (optionally excluding one chat)."""
    if exclude_chat_id:
        rows = conn.execute("SELECT doc_ids FROM chats WHERE id != ?", (exclude_chat_id,)).fetchall()
    else:
        rows = conn.execute("SELECT doc_ids FROM chats").fetchall()
    used = set()
    for r in rows:
        try:
            used.update(json.loads(r["doc_ids"] or "[]"))
        except (TypeError, ValueError):
            pass
    return used


def delete_chunks_for_chat(chat_id: str) -> int:
    """Delete the RAG chunks of the documents attached to `chat_id`.

    Call this BEFORE deleting the chat row. Documents that another chat still
    uses (a branch or duplicate shares its parent's documents) are kept.
    """
    conn = get_db()
    doc_ids = set()
    row = conn.execute("SELECT doc_ids FROM chats WHERE id = ?", (chat_id,)).fetchone()
    if row:
        try:
            doc_ids.update(json.loads(row["doc_ids"] or "[]"))
        except (TypeError, ValueError):
            pass
    doc_ids.update(r["doc_id"] for r in conn.execute(
        "SELECT DISTINCT doc_id FROM doc_chunks WHERE chat_id = ?", (chat_id,)).fetchall())
    doc_ids -= _doc_ids_in_chats(conn, exclude_chat_id=chat_id)
    deleted = 0
    for d in doc_ids:
        deleted += conn.execute("DELETE FROM doc_chunks WHERE doc_id = ?", (d,)).rowcount
    conn.commit()
    conn.close()
    return deleted


def cleanup_orphan_chunks(max_age_hours: int = 24) -> int:
    """Remove chunks of documents that were uploaded but never attached to any
    chat, once they are older than `max_age_hours`. Run at startup."""
    cutoff = (datetime.now() - timedelta(hours=max_age_hours)).isoformat()
    conn = get_db()
    used = _doc_ids_in_chats(conn)
    candidates = [r["doc_id"] for r in conn.execute(
        "SELECT doc_id, MAX(created_at) AS ts FROM doc_chunks GROUP BY doc_id HAVING ts < ?",
        (cutoff,)).fetchall()]
    deleted = 0
    for d in candidates:
        if d not in used:
            deleted += conn.execute("DELETE FROM doc_chunks WHERE doc_id = ?", (d,)).rowcount
    conn.commit()
    conn.close()
    return deleted

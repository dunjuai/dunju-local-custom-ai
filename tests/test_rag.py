from document.rag import chunk_text, is_summary_query, _bm25_scores, _tokenize, _fit_context


def test_chunk_text_empty():
    assert chunk_text("") == []
    assert chunk_text("   \n  ") == []


def test_chunk_text_respects_size_and_keeps_content():
    lines = [f"Line {i}: " + "word " * 20 for i in range(200)]
    text = "\n".join(lines)
    chunks = chunk_text(text, size=500, overlap=50)
    assert len(chunks) > 1
    # each chunk = at most `size` chars + an overlap tail + a newline
    assert all(len(c) <= 500 + 50 + 1 for c in chunks)
    joined = "\n".join(chunks)
    for i in (0, 57, 199):
        assert f"Line {i}:" in joined


def test_chunk_text_splits_oversized_block():
    chunks = chunk_text("x" * 2500, size=1000, overlap=100)
    assert len(chunks) >= 3


def test_summary_query_detection():
    assert is_summary_query("Please summarize this report")
    assert is_summary_query("Give me an overview")
    assert is_summary_query("")
    # word-boundary matching: these must NOT count as summary requests
    assert not is_summary_query("How do I register a vendor?")
    assert not is_summary_query("What does the logistics section say about SKU A-1932?")


def test_bm25_ranks_exact_identifier_first():
    docs = ["revenue grew in the north region",
            "invoice INV-0349 total due 12,400",
            "the weather was pleasant"]
    scores = _bm25_scores("INV-0349", [_tokenize(d) for d in docs])
    assert scores.index(max(scores)) == 1


def test_fit_context_caps_total_length():
    chunks = [{"content": "a" * 1000, "source": "d", "chunk_index": i} for i in range(20)]
    kept = _fit_context(chunks, 5000, summary=False)
    assert sum(len(c["content"]) for c in kept) <= 5000
    kept_s = _fit_context(chunks, 5000, summary=True)
    assert kept_s[0]["chunk_index"] == 0 and kept_s[-1]["chunk_index"] == 19

"""
Dunju AI — Context Builder
Decides HOW to use extracted document text based on user intent.
Sits between DocumentEngine and the LLM — never sends raw text blindly.
"""


INTENT_INSTRUCTIONS = {
    "summarize":      "TASK: Provide a concise, well-structured summary. Use headers and bullet points. Focus on the most important information only.",
    "extract_tables": "TASK: Extract and present all tabular/structured data in a clean, organized format.",
    "compare":        "TASK: Compare the documents side by side. Highlight similarities, differences, and key discrepancies.",
    "analyze":        "TASK: Analyze the document(s) in depth. Provide key insights, notable KPIs/figures, risks, and actionable recommendations.",
    "general_qa":     "TASK: Use the document(s) below as context to answer the user's question accurately and concisely.",
}


def detect_intent(user_text: str, file_count: int) -> str:
    """Detect the user's intent from their message."""
    lower = user_text.lower()
    if re_match(lower, ["summar", "overview", "brief", "tldr"]):
        return "summarize"
    if re_match(lower, ["table", "extract.*data", "rows", "columns", "data from"]):
        return "extract_tables"
    if re_match(lower, ["compar"]) and file_count > 1:
        return "compare"
    if re_match(lower, ["analyz", "insight", "kpi", "finding", "review", "assess"]):
        return "analyze"
    if not user_text.strip():
        return "analyze"
    return "general_qa"


def re_match(text: str, patterns: list) -> bool:
    import re
    return any(re.search(p, text) for p in patterns)


def build_context(user_text: str, file_entries: list) -> str:
    """
    Build a structured prompt combining user intent + document content.
    file_entries: list of dicts with 'name' and 'extracted_text' keys.
    """
    intent = detect_intent(user_text, len(file_entries))
    instruction = INTENT_INSTRUCTIONS.get(intent, INTENT_INSTRUCTIONS["general_qa"])
    docs_block = "\n\n".join(
        f"--- DOCUMENT: {f['name']} ---\n{f['extracted_text']}"
        for f in file_entries
    )
    user_q = user_text or "(no specific question — provide the requested task output)"
    return f"{instruction}\n\n{docs_block}\n\nUSER QUESTION: {user_q}"

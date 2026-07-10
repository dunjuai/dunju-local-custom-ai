"""
Dunju AI — Document Classifier
Keyword-based, fast, fully offline document type detection.
Returns a doc_type string used for Smart Actions and Knowledge Base tagging.
"""

DOC_TYPE_RULES = [
    ("invoice",          ["invoice number", "invoice #", "invoice date", "amount due",
                          "total due", "bill to", "ship to", "tax invoice", "subtotal", "invoice total"], 2),
    ("resume",           ["work experience", "professional experience", "education", "skills",
                          "objective", "curriculum vitae", "career summary", "references available"], 2),
    ("contract",         ["this agreement", "terms and conditions", "party of the first part",
                          "whereas", "hereinafter", "governing law", "termination", "non-disclosure", "effective date"], 2),
    ("financial_report", ["balance sheet", "profit and loss", "income statement", "cash flow",
                          "fiscal year", "revenue", "ebitda", "quarterly report"], 2),
    ("business_report",  ["executive summary", "kpi", "department", "target", "actual",
                          "variance", "recommendations", "operations summary"], 2),
    ("proposal",         ["scope of work", "deliverables", "project timeline",
                          "proposed solution", "pricing", "statement of work"], 2),
    ("legal",            ["plaintiff", "defendant", "court", "jurisdiction",
                          "witness", "affidavit", "hereby"], 2),
    ("presentation",     ["agenda", "next steps", "slide", "thank you"], 1),
    ("hr_policy",        ["leave policy", "hr policy", "code of conduct", "employee handbook",
                          "attendance", "disciplinary", "grievance"], 2),
    ("meeting_notes",    ["meeting minutes", "attendees", "action items",
                          "discussed", "next meeting", "agenda items"], 2),
]


def classify_document(text: str) -> str:
    """Return the best matching document type, or 'general' if nothing matches."""
    lower = text.lower()
    best_type, best_score = "general", 0
    for doc_type, keywords, min_matches in DOC_TYPE_RULES:
        matches = sum(1 for kw in keywords if kw in lower)
        if matches >= min_matches and matches > best_score:
            best_score, best_type = matches, doc_type
    return best_type


def detect_language(text: str) -> str:
    """Lightweight language detector using common stopwords."""
    sample = text[:2000].lower()
    if not sample.strip():
        return "Unknown"
    lang_markers = {
        "English": [" the ", " and ", " is ", " of ", " to ", " in "],
        "Spanish": [" el ", " la ", " de ", " que ", " y ", " en "],
        "French":  [" le ", " la ", " de ", " et ", " est ", " les "],
        "German":  [" der ", " die ", " und ", " ist ", " das ", " mit "],
        "Tamil":   ["மற்றும்", "உள்ளது", "இது"],
    }
    best_lang, best_count = "English", 0
    for lang, markers in lang_markers.items():
        count = sum(sample.count(m) for m in markers)
        if count > best_count:
            best_count, best_lang = count, lang
    return best_lang if best_count > 0 else "English"


DOC_TYPE_LABELS = {
    "invoice": "Invoice", "resume": "Resume", "contract": "Contract",
    "financial_report": "Financial Report", "business_report": "Business Report",
    "proposal": "Proposal", "legal": "Legal Document", "presentation": "Presentation",
    "hr_policy": "HR Policy", "meeting_notes": "Meeting Notes", "general": "Document"
}

from document.classifier import classify_document, detect_language
from document.engine import process_file, legacy_format_message, PROCESSORS


def test_classify_invoice():
    text = "TAX INVOICE\nInvoice Number: 0349\nBill To: TechNova\nSubtotal 100\nAmount Due 118"
    assert classify_document(text) == "invoice"


def test_classify_general():
    assert classify_document("hello there") == "general"


def test_detect_language():
    assert detect_language("This is the report of the team and the plan in May") == "English"


def test_legacy_office_formats_rejected_with_message():
    for ext, new in ((".doc", ".docx"), (".xls", ".xlsx"), (".ppt", ".pptx")):
        msg = legacy_format_message("old" + ext.upper())
        assert msg and new in msg
        assert ext not in PROCESSORS
    assert legacy_format_message("new.docx") is None


def test_process_text_file():
    r = process_file(b"hello world", "a.txt")
    assert "hello world" in r["text"]
    assert r["word_count"] > 0

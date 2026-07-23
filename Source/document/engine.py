"""
Dunju AI — Document Engine
Extracts clean text + metadata from all supported file types.
Each extractor returns a consistent dict: {text, pages, tables, images}

v2.7.0 — extractors accept max_chars / max_pages so the RAG pipeline can
index the WHOLE document (full=True) while the inline preview path keeps
the smaller default caps.
"""

import time
from pathlib import Path
from config.settings import MAX_PAGES, MAX_CHARS, MAX_PAGES_RAG, MAX_CHARS_RAG


def extract_pdf(file_bytes: bytes, filename: str,
                max_chars: int = MAX_CHARS, max_pages: int = MAX_PAGES) -> dict:
    try:
        import fitz
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        page_count = doc.page_count
        full_text = f"[PDF: {filename} — {page_count} pages]\n\n"
        table_count = 0
        image_count = 0
        for page_num in range(min(page_count, max_pages)):
            page = doc[page_num]
            text = page.get_text()
            if text.strip():
                full_text += f"--- Page {page_num + 1} ---\n{text}\n\n"
            image_count += len(page.get_images())
            try:
                tabs = page.find_tables()
                table_count += len(tabs.tables)
            except Exception:
                pass
        doc.close()
        if len(full_text.strip()) < 100:
            return {"text": f"[PDF: {filename} — scanned/image-based. No text extracted.]",
                    "pages": page_count, "tables": 0, "images": image_count}
        return {"text": full_text[:max_chars], "pages": page_count, "tables": table_count, "images": image_count}
    except Exception as e:
        return {"text": f"[PDF Error: {filename} — {e}]", "pages": None, "tables": None, "images": None}


def extract_word(file_bytes: bytes, filename: str,
                 max_chars: int = MAX_CHARS, max_pages: int = MAX_PAGES) -> dict:
    try:
        from docx import Document
        import io
        doc = Document(io.BytesIO(file_bytes))
        full_text = f"[Word Document: {filename}]\n\n"
        for para in doc.paragraphs:
            if para.text.strip():
                if para.style.name.startswith("Heading"):
                    full_text += f"\n## {para.text}\n"
                else:
                    full_text += para.text + "\n"
        table_count = len(doc.tables)
        for i, table in enumerate(doc.tables):
            full_text += f"\n[Table {i+1}]\n"
            for row in table.rows:
                full_text += " | ".join(c.text.strip() for c in row.cells) + "\n"
        image_count = len(doc.inline_shapes)
        return {"text": full_text[:max_chars], "pages": None, "tables": table_count, "images": image_count}
    except Exception as e:
        return {"text": f"[Word Error: {filename} — {e}]", "pages": None, "tables": None, "images": None}


def extract_excel(file_bytes: bytes, filename: str,
                  max_chars: int = MAX_CHARS, max_pages: int = MAX_PAGES) -> dict:
    try:
        import pandas as pd
        import io
        full_text = f"[Excel File: {filename}]\n\n"
        xl = pd.ExcelFile(io.BytesIO(file_bytes))
        sheet_count = len(xl.sheet_names)
        for sheet_name in xl.sheet_names:
            df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=sheet_name)
            if df.empty:
                continue
            full_text += f"--- Sheet: {sheet_name} ---\n"
            full_text += f"Rows: {len(df)}, Columns: {len(df.columns)}\n"
            full_text += f"Columns: {', '.join(str(c) for c in df.columns)}\n\n"
            full_text += df.head(100).to_string(index=False) + "\n\n"
            num_cols = df.select_dtypes(include="number").columns
            if len(num_cols) > 0:
                full_text += "Summary Statistics:\n" + df[num_cols].describe().to_string() + "\n\n"
        return {"text": full_text[:max_chars], "pages": sheet_count, "tables": sheet_count, "images": 0}
    except Exception as e:
        return {"text": f"[Excel Error: {filename} — {e}]", "pages": None, "tables": None, "images": None}


def extract_csv(file_bytes: bytes, filename: str,
                max_chars: int = MAX_CHARS, max_pages: int = MAX_PAGES) -> dict:
    try:
        import pandas as pd
        import io
        df = pd.read_csv(io.BytesIO(file_bytes))
        full_text = f"[CSV File: {filename}]\nRows: {len(df)}, Columns: {len(df.columns)}\n"
        full_text += f"Columns: {', '.join(str(c) for c in df.columns)}\n\n"
        full_text += df.head(100).to_string(index=False) + "\n\n"
        num_cols = df.select_dtypes(include="number").columns
        if len(num_cols) > 0:
            full_text += "Summary Statistics:\n" + df[num_cols].describe().to_string() + "\n"
        return {"text": full_text[:max_chars], "pages": None, "tables": 1, "images": 0}
    except Exception as e:
        return {"text": f"[CSV Error: {filename} — {e}]", "pages": None, "tables": None, "images": None}


def extract_pptx(file_bytes: bytes, filename: str,
                 max_chars: int = MAX_CHARS, max_pages: int = MAX_PAGES) -> dict:
    try:
        from pptx import Presentation
        from pptx.enum.shapes import MSO_SHAPE_TYPE
        import io
        prs = Presentation(io.BytesIO(file_bytes))
        slide_count = len(prs.slides)
        full_text = f"[PowerPoint: {filename} — {slide_count} slides]\n\n"
        table_count = 0
        image_count = 0
        for i, slide in enumerate(prs.slides):
            full_text += f"--- Slide {i+1} ---\n"
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text.strip():
                    full_text += shape.text.strip() + "\n"
                if shape.has_table:
                    table_count += 1
                if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                    image_count += 1
            full_text += "\n"
        return {"text": full_text[:max_chars], "pages": slide_count, "tables": table_count, "images": image_count}
    except Exception as e:
        return {"text": f"[PowerPoint Error: {filename} — {e}]", "pages": None, "tables": None, "images": None}


def extract_image_ocr(file_bytes: bytes, filename: str,
                      max_chars: int = MAX_CHARS, max_pages: int = MAX_PAGES) -> dict:
    try:
        import easyocr
        import numpy as np
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(file_bytes))
        img_array = np.array(img)
        reader = easyocr.Reader(["en"], gpu=False)
        results = reader.readtext(img_array)
        if not results:
            return {"text": f"[Image: {filename} — no text found]", "pages": 1, "tables": 0, "images": 1}
        extracted = "\n".join(text for (_, text, conf) in results if conf > 0.3)
        return {"text": f"[Image OCR: {filename}]\n\n{extracted}"[:max_chars], "pages": 1, "tables": 0, "images": 1}
    except ImportError:
        return {"text": f"[Image: {filename} — EasyOCR not installed. Run: pip install easyocr]", "pages": 1, "tables": 0, "images": 1}
    except Exception as e:
        return {"text": f"[Image OCR Error: {filename} — {e}]", "pages": None, "tables": None, "images": None}


def extract_text_file(file_bytes: bytes, filename: str,
                      max_chars: int = MAX_CHARS, max_pages: int = MAX_PAGES) -> dict:
    try:
        text = file_bytes.decode("utf-8", errors="ignore")
        return {"text": f"[Text File: {filename}]\n\n{text}"[:max_chars], "pages": None, "tables": None, "images": None}
    except Exception as e:
        return {"text": f"[Text Error: {filename} — {e}]", "pages": None, "tables": None, "images": None}


# ── File router ──
PROCESSORS = {
    ".pdf":  extract_pdf,
    ".docx": extract_word, ".doc": extract_word,
    ".xlsx": extract_excel, ".xls": extract_excel,
    ".csv":  extract_csv,
    ".pptx": extract_pptx, ".ppt": extract_pptx,
    ".txt":  extract_text_file, ".md": extract_text_file,
    ".png":  extract_image_ocr, ".jpg": extract_image_ocr,
    ".jpeg": extract_image_ocr, ".gif": extract_image_ocr, ".webp": extract_image_ocr,
}


def process_file(file_bytes: bytes, filename: str, full: bool = False) -> dict:
    """Route to the correct extractor, enrich with derived stats, return unified dict.

    full=False → inline preview caps (MAX_CHARS / MAX_PAGES).
    full=True  → RAG caps (MAX_CHARS_RAG / MAX_PAGES_RAG): index the whole document.
    """
    start = time.time()
    max_chars = MAX_CHARS_RAG if full else MAX_CHARS
    max_pages = MAX_PAGES_RAG if full else MAX_PAGES

    ext = Path(filename).suffix.lower()
    processor = PROCESSORS.get(ext)
    result = processor(file_bytes, filename, max_chars, max_pages) if processor else {
        "text": f"[Unsupported file type: {filename}]", "pages": None, "tables": None, "images": None
    }
    text = result.get("text", "")
    result["word_count"]       = len(text.split())
    result["char_count"]       = len(text)
    result["processing_time"]  = round(time.time() - start, 2)
    return result

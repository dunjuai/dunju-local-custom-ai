"""
Dunju AI — Batch / Folder Automation (v2.12.0)
Scan a folder on disk and run an action (summarize / classify / extract /
custom) over every supported document. Fully local/offline.
"""

from pathlib import Path
from document.engine import process_file, PROCESSORS

SUPPORTED = set(PROCESSORS.keys())


def scan_folder(folder: str, recursive: bool = False):
    """Return a list of supported files in `folder`, or None if it's not a dir."""
    try:
        p = Path(folder).expanduser()
    except Exception:
        return None
    if not p.exists() or not p.is_dir():
        return None
    out = []
    it = p.rglob("*") if recursive else p.glob("*")
    for f in it:
        try:
            if f.is_file() and f.suffix.lower() in SUPPORTED:
                out.append({
                    "name": f.name,
                    "path": str(f),
                    "size": f.stat().st_size,
                    "ext": f.suffix.lower(),
                })
        except Exception:
            continue
    return sorted(out, key=lambda x: x["name"].lower())


def extract_file_text(path: str) -> str:
    """Extract full text from a single file on disk."""
    data = Path(path).read_bytes()
    return process_file(data, Path(path).name, full=True).get("text", "")

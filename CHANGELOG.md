# Changelog — Dunju Local Custom AI

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

> Builds before 1.0.0 were internal pre-releases numbered 2.x; some older notes and the first git commit refer to those numbers.

## [1.0.1] — 2026-11-19

Security and reliability release. **Upgrade recommended.**

### Security
- Backend now listens on `127.0.0.1` only (was `0.0.0.0`, reachable from the local network).
- The backend serves the app page itself and requires a per-launch access token on every API call; the allow-all CORS policy is removed. Other websites can no longer read or change chats, trigger folder scans, or restore the database.
- Requests with an unexpected `Host` header are rejected (DNS-rebinding protection).
- AI replies, file names, chat titles, expert names and settings are HTML-escaped before display, so document-driven prompt injection cannot run script in the page. Added a strict Content-Security-Policy.
- Batch automation only processes files inside the chosen folder.
- Auto-reload (a development setting) is turned off.

### Fixed
- Removed the Google Fonts import so the app makes no external calls (system fonts are used).
- `.doc`, `.xls` and `.ppt` uploads are rejected with a clear "save as .docx/.xlsx/.pptx" message instead of failing.
- Upload size limit is now enforced by the backend, not just the browser.
- Added missing `python-multipart` (required for uploads — fresh installs failed to start) and `numpy` to `requirements.txt`; image OCR (`easyocr`) is documented as optional.
- Document index entries are now cleaned up when their chat is deleted (they previously accumulated), while documents still used by a branched or duplicated chat are kept. Duplicating a chat now keeps its documents.

### Changed
- Open the app at `http://127.0.0.1:8000`; the launcher opens it automatically.
- The embedded logo moved to `Source/frontend/assets/`, shrinking the page from ~930 KB to ~145 KB.
- Removed leftover internal pre-release version numbers (2.x) from source files.
- Added an automated test suite (`python -m pytest`).
- `/health` stays public (status and model names only) so it can be opened directly in a browser when troubleshooting.
- Customer Guide and Internal Documentation updated to v1.0.1 (new start-up address, security model, troubleshooting entries).

## [1.0.0] — 2026-07-15

First stable release of **Dunju Local Custom AI** — a private AI assistant that runs 100% on your own machine. No cloud, no subscription, no API keys, no data collection.

### Added — Chat & experts
- Local, private chat with streaming replies, auto-titled conversations, history search, duplicate and export.
- 6 AI Experts (General, Business, Coding, Medical, Kids, Fashion) with tailored follow-up actions; create your own without writing code.
- Per-expert model selection, and an optional Reasoning mode that shows the model's thinking.
- Regenerate, Edit-and-resend, and Branch any message; live response stats (time, model, tokens, expert).

### Added — Documents
- Document Intelligence for PDF, Word, Excel, PowerPoint, CSV, TXT, Markdown and images — with automatic type detection.
- Smart Retrieval (RAG): reads whole documents of any length, fully offline, and answers from the relevant passages.
- Hybrid search (keyword + semantic) for reliable exact-name/ID/figure lookups, plus a Sources panel that shows what each answer is based on.

### Added — Output & automation
- Export any reply as Word, PDF, PowerPoint or Excel; export a whole chat as PDF, Markdown or text.
- Batch / folder automation: run summarize / classify / extract / custom across every document in a folder.

### Added — Settings, data & privacy
- Rich Settings (temperature & max-tokens sliders, language, theme, RAG controls, and more).
- Backup / restore / clear-all, plus password-protected **encrypted backups** — your live data is never encrypted, so a lost password only affects that one backup.
- A local activity log of recent events.

### Setup
- Requires Python 3.10+ and Ollama. Create the model (`ollama create dunju-ai -f Modelfile`), run `ollama pull nomic-embed-text` for Smart Retrieval, and `pip install -r requirements.txt` (includes reportlab and cryptography).

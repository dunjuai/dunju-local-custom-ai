# Changelog — Dunju Local Custom AI

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

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

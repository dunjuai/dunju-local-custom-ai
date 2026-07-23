# Dunju Local Custom AI — v1.0.0

**First stable release.** A private AI assistant that runs 100% on your own machine — no cloud, no subscription, no API keys, no data collection. This release consolidates all earlier builds into one product version.

## Highlights

- **Smart Retrieval (RAG)** — reads whole documents of any length, fully offline, and answers from the passages that actually matter.
- **Hybrid search + source citations** — keyword + semantic retrieval finds exact names, IDs, SKUs and figures; a Sources panel shows what each answer is based on.
- **Generate & export** — turn any reply into Word, PDF, PowerPoint or Excel, or export a whole chat as PDF / Markdown / text.
- **Batch / folder automation** — run one action (summarize / classify / extract / custom) across every document in a folder. Read-only: it never changes your files.
- **Encrypted backups** — password-protected AES backups. Your live data is never encrypted, so a lost password only affects that one backup.
- **Reasoning mode, per-expert models, and conversation controls** — regenerate, edit-and-resend, or branch any message; live response stats; a local activity log.

## Added — Chat & experts
- Local, private chat with streaming replies, auto-titled conversations, history search, duplicate and export.
- 6 AI Experts (General, Business, Coding, Medical, Kids, Fashion) with tailored follow-up actions; create your own without writing code.
- Per-expert model selection, and an optional Reasoning mode that shows the model's thinking.
- Regenerate, Edit-and-resend, and Branch any message; live response stats (time, model, tokens, expert).

## Added — Documents & retrieval
- Document Intelligence for PDF, Word, Excel, PowerPoint, CSV, TXT, Markdown and images — with automatic type detection.
- Smart Retrieval (RAG) reads whole documents of any length, fully offline.
- Hybrid search (keyword + semantic) for reliable exact-name/ID/figure lookups, plus a Sources panel.

## Added — Output & automation
- Export any reply as Word, PDF, PowerPoint or Excel; export a whole chat as PDF, Markdown or text.
- Batch / folder automation across every document in a folder.

## Added — Settings, data & privacy
- Rich Settings (temperature & max-tokens sliders, language, theme, RAG controls, and more).
- Backup / restore / clear-all, plus password-protected encrypted backups.
- A local activity log of recent events.

## Setup

Requires **Python 3.10+** and **[Ollama](https://ollama.com/download)**.

```powershell
# 1. install dependencies (includes reportlab + cryptography)
pip install -r requirements.txt

# 2. create the model (first run downloads the base model)
cd Configurations
ollama create dunju-ai -f Modelfile

# 3. enable Smart Retrieval (RAG)
ollama pull nomic-embed-text
```

Then start the backend (`Source\Local_Custom_AI_AutoStart.bat`) and open `Source\frontend\DunjuAI_Chat.html`.

Full details in [CHANGELOG.md](CHANGELOG.md).

**Build. Automate. Scale.**

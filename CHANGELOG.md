# Changelog — Dunju Local Custom AI

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [2.6.0] — 2026-07-09

### Added
- Settings redesigned into 6 tabs: General, AI, Documents, Database, AI Experts, About
- Temperature & max tokens passed to Ollama per request (Settings → AI)
- Database backup / restore / clear-all with safety copies (Settings → Database)
- Chat search box, context menu (rename, duplicate, export as Markdown, delete)
- 📄 indicator for chats containing documents
- Keyboard shortcuts: Alt+N new chat · Ctrl+, settings · Ctrl+F search
- Toast notifications; personalized welcome greeting (name from Settings)
- Copy button on code blocks

### Changed
- Non-destructive expert seeding — user-created and edited experts persist across restarts
- Portable launcher — works from any drive, auto-detects Python
- FastAPI lifespan-style startup (no deprecation warning)

### Fixed
- Markdown renderer corrupted characters inside code blocks (`*`, `_`)
- Replies lost when switching chats mid-generation — live-stream tracker keeps them
- False "disconnected" status while the model was busy
- Scroll hijack while the AI is typing (sticky-bottom auto-scroll)

## [2.5.0] — 2026-07-08

- Streamlined to 6 core AI Experts: General, Business, Kids, Coding, Medical, Fashion
- Removed project workspaces, knowledge base and activity log for a focused core product
- Safe automatic database migration and repair
- Stability fixes: connection status, streaming scroll, mid-stream chat switching

## [2.4.0] — 2026-07-07

- Auto chat titling (AI-generated titles after the first exchange)
- AI Expert dropdown in the topbar; General expert added as default
- Base model upgraded to Qwen3.5 4B

## [2.0.0] — 2026-07-03

- Monolithic backend refactored into modular architecture (ai / document / memory / database / settings / config)
- AI Experts and settings stored in SQLite with full CRUD API

## [1.x] — 2026-06

- Initial releases: local Ollama model, custom chat interface, streaming responses,
  document engine (PDF, Word, Excel, PowerPoint, CSV, images), document classifier,
  smart actions, persistent SQLite chat memory

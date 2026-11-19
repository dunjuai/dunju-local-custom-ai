# Dunju Local Custom AI — v1.0.1

**Security and reliability update. Recommended for every user.**

Dunju is sold on privacy, and this release makes sure that promise holds even on shared networks and while you browse other websites.

## What changes for you

- **Open the app at http://127.0.0.1:8000.** The backend now serves the app page itself, and the launcher (`Source\Local_Custom_AI_AutoStart.bat`) opens it in your browser automatically. Opening `DunjuAI_Chat.html` directly from the folder no longer works.
- **After restarting the backend, reload the page (F5).** Each start creates a new private access key.

## Security

- The backend only accepts connections from your own computer (it used to listen on the whole local network).
- Every request needs a private access key that only the Dunju page knows, so other websites open in your browser cannot read or change your chats, scan your folders or replace your database.
- Requests sent under an unexpected web address are rejected (protection against DNS-rebinding attacks).
- Everything the AI writes is shown as text, never run as code — a malicious document cannot use the AI to inject scripts into the app. A strict Content-Security-Policy blocks the page from contacting any other server.
- Batch automation only processes files inside the folder you chose.

## Fixes

- No more web-font download: the app makes **zero** internet requests.
- `.doc`, `.xls` and `.ppt` uploads show a clear “save as .docx / .xlsx / .pptx” message.
- The upload size limit is enforced by the backend, not only the browser.
- **Fresh installs failed to start** because `python-multipart` was missing from `requirements.txt` — fixed (`numpy` added too). Image OCR (`easyocr`) is documented as an optional add-on.
- Document data is cleaned up when you delete the chat that used it; branched or duplicated chats keep their documents.
- The app page is about 6x smaller (the logo is now a separate file).

## Upgrade

1. Stop the backend (close its console window).
2. Replace the `Source` folder with the new one. Your chats live in `Source\dunju_ai_memory.db` — **keep your existing database file** (copy it into the new `Source` folder, or back it up first from Settings > Database).
3. Run `pip install -r requirements.txt` again.
4. Start `Source\Local_Custom_AI_AutoStart.bat` and use http://127.0.0.1:8000.

Full details in [CHANGELOG.md](CHANGELOG.md) and the updated [Customer Guide](docs/Dunju_Local_Custom_AI_Customer_Guide_v1.0.1.docx).

**Build. Automate. Scale.**

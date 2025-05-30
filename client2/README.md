# client2 — Windows Desktop Overlay Kiosk Client

This client displays a large session timer as an overlay on the real Windows desktop, and locks the screen with a blank window when the session ends.

## Features
- **Overlay Timer:** Large, always-on-top, transparent timer banner (does not block desktop icons or mouse).
- **Blank Lock Screen:** When session is not active, shows a fullscreen blank window.
- **Session Logic:** (Demo) Starts a 2-minute session after 2 seconds. (To be connected to server.)

## Usage
```
pip install -r requirements.txt
python main.py
```

## Next Steps
- Add server communication (start/pause/end session from admin panel)
- Add File Explorer watcher/blocker
- Add allowed apps logic (optional) 
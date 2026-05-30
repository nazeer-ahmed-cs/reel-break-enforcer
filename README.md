# 📵 Reel Break Enforcer

A lightweight Windows tool that monitors your screen for short-video apps (Instagram Reels, TikTok, YouTube Shorts, etc.) and pops a **fullscreen overlay** after you've been scrolling for too long.

---

## Features

- 🪟 **Fullscreen overlay** — unskippable, auto-closes with a countdown bar
- ⏱️ **Configurable threshold** — default: 10 minutes of scrolling
- 📊 **Daily stats** — tracks total scroll time and breaks taken
- 🔧 **Settings UI** — change threshold, overlay duration, and monitored apps
- 🧪 **Test mode** — preview the overlay without waiting
- 💾 **Persistent logs** — JSON-based, no database needed

---

## Requirements

- Windows 10 / 11
- Python 3.8+
- No external packages needed (uses only stdlib + tkinter)

---

## Quick Start

```bash
# Clone / download the project
cd reel_enforcer

# Run directly
python enforcer.py
```

1. Click **▶ Start Monitoring**
2. Switch to Instagram / TikTok / YouTube
3. After your configured threshold → fullscreen overlay fires 🔥

---

## How it works

```
Every 3 seconds:
  → Read active window title (Windows API via ctypes)
  → If title contains "instagram", "tiktok", "youtube", etc.
      → Start / continue a timer
      → If timer >= threshold → show fullscreen overlay
  → Else → reset timer
```

The overlay is a `tkinter` fullscreen window (`-topmost`, `-fullscreen`) with:
- Elapsed scroll time badge
- Motivational quote (rotates each break)
- Countdown progress bar
- Auto-dismiss after N seconds

---

## Configuration (`config.json`)

```json
{
  "threshold_minutes": 10,
  "overlay_seconds": 30,
  "target_apps": ["instagram", "tiktok", "youtube", "shorts", "reels", "snapchat"]
}
```

Edit via the Settings button in the UI, or manually.

---

## Extending it

| Idea | Where to add |
|------|-------------|
| System tray icon | `pystray` library + run `App` headless |
| Sound on overlay | `winsound.Beep()` in `show_overlay()` |
| Block the app entirely | `pygetwindow` to minimize the window |
| Weekly email report | Read `log.json`, send via `smtplib` |
| Custom quotes file | Load `QUOTES` from a `.txt` file |

---

## Files

```
reel_enforcer/
├── enforcer.py     # Main app
├── config.json     # Auto-created on first run
├── log.json        # Daily usage log
└── README.md
```

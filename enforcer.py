import tkinter as tk
from tkinter import font as tkfont
import threading
import time
import json
import os
import sys
from datetime import datetime, date
from PIL import Image, ImageDraw
import pystray

# ── Config ───────────────────────────────────────────────────────────────────
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
LOG_FILE    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "log.json")

DEFAULT_CONFIG = {
    "threshold_minutes": 10,
    "overlay_seconds":   30,
    "block_app":         False,
    "target_apps": [
        "instagram", "tiktok", "youtube", "shorts",
        "reels", "snapchat", "facebook", "twitter", "x.com"
    ]
}

QUOTES = [
    "You've been scrolling for a while.\nYour future self will thank you for stopping.",
    "Every reel you skip is a minute\nyou own back.",
    "The algorithm is designed to keep you here.\nYou don't have to stay.",
    "Real life doesn't have a scroll bar.",
    "You opened this app for a reason.\nWas this it?",
    "5 more minutes becomes 50.\nBreak the cycle now.",
    "Your attention is your most valuable asset.\nSpend it wisely.",
]

# ── Persistence ───────────────────────────────────────────────────────────────
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            cfg = json.load(f)
        for k, v in DEFAULT_CONFIG.items():
            cfg.setdefault(k, v)
        return cfg
    return DEFAULT_CONFIG.copy()

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

def load_log():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE) as f:
            return json.load(f)
    return {}

def save_log(log):
    with open(LOG_FILE, "w") as f:
        json.dump(log, f, indent=2)

def log_session(minutes):
    log   = load_log()
    today = str(date.today())
    entry = log.get(today, {"total_minutes": 0, "breaks": 0})
    entry["total_minutes"] = round(entry["total_minutes"] + minutes, 2)
    entry["breaks"] += 1
    log[today] = entry
    save_log(log)

def get_week_data():
    log = load_log()
    from datetime import timedelta
    today = date.today()
    result = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        entry = log.get(str(d), {"total_minutes": 0, "breaks": 0})
        result.append({"date": d.strftime("%a"), "minutes": entry["total_minutes"], "breaks": entry["breaks"]})
    return result

# ── Active window detection (Windows) ────────────────────────────────────────
def get_active_window_title():
    try:
        import ctypes
        hwnd   = ctypes.windll.user32.GetForegroundWindow()
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        buf    = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value.lower()
    except Exception:
        return ""

def minimize_window(title_fragment):
    """Minimize any window whose title contains title_fragment."""
    try:
        import ctypes
        SW_MINIMIZE = 6
        EnumWindows      = ctypes.windll.user32.EnumWindows
        EnumWindowsProc  = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))
        GetWindowText    = ctypes.windll.user32.GetWindowTextW
        GetWindowTextLen = ctypes.windll.user32.GetWindowTextLengthW
        ShowWindow       = ctypes.windll.user32.ShowWindow

        def callback(hwnd, _):
            length = GetWindowTextLen(hwnd)
            buf    = ctypes.create_unicode_buffer(length + 1)
            GetWindowText(hwnd, buf, length + 1)
            if title_fragment in buf.value.lower():
                ShowWindow(hwnd, SW_MINIMIZE)
            return True

        EnumWindows(EnumWindowsProc(callback), 0)
    except Exception:
        pass

def is_reel_app(title, targets):
    return any(t in title for t in targets)

# ── Tray icon image ───────────────────────────────────────────────────────────
def make_tray_image(active=True):
    size  = 64
    img   = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw  = ImageDraw.Draw(img)
    color = (255, 107, 53) if active else (80, 80, 80)
    draw.ellipse([4, 4, size-4, size-4], fill=color)
    # inner circle
    draw.ellipse([20, 20, size-20, size-20], fill=(13, 13, 13))
    return img

# ── Overlay ───────────────────────────────────────────────────────────────────
def show_overlay(cfg, elapsed_minutes, quote_index):
    overlay = tk.Tk()
    overlay.attributes("-fullscreen", True)
    overlay.attributes("-topmost", True)
    overlay.configure(bg="#0d0d0d")
    overlay.lift()
    overlay.focus_force()

    quote        = QUOTES[quote_index % len(QUOTES)]
    seconds_left = [cfg["overlay_seconds"]]
    dismissed    = [False]

    big_font  = tkfont.Font(family="Segoe UI", size=42, weight="bold")
    mid_font  = tkfont.Font(family="Segoe UI", size=20)
    sub_font  = tkfont.Font(family="Segoe UI", size=14)
    mono_font = tkfont.Font(family="Consolas",  size=13)

    outer = tk.Frame(overlay, bg="#0d0d0d")
    outer.place(relx=0.5, rely=0.5, anchor="center")

    badge_txt = f"  {elapsed_minutes:.0f} min of scrolling  "
    tk.Label(outer, text=badge_txt, bg="#1a1a1a", fg="#ff6b35",
             font=mono_font, padx=10, pady=6).pack(pady=(0, 32))

    tk.Label(outer, text="◉", fg="#ff6b35", bg="#0d0d0d",
             font=tkfont.Font(family="Segoe UI", size=64)).pack(pady=(0, 16))

    tk.Label(outer, text="Time for a break", fg="#ffffff",
             bg="#0d0d0d", font=big_font).pack(pady=(0, 24))

    tk.Label(outer, text=quote, fg="#aaaaaa", bg="#0d0d0d",
             font=mid_font, justify="center", wraplength=700).pack(pady=(0, 48))

    bar_bg   = tk.Frame(outer, bg="#1a1a1a", width=400, height=6)
    bar_bg.pack(pady=(0, 16))
    bar_bg.pack_propagate(False)
    bar_fill = tk.Frame(bar_bg, bg="#ff6b35", height=6)
    bar_fill.place(x=0, y=0, relwidth=1.0, height=6)

    countdown_lbl = tk.Label(outer, text=f"Closing in {seconds_left[0]}s",
                             fg="#555555", bg="#0d0d0d", font=sub_font)
    countdown_lbl.pack()

    def tick():
        if dismissed[0]:
            return
        seconds_left[0] -= 1
        bar_fill.place(relwidth=max(0, seconds_left[0] / cfg["overlay_seconds"]))
        countdown_lbl.config(text=f"Closing in {seconds_left[0]}s")
        if seconds_left[0] <= 0:
            dismissed[0] = True
            overlay.destroy()
        else:
            overlay.after(1000, tick)

    overlay.after(1000, tick)
    overlay.mainloop()

# ── Weekly report window ──────────────────────────────────────────────────────
def show_weekly_report():
    data = get_week_data()
    win  = tk.Tk()
    win.title("Weekly Report — Reel Break Enforcer")
    win.geometry("520x420")
    win.resizable(False, False)
    win.configure(bg="#111111")

    hf = tkfont.Font(family="Segoe UI", size=16, weight="bold")
    mf = tkfont.Font(family="Segoe UI", size=11)
    sf = tkfont.Font(family="Segoe UI", size=10)

    tk.Label(win, text="📊  Weekly Screen Time Report", fg="#ff6b35",
             bg="#111111", font=hf).pack(pady=(24, 4))
    tk.Label(win, text="Last 7 days of scroll tracking",
             fg="#555555", bg="#111111", font=sf).pack(pady=(0, 20))

    # Bar chart canvas
    canvas = tk.Canvas(win, bg="#111111", width=480, height=200,
                       highlightthickness=0)
    canvas.pack(padx=20)

    max_min = max((d["minutes"] for d in data), default=1) or 1
    bar_w   = 48
    gap     = 20
    base_y  = 180
    chart_h = 140

    for i, d in enumerate(data):
        x      = 20 + i * (bar_w + gap)
        height = int((d["minutes"] / max_min) * chart_h)
        y0     = base_y - height
        color  = "#ff6b35" if i == 6 else "#2a2a2a"
        canvas.create_rectangle(x, y0, x + bar_w, base_y,
                                 fill=color, outline="")
        canvas.create_text(x + bar_w // 2, base_y + 14,
                           text=d["date"], fill="#555555",
                           font=sf)
        if d["minutes"] > 0:
            canvas.create_text(x + bar_w // 2, y0 - 10,
                               text=f"{d['minutes']:.0f}m",
                               fill="#aaaaaa", font=sf)

    # Summary row
    total_min   = sum(d["minutes"] for d in data)
    total_breaks= sum(d["breaks"]  for d in data)
    avg_min     = total_min / 7

    summary = tk.Frame(win, bg="#111111")
    summary.pack(padx=20, fill="x", pady=20)

    def stat(parent, label, value, col):
        f = tk.Frame(parent, bg="#1a1a1a",
                     highlightbackground="#2a2a2a", highlightthickness=1)
        f.grid(row=0, column=col, sticky="nsew", padx=4)
        tk.Label(f, text=label, fg="#555555", bg="#1a1a1a",
                 font=sf).pack(padx=12, pady=(10, 2))
        tk.Label(f, text=value, fg="#ffffff", bg="#1a1a1a",
                 font=tkfont.Font(family="Segoe UI", size=16, weight="bold")
                 ).pack(padx=12, pady=(0, 10))

    stat(summary, "Total this week", f"{total_min:.0f} min", 0)
    stat(summary, "Daily average",   f"{avg_min:.0f} min",   1)
    stat(summary, "Breaks taken",    str(total_breaks),       2)
    for c in range(3):
        summary.columnconfigure(c, weight=1)

    win.mainloop()

# ── Monitor thread ────────────────────────────────────────────────────────────
class Monitor:
    def __init__(self, cfg, status_cb=None):
        self.cfg        = cfg
        self.status_cb  = status_cb
        self._stop      = threading.Event()
        self._thread    = None
        self.start_time = None
        self.quote_idx  = 0
        self.paused     = False

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _run(self):
        threshold_secs = self.cfg["threshold_minutes"] * 60
        while not self._stop.is_set():
            if self.paused:
                time.sleep(3)
                continue

            title   = get_active_window_title()
            on_reel = is_reel_app(title, self.cfg["target_apps"])

            if on_reel:
                if self.start_time is None:
                    self.start_time = time.time()
                elapsed = time.time() - self.start_time
                if self.status_cb:
                    self.status_cb("watching", elapsed, title)
                if elapsed >= threshold_secs:
                    elapsed_min     = elapsed / 60
                    log_session(elapsed_min)
                    self.start_time = None
                    if self.cfg.get("block_app"):
                        minimize_window(title)
                    show_overlay(self.cfg, elapsed_min, self.quote_idx)
                    self.quote_idx += 1
            else:
                if self.start_time is not None:
                    self.start_time = None
                if self.status_cb:
                    self.status_cb("idle", 0, title)

            time.sleep(3)

# ── Settings window ───────────────────────────────────────────────────────────
def open_settings(cfg, on_save):
    win = tk.Toplevel()
    win.title("Settings — Reel Break Enforcer")
    win.geometry("420x380")
    win.resizable(False, False)
    win.configure(bg="#111111")

    lf = tkfont.Font(family="Segoe UI", size=11)
    hf = tkfont.Font(family="Segoe UI", size=13, weight="bold")

    def row(parent, label, var, row_n):
        tk.Label(parent, text=label, fg="#aaaaaa", bg="#111111",
                 font=lf, anchor="w").grid(row=row_n, column=0, sticky="w", padx=20, pady=8)
        tk.Entry(parent, textvariable=var, bg="#1e1e1e", fg="#ffffff",
                 insertbackground="#ffffff", relief="flat",
                 font=lf, width=8).grid(row=row_n, column=1, sticky="w", padx=10)

    tk.Label(win, text="Settings", fg="#ffffff", bg="#111111",
             font=hf).pack(pady=(20, 10))

    frame = tk.Frame(win, bg="#111111")
    frame.pack(fill="x")

    threshold_var = tk.StringVar(value=str(cfg["threshold_minutes"]))
    overlay_var   = tk.StringVar(value=str(cfg["overlay_seconds"]))
    block_var     = tk.BooleanVar(value=cfg.get("block_app", False))

    row(frame, "Break after (minutes)",      threshold_var, 0)
    row(frame, "Overlay duration (seconds)", overlay_var,   1)

    tk.Checkbutton(frame, text="Also minimize the app when overlay fires",
                   variable=block_var, fg="#aaaaaa", bg="#111111",
                   selectcolor="#1e1e1e", activebackground="#111111",
                   font=lf).grid(row=2, column=0, columnspan=2,
                                 sticky="w", padx=20, pady=8)

    tk.Label(win, text="Monitored apps (comma-separated):",
             fg="#aaaaaa", bg="#111111", font=lf, anchor="w"
             ).pack(padx=20, anchor="w", pady=(12, 4))

    apps_var = tk.StringVar(value=", ".join(cfg["target_apps"]))
    tk.Entry(win, textvariable=apps_var, bg="#1e1e1e", fg="#ffffff",
             insertbackground="#ffffff", relief="flat",
             font=lf, width=42).pack(padx=20)

    def save():
        try:
            cfg["threshold_minutes"] = float(threshold_var.get())
            cfg["overlay_seconds"]   = int(overlay_var.get())
            cfg["block_app"]         = block_var.get()
            cfg["target_apps"] = [a.strip() for a in apps_var.get().split(",") if a.strip()]
            save_config(cfg)
            on_save()
            win.destroy()
        except ValueError:
            pass

    tk.Button(win, text="Save", command=save,
              bg="#ff6b35", fg="#ffffff", relief="flat",
              font=lf, padx=24, pady=8,
              activebackground="#e05520", cursor="hand2").pack(pady=20)

# ── Main App ──────────────────────────────────────────────────────────────────
class App:
    def __init__(self):
        self.cfg     = load_config()
        self.monitor = None
        self.tray    = None

        self.root = tk.Tk()
        self.root.title("Reel Break Enforcer")
        self.root.geometry("460x500")
        self.root.resizable(True, True)
        self.root.minsize(460, 460)
        self.root.configure(bg="#111111")
        self.root.protocol("WM_DELETE_WINDOW", self._hide_to_tray)

        self._build_ui()
        self._update_stats()
        self._start_tray()

    def _build_ui(self):
        root = self.root
        hf   = tkfont.Font(family="Segoe UI", size=22, weight="bold")
        mf   = tkfont.Font(family="Segoe UI", size=13)
        sf   = tkfont.Font(family="Segoe UI", size=11)
        mono = tkfont.Font(family="Consolas",  size=11)

        tk.Label(root, text="◉  Reel Break Enforcer", fg="#ff6b35",
                 bg="#111111", font=hf).pack(pady=(16, 4))
        tk.Label(root, text="Reclaim your attention, one scroll at a time.",
                 fg="#555555", bg="#111111", font=sf).pack(pady=(0, 12))

        # Status card
        sf_card = tk.Frame(root, bg="#1a1a1a",
                           highlightbackground="#2a2a2a", highlightthickness=1)
        sf_card.pack(padx=30, fill="x", pady=(0, 16))

        self.status_dot = tk.Label(sf_card, text="●", fg="#555555", bg="#1a1a1a",
                                   font=tkfont.Font(family="Segoe UI", size=14))
        self.status_dot.grid(row=0, column=0, padx=(16, 8), pady=14)

        self.status_lbl = tk.Label(sf_card, text="Not monitoring",
                                   fg="#888888", bg="#1a1a1a", font=mf, anchor="w")
        self.status_lbl.grid(row=0, column=1, sticky="w")

        self.elapsed_lbl = tk.Label(sf_card, text="", fg="#ff6b35",
                                    bg="#1a1a1a", font=mono, anchor="e")
        self.elapsed_lbl.grid(row=0, column=2, sticky="e", padx=(0, 16))
        sf_card.columnconfigure(1, weight=1)

        # Progress bar
        pb_frame = tk.Frame(root, bg="#111111")
        pb_frame.pack(padx=30, fill="x", pady=(0, 24))
        self.pb_bg   = tk.Frame(pb_frame, bg="#1a1a1a", height=4)
        self.pb_bg.pack(fill="x")
        self.pb_fill = tk.Frame(self.pb_bg, bg="#ff6b35", height=4)
        self.pb_fill.place(x=0, y=0, relwidth=0, height=4)

        # Stats
        stats_frame = tk.Frame(root, bg="#111111")
        stats_frame.pack(padx=30, fill="x", pady=(0, 16))
        self.today_lbl  = self._stat_card(stats_frame, "Today's scroll time", "0 min", 0)
        self.breaks_lbl = self._stat_card(stats_frame, "Breaks taken today",  "0",     1)
        stats_frame.columnconfigure(0, weight=1)
        stats_frame.columnconfigure(1, weight=1)

        self.cfg_lbl = tk.Label(root, text=self._cfg_summary(),
                                fg="#444444", bg="#111111", font=sf)
        self.cfg_lbl.pack(pady=(0, 20))

        # Buttons
        btn_frame = tk.Frame(root, bg="#111111")
        btn_frame.pack(padx=30, fill="x")

        self.toggle_btn = tk.Button(btn_frame, text="▶  Start Monitoring",
                                    command=self._toggle,
                                    bg="#ff6b35", fg="#ffffff",
                                    activebackground="#e05520", relief="flat",
                                    font=mf, pady=6, cursor="hand2")
        self.toggle_btn.pack(fill="x", pady=(0, 8))

        self.pause_btn = tk.Button(btn_frame, text="⏸  Pause",
                                   command=self._toggle_pause,
                                   bg="#1e1e1e", fg="#aaaaaa",
                                   activebackground="#2a2a2a", relief="flat",
                                   font=mf, pady=6, cursor="hand2",
                                   state="disabled")
        self.pause_btn.pack(fill="x", pady=(0, 8))

        tk.Button(btn_frame, text="📊  Weekly Report",
                  command=lambda: threading.Thread(target=show_weekly_report, daemon=True).start(),
                  bg="#1e1e1e", fg="#aaaaaa", activebackground="#2a2a2a",
                  relief="flat", font=mf, pady=6, cursor="hand2"
                  ).pack(fill="x", pady=(0, 8))

        tk.Button(btn_frame, text="⚙  Settings",
                  command=self._open_settings,
                  bg="#1e1e1e", fg="#aaaaaa", activebackground="#2a2a2a",
                  relief="flat", font=mf, pady=6, cursor="hand2"
                  ).pack(fill="x", pady=(0, 8))

        tk.Button(btn_frame, text="🧪  Test Overlay",
                  command=self._test_overlay,
                  bg="#1e1e1e", fg="#aaaaaa", activebackground="#2a2a2a",
                  relief="flat", font=mf, pady=6, cursor="hand2"
                  ).pack(fill="x")

    def _stat_card(self, parent, label, value, col):
        f = tk.Frame(parent, bg="#1a1a1a",
                     highlightbackground="#2a2a2a", highlightthickness=1)
        f.grid(row=0, column=col, sticky="nsew",
               padx=(0, 8) if col == 0 else (0, 0), pady=2)
        tk.Label(f, text=label, fg="#555555", bg="#1a1a1a",
                 font=tkfont.Font(family="Segoe UI", size=10)).pack(padx=12, pady=(12, 2))
        v = tk.Label(f, text=value, fg="#ffffff", bg="#1a1a1a",
                     font=tkfont.Font(family="Segoe UI", size=18, weight="bold"))
        v.pack(padx=12, pady=(0, 12))
        return v

    def _cfg_summary(self):
        block = "  ·  Block on" if self.cfg.get("block_app") else ""
        return f"Break after {self.cfg['threshold_minutes']} min  ·  Overlay {self.cfg['overlay_seconds']}s{block}"

    # ── Tray ──────────────────────────────────────────────────────────────────
    def _start_tray(self):
        img  = make_tray_image(active=False)
        menu = pystray.Menu(
            pystray.MenuItem("Open Dashboard",  self._show_window, default=True),
            pystray.MenuItem("Pause / Resume",  self._tray_pause),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit",            self._quit),
        )
        self.tray = pystray.Icon("ReelBreakEnforcer", img,
                                 "Reel Break Enforcer", menu)
        threading.Thread(target=self.tray.run, daemon=True).start()

    def _hide_to_tray(self):
        self.root.withdraw()
        if self.tray:
            self.tray.notify("Running in background",
                             "Reel Break Enforcer is still active.")

    def _show_window(self, icon=None, item=None):
        self.root.after(0, self.root.deiconify)
        self.root.after(0, self.root.lift)

    def _tray_pause(self, icon=None, item=None):
        self.root.after(0, self._toggle_pause)

    def _quit(self, icon=None, item=None):
        if self.monitor:
            self.monitor.stop()
        if self.tray:
            self.tray.stop()
        self.root.after(0, self.root.destroy)

    # ── Controls ──────────────────────────────────────────────────────────────
    def _toggle(self):
        if self.monitor is None:
            self.monitor = Monitor(self.cfg, status_cb=self._on_status)
            self.monitor.start()
            self.toggle_btn.config(text="■  Stop Monitoring",
                                   bg="#2a2a2a", fg="#ff6b35")
            self.pause_btn.config(state="normal")
            if self.tray:
                self.tray.icon = make_tray_image(active=True)
        else:
            self.monitor.stop()
            self.monitor = None
            self.toggle_btn.config(text="▶  Start Monitoring",
                                   bg="#ff6b35", fg="#ffffff")
            self.pause_btn.config(text="⏸  Pause", state="disabled")
            self.status_dot.config(fg="#555555")
            self.status_lbl.config(text="Not monitoring", fg="#888888")
            self.elapsed_lbl.config(text="")
            self.pb_fill.place(relwidth=0)
            if self.tray:
                self.tray.icon = make_tray_image(active=False)

    def _toggle_pause(self):
        if self.monitor is None:
            return
        self.monitor.paused = not self.monitor.paused
        if self.monitor.paused:
            self.pause_btn.config(text="▶  Resume")
            self.status_lbl.config(text="Paused", fg="#555555")
            self.status_dot.config(fg="#555555")
        else:
            self.pause_btn.config(text="⏸  Pause")
            self.status_lbl.config(text="Monitoring…", fg="#888888")
            self.status_dot.config(fg="#22c55e")

    def _on_status(self, state, elapsed, title):
        threshold = self.cfg["threshold_minutes"] * 60
        if state == "watching":
            frac = min(elapsed / threshold, 1.0)
            mins = elapsed / 60
            self.root.after(0, lambda: (
                self.status_dot.config(fg="#ff6b35"),
                self.status_lbl.config(text="Scrolling detected", fg="#ff6b35"),
                self.elapsed_lbl.config(text=f"{mins:.1f} min"),
                self.pb_fill.place(relwidth=frac),
            ))
        else:
            self.root.after(0, lambda: (
                self.status_dot.config(fg="#22c55e"),
                self.status_lbl.config(text="Monitoring…", fg="#888888"),
                self.elapsed_lbl.config(text=""),
                self.pb_fill.place(relwidth=0),
            ))

    def _open_settings(self):
        open_settings(self.cfg, self._on_settings_saved)

    def _on_settings_saved(self):
        self.cfg = load_config()
        self.cfg_lbl.config(text=self._cfg_summary())
        if self.monitor:
            self.monitor.cfg = self.cfg

    def _test_overlay(self):
        threading.Thread(target=show_overlay,
                         args=(self.cfg, 12.5, 0), daemon=True).start()

    def _update_stats(self):
        log   = load_log()
        today = str(date.today())
        entry = log.get(today, {"total_minutes": 0, "breaks": 0})
        self.today_lbl.config(text=f"{entry['total_minutes']:.0f} min")
        self.breaks_lbl.config(text=str(entry["breaks"]))
        self.root.after(10_000, self._update_stats)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    App().run()

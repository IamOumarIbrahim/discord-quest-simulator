#!/usr/bin/env python3
"""
Discord Quest Runner (Linux and Windows)

Search Discord's list of detectable games, pick the ones you want, press Start.
For each pick we run a tiny window from a *copy* of the Python binary named like
the game's executable (e.g. .../wwm.exe). Discord's native scanner reads
/proc/<pid>/exe, sees that name and reports the game as running, which is what
drives "play X for 15 minutes" quests.

Needs only python3 + tkinter. Run with --selftest for a no-GUI check.
"""
import json, os, shutil, subprocess, sys, threading, time, urllib.request
import tkinter as tk
from tkinter import ttk, messagebox

IS_WIN = os.name == "nt"
if IS_WIN:
    import winreg

API = "https://discord.com/api/v9/applications/detectable"
if IS_WIN:
    _base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local"))
else:
    _base = os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))
DATA = os.path.join(_base, "discord-quest-runner")
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall"
REG_PREFIX = "DiscordQuestRunner_"
CACHE = os.path.join(DATA, "detectable.json")
SELECTION = os.path.join(DATA, "selection.json")
GAMES_DIR = os.path.join(DATA, "games")
WINDOW_PY = os.path.join(DATA, "window.py")
CACHE_MAX_AGE = 3 * 86400

# Games with a current Discord quest (lower-case API names) - shown first with a star.
QUEST_NAMES = {
    "where winds meet", "arknights: endfield", "call of duty: modern warfare 4",
    "roblox", "honkai: star rail", "delta force",
}

WINDOW_SRC = '''
import tkinter as tk, sys
r = tk.Tk(); r.title(sys.argv[1]); r.geometry("340x120"); r.configure(bg="#1e1f22")
tk.Label(r, text=sys.argv[1], font=("Sans", 13, "bold"), fg="#fff", bg="#1e1f22").pack(pady=26)
tk.Label(r, text="Quest Runner - keep open", fg="#949ba4", bg="#1e1f22").pack()
r.mainloop()
'''


# ----------------------------------------------------------------- game data
def load_raw(force=False):
    """Return Discord's detectable list, from cache when fresh, else the network."""
    os.makedirs(DATA, exist_ok=True)
    fresh = os.path.exists(CACHE) and time.time() - os.path.getmtime(CACHE) < CACHE_MAX_AGE
    if fresh and not force:
        with open(CACHE, encoding="utf-8") as f:
            return json.load(f)
    try:
        req = urllib.request.Request(API, headers={"User-Agent": "discord-quest-runner"})
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = json.load(r)
        with open(CACHE, "w", encoding="utf-8") as f:
            json.dump(raw, f)
        return raw
    except Exception:
        if os.path.exists(CACHE):  # stale cache beats nothing
            with open(CACHE, encoding="utf-8") as f:
                return json.load(f)
        raise


def safe_exe(name):
    parts = name.split("/")
    return all(p not in ("", ".", "..") and "\0" not in p and "\\" not in p for p in parts)


def parse(raw):
    games = []
    for g in raw:
        exes = [e for e in (g.get("executables") or [])
                if not e.get("is_launcher") and e.get("os") in ("win32", "linux")]
        if not exes:
            continue
        # prefer win32, then the shortest path (plain basename matches anywhere)
        exes.sort(key=lambda e: (e["os"] != "win32", e["name"].count("/")))
        exe = exes[0]["name"].lstrip(">")
        if not safe_exe(exe):
            continue
        name = g["name"]
        games.append({"id": str(g["id"]), "name": name, "exe": exe,
                      "lname": name.lower(), "quest": name.lower() in QUEST_NAMES})
    games.sort(key=lambda x: (not x["quest"], x["lname"]))
    return games


def search(games, query, quest_only=False, limit=400):
    words = query.lower().split()
    out = [g for g in games
           if (not quest_only or g["quest"]) and all(w in g["lname"] for w in words)]
    return len(out), out[:limit]


# ------------------------------------------------------------------- running
def python_binary():
    """The interpreter to copy. Windows: pythonw.exe (no console window)."""
    exe = os.path.realpath(sys.executable)
    if IS_WIN:
        w = os.path.join(os.path.dirname(exe), "pythonw.exe")
        return w if os.path.exists(w) else exe
    return exe


def register_windows(game, folder, target):
    """Discord's scanner also checks Uninstall registry entries for installed games."""
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, f"{UNINSTALL_KEY}\\{REG_PREFIX}{game['id']}") as k:
        winreg.SetValueEx(k, "DisplayName", 0, winreg.REG_SZ, game["name"])
        winreg.SetValueEx(k, "InstallLocation", 0, winreg.REG_SZ, folder)
        winreg.SetValueEx(k, "DisplayIcon", 0, winreg.REG_SZ, target)
        winreg.SetValueEx(k, "Publisher", 0, winreg.REG_SZ, game["name"])


def unregister_windows(gid):
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, f"{UNINSTALL_KEY}\\{REG_PREFIX}{gid}")
    except OSError:
        pass


def cleanup_stale_windows_keys():
    """Remove entries left behind by a crash."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as k:
            n = winreg.QueryInfoKey(k)[0]
            stale = [winreg.EnumKey(k, i) for i in range(n)]
        for name in stale:
            if name.startswith(REG_PREFIX):
                unregister_windows(name[len(REG_PREFIX):])
    except OSError:
        pass


class Runner:
    def __init__(self):
        self.procs = {}  # game id -> Popen
        self.dirs = {}

    def start(self, game):
        if self.running(game["id"]):
            return
        os.makedirs(DATA, exist_ok=True)
        with open(WINDOW_PY, "w") as f:
            f.write(WINDOW_SRC)
        folder = os.path.join(GAMES_DIR, game["id"])
        target = os.path.join(folder, *game["exe"].split("/"))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        if os.path.lexists(target):
            os.remove(target)
        # A real copy: Discord reads the resolved exe path, a symlink would not match.
        shutil.copy2(python_binary(), target)
        env = os.environ.copy()
        env["PYTHONHOME"] = sys.base_prefix  # the copy can't locate the stdlib otherwise
        if IS_WIN:  # the copy also needs python3xx.dll, which lives next to the original
            env["PATH"] = os.path.dirname(python_binary()) + os.pathsep + env.get("PATH", "")
            register_windows(game, folder, target)
        self.procs[game["id"]] = subprocess.Popen(
            [target, WINDOW_PY, game["name"]], env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.dirs[game["id"]] = folder

    def running(self, gid):
        p = self.procs.get(gid)
        return p is not None and p.poll() is None

    def stop(self, gid):
        p = self.procs.pop(gid, None)
        if p and p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=3)
            except subprocess.TimeoutExpired:
                p.kill()
        d = self.dirs.pop(gid, None)
        if d:
            shutil.rmtree(d, ignore_errors=True)
        if IS_WIN:
            unregister_windows(gid)

    def stop_all(self):
        for gid in list(self.procs):
            self.stop(gid)


# ----------------------------------------------------------------------- GUI
BG, PANEL, FG, MUTED, ACCENT = "#1e1f22", "#2b2d31", "#dbdee1", "#949ba4", "#5865F2"


class App:
    def __init__(self, root):
        self.root = root
        self.runner = Runner()
        self.games, self.by_id = [], {}
        self.selected = []  # game ids, in order added
        root.title("Discord Quest Runner")
        root.geometry("980x640")
        root.minsize(760, 480)
        root.configure(bg=BG)
        self.style()
        self.build()
        self.load_selection_ids = self.read_selection()
        self.status("Loading Discord's game list...")
        threading.Thread(target=self.load_games, daemon=True).start()
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.poll()

    def style(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure(".", background=BG, foreground=FG, fieldbackground=PANEL, font=("Sans", 10))
        s.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=FG,
                    rowheight=26, borderwidth=0)
        s.map("Treeview", background=[("selected", ACCENT)], foreground=[("selected", "#fff")])
        s.configure("Treeview.Heading", background=BG, foreground=MUTED, borderwidth=0)
        s.configure("TButton", background=PANEL, foreground=FG, padding=8, borderwidth=0)
        s.map("TButton", background=[("active", "#3a3c43")])
        s.configure("Accent.TButton", background=ACCENT, foreground="#fff", font=("Sans", 10, "bold"))
        s.map("Accent.TButton", background=[("active", "#4752c4")])
        s.configure("Stop.TButton", background="#da373c", foreground="#fff", font=("Sans", 10, "bold"))
        s.map("Stop.TButton", background=[("active", "#a12828")])
        s.configure("TCheckbutton", background=BG, foreground=FG)
        s.configure("TEntry", insertcolor=FG, padding=6)
        s.configure("Title.TLabel", font=("Sans", 15, "bold"))
        s.configure("Muted.TLabel", foreground=MUTED)

    def build(self):
        top = ttk.Frame(self.root, padding=(16, 14, 16, 6))
        top.pack(fill="x")
        ttk.Label(top, text="Discord Quest Runner", style="Title.TLabel").pack(anchor="w")
        ttk.Label(top, text="Type to search every game Discord can detect, add the ones you want, press Start.",
                  style="Muted.TLabel").pack(anchor="w", pady=(2, 8))
        row = ttk.Frame(top)
        row.pack(fill="x")
        self.query = tk.StringVar()
        self.query.trace_add("write", lambda *_: self.refresh())
        self.entry = ttk.Entry(row, textvariable=self.query, font=("Sans", 12))
        self.entry.pack(side="left", fill="x", expand=True)
        self.quest_only = tk.BooleanVar(value=False)
        ttk.Checkbutton(row, text="★ Quest games only", variable=self.quest_only,
                        command=self.refresh).pack(side="left", padx=(12, 0))

        mid = ttk.Frame(self.root, padding=(16, 6))
        mid.pack(fill="both", expand=True)
        mid.columnconfigure(0, weight=3, uniform="c")
        mid.columnconfigure(2, weight=2, uniform="c")
        mid.rowconfigure(1, weight=1)

        self.count = ttk.Label(mid, text="", style="Muted.TLabel")
        self.count.grid(row=0, column=0, sticky="w", pady=(0, 4))
        ttk.Label(mid, text="Selected", style="Muted.TLabel").grid(row=0, column=2, sticky="w", pady=(0, 4))

        self.results = ttk.Treeview(mid, columns=("exe",), selectmode="extended")
        self.results.heading("#0", text="Game")
        self.results.heading("exe", text="Process")
        self.results.column("#0", width=300)
        self.results.column("exe", width=180)
        self.results.grid(row=1, column=0, sticky="nsew")
        sb = ttk.Scrollbar(mid, command=self.results.yview)
        self.results.configure(yscrollcommand=sb.set)
        sb.grid(row=1, column=1, sticky="ns")
        self.results.bind("<Double-1>", lambda e: self.add())
        self.results.bind("<Return>", lambda e: self.add())

        self.chosen = ttk.Treeview(mid, columns=("state",), selectmode="extended")
        self.chosen.heading("#0", text="Game")
        self.chosen.heading("state", text="State")
        self.chosen.column("#0", width=200)
        self.chosen.column("state", width=80, anchor="center")
        self.chosen.grid(row=1, column=2, sticky="nsew", padx=(10, 0))
        self.chosen.bind("<Delete>", lambda e: self.remove())
        self.chosen.bind("<Double-1>", lambda e: self.remove())

        btns = ttk.Frame(mid)
        btns.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        ttk.Button(btns, text="Add selected  →", command=self.add).pack(side="left")
        ttk.Button(btns, text="Remove", command=self.remove).pack(side="right")
        ttk.Button(btns, text="Clear", command=self.clear).pack(side="right", padx=(0, 6))

        bottom = ttk.Frame(self.root, padding=(16, 8, 16, 14))
        bottom.pack(fill="x")
        ttk.Button(bottom, text="▶  Start", style="Accent.TButton", command=self.start).pack(side="left")
        ttk.Button(bottom, text="■  Stop all", style="Stop.TButton", command=self.stop_all).pack(side="left", padx=8)
        self.msg = ttk.Label(bottom, text="", style="Muted.TLabel")
        self.msg.pack(side="left", padx=12)
        self.entry.focus_set()

    # ---- data
    def load_games(self):
        try:
            games = parse(load_raw())
        except Exception as e:
            self.root.after(0, lambda: self.status(f"Could not load game list: {e}"))
            return
        self.root.after(0, lambda: self.loaded(games))

    def loaded(self, games):
        self.games = games
        self.by_id = {g["id"]: g for g in games}
        self.selected = [i for i in self.load_selection_ids if i in self.by_id]
        self.refresh()
        self.refresh_chosen()
        self.status(f"{len(games):,} games available.")

    def read_selection(self):
        try:
            with open(SELECTION) as f:
                return json.load(f)
        except Exception:
            return []

    def save_selection(self):
        try:
            os.makedirs(DATA, exist_ok=True)
            with open(SELECTION, "w") as f:
                json.dump(self.selected, f)
        except OSError:
            pass

    # ---- list views
    def refresh(self):
        total, rows = search(self.games, self.query.get(), self.quest_only.get())
        self.results.delete(*self.results.get_children())
        for g in rows:
            self.results.insert("", "end", iid=g["id"], text=("★ " if g["quest"] else "") + g["name"],
                                values=(g["exe"],))
        shown = f"showing first {len(rows)} of {total:,}" if total > len(rows) else f"{total:,} match"
        self.count.config(text=f"Results ({shown})")

    def refresh_chosen(self):
        self.chosen.delete(*self.chosen.get_children())
        for gid in self.selected:
            g = self.by_id[gid]
            self.chosen.insert("", "end", iid=gid, text=g["name"],
                               values=("running" if self.runner.running(gid) else "ready",))

    def add(self):
        for gid in self.results.selection():
            if gid not in self.selected:
                self.selected.append(gid)
        self.save_selection()
        self.refresh_chosen()

    def remove(self):
        for gid in self.chosen.selection():
            self.runner.stop(gid)
            if gid in self.selected:
                self.selected.remove(gid)
        self.save_selection()
        self.refresh_chosen()

    def clear(self):
        self.stop_all()
        self.selected = []
        self.save_selection()
        self.refresh_chosen()

    # ---- running
    def start(self):
        if not self.selected:
            messagebox.showinfo("Nothing selected", "Search for a game and add it first.")
            return
        failed = []
        for gid in self.selected:
            try:
                self.runner.start(self.by_id[gid])
            except Exception as e:
                failed.append(f"{self.by_id[gid]['name']}: {e}")
        self.refresh_chosen()
        if failed:
            messagebox.showerror("Could not start", "\n".join(failed))
        else:
            self.status("Running. Keep this app open; accept the quests in Discord and wait ~15 min.")

    def stop_all(self):
        self.runner.stop_all()
        self.refresh_chosen()
        self.status("Stopped.")

    def poll(self):
        for gid in self.selected:
            if self.chosen.exists(gid):
                self.chosen.set(gid, "state", "running" if self.runner.running(gid) else "ready")
        self.root.after(1500, self.poll)

    def status(self, text):
        self.msg.config(text=text)

    def on_close(self):
        self.runner.stop_all()
        self.root.destroy()


# ---------------------------------------------------------------------- main
def selftest():
    games = parse(load_raw())
    print(f"{len(games)} detectable games; quest games: {[g['name'] for g in games if g['quest']]}")
    g = next(x for x in games if x["quest"])
    r = Runner()
    r.start(g)
    time.sleep(1.5)
    pid = r.procs[g["id"]].pid
    if IS_WIN:
        exe = os.path.join(GAMES_DIR, g["id"], *g["exe"].split("/"))
        ok = os.path.exists(exe) and r.running(g["id"])
    else:
        exe = os.readlink(f"/proc/{pid}/exe")
        ok = exe.endswith(g["exe"]) and r.running(g["id"])
    print(f"{g['name']}: pid {pid} -> {exe}  {'OK' if ok else 'FAIL'}")
    r.stop_all()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    if IS_WIN:
        cleanup_stale_windows_keys()
    root = tk.Tk()
    App(root)
    root.mainloop()

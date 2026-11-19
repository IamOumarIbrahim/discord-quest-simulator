#!/usr/bin/env python3
"""
Discord Quest Simulator - Linux launcher (process-name based).

Why this works: Discord on Linux scans /proc and matches each process's
command line (argv[0] path) / comm against the `executables` of its
detectable-games list. Overwatch under Proton is seen as
`S:\\...\\Overwatch\\Overwatch.exe`, which matches `overwatch.exe`.

So for each game we create  <base>/<folder>/<exe>  as a COPY of the python binary
(giving both argv[0] and comm the right name, like the Windows version that
copied pythonw.exe), and run a small tkinter window with it.

Usage: python3 linux_quest_launcher.py [name-filter ...]
"""
import os, sys, signal, subprocess, time, shutil

# exe = path suffix exactly as in Discord's detectable list (lowercase, '/' separated)
GAMES = [
    {"name": "Where Winds Meet",    "exe": "wwm.exe"},
    {"name": "Arknights: Endfield", "exe": "endfield.exe"},
    {"name": "COD Modern Warfare 4", "exe": "sp26-cod.exe"},
    {"name": "Roblox",              "exe": "robloxplayerbeta.exe"},
    {"name": "Honkai: Star Rail",   "exe": "games/starrail.exe"},
    {"name": "Delta Force",         "exe": "win64/deltaforceclient-win64-shipping.exe"},
    {"name": "Overwatch (test)",    "exe": "overwatch.exe", "optional": True},
]

BASE = os.path.expanduser("~/.cache/discord-quest-games")
WINDOW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_quest_window.py")

WINDOW_SRC = '''
import tkinter as tk, sys
r = tk.Tk(); r.title(sys.argv[1]); r.geometry("360x140"); r.configure(bg="#1e1f22")
tk.Label(r, text=sys.argv[1], font=("Sans", 14, "bold"), fg="#fff", bg="#1e1f22").pack(pady=30)
tk.Label(r, text="Quest simulator running", fg="#949ba4", bg="#1e1f22").pack()
r.mainloop()
'''

procs = []

def cleanup(*_):
    for p, _n in procs:
        try: p.terminate()
        except Exception: pass
    shutil.rmtree(BASE, ignore_errors=True)
    try: os.remove(WINDOW)
    except OSError: pass
    print("\nStopped.")
    sys.exit(0)

def main():
    filt = [a.lower() for a in sys.argv[1:]]
    games = [g for g in GAMES if (not filt and not g.get("optional"))
             or any(f in g["name"].lower() for f in filt)]
    open(WINDOW, "w").write(WINDOW_SRC)
    py = os.path.realpath(sys.executable)
    env = os.environ.copy()
    env.setdefault("DISPLAY", ":0")
    env["PYTHONHOME"] = sys.base_prefix  # copied binary can't locate stdlib otherwise

    for g in games:
        # folder like ".../Where Winds Meet/<exe path>" so the path suffix matches
        target = os.path.join(BASE, g["name"].replace(":", ""), *g["exe"].split("/"))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        if os.path.lexists(target): os.remove(target)
        shutil.copy2(py, target)  # real copy: Discord reads /proc/<pid>/exe (resolved)
        p = subprocess.Popen([target, WINDOW, g["name"]], env=env,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        procs.append((p, g["name"]))
        time.sleep(0.5)
        # verify what Discord will see
        try:
            cmd = open(f"/proc/{p.pid}/cmdline").read().split("\0")[0]
            comm = open(f"/proc/{p.pid}/comm").read().strip()
            print(f"[+] {g['name']:<24} pid={p.pid} comm={comm!r} argv0=...{cmd[-45:]}")
        except OSError:
            print(f"[!] {g['name']} exited immediately (tkinter/display problem?)")

    print("\nKeep running ~15 min. Ctrl+C to stop.")
    signal.signal(signal.SIGINT, cleanup); signal.signal(signal.SIGTERM, cleanup)
    while True:
        time.sleep(5)

main()

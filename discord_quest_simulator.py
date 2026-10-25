#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Discord Quest Simulator & Completer (Orbs Edition)
===================================================
A tool to simulate games on your desktop so Discord detects them
for Quest completion, and to complete Quests instantly.

How Discord Detects Applications:
  1. Desktop Process Scanning:
     Discord's native module (`discord_game_utils.node`) periodically scans running
     processes, checks top-level windows, and matches them against installed games
     found in the Windows Registry (`HKCU/HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall`).
     When an executable runs with a window and has matching registry metadata,
     Discord's native `identifyGame` returns code 0 (Success!) and marks the game as "Playing [Game]".

  2. In-Client Quest Tracking:
     Discord's frontend `RunningGameStore` and `FluxDispatcher` manage active games.
     When a game is recognized, Discord's internal client sends authenticated heartbeats
     to `POST /api/v9/quests/{id}/heartbeat`.
     For video quests, the client posts directly to `/api/v9/quests/{id}/video-progress`,
     which completes INSTANTLY.

Features:
  - Live Quest Viewer: Fetches your enrolled quests directly from `GET /api/v9/quests/@me`.
  - Instant Video Completer: Completes video quests in 1 second via API.
  - One-Click DevTools Enabler: Patches `%APPDATA%\\discord\\settings.json` to enable
    `Ctrl + Shift + I` in Discord Desktop.
  - Clipboard Helper: Copies the in-app Webpack Quest Completer script to your clipboard.
  - Pseudo-App Launcher: Creates real registered Windows GUI applications with matching
    metadata so Discord natively displays them just like Genshin Impact.
"""

import os
import sys
import json
import time
import shutil
import signal
import winreg
import argparse
import subprocess
import urllib.request
import urllib.error
from typing import Optional, List, Dict, Any

# Force UTF-8 on Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

DISCORD_API = "https://discord.com/api/v9"
DISCORD_SETTINGS_PATH = os.path.expandvars(r"%APPDATA%\discord\settings.json")

# Verified Quest Database matching Discord's Detectable Games & Current Quests
QUEST_GAMES = [
    {
        "name": "Arknights: Endfield",
        "app_id": "1461154307171811401",
        "quest_id": "1555080843502813245",
        "executables": ["endfield.exe"],
        "publisher": "GRYPHLINE",
        "orbs": 700
    },
    {
        "name": "Once Human",
        "app_id": "1260340082150346932",
        "quest_id": "1554696065704529930",
        "executables": ["once_human.exe"],
        "publisher": "Starry Studio",
        "orbs": 700
    },
    {
        "name": "Nekome",
        "app_id": "1560760495248777256",
        "quest_id": "1560389333956034571",
        "executables": ["nekomedemo.exe"],
        "publisher": "ProbablyMonsters",
        "orbs": 700
    },
    {
        "name": "Where Winds Meet",
        "app_id": "1437509662303059998",
        "quest_id": "1554689886835966094",
        "executables": ["wwm.exe"],
        "publisher": "NetEase Games",
        "orbs": 700
    },
    {
        "name": "Call of Duty: Modern Warfare 4",
        "app_id": "1511443377927880775",
        "quest_id": "1552893313500184617",
        "executables": ["sp26-cod.exe"],
        "publisher": "Activision",
        "orbs": 700
    },
    {
        "name": "Resident Evil (Sale Quest)",
        "app_id": "1129504165727584307",
        "quest_id": "1560042472560787507",
        "executables": ["re2.exe"],
        "publisher": "Capcom",
        "orbs": 700
    },
    {
        "name": "EA SPORTS FC 27",
        "app_id": "1531874756096295054",
        "quest_id": "1563322864659202169",
        "executables": ["fc26.exe"],
        "publisher": "Electronic Arts",
        "orbs": 700
    },
    {
        "name": "VALORANT",
        "app_id": "700136079562375258",
        "quest_id": "1549142163487592600",
        "executables": ["valorant-win64-shipping.exe"],
        "publisher": "Riot Games",
        "orbs": 700
    },
    {
        "name": "ROBLOX",
        "app_id": "363445589247131668",
        "quest_id": "1562915304299044884",
        "executables": ["roblox.exe"],
        "publisher": "Roblox Corporation",
        "orbs": 700
    }
]

# ANSI Styling
def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m"

GREEN = lambda t: _c("32", t)
YELLOW = lambda t: _c("33", t)
RED = lambda t: _c("31", t)
CYAN = lambda t: _c("36", t)
MAGENTA = lambda t: _c("35", t)
BOLD = lambda t: _c("1", t)
DIM = lambda t: _c("2", t)

# ─────────────────────────────────────────────────────────────
# DISCORD API HELPERS
# ─────────────────────────────────────────────────────────────
def fetch_user_quests(token: str) -> Optional[List[Dict[str, Any]]]:
    """Fetch all active quests for the user from Discord's official endpoint."""
    url = f"{DISCORD_API}/quests/@me"
    req = urllib.request.Request(url, headers={
        "Authorization": token,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) discord/1.0.9265 Safari/537.36"
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("quests", [])
    except urllib.error.HTTPError as e:
        print(RED(f"[-] Discord API HTTP Error {e.code}: {e.read().decode('utf-8', errors='replace')}"))
        return None
    except Exception as e:
        print(RED(f"[-] Connection Error: {e}"))
        return None

def complete_video_quest(token: str, quest_id: str, seconds: int = 900) -> bool:
    """Instant completion for video quests via the video-progress endpoint."""
    url = f"{DISCORD_API}/quests/{quest_id}/video-progress"
    payload = json.dumps({"timestamp": seconds}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, method="POST", headers={
        "Authorization": token,
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("completed_at") is not None
    except Exception as e:
        print(RED(f"[-] Video completion error: {e}"))
        return False

# ─────────────────────────────────────────────────────────────
# DEVTOOLS ENABLER
# ─────────────────────────────────────────────────────────────
def enable_discord_devtools() -> bool:
    """Enable Ctrl + Shift + I in Discord Desktop by editing settings.json."""
    if not os.path.exists(DISCORD_SETTINGS_PATH):
        print(RED(f"[-] Discord settings.json not found at {DISCORD_SETTINGS_PATH}"))
        return False

    try:
        with open(DISCORD_SETTINGS_PATH, "r", encoding="utf-8") as f:
            settings = json.load(f)

        key = "DANGEROUS_ENABLE_DEVTOOLS_ONLY_ENABLE_IF_YOU_KNOW_WHAT_YOURE_DOING"
        if settings.get(key) is True:
            print(GREEN("[✓] Discord DevTools is ALREADY enabled!"))
            return True

        settings[key] = True
        with open(DISCORD_SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)

        print(GREEN("[✓] Successfully enabled Discord DevTools in settings.json!"))
        print(YELLOW("[!] Please RESTART Discord for this change to take effect."))
        print(CYAN("[i] After restarting, press Ctrl + Shift + I anywhere in Discord to open DevTools."))
        return True
    except Exception as e:
        print(RED(f"[-] Failed to update settings.json: {e}"))
        return False

# ─────────────────────────────────────────────────────────────
# CLIPBOARD HELPER
# ─────────────────────────────────────────────────────────────
def copy_completer_to_clipboard() -> bool:
    """Copy the contents of orbs/discord_console_completer.js to clipboard."""
    script_path = os.path.join(os.path.dirname(__file__), "discord_console_completer.js")
    if not os.path.exists(script_path):
        print(RED(f"[-] Script not found: {script_path}"))
        return False

    with open(script_path, "r", encoding="utf-8") as f:
        code = f.read()

    try:
        # Use PowerShell Set-Clipboard
        proc = subprocess.Popen(["powershell", "-NoProfile", "-Command", "Set-Clipboard -Value $input"],
                                stdin=subprocess.PIPE)
        proc.communicate(input=code.encode("utf-8"))
        print(GREEN("[✓] Copied 'discord_console_completer.js' to your Windows Clipboard!"))
        print(CYAN("    Now go to Discord -> Press Ctrl + Shift + I -> Console tab -> Ctrl + V -> Press Enter!"))
        return True
    except Exception as e:
        print(YELLOW(f"[!] Could not set clipboard directly ({e}). You can copy directly from {script_path}"))
        return False

# ─────────────────────────────────────────────────────────────
# DESKTOP PSEUDO-APPLICATION ENGINE (WITH REGISTRY REGISTRATION)
# ─────────────────────────────────────────────────────────────
class PseudoGameManager:
    """
    Manages pseudo-applications on Windows.
    Registers the applications under HKCU Uninstall and launches lightweight GUI
    windows matching the target game executable names and window titles.
    Discord's native scanner detects them as verified installed games.
    """
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.procs = []
        self.reg_keys = []
        self.pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        if not os.path.exists(self.pythonw):
            self.pythonw = sys.executable

    def launch_game(self, game: Dict[str, Any]) -> bool:
        name = game["name"]
        exe_name = game["executables"][0]
        publisher = game.get("publisher", "Verified Game")

        game_folder = os.path.join(self.base_dir, name.replace(":", ""))
        os.makedirs(game_folder, exist_ok=True)

        target_exe = os.path.join(game_folder, exe_name)
        if not os.path.exists(target_exe):
            shutil.copy2(self.pythonw, target_exe)

        # Register in Windows HKCU Uninstall
        safe_key_name = name.replace(":", "").replace(" ", "")
        reg_subpath = f"Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{safe_key_name}"
        try:
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, reg_subpath)
            winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, name)
            winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, game_folder)
            winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, target_exe)
            winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, publisher)
            winreg.CloseKey(key)
            self.reg_keys.append(reg_subpath)
        except Exception as e:
            print(YELLOW(f"[!] Registry registration warning for {name}: {e}"))

        # Create GUI script
        script_path = os.path.join(game_folder, "game_window.py")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(f'''import tkinter as tk
root = tk.Tk()
root.title("{name}")
root.geometry("380x180")
root.configure(bg="#1e1f22")
lbl = tk.Label(root, text="{name}", font=("Segoe UI", 14, "bold"), fg="#ffffff", bg="#1e1f22")
lbl.pack(pady=20)
sub = tk.Label(root, text="Discord Quest Simulator (Active)", font=("Segoe UI", 10), fg="#949ba4", bg="#1e1f22")
sub.pack()
root.mainloop()
''')

        try:
            proc = subprocess.Popen([target_exe, script_path])
            self.procs.append((proc, name, target_exe))
            print(GREEN(f"  [✓] Launched Pseudo Game: {name}") + DIM(f" ({exe_name}, PID {proc.pid})"))
            return True
        except Exception as e:
            print(RED(f"  [-] Failed to launch {name}: {e}"))
            return False

    def stop_all(self):
        print(YELLOW("\n[*] Terminating all pseudo game processes..."))
        for proc, name, _ in self.procs:
            try:
                proc.terminate()
            except Exception:
                pass
        self.procs.clear()

        print(YELLOW("[*] Cleaning up Windows Registry entries..."))
        for reg_subpath in self.reg_keys:
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, reg_subpath)
            except Exception:
                pass
        self.reg_keys.clear()
        print(GREEN("[✓] All processes and registry keys cleaned up."))

def run_desktop_simulation(selected_games: List[Dict[str, Any]], duration_minutes: float = 15.0):
    base_dir = os.path.join(os.path.dirname(__file__), "pseudo_games")
    os.makedirs(base_dir, exist_ok=True)

    manager = PseudoGameManager(base_dir)

    print(BOLD(f"\n[+] Starting Desktop Pseudo-Application Simulation"))
    print(DIM("    Each application will be registered in Windows Registry & launched with a GUI window."))
    print(DIM("    Discord's native game detector will recognize it as a verified game.\n"))

    for g in selected_games:
        manager.launch_game(g)

    def handle_exit(signum=None, frame=None):
        manager.stop_all()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    total_secs = int(duration_minutes * 60)
    print(BOLD(f"\n[+] All applications running. Waiting {duration_minutes:.1f} minutes for Discord..."))
    print(DIM("    Press Ctrl + C at any time to stop.\n"))

    start_time = time.time()
    bar_width = 40
    try:
        while True:
            elapsed = time.time() - start_time
            if duration_minutes > 0 and elapsed >= total_secs:
                break
            pct = min(1.0, elapsed / max(total_secs, 1))
            filled = int(bar_width * pct)
            bar = "█" * filled + "░" * (bar_width - filled)
            mins_left = max(0, int((total_secs - elapsed) // 60))
            secs_left = max(0, int((total_secs - elapsed) % 60))
            print(f"\r  [{bar}] {pct*100:5.1f}%  {mins_left:02d}:{secs_left:02d} remaining", end="", flush=True)
            time.sleep(1)
        print()
    finally:
        manager.stop_all()

# ─────────────────────────────────────────────────────────────
# INTERACTIVE CLI INTERFACE
# ─────────────────────────────────────────────────────────────
def show_live_quests(token: str):
    print(BOLD("\n[+] Fetching live quest status from Discord..."))
    quests = fetch_user_quests(token)
    if quests is None:
        return

    enrolled = [q for q in quests if (q.get("user_status") or {}).get("enrolled_at") and not (q.get("user_status") or {}).get("completed_at")]
    completed = [q for q in quests if (q.get("user_status") or {}).get("completed_at")]

    print(BOLD(f"\n{'═'*70}"))
    print(CYAN(BOLD(f"  ACTIVE ENROLLED QUESTS ({len(enrolled)} Incomplete)")))
    print(BOLD(f"{'═'*70}"))

    if not enrolled:
        print(YELLOW("  No incomplete enrolled quests! Accept a quest in Discord's Quest tab first."))
    else:
        for q in enrolled:
            cfg = q.get("config", {})
            msgs = cfg.get("messages", {})
            name = msgs.get("quest_name") or cfg.get("quest_name") or q.get("id")
            game_title = msgs.get("game_title") or "Game"
            task_cfg = cfg.get("task_config_v2", {}).get("tasks", {})
            task_names = list(task_cfg.keys())
            target = 900
            for t in task_cfg.values():
                target = t.get("target", 900)
                break
            user_status = q.get("user_status") or {}
            progress = user_status.get("progress") or {}
            val = 0
            for p in progress.values():
                val = p.get("value", 0)
                break
            pct = round((val / target) * 100) if target else 0
            print(f"  • {BOLD(name)} ({game_title})")
            print(f"    Task: {', '.join(task_names)} | Progress: {val}/{target}s ({pct}%) | ID: {q.get('id')}")

    print(BOLD(f"\n{'─'*70}"))
    print(DIM(f"  Completed Quests: {len(completed)}"))
    print(BOLD(f"{'─'*70}\n"))

def interactive_menu():
    print(BOLD(CYAN("""
╔══════════════════════════════════════════════════════════════════╗
║           DISCORD QUEST SIMULATOR & COMPLETER (ORBS)             ║
╚══════════════════════════════════════════════════════════════════╝
""")))
    print("  1. " + BOLD("View Live Enrolled Quests & Progress") + " (via Discord Token)")
    print("  2. " + GREEN(BOLD("⚡ Instant Console Completer")) + " (Enable DevTools + Copy Script)")
    print("  3. " + CYAN(BOLD("🖥 Launch Desktop Pseudo-Applications")) + " (Native Windows Detection)")
    print("  4. " + MAGENTA(BOLD("▶ Instantly Complete Video Quests")) + " (No wait)")
    print("  0. Exit\n")

    choice = input(BOLD("Select an option [1-4]: ")).strip()

    if choice == "1":
        token = input("Enter your Discord token: ").strip()
        if token:
            show_live_quests(token)
    elif choice == "2":
        print(BOLD("\n[+] Setting up In-Discord Quest Completer:"))
        enable_discord_devtools()
        copy_completer_to_clipboard()
        print(BOLD("\nInstructions:"))
        print("  1. Restart Discord (if you haven't enabled DevTools before).")
        print("  2. Inside Discord, press " + CYAN(BOLD("Ctrl + Shift + I")) + " to open Developer Tools.")
        print("  3. Click the " + BOLD("Console") + " tab.")
        print("  4. Press " + CYAN(BOLD("Ctrl + V")) + " then hit " + BOLD("Enter") + "!")
        print("  5. The script will automatically spoof the game and advance the quest!\n")
    elif choice == "3":
        print(BOLD("\nSelect which games to simulate:"))
        for i, g in enumerate(QUEST_GAMES, 1):
            print(f"  {CYAN(str(i))}. {g['name']} ({g['orbs']} Orbs)")
        print(f"  {CYAN('0')}. All Games")
        selection = input("\nEnter numbers (comma-separated) or 0 for all [0]: ").strip()
        if not selection or selection == "0":
            selected = QUEST_GAMES
        else:
            try:
                indices = [int(x.strip()) - 1 for x in selection.split(",")]
                selected = [QUEST_GAMES[i] for i in indices if 0 <= i < len(QUEST_GAMES)]
            except Exception:
                selected = QUEST_GAMES
        mins = input("Duration in minutes [15]: ").strip()
        duration = float(mins) if mins else 15.0
        run_desktop_simulation(selected, duration)
    elif choice == "4":
        token = input("Enter your Discord token: ").strip()
        if token:
            quests = fetch_user_quests(token)
            if quests:
                for q in quests:
                    cfg = q.get("config", {})
                    task_cfg = cfg.get("task_config_v2", {}).get("tasks", {})
                    if "WATCH_VIDEO" in task_cfg:
                        name = cfg.get("messages", {}).get("quest_name", q.get("id"))
                        print(f"[*] Found Video Quest: {name} (ID {q.get('id')}). Completing...")
                        ok = complete_video_quest(token, q.get("id"))
                        if ok:
                            print(GREEN(f"[✓] {name} COMPLETED!"))
                        else:
                            print(YELLOW(f"[!] Could not complete {name}"))
    else:
        print("Exiting.")

def main():
    parser = argparse.ArgumentParser(description="Discord Quest Simulator & Completer")
    parser.add_argument("--token", type=str, help="Discord user token")
    parser.add_argument("--enable-devtools", action="store_true", help="Enable DevTools in Discord settings.json")
    parser.add_argument("--copy-script", action="store_true", help="Copy console completer script to clipboard")
    parser.add_argument("--mode", choices=["pseudo", "quests", "video"], help="Run directly without interactive menu")
    parser.add_argument("--duration", type=float, default=15.0, help="Duration for pseudo game mode in minutes")
    args = parser.parse_args()

    if args.enable_devtools:
        enable_discord_devtools()
        return

    if args.copy_script:
        copy_completer_to_clipboard()
        return

    if args.mode == "quests" and args.token:
        show_live_quests(args.token)
        return

    if args.mode == "pseudo":
        run_desktop_simulation(QUEST_GAMES, args.duration)
        return

    interactive_menu()

if __name__ == "__main__":
    main()

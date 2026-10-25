# Discord Quest Simulator & Completer (Orbs Edition)

A reverse-engineered toolkit designed to simulate running games for Discord Quest rewards and complete quests.

---

## 🔍 Root Cause Analysis: How Discord Actually Logs and Verifies Applications

By reverse engineering Discord Desktop's native modules (`discord_game_utils.node`, `discord_utils.node`), `core.asar`, and Discord's client runtime logs (`renderer_js.log`), here is how game verification works:

### 1. Why Genshin Impact Was Detected
When Genshin Impact is running on your machine:
- It is registered in the Windows Registry under `HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall\Genshin Impact`.
- Its process path is `C:\Program Files\HoYoPlay\games\Genshin Impact game\GenshinImpact.exe`.
- Discord's native module runs `ScanUninstallEntries` and calls `identifyGame(pid)`.
- Because the running executable matches an installed, registered application in Windows Registry, `identifyGame` returns code `0` (Success) with `name: "Genshin Impact"` and extracts its icon.
- Discord's `RunningGameStore` receives this and logs:
  `[Clips] decider: handleRunningGamesChange visibleGame=Genshin Impact`
- Discord's UI displays **"Genshin Impact, Not Sharing"** in the bottom-left panel.

### 2. Why the Initial Dummy Python Script Failed
- Headless, invisible console processes (`CREATE_NO_WINDOW`) without a top-level Windows GUI handle are classified by Discord's window scanner as **"Non-Games"** (`Running Non-Games Changed`).
- Unregistered `.exe` files in temporary directories return `identifyGame err: 3` (`name: ""`) and are ignored by Discord's Quest tracking.

### 3. Why External Heartbeats Returned 404 & 401
- **404**: The endpoint was `/quests/@me` (not `/users/@me/quests`).
- **401**: Discord's server enforces strict Cloudflare/Session authentication (`x-discord-features: quests`, internal browser cookies, session fingerprinting) on `POST /quests/{id}/heartbeat`. Raw standalone HTTP scripts without the active browser session are rejected with `401 Unauthorised` (`code: 40001`).

---

## 🚀 Two Methods to Complete Quests

### Method 1: In-Discord Webpack Completer (Recommended — Instant & Safe)
Because Discord's own desktop client already holds all session credentials and authentication tokens, we can hook into Discord's internal `RunningGameStore` directly.

1. **Enable DevTools in Discord**:
   ```bash
   python discord_quest_simulator.py --enable-devtools
   ```
2. **Restart Discord** (close and re-open Discord).
3. **Copy the Completer Script**:
   ```bash
   python discord_quest_simulator.py --copy-script
   ```
   *(Or copy the contents of `discord_console_completer.js` manually).*
4. Inside Discord, press **`Ctrl + Shift + I`** to open Developer Tools.
5. Click the **Console** tab.
6. Press **`Ctrl + V`** and hit **Enter**.
   - **Video Quests**: Completed **instantly in 1 second**!
   - **Play Quests**: Spoofs `RunningGameStore` and dispatches `RUNNING_GAMES_CHANGE` so Discord's own client sends the real authenticated heartbeats in the background every 30s.

---

### Method 2: Desktop Pseudo-Application Engine (Windows Native)
If you prefer running a simulated desktop application that Discord detects natively without touching the console:

```bash
python discord_quest_simulator.py --mode pseudo
```
- Creates a dedicated folder for each game.
- Automatically registers the application in Windows Registry under `HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall` with the verified game publisher and metadata.
- Launches a lightweight GUI window (`pythonw.exe`) with the exact game title and process name (`endfield.exe`, `wwm.exe`, etc.).
- Discord's native `identifyGame` returns `result: 0` (success), recognizing the game natively just like Genshin Impact!
- When you press `Ctrl + C`, all registry entries and processes are cleanly removed.

---

## 📋 View Live Quests

To see all your active enrolled quests and their real-time progress:
```bash
python discord_quest_simulator.py --mode quests --token YOUR_TOKEN
```

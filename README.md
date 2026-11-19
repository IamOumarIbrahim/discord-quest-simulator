<div align="center">

# 🎮 Discord Quest Runner

**Finish Discord Quests and collect your Orbs without playing the game or watching the video.**

Pick the game. Press Start. Do something else.

[Install](#-install-takes-1-minute) · [Which tool do I need?](#-which-tool-do-i-need) · [Questions](#-questions-people-ask) · [Something broke](#-something-broke)

</div>

---

## ✨ What is this?

Discord Quests give you **Orbs** and rewards for things like *"play this game for 15 minutes"* or *"watch this trailer"*. This app does the waiting for you, on **Windows and Linux**.

It comes with two simple tools:

| | Tool | For quests that say... | What it does |
|---|---|---|---|
| 🕹️ | **Discord Quest Runner** | *"Play [game] for 15 minutes"* | Search for the game, click it, press **Start**. Discord thinks the game is running and counts your time. |
| 🎬 | **Discord Video Quests** | *"Watch this video"* | Press one button. It finishes the video quests for you. |

---

## 📥 Install (takes 1 minute)

You need **Python 3** on your computer. If you don't have it, the installer tells you where to get it.

### 🪟 Windows
1. Press the **Windows key**, type **PowerShell**, and open it.
2. Paste this line and press **Enter**:
   ```powershell
   irm https://raw.githubusercontent.com/IamOumarIbrahim/discord-quest-simulator/main/install.ps1 | iex
   ```
3. Open the **Start menu**. You'll find **Discord Quest Runner** and **Discord Video Quests**.

### 🐧 Linux
1. Open **Terminal**.
2. Paste this line and press **Enter**:
   ```bash
   curl -fsSL https://raw.githubusercontent.com/IamOumarIbrahim/discord-quest-simulator/main/install.sh | bash
   ```
3. Open your app menu. You'll find **Discord Quest Runner** and **Discord Video Quests**.

> If it says `tkinter is missing`, install it with the command it shows you, then run the line again.

---

## 🧭 Which tool do I need?

Look at your quest on Discord's **Quests** page:

- It says **"Play ... for 15 minutes"** → use **🕹️ Discord Quest Runner**
- It says **"Watch the video"** or **"Trailer Quest"** → use **🎬 Discord Video Quests**

---

## 🕹️ Using Discord Quest Runner (play-a-game quests)

1. In Discord, open **Quests** and click **Accept Quest** on the quest you want.
2. Open **Discord Quest Runner**.
3. **Type the name of the game** in the search bar. The list shrinks as you type. Games with a current quest have a ⭐.
4. **Double-click** a game to add it to your *Selected* list. You can add several.
5. Press **▶ Start**. Small windows appear. That's normal, leave them open.
6. Wait about **15 minutes**, then claim your reward in Discord.
7. Press **■ Stop all** (or just close the app) when you're done.

Your selected games are remembered for next time.

## 🎬 Using Discord Video Quests (watch-the-video quests)

1. Make sure you're **logged in to Discord** and have **accepted** the video quest.
2. Open **Discord Video Quests**.
3. It will **restart Discord by itself**. That's expected, so save anything you were typing first.
4. Watch the progress counting up in the window. When it says **DONE**, go to Discord and click **Claim Reward**.

It takes a few minutes. It can't go faster than Discord allows, which depends on how long ago you accepted the quest.

---

## ❓ Questions people ask

**Is it safe?**
It never asks for your password and never reads your Discord token. Everything stays on your computer. **But** using tools like this goes against Discord's rules, so there is a small chance of a warning or a ban on your account. Use it at your own risk, ideally not on an account you can't afford to lose.

**Do I need to install the games?**
No. That's the whole point.

**I clicked Start but the quest isn't moving.**
Make sure you pressed **Accept Quest** in Discord first, keep the small windows open, and give it a couple of minutes. Quests move in steps, not second by second.

**Some quests aren't in the list.**
A few quests (for example Firefox's *play* quest and Audible's Exoplanet) aren't tied to a game program, so the Quest Runner can't do them. Trailer and video quests, including GTA VI and NBA 2K27, are handled by **Discord Video Quests**.

**Why did Discord restart?**
Discord Video Quests has to start Discord in a special mode to work. Restart Discord normally afterwards (just close and reopen it) to switch that off.

**Does it work on Mac?**
The Video Quests tool should. The Quest Runner is built for Windows and Linux.

---

## 🛠️ Something broke?

| What you see | Try this |
|---|---|
| `python3 is required` / Python not found | Install Python 3 from [python.org](https://www.python.org/downloads/) (on Windows tick **tcl/tk** during install), then run the install line again. |
| `Discord has not loaded your quests yet` | Wait for Discord to fully load, open the **Quests** tab once, then run the tool again. |
| Video quest says **NOT COMPLETED** | You probably accepted it only a moment ago. Wait 2 minutes and run it again. |
| The game list is empty | Check your internet. The list is downloaded from Discord the first time. |

## 🗑️ Uninstall

- **Windows:** `& ([scriptblock]::Create((irm https://raw.githubusercontent.com/IamOumarIbrahim/discord-quest-simulator/main/install.ps1))) -Uninstall`
- **Linux:** `curl -fsSL https://raw.githubusercontent.com/IamOumarIbrahim/discord-quest-simulator/main/install.sh | bash -s -- --uninstall`

---

<details>
<summary><b>For developers</b></summary>

- `quest_runner.py` lists every game in Discord's public detectable-games list. For each selected game it runs a small window from a copy of the Python binary named like the game's executable (on Windows it also adds a temporary `HKCU` Uninstall entry), which is what Discord's native scanner looks for.
- `video_quest.py` talks to Discord's own HTTP client through the local debug port (`--remote-debugging-port=9222`) and reports video progress inside the server's allowed window.
- `discord_console_completer.js` and `discord_quest_simulator.py` are the original Windows tools.
- Reverse-engineering notes: [docs/TECHNICAL.md](docs/TECHNICAL.md).

</details>

<div align="center">

Made for fun. Not affiliated with Discord. See [LICENSE](LICENSE).

</div>

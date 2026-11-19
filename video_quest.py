#!/usr/bin/env python3
"""
Discord video-quest completer ("Watch the trailer" quests), Linux + Windows + macOS.

Instead of watching the video, this reports watch progress to Discord's own quest
endpoint from inside the Discord desktop app (so it uses your real session; no token
is read or copied). It runs the code via Discord's Chrome DevTools port.

1. Easiest: add --launch and the script restarts Discord for you. Or start it yourself
   with the debug port (close Discord completely first):
     Linux:    discord --remote-debugging-port=9222
     Windows:  %LOCALAPPDATA%\\Discord\\Update.exe --processStart Discord.exe --process-start-args "--remote-debugging-port=9222"
     macOS:    open -a Discord --args --remote-debugging-port=9222
2. python3 video_quest.py --list          show video quests and your progress
   python3 video_quest.py                 complete every unfinished video quest
   python3 video_quest.py --name exterm   only quests whose name contains "exterm"
3. Click "Claim Reward" in Discord when it finishes.

Pure standard library. The debug port only listens on localhost; close that Discord
instance (restart it normally) when done.
"""
import argparse, base64, json, os, shutil, socket, struct, subprocess, sys, time, urllib.request

PAYLOAD = r"""
(async (opts) => {
  const log = (...a) => console.log("[vq]", ...a);
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const wp = webpackChunkdiscord_app.push([[Symbol()], {}, (r) => r]);
  webpackChunkdiscord_app.pop();
  const find = (pred) => {
    for (const m of Object.values(wp.c)) {
      const e = m?.exports; if (!e) continue;
      for (const c of [e, e.default, e.A, e.Ay, e.h, e.Bo, e.Z, e.ZP]) {
        try { if (c && pred(c)) return c; } catch (_) {}
      }
    }
    return null;
  };
  // Several modules expose getQuest; the real store is the one actually holding quests.
  const count = (x) => (x.quests instanceof Map ? x.quests.size : Object.keys(x.quests || {}).length);
  const findQuests = () => find((x) => (x?.getQuest || x?.__proto__?.getQuest) && x.quests && count(x) > 0);
  let Quests = findQuests();
  for (let i = 0; !Quests && i < 60; i++) { await sleep(1000); Quests = findQuests(); }  // fresh start: data still loading
  // The real HTTP client has get/post/put/patch + del (and is not a store or superagent).
  const api = find((x) => ["get", "post", "put", "patch"].every((k) => typeof x?.[k] === "function")
    && typeof x.del === "function" && !x.getQuest && !x.Request);
  if (!Quests || !api) throw new Error("Discord has not loaded your quests yet. Log in, open the Quests tab once, then run this again.");

  const VIDEO = ["WATCH_VIDEO", "WATCH_VIDEO_ON_MOBILE"];
  let all = Quests.quests instanceof Map ? [...Quests.quests.values()] : Object.values(Quests.quests || {});
  const info = (q) => {
    const cfg = q.config || {};
    const tc = cfg.taskConfigV2 || cfg.task_config_v2 || cfg.taskConfig || cfg.task_config || {};
    const tasks = tc.tasks || {};
    const task = Object.keys(tasks).find((t) => VIDEO.includes(t));
    const us = q.userStatus || q.user_status || {};
    return {
      id: q.id, task, target: task ? tasks[task].target : null,
      name: cfg.messages?.questName || cfg.messages?.quest_name || cfg.id,
      done: task ? (us.progress?.[task]?.value || 0) : 0,
      enrolledAt: us.enrolledAt || us.enrolled_at || null,
      completed: !!(us.completedAt || us.completed_at),
    };
  };
  let rows = all.map(info).filter((r) => r.task);
  if (opts.name) rows = rows.filter((r) => String(r.name).toLowerCase().includes(opts.name.toLowerCase()));
  if (opts.list) return rows;

  // Without --name, skip mobile-only quests (they are meant for the phone app).
  const todo = rows.filter((r) => !r.completed && (opts.name || r.task === "WATCH_VIDEO"));
  if (!todo.length) { log("No unfinished video quests found."); return rows; }

  for (const r of todo) {
    log(`>> ${r.name}: ${r.done}/${r.target}s`);
    let enrolledAt = r.enrolledAt ? new Date(r.enrolledAt).getTime() : null;
    if (!enrolledAt) {
      log("   enrolling...");
      const res = await api.post({ url: `/quests/${r.id}/enroll`, body: { location: 0 } });
      enrolledAt = new Date(res.body?.enrolled_at || Date.now()).getTime();
    }
    // The server rejects timestamps far ahead of (time since enrolment): stay inside that window.
    const speed = 7, maxFuture = 10;
    let done = r.done, completed = false;
    while (done < r.target && !completed) {
      const allowed = Math.floor((Date.now() - enrolledAt) / 1000) + maxFuture;
      if (allowed - done >= speed) {
        const ts = Math.min(r.target, done + speed);
        const res = await api.post({ url: `/quests/${r.id}/video-progress`, body: { timestamp: ts + Math.random() } });
        completed = res.body?.completed_at != null;
        done = ts;
        log(`   ${done}/${r.target}s`);
      } else {
        await sleep(1000);
      }
    }
    if (!completed) {
      const res = await api.post({ url: `/quests/${r.id}/video-progress`, body: { timestamp: r.target } });
      completed = res.body?.completed_at != null;
    }
    // Trust the server, not our own counter.
    const chk = await api.get({ url: "/quests/@me" });
    const sv = (chk.body?.quests || []).find((q) => q.id === r.id);
    const ok = !!sv?.user_status?.completed_at;
    log(ok ? `DONE: ${r.name}. Click "Claim Reward" in Discord.`
           : `NOT COMPLETED by server: ${r.name} (server progress ${JSON.stringify(sv?.user_status?.progress)})`);
  }
  return "finished";
})(%OPTS%)
"""


class WS:
    """Minimal RFC 6455 client (text frames only), enough for the DevTools protocol."""
    def __init__(self, host, port, path):
        self.s = socket.create_connection((host, port), timeout=30)
        key = base64.b64encode(os.urandom(16)).decode()
        # No Origin header: Chromium rejects unexpected origins on DevTools sockets.
        self.s.sendall((f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\nUpgrade: websocket\r\n"
                        f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = self.s.recv(4096)
            if not chunk:
                raise ConnectionError("handshake failed")
            buf += chunk
        if b" 101 " not in buf.split(b"\r\n")[0]:
            raise ConnectionError(buf.split(b"\r\n")[0].decode(errors="replace"))
        self.extra = buf.split(b"\r\n\r\n", 1)[1]
        self.s.settimeout(None)

    def _read(self, n):
        while len(self.extra) < n:
            chunk = self.s.recv(65536)
            if not chunk:
                raise ConnectionError("socket closed")
            self.extra += chunk
        out, self.extra = self.extra[:n], self.extra[n:]
        return out

    def send(self, text):
        data = text.encode()
        hdr = bytearray([0x81])
        n = len(data)
        if n < 126: hdr.append(0x80 | n)
        elif n < 65536: hdr += bytes([0x80 | 126]) + struct.pack(">H", n)
        else: hdr += bytes([0x80 | 127]) + struct.pack(">Q", n)
        mask = os.urandom(4)
        self.s.sendall(bytes(hdr) + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def recv(self):
        msg = b""
        while True:
            b1, b2 = self._read(2)
            op, n = b1 & 0x0F, b2 & 0x7F
            if n == 126: n = struct.unpack(">H", self._read(2))[0]
            elif n == 127: n = struct.unpack(">Q", self._read(8))[0]
            payload = self._read(n)
            if op == 0x8: raise ConnectionError("closed by Discord")
            if op == 0x9:  # ping -> pong
                self.s.sendall(bytes([0x8A, 0x80]) + b"\0\0\0\0"); continue
            msg += payload
            if b1 & 0x80:
                return msg.decode(errors="replace")


def port_open(port):
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=2)
        return True
    except Exception:
        return False


def launch_discord(port):
    """Restart Discord with the debug port switched on (this closes Discord first)."""
    flag = f"--remote-debugging-port={port}"
    print("Restarting Discord so it can be controlled by this tool...")
    quiet = dict(stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if os.name == "nt":
        subprocess.run(["taskkill", "/IM", "Discord.exe", "/F"], **quiet)
        time.sleep(2)
        upd = os.path.expandvars(r"%LOCALAPPDATA%\Discord\Update.exe")
        subprocess.Popen([upd, "--processStart", "Discord.exe", "--process-start-args", flag], **quiet)
    elif sys.platform == "darwin":
        subprocess.run(["pkill", "-x", "Discord"], **quiet)
        time.sleep(2)
        subprocess.Popen(["open", "-a", "Discord", "--args", flag], **quiet)
    else:
        exe = shutil.which("discord") or shutil.which("Discord")
        if not exe:
            sys.exit("Couldn't find the Discord program. Start it yourself with: discord " + flag)
        subprocess.run(["pkill", "-x", "Discord"], **quiet)
        time.sleep(2)
        subprocess.Popen([exe, flag], start_new_session=True, **quiet)
    for _ in range(90):
        if port_open(port):
            print("Discord is back. Waiting for it to finish loading...")
            time.sleep(8)
            return
        time.sleep(1)
    sys.exit("Discord did not come back in time. Open it manually and try again.")


def main():
    ap = argparse.ArgumentParser(description="Auto-complete Discord 'watch the video' quests")
    ap.add_argument("--port", type=int, default=9222)
    ap.add_argument("--list", action="store_true", help="list video quests and exit")
    ap.add_argument("--name", help="only quests whose name contains this text")
    ap.add_argument("--launch", action="store_true",
                    help="restart Discord with the needed setting if it isn't already (closes Discord first)")
    ap.add_argument("--pause", action="store_true", help="wait for Enter at the end (for double-click use)")
    a = ap.parse_args()
    if a.pause:
        import atexit
        atexit.register(lambda: input("\nPress Enter to close..."))
    if a.launch and not port_open(a.port):
        launch_discord(a.port)

    try:
        targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{a.port}/json", timeout=5))
    except Exception:
        sys.exit(f"Can't reach Discord's debug port {a.port}.\nFully quit Discord, then start it with:\n"
                 f"  Linux:   discord --remote-debugging-port={a.port}\n"
                 f"  Windows: %LOCALAPPDATA%\\Discord\\Update.exe --processStart Discord.exe "
                 f"--process-start-args \"--remote-debugging-port={a.port}\"\n"
                 f"  macOS:   open -a Discord --args --remote-debugging-port={a.port}")
    pages = [t for t in targets if t.get("type") == "page" and "discord.com" in t.get("url", "")] \
        or [t for t in targets if t.get("type") == "page"]
    if not pages:
        sys.exit("No Discord page found. Wait for Discord to finish loading and retry.")
    ws = WS("127.0.0.1", a.port, "/" + pages[0]["webSocketDebuggerUrl"].split("/", 3)[3])

    mid = [0]
    def call(method, params=None):
        mid[0] += 1
        ws.send(json.dumps({"id": mid[0], "method": method, "params": params or {}}))
        return mid[0]

    call("Runtime.enable")
    t0 = time.time() * 1000  # DevTools replays old console output on attach; ignore it
    opts = json.dumps({"list": a.list, "name": a.name or ""})
    want = call("Runtime.evaluate", {"expression": PAYLOAD.replace("%OPTS%", opts),
                                     "awaitPromise": True, "returnByValue": True, "userGesture": True})
    while True:
        m = json.loads(ws.recv())
        if m.get("method") == "Runtime.consoleAPICalled":
            args = [x.get("value", x.get("description")) for x in m["params"]["args"]]
            if args and args[0] == "[vq]" and m["params"].get("timestamp", t0) >= t0:
                print(*args[1:], flush=True)
        elif m.get("id") == want:
            res = m["result"]
            if "exceptionDetails" in res:
                d = res["exceptionDetails"]
                sys.exit("Error: " + (d.get("exception", {}).get("description") or d.get("text", "unknown")))
            val = res["result"].get("value")
            if a.list:
                if not val: print("No video quests found.")
                for r in val or []:
                    state = "completed" if r["completed"] else f"{r['done']}/{r['target']}s"
                    print(f"- {r['name']}  [{r['task']}]  {state}")
            return


if __name__ == "__main__":
    main()

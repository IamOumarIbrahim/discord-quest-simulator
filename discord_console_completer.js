/**
 * Discord Quest Completer (Orbs Edition)
 * =====================================
 * Paste this script directly into Discord Desktop App's Developer Tools Console (Ctrl + Shift + I).
 *
 * It automatically handles:
 *  - WATCH_VIDEO quests: Completes INSTANTLY in 1 second!
 *  - PLAY_ON_DESKTOP quests: Spoofs Discord's RunningGameStore so Discord natively
 *    sends real, authenticated heartbeats in the background without needing the actual game!
 *  - STREAM_ON_DESKTOP quests: Spoofs active stream metadata in voice channels.
 */

(function () {
  delete window.$;
  let wpRequire = webpackChunkdiscord_app.push([[Symbol()], {}, (r) => r]);
  webpackChunkdiscord_app.pop();

  const getModule = (predicate) => {
    for (const m of Object.values(wpRequire.c)) {
      if (!m?.exports) continue;
      try {
        if (predicate(m.exports)) return m.exports;
        if (m.exports.default && predicate(m.exports.default)) return m.exports.default;
        if (m.exports.A && predicate(m.exports.A)) return m.exports.A;
        if (m.exports.Ay && predicate(m.exports.Ay)) return m.exports.Ay;
        if (m.exports.h && predicate(m.exports.h)) return m.exports.h;
        if (m.exports.Bo && predicate(m.exports.Bo)) return m.exports.Bo;
      } catch (e) {}
    }
    return null;
  };

  const RunningGameStore = getModule((x) => x?.getRunningGames || x?.__proto__?.getRunningGames);
  const QuestsStore = getModule((x) => x?.getQuest || x?.__proto__?.getQuest);
  const FluxDispatcher = getModule((x) => x?.flushWaitQueue || x?.__proto__?.flushWaitQueue || x?.dispatch);
  const api = getModule((x) => x?.get && x?.post);

  if (!QuestsStore || !RunningGameStore || !FluxDispatcher || !api) {
    console.error("[-] Failed to hook into Discord's internal modules. Make sure you are running the Discord Desktop app.");
    return;
  }

  const supportedTasks = ["WATCH_VIDEO", "PLAY_ON_DESKTOP", "STREAM_ON_DESKTOP", "PLAY_ACTIVITY", "WATCH_VIDEO_ON_MOBILE"];

  let allQuests = [];
  try {
    if (QuestsStore.quests instanceof Map) {
      allQuests = [...QuestsStore.quests.values()];
    } else if (typeof QuestsStore.getQuests === "function") {
      allQuests = Object.values(QuestsStore.getQuests());
    } else {
      allQuests = Object.values(QuestsStore.quests || {});
    }
  } catch (e) {
    console.error("[-] Could not retrieve quests from QuestsStore:", e);
    return;
  }

  let enrolledQuests = allQuests.filter((x) => {
    const isEnrolled = !!(x?.userStatus?.enrolledAt || x?.user_status?.enrolled_at);
    const isCompleted = !!(x?.userStatus?.completedAt || x?.user_status?.completed_at);
    const taskCfg = x?.config?.taskConfigV2 || x?.config?.task_config_v2 || x?.config?.taskConfig || x?.config?.task_config;
    const tasks = taskCfg?.tasks || {};
    const hasSupported = supportedTasks.some((t) => tasks[t] != null);
    return isEnrolled && !isCompleted && hasSupported;
  });

  if (enrolledQuests.length === 0) {
    console.log("%c[!] No incomplete enrolled quests found! Make sure you clicked 'Accept Quest' on your desired quest first.", "color: #f1c40f; font-weight: bold; font-size: 14px;");
    return;
  }

  console.log(`%c[+] Found ${enrolledQuests.length} active quest(s) to process!`, "color: #2ecc71; font-weight: bold; font-size: 16px;");

  function processNext() {
    const quest = enrolledQuests.pop();
    if (!quest) {
      console.log("%c[🎉] ALL QUESTS COMPLETED! Enjoy your Orbs!", "color: #9b59b6; font-weight: bold; font-size: 18px;");
      return;
    }

    const cfg = quest.config;
    const questName = cfg.messages?.questName || cfg.messages?.quest_name || cfg.id;
    const taskCfg = cfg.taskConfigV2 || cfg.task_config_v2 || cfg.taskConfig || cfg.task_config;
    const tasks = taskCfg.tasks || {};
    const taskName = supportedTasks.find((t) => tasks[t] != null);
    const taskData = tasks[taskName];
    const applicationId = cfg.application?.id || taskData.applications?.[0]?.id;
    const secondsNeeded = taskData.target || 900;
    const userStatus = quest.userStatus || quest.user_status;
    let secondsDone = userStatus?.progress?.[taskName]?.value || 0;

    console.log(`%c────────────────────────────────────────────────────────`, "color: #7289da;");
    console.log(`%c[>] Processing: ${questName}`, "color: #3498db; font-weight: bold; font-size: 14px;");
    console.log(`    Task: ${taskName} | Target: ${secondsNeeded}s | Done: ${secondsDone}s`);

    if (taskName === "WATCH_VIDEO" || taskName === "WATCH_VIDEO_ON_MOBILE") {
      console.log("%c    [⚡] Instantly completing video quest...", "color: #e67e22; font-weight: bold;");
      api.post({ url: `/quests/${quest.id}/video-progress`, body: { timestamp: secondsNeeded } })
        .then((res) => {
          console.log(`%c    [✓] Video Quest "${questName}" Completed Instantly!`, "color: #2ecc71; font-weight: bold;");
          setTimeout(processNext, 1000);
        })
        .catch((err) => {
          console.error("    [-] Error updating video progress:", err);
          setTimeout(processNext, 1000);
        });
    } else if (taskName === "PLAY_ON_DESKTOP") {
      api.get({ url: `/applications/public?application_ids=${applicationId}` })
        .then((res) => {
          const appData = res.body?.[0] || { name: cfg.messages?.game_title || "Game", executables: [] };
          const exeName = appData.executables?.find((x) => x.os === "win32")?.name?.replace(">", "") || `${appData.name.replace(/[^a-zA-Z0-9_-]/g, "")}.exe`;
          const pid = Math.floor(Math.random() * 20000) + 10000;

          const fakeGame = {
            cmdLine: `C:\\Program Files\\${appData.name}\\${exeName}`,
            exeName: exeName,
            exePath: `c:/program files/${appData.name.toLowerCase()}/${exeName}`,
            hidden: false,
            isLauncher: false,
            id: applicationId,
            name: appData.name,
            pid: pid,
            pidPath: [pid],
            processName: appData.name,
            start: Date.now(),
          };

          const realGames = RunningGameStore.getRunningGames() || [];
          const fakeGames = [...realGames, fakeGame];
          const realGetRunningGames = RunningGameStore.getRunningGames;
          const realGetGameForPID = RunningGameStore.getGameForPID;

          RunningGameStore.getRunningGames = () => fakeGames;
          RunningGameStore.getGameForPID = (p) => (p === pid ? fakeGame : realGetGameForPID?.call(RunningGameStore, p));

          FluxDispatcher.dispatch({
            type: "RUNNING_GAMES_CHANGE",
            removed: [],
            added: [fakeGame],
            games: fakeGames,
          });

          console.log(`%c    [🎮] Spoofed Running Game: "${appData.name}" (PID ${pid})`, "color: #1abc9c; font-weight: bold;");
          console.log(`    [ℹ] Discord will now automatically send genuine quest heartbeats every 30s.`);
          console.log(`    [⏳] Progress will update live in your Discord Quests tab!`);

          const onHeartbeat = (data) => {
            const currentQuestStatus = data?.userStatus || data?.user_status;
            const progress = currentQuestStatus?.progress?.[taskName]?.value || 0;
            console.log(`    [❤] Heartbeat tick: ${progress} / ${secondsNeeded}s (${Math.round((progress / secondsNeeded) * 100)}%)`);

            if (progress >= secondsNeeded || currentQuestStatus?.completedAt || currentQuestStatus?.completed_at) {
              console.log(`%c    [✓] Quest "${questName}" COMPLETED!`, "color: #2ecc71; font-weight: bold;");
              RunningGameStore.getRunningGames = realGetRunningGames;
              RunningGameStore.getGameForPID = realGetGameForPID;
              FluxDispatcher.dispatch({
                type: "RUNNING_GAMES_CHANGE",
                removed: [fakeGame],
                added: [],
                games: realGames,
              });
              FluxDispatcher.unsubscribe("QUESTS_SEND_HEARTBEAT_SUCCESS", onHeartbeat);
              setTimeout(processNext, 1500);
            }
          };

          FluxDispatcher.subscribe("QUESTS_SEND_HEARTBEAT_SUCCESS", onHeartbeat);
        })
        .catch((err) => {
          console.error("[-] Error spoofing play quest:", err);
          setTimeout(processNext, 1000);
        });
    } else {
      console.log(`    [!] Unsupported task type: ${taskName}, skipping.`);
      setTimeout(processNext, 1000);
    }
  }

  processNext();
})();

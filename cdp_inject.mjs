// Injects discord_console_completer.js into Discord's renderer via CDP.
// Usage: node cdp_inject.mjs [port] [scriptPath]
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const port = process.argv[2] || '9222';
const script = process.argv[3] || join(dirname(fileURLToPath(import.meta.url)), 'discord_console_completer.js');
const code = readFileSync(script, 'utf8');

const targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json();
const page = targets.find(t => t.type === 'page' && /discord\.com\/(app|channels|login)/.test(t.url))
          || targets.find(t => t.type === 'page');
if (!page) { console.error('No page target found:', targets); process.exit(1); }
console.log('Target:', page.title, page.url);

const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });

let id = 0;
const pending = new Map();
ws.onmessage = (ev) => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
  else if (m.method === 'Runtime.consoleAPICalled') {
    console.log('[discord]', ...m.params.args.map(a => a.value ?? a.description));
  }
};
const send = (method, params = {}) => new Promise(res => {
  const i = ++id; pending.set(i, res); ws.send(JSON.stringify({ id: i, method, params }));
});

await send('Runtime.enable');
const r = await send('Runtime.evaluate', { expression: code, awaitPromise: true, userGesture: true });
if (r.result?.exceptionDetails) console.error('Exception:', JSON.stringify(r.result.exceptionDetails, null, 2));
else console.log('Injected OK. Streaming Discord console output (Ctrl+C to stop)...');

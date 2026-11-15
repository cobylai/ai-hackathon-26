"""Plain chat window: python -m reason.web [--port 8765] [--today YYYY-MM-DD]

One local page served by the standard library; nothing is loaded from the internet,
so it opens with Wi-Fi off. It calls the same answer() as the typed chat loop.
Single-threaded on purpose: the web route drives one Playwright browser, which must
stay on one thread.

    GET  /        the page
    GET  /status  {"online": bool, "items": int}
    POST /ask     {"question": str} -> {"text", "route", "sources", "seconds"}
"""
from __future__ import annotations

import argparse
import json
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

from bank import store

from .answer import answer as _answer, online as _online

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Muse</title>
<style>
  :root { color-scheme: light; }
  body { margin: 0; font: 16px/1.45 -apple-system, BlinkMacSystemFont, "Helvetica Neue", Arial, sans-serif;
         background: #fff; color: #111; display: flex; flex-direction: column; height: 100vh; }
  header { display: flex; justify-content: space-between; align-items: center;
           padding: 10px 16px; border-bottom: 1px solid #ddd; }
  header h1 { font-size: 18px; margin: 0; }
  #status { font-size: 13px; color: #666; }
  #log { flex: 1; overflow-y: auto; padding: 16px; }
  .msg { max-width: 75%; margin: 0 0 12px; padding: 8px 12px; border-radius: 10px; white-space: pre-wrap; }
  .you { margin-left: auto; background: #e8eefc; }
  .muse { margin-right: auto; background: #f2f2f2; }
  .src { display: block; margin-top: 4px; font-size: 13px; color: #777; }
  .meta { display: block; margin-top: 2px; font-size: 12px; color: #999; }
  form { display: flex; gap: 8px; padding: 12px 16px; border-top: 1px solid #ddd; }
  input { flex: 1; font: inherit; padding: 8px 10px; border: 1px solid #bbb; border-radius: 6px; }
  button { font: inherit; padding: 8px 14px; border: 1px solid #888; border-radius: 6px; background: #fff; }
  button:disabled { color: #aaa; border-color: #ddd; }
</style></head>
<body>
<header><h1>Muse</h1><span id="status">checking…</span></header>
<div id="log"></div>
<form id="f">
  <input id="q" autocomplete="off" placeholder="Ask a question" autofocus>
  <button type="submit" id="send">Send</button>
  <button type="button" id="talk" disabled title="Voice is not available yet">Hold to talk</button>
</form>
<script>
const log = document.getElementById('log'), q = document.getElementById('q'),
      send = document.getElementById('send'), statusEl = document.getElementById('status');

function add(cls, text) {
  const d = document.createElement('div'); d.className = 'msg ' + cls;
  if (cls === 'muse') {
    for (const line of text.split('\\n')) {
      const s = document.createElement('span');
      if (line.startsWith('Source:')) { s.className = 'src'; }
      s.textContent = line; d.appendChild(s);
      if (!s.className) d.appendChild(document.createTextNode('\\n'));
    }
  } else { d.textContent = text; }
  log.appendChild(d); log.scrollTop = log.scrollHeight; return d;
}

async function refresh() {
  try {
    const r = await (await fetch('/status')).json();
    statusEl.textContent = (r.online ? 'online' : 'offline') + ' · ' + r.items + ' items in bank';
  } catch (e) { statusEl.textContent = 'status unavailable'; }
}

document.getElementById('f').addEventListener('submit', async (ev) => {
  ev.preventDefault();
  const question = q.value.trim(); if (!question) return;
  add('you', question); q.value = ''; send.disabled = true;
  const wait = add('muse', 'Thinking…');
  try {
    const r = await (await fetch('/ask', {method: 'POST', headers: {'Content-Type': 'application/json'},
                                         body: JSON.stringify({question})})).json();
    wait.remove();
    const d = add('muse', r.text);
    const m = document.createElement('span'); m.className = 'meta';
    m.textContent = r.route + ', ' + r.seconds.toFixed(1) + 's'; d.appendChild(m);
  } catch (e) { wait.textContent = 'Error: ' + e; }
  send.disabled = false; q.focus(); refresh();
});
refresh();
</script>
</body></html>
"""


def make_handler(today=None, answer_fn=None, online_fn=None, count_fn=None):
    answer_fn = answer_fn or _answer
    online_fn = online_fn or _online
    count_fn = count_fn or (lambda: len(store.all_entries()))

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code, body, ctype):
            data = body.encode() if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _json(self, obj, code=200):
            self._send(code, json.dumps(obj), "application/json")

        def do_GET(self):
            if self.path == "/":
                self._send(200, PAGE, "text/html; charset=utf-8")
            elif self.path == "/status":
                self._json({"online": online_fn(), "items": count_fn()})
            else:
                self._send(404, "not found", "text/plain")

        def do_POST(self):
            if self.path != "/ask":
                return self._send(404, "not found", "text/plain")
            try:
                n = int(self.headers.get("Content-Length") or 0)
                question = str(json.loads(self.rfile.read(n) or b"{}").get("question") or "")
                a = answer_fn(question, today=today)
                self._json({"text": a.text, "route": a.route, "sources": a.sources,
                            "seconds": a.seconds})
            except Exception as e:  # show it in the window; keep serving
                self._json({"text": f"Error: {type(e).__name__}: {e}", "route": "error",
                            "sources": [], "seconds": 0.0})

        def log_message(self, fmt, *args):  # quiet
            pass

    return Handler


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m reason.web")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--today", help="pretend today is this date (YYYY-MM-DD)")
    ap.add_argument("--no-open", action="store_true", help="don't open a browser tab")
    args = ap.parse_args(argv)
    srv = HTTPServer(("127.0.0.1", args.port), make_handler(today=args.today))
    url = f"http://localhost:{args.port}/"
    print(f"Muse window at {url}  (Ctrl-C to stop)", flush=True)
    if not args.no_open:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

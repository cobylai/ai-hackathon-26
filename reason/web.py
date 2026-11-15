"""Plain chat window: python -m reason.web [--port 8765] [--today YYYY-MM-DD]

One local page served by the standard library; nothing is loaded from the internet,
so it opens with Wi-Fi off. It calls the same answer() as the typed chat loop.
Hold to talk: POST /listen/start, then POST /listen/stop -> {"text"} (or {"error"}).
Single-threaded on purpose: the web route drives one Playwright browser, which must
stay on one thread.

    GET  /        the page
    GET  /status  {"online": bool, "items": int, "voice": bool, "voice_why": str | None}
    GET  /bank    [{"date", "sender", "subject", "summary", "ask", "deadlines", "folder", "id"}], newest first
    POST /ask     {"question": str, "speak": bool} -> {"text", "route", "sources", "seconds", "pending"}
                  speak: read the answer aloud with the Mac's `say` (the Speak switch in the bar)
                  pending: an action is held for a yes; the page shows Yes / Cancel
                  choices: [[label, word]] when a discovery question is held; the page shows
                  those buttons instead (Yes / No / Skip / Stop), each reply as a new turn
                  suggestions: [{"id", "line", "button", "kind"}], at most 2 (playbooks/suggest.md)
                  draft: {"id", "to", "to_name", "subject", "body", "used", "kind"} for the draft box
    POST /speak/stop  stop reading aloud (the Speak switch turned off)
    POST /suggest/<id>          a Suggested button: {"draft"} for a reply, {"text"} after opening a page,
                                adding a calendar event or a reminder (reason/computer.py)
    POST /suggest/<id>/dismiss  it won't be suggested again in this chat
    POST /draft/<id>/write      {"gist"} -> {"draft"} with a new body (Bonsai)
    POST /draft/open            {"to", "subject", "body"} -> {"text"}: `open mailto:...`, never sends
The Discover button in the bar sends "discover" to /ask (playbooks/discover.md).
Follow-ups ("and tomorrow?", "the first one", "open it") lean on the last answer of the
open chat: one current Session (reason/session.py) for the server, since the window serves
one person and the Mac app shows the same page. Each chat is saved after every answer
(reason/chats.py, outside the repo); launch starts a new one.

    GET  /chats             {"current": id, "chats": [{"id", "title", "started", "updated", "turns"}]}, newest first
    GET  /chats/<id>        the saved chat: {"id", "title", "started", "turns": [{"question", "route", "text", "sources", ...}]}
    POST /chats/new         start a new chat -> {"current": id}
    POST /chats/<id>/open   make it the current chat (follow-ups go on from it) -> the saved chat
    POST /chats/<id>/delete delete its file; deleting the open chat starts a new one -> {"ok", "current"}
Any /ask and /listen/start stop the spoken answer first, so talking cuts it off.
"""
from __future__ import annotations

import argparse
import json
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

import discover
from bank import store

from . import act, compose, suggest
from .answer import answer as _answer, online as _online
from . import chats
from .session import Session
from .speak import Speaker
from .speech import HoldToTalk, start_voice

DISCOVER_CHOICES = [["Yes", "yes"], ["No", "no"], ["Skip", "skip"], ["Stop", "stop"]]

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Flux</title>
<style>
  :root {
    color-scheme: light dark;
    --bg: #ffffff; --side: #f5f5f7; --text: #1d1d1f; --text2: #6e6e73; --text3: #8e8e93;
    --line: rgba(0,0,0,.09); --field: #ffffff; --fieldline: rgba(0,0,0,.16); --hover: rgba(0,0,0,.045);
    --accent: #007aff; --red: #d70015; --green: #34c759;
  }
  @media (prefers-color-scheme: dark) { :root {
    --bg: #1e1e1e; --side: #262626; --text: #f2f2f7; --text2: #a1a1a6; --text3: #7c7c80;
    --line: rgba(255,255,255,.09); --field: #2b2b2b; --fieldline: rgba(255,255,255,.14); --hover: rgba(255,255,255,.06);
    --accent: #0a84ff; --red: #ff6961; --green: #30d158;
  } }
  * { box-sizing: border-box; }
  html, body { height: 100%; }
  body { margin: 0; background: var(--bg); color: var(--text); display: flex; overflow: hidden;
         font: 14px/1.5 -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", sans-serif;
         -webkit-font-smoothing: antialiased; }
  button { font: inherit; color: inherit; background: none; border: 0; padding: 0; cursor: default; }
  button:focus-visible { outline: 2px solid var(--accent); outline-offset: 1px; }
  svg { display: block; flex: none; }
  [hidden] { display: none !important; }

  /* saved chats: a column on the left (worker 18's list; hooks #chats #newchat .chday .chat[data-id].on .chtitle .chdel) */
  #chats { width: 232px; flex: none; background: var(--side); border-right: 1px solid var(--line); display: none;
           flex-direction: column; min-height: 0; }
  body.chatsopen #chats { display: flex; }
  #chats .head { display: flex; align-items: center; gap: 4px; min-height: 38px; flex: none; padding: 0 8px 0 16px;
                 font-size: 13px; font-weight: 600; border-bottom: 1px solid var(--line); }
  #chats .head span { flex: 1; }
  #chatlist { flex: 1; overflow-y: auto; padding: 4px 8px 12px; }
  #chatsclose { display: none; height: 22px; padding: 0 10px; font-size: 12px; font-weight: 400; }
  #chats .chday { padding: 12px 8px 4px; font-size: 11px; font-weight: 600; color: var(--text3); }
  #chats .chempty { padding: 12px 8px; font-size: 12px; color: var(--text3); }
  #chats ul { list-style: none; margin: 0; padding: 0; }
  #chats .chat { display: flex; align-items: center; border-radius: 6px; }
  #chats .chat:hover { background: var(--hover); }
  #chats .chat.on { background: color-mix(in srgb, var(--accent) 14%, transparent); }
  #chats .chtitle { flex: 1; min-width: 0; text-align: left; padding: 5px 4px 5px 8px; font-size: 13px;
                    overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  #chats .chdel { flex: none; height: 22px; min-width: 22px; margin-right: 3px; padding: 0 5px; border-radius: 5px;
                  font-size: 14px; line-height: 22px; color: var(--text3); visibility: hidden; }
  #chats .chdel:hover { background: var(--hover); color: var(--text2); }
  #chats .chat:hover .chdel, #chats .chdel.armed, #chats .chdel:focus-visible { visibility: visible; }
  #chats .chdel.armed { font-size: 12px; color: var(--red); }
  /* the bank: a slide-over from the right */
  #side { position: fixed; z-index: 3; top: 0; right: 0; bottom: 0; width: 320px; max-width: 100%; background: var(--side);
          border-left: 1px solid var(--line); box-shadow: -8px 0 24px rgba(0,0,0,.10); display: flex; flex-direction: column;
          transform: translateX(100%); visibility: hidden; transition: transform .2s ease, visibility 0s linear .2s; }
  body.bankopen #side { transform: none; visibility: visible; transition: transform .2s ease; }
  @media (prefers-reduced-motion: reduce) { #side, body.bankopen #side { transition: none; } }
  #side .head { display: flex; align-items: center; justify-content: space-between; min-height: 38px; flex: none;
                padding: 0 12px 0 16px; font-size: 13px; font-weight: 600; border-bottom: 1px solid var(--line); margin-bottom: 6px; }
  #sideclose { height: 22px; padding: 0 10px; font-size: 12px; font-weight: 400; color: var(--text); }
  #sidebtn[aria-pressed="true"], #chatsbtn[aria-pressed="true"] { background: var(--hover); color: var(--text); }
  #groups { flex: 1; overflow-y: auto; padding: 0 8px 12px; }
  .group > button { width: 100%; display: flex; align-items: center; gap: 4px; padding: 6px 8px 4px;
                    font-size: 11px; font-weight: 600; color: var(--text2); text-align: left; }
  .group > button .n { margin-left: auto; font-weight: 400; color: var(--text3); }
  .group > button svg { transition: transform .12s; }
  .group.shut > button svg { transform: rotate(-90deg); }
  .group.shut ul { display: none; }
  .group ul { list-style: none; margin: 0 0 6px; padding: 0; }
  .group li > button { width: 100%; text-align: left; padding: 4px 8px 5px 22px; border-radius: 6px; display: block; }
  .group li > button:hover { background: var(--hover); }
  .group .t { display: block; font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .group .d { display: block; font-size: 11px; color: var(--text3); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .group li.sel > button { background: var(--accent); color: #fff; }
  .group li.sel > button .d { color: rgba(255,255,255,.78); }
  .group .more { padding: 2px 8px 8px 22px; font-size: 12px; color: var(--text2); white-space: pre-wrap; }
  .group .more b { font-weight: 600; color: var(--text); }
  .group .none { padding: 2px 8px 6px 22px; font-size: 12px; color: var(--text3); }

  /* main column */
  main { flex: 1; display: flex; flex-direction: column; min-width: 0; min-height: 0; }
  .bar { display: flex; align-items: center; gap: 10px; height: 38px; padding: 0 12px; border-bottom: 1px solid var(--line); flex: none; }
  .iconbtn { width: 28px; height: 24px; border-radius: 6px; display: grid; place-items: center; color: var(--text2); }
  .iconbtn:hover { background: var(--hover); }
  .bar h1 { margin: 0; font-size: 13px; font-weight: 600; }
  #status { margin-left: auto; font-size: 12px; color: var(--text3); white-space: nowrap; overflow: hidden;
            text-overflow: ellipsis; padding: 2px 6px; border-radius: 6px; }
  #status:hover { background: var(--hover); }
  #status .dot { display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: var(--text3); margin-right: 6px; vertical-align: 1px; }
  #status.on .dot { background: var(--green); }

  #log { flex: 1; overflow-y: auto; padding: 4px 0 24px; }
  .turn, .empty { max-width: 680px; margin: 0 auto; padding: 18px 24px 0; }
  .turn + .turn { border-top: 1px solid var(--line); margin-top: 18px; }
  .q { font-size: 13px; font-weight: 600; color: var(--text2); margin: 0 0 6px; display: flex; gap: 6px; align-items: center; }
  .q svg { color: var(--text3); }
  .a { font-size: 15px; line-height: 1.5; overflow-wrap: anywhere; }
  .a p { margin: 0 0 6px; }
  .a h3 { font-size: 13px; font-weight: 600; margin: 10px 0 4px; }
  .a h3:first-child { margin-top: 0; }
  .a ul { margin: 0 0 6px; padding-left: 18px; }
  .a li { margin: 2px 0; }
  .a .sub { display: block; font-size: 13px; color: var(--text2); }
  table.rows { border-collapse: collapse; width: 100%; font-size: 14px; margin: 2px 0 6px; }
  table.rows td { padding: 5px 12px 5px 0; vertical-align: top; border-bottom: 1px solid var(--line); }
  table.rows tr:last-child td { border-bottom: 0; }
  table.rows td.when { white-space: nowrap; color: var(--text2); font-variant-numeric: tabular-nums; width: 1%; }
  .foot { display: flex; gap: 4px 12px; margin-top: 6px; font-size: 12px; color: var(--text3); flex-wrap: wrap; }
  .foot a { color: var(--text3); text-decoration: none; cursor: pointer; }
  .foot a:hover { color: var(--accent); text-decoration: underline; }
  .working { display: flex; align-items: center; gap: 8px; color: var(--text3); font-size: 14px; }
  .err { color: var(--red); font-size: 14px; }

  .confirm { margin-top: 10px; padding: 8px 8px 8px 12px; border: 1px solid var(--line); border-radius: 8px; display: flex;
             align-items: center; gap: 8px; flex-wrap: wrap; font-size: 13px; }
  .confirm .what { flex: 1 1 220px; color: var(--text); }
  .confirm .done { color: var(--text2); white-space: pre-wrap; }
  .btn { height: 24px; padding: 0 12px; white-space: nowrap; flex: none; border-radius: 6px; font-size: 13px; border: 1px solid var(--fieldline); background: var(--field); }
  .btn:hover { filter: brightness(.97); }
  .btn.primary { background: var(--accent); border-color: var(--accent); color: #fff; }

  /* Suggested next steps and the draft box (brief W; playbooks/suggest.md, compose.md) */
  .sugg { margin-top: 10px; }
  .sugg .lbl { font-size: 11px; font-weight: 600; color: var(--text3); margin: 0 0 4px; }
  .suggest { margin-top: 4px; padding: 5px 5px 5px 12px; border: 1px solid var(--line); border-radius: 8px; display: flex;
             align-items: center; gap: 8px; font-size: 13px; }
  .suggest .what { flex: 1 1 auto; min-width: 0; }
  .suggest .done { color: var(--text2); white-space: pre-wrap; }
  .suggest .x { width: 22px; height: 22px; border-radius: 5px; color: var(--text3); display: grid; place-items: center; font-size: 14px; flex: none; }
  .suggest .x:hover { background: var(--hover); color: var(--text2); }
  .draft { margin-top: 10px; padding: 12px; border: 1px solid var(--line); border-radius: 8px; display: flex;
           flex-direction: column; gap: 8px; font-size: 13px; }
  .draft label { display: flex; align-items: center; gap: 8px; color: var(--text2); }
  .draft label > span { width: 52px; flex: none; }
  .draft input, .draft textarea { flex: 1; min-width: 0; width: 100%; font: inherit; font-size: 13px; color: var(--text);
           background: var(--field); border: 1px solid var(--fieldline); border-radius: 6px; padding: 5px 8px; outline: 0; }
  .draft textarea { resize: vertical; min-height: 9em; line-height: 1.45; }
  .draft input:focus, .draft textarea:focus { border-color: var(--accent); box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 25%, transparent); }
  .draft input::placeholder { color: var(--text3); }
  .draft .row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
  .draft .note { flex: 1 1 160px; font-size: 12px; color: var(--text3); }
  .draft .used { font-size: 12px; color: var(--text3); }
  .draft.closed { padding: 8px 12px; color: var(--text2); }

  .empty { padding-top: 12vh; }
  .empty p { margin: 0 0 12px; color: var(--text2); font-size: 13px; }
  .empty button { display: block; font-size: 15px; padding: 7px 0; border-top: 1px solid var(--line); width: 100%; text-align: left; }
  .empty button:last-child { border-bottom: 1px solid var(--line); }
  .empty button:hover { color: var(--accent); }

  /* input */
  form { flex: none; margin: 0; padding: 10px 16px 12px; border-top: 1px solid var(--line); }
  .field { max-width: 680px; margin: 0 auto; display: flex; align-items: center; gap: 6px; height: 36px; padding: 0 4px 0 12px;
           background: var(--field); border: 1px solid var(--fieldline); border-radius: 8px; }
  .field:focus-within { border-color: var(--accent); box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 25%, transparent); }
  #q { flex: 1; min-width: 0; border: 0; outline: 0; background: none; font: inherit; font-size: 14px; color: var(--text); }
  #q::placeholder { color: var(--text3); }
  .hint { font-size: 11px; color: var(--text3); white-space: nowrap; }
  #send, #talk { height: 28px; min-width: 28px; padding: 0 6px; border-radius: 6px; display: flex; align-items: center;
                 justify-content: center; gap: 6px; color: var(--text2); font-size: 12px; }
  #send:hover, #talk:hover:not(:disabled) { background: var(--hover); }
  #send:disabled, #talk:disabled { color: var(--text3); opacity: .55; }
  #talk.listening { color: var(--red); background: color-mix(in srgb, var(--red) 12%, transparent); opacity: 1; }
  #talk.working { color: var(--text3); opacity: 1; }
  .bars { display: flex; gap: 2px; align-items: center; height: 14px; }
  .bars i { width: 2px; height: 3px; background: currentColor; border-radius: 1px; animation: lvl .9s ease-in-out infinite; }
  .bars i:nth-child(2) { animation-delay: -.3s } .bars i:nth-child(3) { animation-delay: -.6s } .bars i:nth-child(4) { animation-delay: -.15s }
  @keyframes lvl { 0%, 100% { height: 3px } 50% { height: 13px } }
  .spin { width: 12px; height: 12px; border: 1.5px solid currentColor; border-right-color: transparent; border-radius: 50%; animation: r .8s linear infinite; }
  @keyframes r { to { transform: rotate(360deg) } }
  @media (prefers-reduced-motion: reduce) { .bars i, .spin { animation-duration: 3s; } }

  /* roomy windows: the open bank pushes the conversation left instead of covering it */
  @media (min-width: 1000px) { body.bankopen main { margin-right: 320px; } }
  /* compact (the ~640 pt panel): the bank starts hidden and, open, covers the whole panel (Done or Escape closes it).
     The page lets the panel's material show through. */
  @media (max-width: 760px) {
    body { background: transparent; }
    #chats { position: fixed; z-index: 3; inset: 0; width: 100%; border-right: 0; }
    #chatsclose { display: block; }
    body.chatsopen main { visibility: hidden; }
    #side { width: 100%; border-left: 0; box-shadow: none; }
    body.bankopen main { visibility: hidden; }
    .turn, .empty { padding-left: 18px; padding-right: 18px; }
    .hint { display: none; }
  }
  /* very narrow: a table row puts the date above the item instead of squeezing both */
  @media (max-width: 480px) {
    table.rows td { display: block; border: 0; padding: 0; width: auto; }
    table.rows td.when { padding-top: 6px; font-size: 12px; }
    table.rows tr { display: block; border-bottom: 1px solid var(--line); padding-bottom: 6px; }
  }
</style></head>
<body>
<nav id="chats" aria-label="Chats">
  <div class="head"><span>Chats</span>
    <button type="button" class="iconbtn" id="newchat" title="New chat" aria-label="New chat"><svg width="15" height="15" viewBox="0 0 15 15"><path d="M7 2H3.5A1.5 1.5 0 0 0 2 3.5v8A1.5 1.5 0 0 0 3.5 13h8a1.5 1.5 0 0 0 1.5-1.5V8M11.3 1.7l2 2L7.5 9.5H5.5v-2z" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round"/></svg></button>
    <button type="button" class="btn" id="chatsclose" title="Close (Escape)">Done</button></div>
  <div id="chatlist"></div>
</nav>
<main>
  <div class="bar">
    <button class="iconbtn" type="button" id="chatsbtn" title="Show chats" aria-pressed="false"><svg width="16" height="14" viewBox="0 0 16 14"><rect x=".75" y=".75" width="14.5" height="12.5" rx="2.5" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M5.5 1v12" stroke="currentColor" stroke-width="1.3"/></svg></button>
    <h1>Flux</h1>
    <button type="button" class="btn" id="speak" aria-pressed="false" title="Read answers aloud">Speak</button>
    <button type="button" class="btn" id="discover" title="Let Flux ask you a few questions about yourself">Discover</button>
    <button type="button" id="status" title="Show what's in the bank"><span class="dot"></span>Checking…</button>
    <button class="iconbtn" type="button" id="sidebtn" title="Show the bank (⌘B)" aria-pressed="false"><svg width="16" height="14" viewBox="0 0 16 14"><rect x=".75" y=".75" width="14.5" height="12.5" rx="2.5" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M10.5 1v12" stroke="currentColor" stroke-width="1.3"/></svg></button>
  </div>
  <div id="log" aria-live="polite"></div>
  <form id="f">
    <div class="field">
      <input id="q" autocomplete="off" placeholder="Ask about your mail, courses or calendar" autofocus>
      <span class="hint" id="hint" hidden>Hold ⌥ to talk</span>
      <button type="submit" id="send" title="Ask (Return)" aria-label="Ask"><svg width="14" height="14" viewBox="0 0 14 14"><path d="M12.5 2v4.5a2 2 0 0 1-2 2H2.5M5.5 5.5l-3 3 3 3" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg></button>
      <button type="button" id="talk" disabled title="Voice is unavailable" aria-label="Hold to talk"></button>
    </div>
  </form>
</main>
<aside id="side" aria-label="In the bank">
  <div class="head"><span>In the bank</span><button type="button" class="btn" id="sideclose" title="Close (Escape)">Done</button></div>
  <div id="groups"></div>
</aside>
<script>
/* Hooks other code relies on (keep them):
   ids #q #send #talk #status; POST /ask -> r.pending shows Yes / Cancel;
   window.fluxTalk.start() / .stop() and window.fluxFocus() for the Mac app's hotkey panel (docs/window.md). */
const $ = (id) => document.getElementById(id);
const log = $('log'), q = $('q'), send = $('send'), talk = $('talk'), statusEl = $('status'), groupsEl = $('groups');
const NL = String.fromCharCode(10);
const MIC = '<svg width="12" height="16" viewBox="0 0 12 16"><rect x="3.25" y=".75" width="5.5" height="9.5" rx="2.75" fill="none" stroke="currentColor" stroke-width="1.4"/><path d="M1 7.5a5 5 0 0 0 10 0M6 12.5V15" fill="none" stroke="currentColor" stroke-width="1.4"/></svg>';
const CHEV = '<svg width="10" height="10" viewBox="0 0 10 10"><path d="M2 3.5l3 3 3-3" fill="none" stroke="currentColor" stroke-width="1.4"/></svg>';
// From the playbooks' Examples tables (due.md, calendar.md, person.md).
const EXAMPLES = ["What's due tomorrow?", "When is my next meeting?", "What did Felix ask me?"];
const ASK_YES = /^say or type yes/i;
let rows = [], busy = false, recording = false, voiceOk = false, pending = null;

function el(tag, cls, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
function store(k, v) { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) { return null; } }
function bottom() { log.scrollTop = log.scrollHeight; }
function shortDate(iso) {
  const m = /^(\\d{4})-(\\d{2})-(\\d{2})/.exec(iso || ''); if (!m) return iso || '';
  return ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][+m[2] - 1] + ' ' + (+m[3]);
}

/* ---------- empty state ---------- */
function showEmpty() {
  const d = el('div', 'empty'); d.id = 'empty';
  d.appendChild(el('p', '', 'Ask about your mail, coursework, calendar and the people in them. Everything stays on this Mac.'));
  for (const ex of EXAMPLES) { const b = el('button', '', ex); b.type = 'button'; b.onclick = () => ask(ex, false); d.appendChild(b); }
  log.appendChild(d);
}

/* ---------- one question and its answer ---------- */
function newTurn(question, spoken) {
  const e = $('empty'); if (e) e.remove();
  const t = el('section', 'turn'), h = el('div', 'q');
  if (spoken) h.insertAdjacentHTML('beforeend', MIC);
  h.appendChild(el('span', '', question));
  t.appendChild(h);
  const a = el('div', 'a');
  const w = el('div', 'working'); w.appendChild(el('span', 'spin')); w.appendChild(el('span', '', 'Thinking…'));
  a.appendChild(w); t.appendChild(a); log.appendChild(t); bottom();
  return t;
}

// Answer text -> document: "- when  what" lines become a table, other "- " lines a list,
// short lines ending in ":" a heading, indented lines a note under the row above.
function render(box, text) {
  box.textContent = '';
  let table = null, list = null, last = null;
  for (const raw of text.split(NL)) {
    const line = raw.replace(/\\s+$/, '');
    if (!line.trim()) { table = list = last = null; continue; }
    let m;
    if (last && /^\\s{2,}\\S/.test(line)) { last.appendChild(el('span', 'sub', line.trim())); continue; }
    if ((m = /^\\s*[-•] (\\S.*?) {2,}(\\S.*)$/.exec(line))) {
      if (!table) { table = el('table', 'rows'); box.appendChild(table); list = null; }
      const tr = el('tr'); tr.appendChild(el('td', 'when', m[1])); last = el('td', '', m[2]); tr.appendChild(last); table.appendChild(tr);
      continue;
    }
    if (table && (m = /^\\s*[-•] (.+)$/.exec(line))) {  // an undated row in a dated list stays in the table
      const tr = el('tr'); tr.appendChild(el('td', 'when', '')); last = el('td', '', m[1]); tr.appendChild(last); table.appendChild(tr);
      continue;
    }
    if ((m = /^\\s*[-•] (.+)$/.exec(line))) {
      if (!list) { list = el('ul'); box.appendChild(list); table = null; }
      last = el('li', '', m[1]); list.appendChild(last); continue;
    }
    table = list = last = null;
    if (line.endsWith(':') && line.length < 90) box.appendChild(el('h3', '', line.slice(0, -1)));
    else box.appendChild(el('p', '', line));
  }
}

function rowFor(path) {
  const m = /-([0-9a-f]{6,})\\.md$/.exec(path || ''); return m ? rows.find((r) => r.id === m[1]) : null;
}

function foot(t, r, sourceLine) {
  const f = el('div', 'foot');
  const srcs = (r.sources || []).filter(Boolean);
  if (srcs.length && /^https?:/.test(srcs[0])) {
    const a = el('a', '', sourceLine || srcs[0].replace(/^https?:\\/\\/(www\\.)?/, '').split('/')[0]);
    a.href = srcs[0]; a.target = '_blank'; a.rel = 'noopener'; f.appendChild(a);
  } else if (srcs.length) {
    srcs.slice(0, sourceLine ? 1 : 3).forEach((p) => {
      const row = rowFor(p);
      const a = el('a', '', sourceLine || (row ? (row.sender + ', ' + shortDate(row.date)) : 'Open in the bank'));
      a.title = 'Show this in the bank'; a.onclick = () => openEntry(p); f.appendChild(a);
    });
  } else if (sourceLine) { f.appendChild(el('span', '', sourceLine)); }
  if (r.route && r.route !== 'error') f.appendChild(el('span', '', r.route + ' · ' + (r.seconds || 0).toFixed(1) + ' s'));
  if (f.childNodes.length) t.appendChild(f);
}

function confirmRow(t, what) {
  const c = el('div', 'confirm'); c.appendChild(el('span', 'what', what));
  const no = el('button', 'btn', 'Cancel'), yes = el('button', 'btn primary', 'Yes, do it');
  no.type = yes.type = 'button';
  const choose = (word) => { if (busy) return; pending = null; ask(word, false, c); };
  no.onclick = () => choose('no');
  yes.onclick = () => choose('yes');
  c.appendChild(no); c.appendChild(yes); t.appendChild(c);
  pending = { cancel: () => no.click() };
}

// Discovery: one button per answer; the reply (and the next question) is a new turn.
function choiceRow(t, choices) {
  const c = el('div', 'confirm');
  const choose = (word) => { if (busy) return; pending = null; c.remove(); ask(word, false); };
  choices.forEach(([label, word], i) => {
    const b = el('button', i === 0 ? 'btn primary' : 'btn', label); b.type = 'button';
    b.onclick = () => choose(word); c.appendChild(b);
  });
  t.appendChild(c);
  pending = { cancel: () => choose('stop'), row: c };
}

function showAnswer(t, r) {
  const a = t.querySelector('.a');
  let text = r.text || '', sourceLine = '';
  const kept = [];
  for (const line of text.split(NL)) {
    if (line.startsWith('Source:')) sourceLine = line.slice(7).trim();
    else if (r.pending && ASK_YES.test(line.trim())) continue;
    else kept.push(line);
  }
  if (r.route === 'error') { a.textContent = ''; a.appendChild(el('div', 'err', "Something went wrong answering that (" + text.replace(/^Error:\\s*/, '') + "). Try asking again.")); return; }
  if (r.choices) {
    render(a, kept.join(NL));
    choiceRow(t, r.choices);
  } else if (r.pending) {
    const what = (kept.shift() || 'Flux is waiting for a yes.').trim();
    render(a, kept.join(NL)); if (!a.childNodes.length) a.remove();
    confirmRow(t, what);
  } else if (r.draft) {
    render(a, (kept[0] || '').trim());  // the head; the box holds To, Subject and body
    draftBox(t, r.draft, null);
  } else render(a, kept.join(NL));
  foot(t, r, sourceLine);
  if (r.suggestions && r.suggestions.length) suggestRows(t, r.suggestions);
}

// Suggested: at most two rows, one line + one button + a dismiss ×. Nothing runs until a click.
function suggestRows(t, list) {
  const box = el('div', 'sugg'); box.appendChild(el('div', 'lbl', 'Suggested'));
  list.forEach((s, i) => {
    const row = el('div', 'suggest'); row.id = 'suggest-' + i;
    row.appendChild(el('span', 'what', s.line));
    const go = el('button', 'btn', s.button), x = el('button', 'x', '×');
    go.type = x.type = 'button'; x.title = 'Dismiss'; x.setAttribute('aria-label', 'Dismiss');
    go.onclick = async () => {
      if (busy) return;
      row.textContent = ''; const w = el('div', 'working'); w.appendChild(el('span', 'spin'));
      w.appendChild(el('span', '', s.kind === 'open' ? 'Opening…' : (s.kind === 'calendar' || s.kind === 'remind') ? 'Adding…' : 'Writing…')); row.appendChild(w);
      let r; try { r = await postJSON('/suggest/' + s.id, {}); } catch (e) { r = { text: "Couldn't reach Flux." }; }
      if (r.draft) { const d = draftBox(box, r.draft, row); row.remove(); d.querySelector('textarea').focus(); }
      else { row.textContent = ''; row.appendChild(el('span', 'what done', (r.text || '').trim())); }
    };
    x.onclick = async () => {
      row.remove(); if (!box.querySelector('.suggest')) box.remove();
      try { await post('/suggest/' + s.id + '/dismiss'); } catch (e) {}
      q.focus();
    };
    row.appendChild(go); row.appendChild(x); box.appendChild(row);
  });
  t.appendChild(box);
}

// The draft box: editable To / Subject / body; Open in Mail hands a mailto: to macOS. Nothing is sent.
function draftBox(parent, d, before) {
  const c = el('div', 'draft');
  const field = (label, value, ph) => { const l = el('label'); l.appendChild(el('span', '', label));
    const i = el('input'); i.value = value || ''; if (ph) i.placeholder = ph; l.appendChild(i); c.appendChild(l); return i; };
  const to = field('To', d.to, d.to ? '' : 'No address stored' + (d.to_name ? ' for ' + d.to_name : ''));
  const subj = field('Subject', d.subject);
  let gist = null;
  if (d.kind !== 'new') {
    const l = el('label'); l.appendChild(el('span', '', 'Say'));
    gist = el('input'); gist.placeholder = 'What should it say? (optional)'; l.appendChild(gist);
    const w = el('button', 'btn', 'Write'); w.type = 'button'; l.appendChild(w); c.appendChild(l);
    const write = async () => {
      if (!gist.value.trim()) { gist.focus(); return; }
      w.disabled = true; note.textContent = 'Writing…';
      let r; try { r = await postJSON('/draft/' + d.id + '/write', { gist: gist.value }); } catch (e) { r = {}; }
      w.disabled = false;
      if (r.draft) { body.value = r.draft.body; d.id = r.draft.id; note.textContent = 'Nothing is sent.'; }
      else note.textContent = (r.text || "Couldn't write that.").trim();
    };
    w.onclick = write; gist.addEventListener('keydown', (ev) => { if (ev.key === 'Enter') { ev.preventDefault(); write(); } });
  }
  const body = el('textarea'); body.value = d.body || ''; body.rows = 8; c.appendChild(body);
  if (d.used && d.used.length) c.appendChild(el('div', 'used', 'Used: ' + d.used.join('; ')));
  const row = el('div', 'row'), note = el('span', 'note', 'Nothing is sent.');
  const discard = el('button', 'btn', 'Discard'), open = el('button', 'btn primary', 'Open in Mail');
  discard.type = open.type = 'button';
  discard.onclick = () => { c.textContent = ''; c.className = 'draft closed'; c.appendChild(el('span', '', 'Discarded.')); q.focus(); };
  open.onclick = async () => {
    open.disabled = true;
    let r; try { r = await postJSON('/draft/open', { to: to.value, subject: subj.value, body: body.value }); }
    catch (e) { r = { text: "Couldn't reach Flux." }; }
    open.disabled = false; note.textContent = (r.text || '').trim();
  };
  row.appendChild(note); row.appendChild(discard); row.appendChild(open); c.appendChild(row);
  parent.insertBefore(c, before && before.parentNode === parent ? before : null);
  return c;
}

// into: a confirm row; the yes / no and its result stay in that row instead of a new turn.
async function ask(question, spoken, into) {
  question = (question || '').trim(); if (!question || busy) return;
  if (pending && pending.row) { pending.row.remove(); pending = null; }  // a typed or spoken discovery reply
  if (pending && !/^(yes|no)$/i.test(question)) { pending = null; }  // any other question drops the held action
  busy = true; send.disabled = true;
  if (sideShown() && !window.matchMedia('(min-width: 1000px)').matches) toggleSide(false, true);  // the bank would cover the answer
  let t;
  if (into) {
    into.textContent = ''; const w = el('div', 'working'); w.appendChild(el('span', 'spin'));
    w.appendChild(el('span', '', question === 'yes' ? 'Doing it…' : 'Cancelling…')); into.appendChild(w);
  } else t = newTurn(question, spoken);
  try {
    const res = await fetch('/ask', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question, speak: speakOn }) });
    const r = await res.json();
    if (into) { into.textContent = ''; into.appendChild(el('span', 'what' + (r.route === 'error' ? ' err' : ' done'), (r.text || '').trim())); }
    else showAnswer(t, r);
  } catch (e) {
    const msg = "Couldn't reach Flux. Check that it's still running, then ask again.";
    if (into) { into.textContent = ''; into.appendChild(el('span', 'what err', msg)); }
    else { const a = t.querySelector('.a'); a.textContent = ''; a.appendChild(el('div', 'err', msg)); }
  }
  busy = false; send.disabled = false; bottom();
  if (!recording) q.focus();
  refresh(); loadBank(); loadChats();
}

$('discover').addEventListener('click', () => ask('discover', false));
// Speak switch: off by default, remembered in this browser. Turning it off stops reading.
let speakOn = store('flux.speak') === '1';
function speakState() { const b = $('speak'); b.setAttribute('aria-pressed', speakOn ? 'true' : 'false'); b.classList.toggle('primary', speakOn); b.title = speakOn ? 'Reading answers aloud (click to stop)' : 'Read answers aloud'; }
$('speak').addEventListener('click', () => { speakOn = !speakOn; store('flux.speak', speakOn ? '1' : '0'); speakState(); if (!speakOn) post('/speak/stop').catch(() => {}); q.focus(); });
speakState();
$('f').addEventListener('submit', (ev) => { ev.preventDefault(); const v = q.value; q.value = ''; ask(v, false); });

/* ---------- status line ---------- */
async function refresh() {
  try {
    const r = await (await fetch('/status')).json();
    statusEl.className = r.online ? 'on' : '';
    statusEl.innerHTML = '<span class="dot"></span>';
    statusEl.appendChild(document.createTextNode((r.online ? 'Online' : 'Offline') + ' · ' + r.items + (r.items === 1 ? ' item' : ' items') + ' in the bank'));
    voiceOk = !!r.voice;
    if (!recording && !talk.classList.contains('working')) {
      talk.disabled = !voiceOk;
      talk.title = voiceOk ? 'Hold to talk' : 'Voice is unavailable: ' + (r.voice_why || 'not set up');
    }
    $('hint').hidden = !voiceOk;
  } catch (e) { statusEl.className = ''; statusEl.textContent = "Can't reach Flux"; }
}

/* ---------- talk: idle, listening, working ---------- */
function talkState(s) {
  talk.className = s === 'idle' ? '' : s;
  if (s === 'listening') { talk.innerHTML = '<span class="bars"><i></i><i></i><i></i><i></i></span>Listening'; talk.title = 'Release to ask, Escape to cancel'; }
  else if (s === 'working') { talk.innerHTML = '<span class="spin"></span>'; talk.title = 'Writing down what you said'; }
  else { talk.innerHTML = MIC; talk.title = voiceOk ? 'Hold to talk' : talk.title; }
  q.placeholder = s === 'listening' ? 'Listening — release to ask' : s === 'working' ? 'Writing down what you said…' : 'Ask about your mail, courses or calendar';
}
async function post(path) { return (await fetch(path, { method: 'POST' })).json(); }
async function postJSON(path, obj) { return (await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(obj) })).json(); }
function voiceError(msg) {
  if (/too short/.test(msg)) msg = "that was too short to hear. Hold the mic while you speak, or click it once, speak, then click again";
  const t = el('section', 'turn'); t.appendChild(el('div', 'err', "Couldn't listen: " + msg + '. Type your question instead.'));
  const e = $('empty'); if (e) e.remove(); log.appendChild(t); bottom();
}
async function startTalk() {
  if (!voiceOk || recording || busy || talk.classList.contains('working')) return;
  recording = true; talkState('listening'); q.blur();
  let r; try { r = await post('/listen/start'); } catch (e) { r = { error: "Flux isn't reachable" }; }
  if (r.error) { recording = false; talkState('idle'); voiceError(r.error); q.focus(); }
}
async function stopTalk(cancel) {
  if (!recording) return;
  recording = false; latched = false; talkState('working'); talk.disabled = true;
  let r; try { r = await post('/listen/stop'); } catch (e) { r = { error: "Flux isn't reachable" }; }
  talk.disabled = !voiceOk; talkState('idle'); q.focus();
  if (cancel) return;
  if (r.error) { voiceError(r.error); return; }
  if (r.text && r.text.trim()) ask(r.text.trim(), true);
  else voiceError("nothing was heard");
}
// Hold to talk, or click once to start and click again to send. A press shorter than 0.4 s is a click:
// it keeps listening (a release that fast would record almost nothing and fail with "recording too short").
let pressAt = 0, latched = false;
talk.addEventListener('pointerdown', (ev) => {
  if (talk.disabled) return; ev.preventDefault();
  if (latched) { latched = false; stopTalk(false); return; }
  talk.setPointerCapture(ev.pointerId); pressAt = Date.now(); startTalk();
});
talk.addEventListener('pointerup', () => {
  if (!recording || !pressAt) return;
  if (Date.now() - pressAt < 400) { latched = true; talk.title = 'Click again to ask, Escape to cancel'; q.placeholder = 'Listening — click the mic again to ask'; }
  else stopTalk(false);
  pressAt = 0;
});
talk.addEventListener('pointercancel', () => { if (!latched) stopTalk(false); pressAt = 0; });
window.fluxTalk = { start: startTalk, stop: () => stopTalk(false) };
window.fluxFocus = () => { if (!recording) q.focus(); };

// Hold Option (alone) to talk; Escape cancels listening, then a held action, then closes the bank overlay.
let altTimer = null, altTalk = false;
document.addEventListener('keydown', (ev) => {
  if (ev.key === 'Alt') {
    if (!ev.repeat && voiceOk && !altTimer && !recording) altTimer = setTimeout(() => { altTimer = null; altTalk = true; startTalk(); }, 250);
    return;
  }
  if (altTimer) { clearTimeout(altTimer); altTimer = null; }
  if (ev.key === 'Escape') {
    if (recording) { altTalk = false; stopTalk(true); }
    else if (sideShown()) toggleSide(false);
    else if (!isWide() && chatsShown()) toggleChats(false);
    else if (pending) pending.cancel();
    ev.preventDefault(); return;
  }
  const typing = /^(INPUT|TEXTAREA)$/.test(document.activeElement.tagName);  // the draft box's fields keep their keys
  if (!recording && !typing && ev.key.length === 1 && !ev.metaKey && !ev.ctrlKey) q.focus();
});
document.addEventListener('keyup', (ev) => {
  if (ev.key !== 'Alt') return;
  if (altTimer) { clearTimeout(altTimer); altTimer = null; }
  if (altTalk) { altTalk = false; stopTalk(false); }
});
window.addEventListener('focus', () => window.fluxFocus());
document.addEventListener('pointerup', () => {
  setTimeout(() => { if (!recording && window.getSelection().isCollapsed && !/^(INPUT|TEXTAREA)$/.test(document.activeElement.tagName)) q.focus(); }, 0);
});

/* ---------- the bank sidebar ---------- */
const GROUPS = [
  ['mail', 'Mail', (r) => r.folder === 'person' || r.folder === 'other' || !r.folder],
  ['course', 'Coursework', (r) => r.folder === 'course'],
  ['me', 'Notes about you', (r) => r.folder === 'me'],
];
function isWide() { return window.matchMedia('(min-width: 761px)').matches; }
// Show / hide the bank (a slide-over on the right): the bar's bank button, Done, Escape or ⌘B.
// Remembered per viewer in wide windows; the compact panel always starts with it hidden.
// keep: closing it for an answer doesn't change the remembered choice.
function sideShown() { return document.body.classList.contains('bankopen'); }
function syncSideBtn() {
  const on = sideShown(), b = $('sidebtn');
  b.setAttribute('aria-pressed', on ? 'true' : 'false'); b.title = (on ? 'Hide' : 'Show') + ' the bank (⌘B)';
}
function toggleSide(show, keep) {
  const on = show ?? !sideShown();
  document.body.classList.toggle('bankopen', on);
  if (isWide() && !keep) store('flux.bank', on ? '1' : '0');
  syncSideBtn();
  if (!recording) q.focus();
}
if (isWide() && store('flux.bank') === '1') document.body.classList.add('bankopen');
$('sidebtn').onclick = () => toggleSide();
$('sideclose').onclick = () => toggleSide(false);
window.matchMedia('(min-width: 761px)').addEventListener('change', (e) => { if (!e.matches) document.body.classList.remove('bankopen'); syncSideBtn(); });
document.addEventListener('keydown', (ev) => {
  if ((ev.metaKey || ev.ctrlKey) && !ev.altKey && !ev.shiftKey && ev.key.toLowerCase() === 'b') { ev.preventDefault(); toggleSide(); }
});
syncSideBtn();
statusEl.onclick = () => toggleSide(true);

function group(key, title, items, fill) {
  const g = el('div', 'group'); g.dataset.key = key;
  if (store('flux.shut.' + key) === '1') g.classList.add('shut');
  const h = el('button'); h.type = 'button'; h.innerHTML = CHEV; h.appendChild(el('span', '', title)); h.appendChild(el('span', 'n', String(items.length)));
  h.onclick = () => { g.classList.toggle('shut'); store('flux.shut.' + key, g.classList.contains('shut') ? '1' : '0'); };
  const ul = el('ul'); g.appendChild(h); g.appendChild(ul);
  if (!items.length) ul.appendChild(el('li', 'none', 'Nothing yet'));
  items.forEach((it) => ul.appendChild(fill(it)));
  return g;
}
function entryItem(r) {
  const li = el('li'); li.dataset.id = r.id || '';
  const b = el('button'); b.type = 'button';
  b.appendChild(el('span', 't', r.subject)); b.appendChild(el('span', 'd', r.sender + ' · ' + shortDate(r.date)));
  b.onclick = () => select(li, r); li.appendChild(b); return li;
}
function select(li, r) {
  const was = li.classList.contains('sel');
  groupsEl.querySelectorAll('li.sel').forEach((x) => { x.classList.remove('sel'); const m = x.querySelector('.more'); if (m) m.remove(); });
  if (was) return;
  li.classList.add('sel');
  const m = el('div', 'more');
  if (r.summary) m.appendChild(el('div', '', r.summary));
  if (r.ask) { const d = el('div'); d.appendChild(el('b', '', 'Ask: ')); d.appendChild(document.createTextNode(r.ask)); m.appendChild(d); }
  if (r.deadlines) { const d = el('div'); d.appendChild(el('b', '', 'Due: ')); d.appendChild(document.createTextNode(r.deadlines)); m.appendChild(d); }
  li.appendChild(m);
}
function openEntry(path) {
  const row = rowFor(path); if (!row) return;
  toggleSide(true);
  const li = groupsEl.querySelector('li[data-id="' + row.id + '"]'); if (!li) return;
  const g = li.closest('.group'); g.classList.remove('shut');
  if (!li.classList.contains('sel')) select(li, row);
  li.scrollIntoView({ block: 'nearest' });
}
async function loadBank() {
  try { rows = await (await fetch('/bank')).json(); }
  catch (e) { groupsEl.textContent = ''; groupsEl.appendChild(el('div', 'none', "Couldn't load the bank. Check that Flux is running.")); return; }
  const sel = groupsEl.querySelector('li.sel'), selId = sel && sel.dataset.id;
  groupsEl.textContent = '';
  for (const [key, title, test] of GROUPS) groupsEl.appendChild(group(key, title, rows.filter(test), entryItem));
  const counts = new Map();
  rows.filter((r) => r.folder !== 'me' && r.folder !== 'course' && r.sender && r.sender !== 'unknown')
      .forEach((r) => counts.set(r.sender, (counts.get(r.sender) || 0) + 1));
  const people = [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  groupsEl.appendChild(group('people', 'People', people, ([name, n]) => {
    const li = el('li'), b = el('button'); b.type = 'button'; b.title = 'Ask who ' + name + ' is';
    b.appendChild(el('span', 't', name)); b.appendChild(el('span', 'd', n + (n === 1 ? ' email' : ' emails')));
    b.onclick = () => ask('Who is ' + name + '?', false); li.appendChild(b); return li;
  }));
  if (selId) { const li = groupsEl.querySelector('li[data-id="' + selId + '"]'); const r = rows.find((x) => x.id === selId); if (li && r) select(li, r); }
}

talkState('idle');
/* ---------- saved chats (left column, #chats) ----------
   Hooks for the layout: #newchat, .chat[data-id] (.on = the open chat), .chtitle, .chdel;
   window.fluxChats.refresh() / .open(id) / .new() / .remove(id). A reopened chat shows its
   answers as they were given; nothing is asked again. Delete takes two clicks. */
const chatsEl = $('chatlist');
let currentChat = null;
function dayLabel(iso) {
  const d = new Date((iso || '').slice(0, 10) + 'T12:00:00'); if (isNaN(d)) return '';
  const today = new Date(); today.setHours(12, 0, 0, 0);
  const n = Math.round((today - d) / 864e5);
  if (n === 0) return 'Today'; if (n === 1) return 'Yesterday';
  return d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
}
function drawChats(list) {
  chatsEl.textContent = '';
  if (!list.length) chatsEl.appendChild(el('div', 'chempty', 'Your chats will show here.'));
  let day = null, ul = null;
  for (const c of list) {
    const d = dayLabel(c.updated);
    if (d !== day) { day = d; chatsEl.appendChild(el('div', 'chday', d)); ul = el('ul'); chatsEl.appendChild(ul); }
    const li = el('li', 'chat' + (c.id === currentChat ? ' on' : '')); li.dataset.id = c.id;
    const b = el('button', 'chtitle', c.title); b.type = 'button'; b.title = c.title; b.onclick = () => openChat(c.id);
    const x = el('button', 'chdel', '×'); x.type = 'button'; x.title = 'Delete this chat'; x.setAttribute('aria-label', 'Delete chat: ' + c.title);
    x.onclick = () => removeChat(c.id, x);
    li.appendChild(b); li.appendChild(x); ul.appendChild(li);
  }
}
async function loadChats() {
  try { const r = await (await fetch('/chats')).json(); currentChat = r.current; drawChats(r.chats || []); } catch (e) { /* the list waits for the next answer */ }
}
function clearLog() { log.textContent = ''; pending = null; }
async function newChat() {
  if (busy) return;
  try { await post('/chats/new'); } catch (e) { return; }
  clearLog(); showEmpty(); loadChats(); chatsDone(); q.focus();
}
async function openChat(id) {
  if (busy) return;
  let r; try { r = await post('/chats/' + id + '/open'); } catch (e) { return; }
  if (!r || r.error) { loadChats(); return; }
  clearLog();
  for (const t of r.turns || []) showAnswer(newTurn(t.question, false), { text: t.text, route: t.route, sources: t.sources, seconds: t.seconds || 0 });
  if (!(r.turns || []).length) showEmpty();
  bottom(); loadChats(); chatsDone(); q.focus();
}
async function removeChat(id, btn) {
  if (btn && !btn.classList.contains('armed')) {  // first click asks; the second deletes
    btn.classList.add('armed'); btn.textContent = 'Delete';
    setTimeout(() => { btn.classList.remove('armed'); btn.textContent = '×'; }, 3000);
    return;
  }
  try { await post('/chats/' + id + '/delete'); } catch (e) { return; }
  if (id === currentChat) { clearLog(); showEmpty(); }
  loadChats();
}
$('newchat').onclick = () => newChat();
// Show / hide the chats column: the bar's left button or Done / Escape in the panel. Wide windows show it by
// default and remember the choice; the compact panel starts with it hidden and shows it over the whole panel.
function chatsShown() { return document.body.classList.contains('chatsopen'); }
function toggleChats(show) {
  const on = show ?? !chatsShown();
  document.body.classList.toggle('chatsopen', on);
  if (isWide()) store('flux.chats', on ? '1' : '0');
  const b = $('chatsbtn'); b.setAttribute('aria-pressed', on ? 'true' : 'false'); b.title = on ? 'Hide chats' : 'Show chats';
  if (!recording) q.focus();
}
function chatsDone() { if (!isWide() && chatsShown()) toggleChats(false); }  // compact: back to the conversation
$('chatsbtn').onclick = () => toggleChats();
$('chatsclose').onclick = () => toggleChats(false);
if (isWide() && store('flux.chats') !== '0') document.body.classList.add('chatsopen');
toggleChats(chatsShown());
window.matchMedia('(min-width: 761px)').addEventListener('change', (e) => { if (!e.matches) toggleChats(false); });
window.fluxChats = { refresh: loadChats, open: openChat, new: newChat, remove: (id) => removeChat(id, null) };

showEmpty();
refresh(); loadBank(); loadChats();
q.focus();
</script>
</body></html>
"""


def bank_rows(entries) -> list[dict]:
    """What the bank list shows, newest first. Read-only."""
    rows = []
    for e in entries:
        dls = "; ".join(f"{d.get('phrase')}" + (f" ({d['date']}{' ' + d['time'] if d.get('time') else ''})"
                                                if d.get("date") else "")
                        for d in e.get("deadlines") or [])
        rows.append({"date": e.get("sent_date") or "", "subject": e.get("subject") or "(no subject)",
                     "sender": (e.get("sender_name") or e.get("sender_address")
                                or (e.get("source") if e.get("kind") == "page" else "") or "unknown"),
                     "summary": e.get("body") or "", "ask": e.get("ask") or "", "deadlines": dls,
                     "folder": e.get("folder") or "", "id": e.get("id") or ""})
    rows.sort(key=lambda r: r["date"], reverse=True)
    return rows


def make_handler(today=None, answer_fn=None, online_fn=None, count_fn=None, talk=None, voice_why=None,
                 entries_fn=None, speaker=None, session=None, chats_root=None, mail_fn=None, open_fn=None,
                 draft_fn=None, run_fn=None):
    entries_fn = entries_fn or store.all_entries
    cur = {"s": session or Session()}  # the open chat (single user); swapped on new / open
    answer_fn = answer_fn or (lambda q, today=None: _answer(q, today=today, session=cur["s"]))

    def _switch(s):
        act.reset()       # a held yes/no belongs to the chat it was asked in
        discover.reset()
        compose.reset()   # so does a held "Who is this to?"
        cur["s"] = s
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
                self._json({"online": online_fn(), "items": count_fn(), "voice": talk is not None,
                            "voice_why": voice_why})
            elif self.path == "/bank":
                self._json(bank_rows(entries_fn()))
            elif self.path == "/chats":
                self._json({"current": cur["s"].id, "chats": chats.listing(chats_root)})
            elif self.path.startswith("/chats/"):
                try:
                    self._json(chats.read(self.path.split("/")[2], chats_root))
                except (ValueError, OSError):
                    self._json({"error": "no such chat"}, 404)
            else:
                self._send(404, "not found", "text/plain")

        def do_POST(self):
            if speaker is not None and self.path in ("/ask", "/listen/start", "/speak/stop"):
                speaker.stop()  # talking, a new question or the switch cuts off the spoken answer
            if self.path == "/speak/stop":
                return self._json({"ok": True})
            if self.path.startswith("/chats/"):
                return self._chats_post(self.path.split("/")[2:])
            if self.path.startswith(("/suggest/", "/draft/")):
                return self._draft_post(self.path.split("/")[1:])
            if self.path in ("/listen/start", "/listen/stop"):
                if talk is None:
                    return self._json({"error": f"voice is unavailable ({voice_why})"})
                if self.path.endswith("start"):
                    talk.start()
                    return self._json({"ok": True})
                return self._json(talk.stop())
            if self.path != "/ask":
                return self._send(404, "not found", "text/plain")
            try:
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"{}")
                question = str(body.get("question") or "")
                a = answer_fn(question, today=today)
                try:
                    chats.save(cur["s"], chats_root)
                except OSError as e:  # the answer still stands; say it once in the server log
                    print(f"Couldn't save the chat: {e}", flush=True)
                if speaker is not None and body.get("speak") and a.route != "error":
                    speaker.speak(a.text)
                held = a.route == "discover" and discover.waiting()
                self._json({"text": a.text, "route": a.route, "sources": a.sources,
                            "seconds": a.seconds, "pending": held or (a.route == "act" and act.waiting()),
                            "choices": DISCOVER_CHOICES if held else None,
                            "suggestions": suggest.public(a.suggestions), "draft": a.draft})
            except Exception as e:  # show it in the window; keep serving
                self._json({"text": f"Error: {type(e).__name__}: {e}", "route": "error",
                            "sources": [], "seconds": 0.0})

        def _body(self) -> dict:
            n = int(self.headers.get("Content-Length") or 0)
            try:
                got = json.loads(self.rfile.read(n) or b"{}")
            except ValueError:
                return {}
            return got if isinstance(got, dict) else {}

        def _draft_post(self, parts):
            """Suggested buttons and the draft box (playbooks/suggest.md, compose.md). Never sends."""
            from .playbook import say
            body = self._body()
            try:
                if parts[0] == "suggest" and len(parts) == 3 and parts[2] == "dismiss":
                    return self._json({"ok": suggest.dismiss(parts[1]), "text": say("suggest", "dismissed")})
                if parts[0] == "suggest" and len(parts) == 2:
                    s = suggest.take(parts[1])
                    if s is None:
                        return self._json({"text": say("suggest", "gone")})
                    if s["kind"] == "open":
                        return self._json({"text": (open_fn or act.open_page)(s["url"])})
                    if s["kind"] in ("calendar", "remind"):
                        return self._json({"text": (run_fn or suggest.run)(s)})
                    return self._json({"draft": (draft_fn or compose.reply_draft)(s["entry"])})
                if parts == ["draft", "open"]:
                    return self._json({"text": compose.open_in_mail(
                        str(body.get("to") or ""), str(body.get("subject") or ""), str(body.get("body") or ""),
                        runner=mail_fn)})
                if parts[0] == "draft" and len(parts) == 3 and parts[2] == "write":
                    d = compose.rewrite(parts[1], str(body.get("gist") or ""))
                    return self._json({"draft": d} if d else {"text": say("suggest", "gone")})
            except Exception as e:  # model down, calendar slow, ...: say it in the box
                return self._json({"text": say("compose", "cannot_write", why=f"{type(e).__name__}: {e}")})
            return self._send(404, "not found", "text/plain")

        def _chats_post(self, parts):
            if parts == ["new"]:
                _switch(Session())
                return self._json({"current": cur["s"].id})
            if len(parts) != 2 or parts[1] not in ("open", "delete"):
                return self._send(404, "not found", "text/plain")
            chat_id, verb = parts
            try:
                if verb == "open":
                    _switch(chats.load(chat_id, chats_root))
                    return self._json(chats.read(chat_id, chats_root))
                chats.delete(chat_id, chats_root)
            except (ValueError, OSError):
                return self._json({"error": "no such chat"}, 404)
            if chat_id == cur["s"].id:
                _switch(Session())
            return self._json({"ok": True, "current": cur["s"].id})

        def log_message(self, fmt, *args):  # quiet
            pass

    return Handler


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m reason.web")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--today", help="pretend today is this date (YYYY-MM-DD)")
    ap.add_argument("--no-open", action="store_true", help="don't open a browser tab")
    ap.add_argument("--no-voice", action="store_true", help="typing only")
    args = ap.parse_args(argv)
    voice, why = (None, "turned off") if args.no_voice else start_voice()
    print("Voice: ready" if voice else f"Voice is unavailable ({why}); typing only.", flush=True)
    srv = HTTPServer(("127.0.0.1", args.port), make_handler(
        today=args.today, talk=HoldToTalk(voice) if voice else None, voice_why=why, speaker=Speaker()))
    url = f"http://localhost:{args.port}/"
    print(f"Flux window at {url}  (Ctrl-C to stop)", flush=True)
    if not args.no_open:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if voice:
            voice.close()
    return 0


if __name__ == "__main__":
    import applecal
    applecal.warm()  # read Apple Calendar in the background (docs/calendar.md, Speed)
    raise SystemExit(main())

"""Plain chat window: python -m reason.web [--port 8765] [--today YYYY-MM-DD]

One local page served by the standard library; nothing is loaded from the internet,
so it opens with Wi-Fi off. It calls the same answer() as the typed chat loop.
Hold to talk: POST /listen/start, then POST /listen/stop -> {"text"} (or {"error"}).
Single-threaded on purpose: the web route drives one Playwright browser, which must
stay on one thread.

    GET  /        the page
    GET  /status  {"online": bool, "items": int, "voice": bool, "voice_why": str | None}
    GET  /bank    [{"date", "sender", "subject", "summary", "ask", "deadlines", "folder", "id"}], newest first
    POST /ask     {"question": str} -> {"text", "route", "sources", "seconds", "pending"}
                  pending: an action is held for a yes; the page shows Yes / Cancel
                  choices: [[label, word]] when a discovery question is held; the page shows
                  those buttons instead (Yes / No / Skip / Stop), each reply as a new turn
The Discover button in the bar sends "discover" to /ask (playbooks/discover.md).
"""
from __future__ import annotations

import argparse
import json
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

import discover
from bank import store

from . import act
from .answer import answer as _answer, online as _online
from .speech import HoldToTalk, start_voice

DISCOVER_CHOICES = [["Yes", "yes"], ["No", "no"], ["Skip", "skip"], ["Stop", "stop"]]

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Muse</title>
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

  /* sidebar: the bank, grouped */
  #side { width: 240px; flex: none; background: var(--side); border-right: 1px solid var(--line);
          display: flex; flex-direction: column; min-height: 0; }
  #side .head { padding: 13px 16px 6px; font-size: 11px; font-weight: 600; color: var(--text3); }
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
  .btn { height: 24px; padding: 0 12px; border-radius: 6px; font-size: 13px; border: 1px solid var(--fieldline); background: var(--field); }
  .btn:hover { filter: brightness(.97); }
  .btn.primary { background: var(--accent); border-color: var(--accent); color: #fff; }

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

  /* wide: sidebar beside the conversation, hidden on request */
  @media (min-width: 761px) { body.noside #side { display: none; } }
  /* compact (the ~640 pt panel): sidebar slides over, page lets the panel's material show through */
  @media (max-width: 760px) {
    body { background: transparent; }
    #side { position: fixed; z-index: 2; top: 38px; bottom: 0; left: 0; box-shadow: 0 0 0 1px var(--line), 0 8px 24px rgba(0,0,0,.12); }
    body:not(.sideopen) #side { display: none; }
    .turn, .empty { padding-left: 18px; padding-right: 18px; }
    .hint { display: none; }
  }
</style></head>
<body>
<aside id="side" aria-label="In the bank">
  <div class="head">In the bank</div>
  <div id="groups"></div>
</aside>
<main>
  <div class="bar">
    <button class="iconbtn" type="button" id="sidebtn" title="Show or hide the bank"><svg width="16" height="14" viewBox="0 0 16 14"><rect x=".75" y=".75" width="14.5" height="12.5" rx="2.5" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M5.5 1v12" stroke="currentColor" stroke-width="1.3"/></svg></button>
    <h1>Muse</h1>
    <button type="button" class="btn" id="discover" title="Let Muse ask you a few questions about yourself">Discover</button>
    <button type="button" id="status" title="Show what's in the bank"><span class="dot"></span>Checking…</button>
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
<script>
/* Hooks other code relies on (keep them):
   ids #q #send #talk #status; POST /ask -> r.pending shows Yes / Cancel;
   window.museTalk.start() / .stop() and window.museFocus() for the Mac app's hotkey panel (docs/window.md). */
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
    const what = (kept.shift() || 'Muse is waiting for a yes.').trim();
    render(a, kept.join(NL)); if (!a.childNodes.length) a.remove();
    confirmRow(t, what);
  } else render(a, kept.join(NL));
  foot(t, r, sourceLine);
}

// into: a confirm row; the yes / no and its result stay in that row instead of a new turn.
async function ask(question, spoken, into) {
  question = (question || '').trim(); if (!question || busy) return;
  if (pending && pending.row) { pending.row.remove(); pending = null; }  // a typed or spoken discovery reply
  if (pending && !/^(yes|no)$/i.test(question)) { pending = null; }  // any other question drops the held action
  busy = true; send.disabled = true;
  let t;
  if (into) {
    into.textContent = ''; const w = el('div', 'working'); w.appendChild(el('span', 'spin'));
    w.appendChild(el('span', '', question === 'yes' ? 'Doing it…' : 'Cancelling…')); into.appendChild(w);
  } else t = newTurn(question, spoken);
  try {
    const res = await fetch('/ask', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question }) });
    const r = await res.json();
    if (into) { into.textContent = ''; into.appendChild(el('span', 'what' + (r.route === 'error' ? ' err' : ' done'), (r.text || '').trim())); }
    else showAnswer(t, r);
  } catch (e) {
    const msg = "Couldn't reach Muse. Check that it's still running, then ask again.";
    if (into) { into.textContent = ''; into.appendChild(el('span', 'what err', msg)); }
    else { const a = t.querySelector('.a'); a.textContent = ''; a.appendChild(el('div', 'err', msg)); }
  }
  busy = false; send.disabled = false; bottom();
  if (!recording) q.focus();
  refresh(); loadBank();
}

$('discover').addEventListener('click', () => ask('discover', false));
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
  } catch (e) { statusEl.className = ''; statusEl.textContent = "Can't reach Muse"; }
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
function voiceError(msg) {
  const t = el('section', 'turn'); t.appendChild(el('div', 'err', "Couldn't listen: " + msg + '. Type your question instead.'));
  const e = $('empty'); if (e) e.remove(); log.appendChild(t); bottom();
}
async function startTalk() {
  if (!voiceOk || recording || busy || talk.classList.contains('working')) return;
  recording = true; talkState('listening'); q.blur();
  let r; try { r = await post('/listen/start'); } catch (e) { r = { error: "Muse isn't reachable" }; }
  if (r.error) { recording = false; talkState('idle'); voiceError(r.error); q.focus(); }
}
async function stopTalk(cancel) {
  if (!recording) return;
  recording = false; talkState('working'); talk.disabled = true;
  let r; try { r = await post('/listen/stop'); } catch (e) { r = { error: "Muse isn't reachable" }; }
  talk.disabled = !voiceOk; talkState('idle'); q.focus();
  if (cancel) return;
  if (r.error) { voiceError(r.error); return; }
  if (r.text && r.text.trim()) ask(r.text.trim(), true);
  else voiceError("nothing was heard");
}
talk.addEventListener('pointerdown', (ev) => { if (talk.disabled) return; ev.preventDefault(); talk.setPointerCapture(ev.pointerId); startTalk(); });
talk.addEventListener('pointerup', () => stopTalk(false));
talk.addEventListener('pointercancel', () => stopTalk(false));
window.museTalk = { start: startTalk, stop: () => stopTalk(false) };
window.museFocus = () => { if (!recording) q.focus(); };

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
    else if (pending) pending.cancel();
    else if (document.body.classList.contains('sideopen')) document.body.classList.remove('sideopen');
    ev.preventDefault(); return;
  }
  if (!recording && document.activeElement !== q && ev.key.length === 1 && !ev.metaKey && !ev.ctrlKey) q.focus();
});
document.addEventListener('keyup', (ev) => {
  if (ev.key !== 'Alt') return;
  if (altTimer) { clearTimeout(altTimer); altTimer = null; }
  if (altTalk) { altTalk = false; stopTalk(false); }
});
window.addEventListener('focus', () => window.museFocus());
document.addEventListener('pointerup', () => {
  setTimeout(() => { if (!recording && window.getSelection().isCollapsed && document.activeElement.tagName !== 'INPUT') q.focus(); }, 0);
});

/* ---------- the bank sidebar ---------- */
const GROUPS = [
  ['mail', 'Mail', (r) => r.folder === 'person' || r.folder === 'other' || !r.folder],
  ['course', 'Coursework', (r) => r.folder === 'course'],
  ['me', 'Notes about you', (r) => r.folder === 'me'],
];
function isWide() { return window.matchMedia('(min-width: 761px)').matches; }
function toggleSide(show) {
  const b = document.body;
  if (isWide()) { const on = show ?? b.classList.contains('noside'); b.classList.toggle('noside', !on); store('muse.side', on ? '1' : '0'); }
  else b.classList.toggle('sideopen', show ?? !b.classList.contains('sideopen'));
}
if (store('muse.side') === '0') document.body.classList.add('noside');
$('sidebtn').onclick = () => toggleSide();
statusEl.onclick = () => toggleSide(true);

function group(key, title, items, fill) {
  const g = el('div', 'group'); g.dataset.key = key;
  if (store('muse.shut.' + key) === '1') g.classList.add('shut');
  const h = el('button'); h.type = 'button'; h.innerHTML = CHEV; h.appendChild(el('span', '', title)); h.appendChild(el('span', 'n', String(items.length)));
  h.onclick = () => { g.classList.toggle('shut'); store('muse.shut.' + key, g.classList.contains('shut') ? '1' : '0'); };
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
  catch (e) { groupsEl.textContent = ''; groupsEl.appendChild(el('div', 'none', "Couldn't load the bank. Check that Muse is running.")); return; }
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
showEmpty();
refresh(); loadBank();
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
                 entries_fn=None):
    entries_fn = entries_fn or store.all_entries
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
                self._json({"online": online_fn(), "items": count_fn(), "voice": talk is not None,
                            "voice_why": voice_why})
            elif self.path == "/bank":
                self._json(bank_rows(entries_fn()))
            else:
                self._send(404, "not found", "text/plain")

        def do_POST(self):
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
                question = str(json.loads(self.rfile.read(n) or b"{}").get("question") or "")
                a = answer_fn(question, today=today)
                held = a.route == "discover" and discover.waiting()
                self._json({"text": a.text, "route": a.route, "sources": a.sources,
                            "seconds": a.seconds, "pending": held or (a.route == "act" and act.waiting()),
                            "choices": DISCOVER_CHOICES if held else None})
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
    ap.add_argument("--no-voice", action="store_true", help="typing only")
    args = ap.parse_args(argv)
    voice, why = (None, "turned off") if args.no_voice else start_voice()
    print("Voice: ready" if voice else f"Voice is unavailable ({why}); typing only.", flush=True)
    srv = HTTPServer(("127.0.0.1", args.port), make_handler(
        today=args.today, talk=HoldToTalk(voice) if voice else None, voice_why=why))
    url = f"http://localhost:{args.port}/"
    print(f"Muse window at {url}  (Ctrl-C to stop)", flush=True)
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

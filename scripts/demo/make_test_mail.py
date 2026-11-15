"""Many-sender fake mail for testing reason.answer, and a checker that scores it.

    uv run python scripts/demo/make_test_mail.py write OUT_DIR            # N emails + truth.json
    FLUX_BANK_DIR=FRESH uv run python -m bank.load OUT_DIR --kind email
    FLUX_BANK_DIR=FRESH uv run python scripts/demo/make_test_mail.py check OUT_DIR [--offline]

Every name, address and course here is made up (example.edu / example.com). Write
OUT_DIR and FRESH outside the repo. Today defaults to Sat 2026-11-14 (--today YYYY-MM-DD
moves it; sent and due dates are offsets from it), and the seed is
fixed, so runs repeat. check asks person, due and bank questions through
reason.answer and scores each against truth.json (keyword and source checks).

Reuse: build() -> list of dicts, one per email, with key, sender (id), name, first,
address, sent (YYYY-MM-DD), sent_at (YYYY-MM-DDTHH:MM, -0500), subject, body (no header
lines), text (header lines + body), due (YYYY-MM-DD or None), phrase, ask_kw, facts.
The questions and expected answers live in check(); it scores whatever bank
$FLUX_BANK_DIR points at against truth.json in OUT_DIR.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

TODAY = date(2026, 11, 14)  # a Saturday
SEED = 2600

# (first, last, address)
SENDERS = {
    "lena": ("Lena", "Marsh", "lena.marsh@example.edu"),       # several emails
    "omar": ("Omar", "Haddad", "ohaddad@example.edu"),
    "tess": ("Tess", "Okoro", "tess.okoro@example.edu"),
    "rafe": ("Rafe", "Quill", "rquill@example.com"),
    "ninav": ("Nina", "Valdez", "nvaldez@example.edu"),        # shares a first name
    "ninab": ("Nina", "Brooks", "nina.brooks@example.com"),    # shares a first name
    "felix": ("Felix", "Ambrose", "fambrose@example.edu"),
    "greta": ("Greta", "Lund", "glund@example.edu"),
    "hugo": ("Hugo", "Sato", "hsato@example.com"),
    "ivy": ("Ivy", "Marlow", "imarlow@example.edu"),
    "jonah": ("Jonah", "Pike", "jpike@example.edu"),
    "kiri": ("Kiri", "Atwell", "katwell@example.com"),
    "milo": ("Milo", "Fenn", "mfenn@example.edu"),
}

# key, sender, subject, body ({dl} is replaced by the deadline phrase), deadline date
# offset from TODAY (None = no deadline), ask keyword (None = no ask), fact keywords.
MAIL = [
    ("m01", "lena", "Problem set 7 for ZOOL 2150",
     "Hi,\n\nProblem set 7 is posted. Please upload your solutions to the course site {dl}.\n"
     "It covers enzyme kinetics only.\n\nLena", 4, "upload", ["enzyme"]),
    ("m02", "lena", "Lab report format",
     "Hi,\n\nFor the lab report, please use the two-column template and cite at least three papers.\n"
     "Send me your outline {dl}.\n\nLena", 9, "outline", ["two-column"]),
    ("m03", "lena", "Room change for review session",
     "Hi all,\n\nThe review session moves to Barrow Hall room 112. Nothing else changes.\n\nLena",
     None, None, ["barrow"]),
    ("m04", "omar", "Bike for sale?",
     "Hey,\n\nAre you still selling your old bike? Could you send me a photo of it? "
     "I could pick it up this week.\n\nOmar", None, "photo", ["bike"]),
    ("m05", "tess", "Choir rehearsal moved",
     "Hello singers,\n\nRehearsal moves to the chapel this week. Please confirm you can come {dl}.\n\nTess",
     2, "confirm", ["chapel"]),
    ("m06", "rafe", "Thanks for the notes",
     "Hey,\n\nThanks for the notes from last week, they saved me. The exam went fine.\n\nRafe",
     None, None, ["exam"]),
    ("m07", "ninav", "Poster draft",
     "Hi,\n\nCould you review my poster draft and leave comments in the doc {dl}? "
     "Mainly the methods panel.\n\nNina", 3, "poster", ["methods"]),
    ("m08", "ninab", "Carpool to the airport",
     "Hi!\n\nI'm driving to the airport for break. Can you tell me {dl} if you want a seat in the carpool?\n\nNina B.",
     6, "carpool", ["airport"]),
    ("m09", "felix", "Pay your share for the cabin",
     "Hey team,\n\nPlease send me your $35 share for the cabin trip {dl}.\n\nFelix", 5, "35", ["cabin"]),
    ("m10", "greta", "Library book hold",
     "Hi,\n\nThe book you asked about, Tidal Ecology, is on hold for you at the front desk. "
     "Please pick it up {dl}.\n\nGreta", 7, "pick", ["tidal"]),
    ("m11", "hugo", "Hackathon team name",
     "Yo,\n\nWe need a team name. Reply with your vote {dl}. Options are Night Owls or Byte Club.\n\nHugo",
     1, "vote", ["night owls"]),
    ("m12", "ivy", "Garden club newsletter",
     "Hello,\n\nThis month the garden club planted tulip bulbs and repaired the shed. Thanks to all volunteers.\n\nIvy",
     None, None, ["tulip"]),
    ("m13", "jonah", "Study group for MATH 3320",
     "Hi,\n\nCan you book a study room for the MATH 3320 group {dl}? Any room for four is fine.\n\nJonah",
     10, "book", ["study room"]),
    ("m14", "kiri", "Volunteer shift swap",
     "Hi,\n\nCould you swap volunteer shifts with me? I need someone for the food bank shift. "
     "Let me know {dl}.\n\nKiri", 12, "swap", ["food bank"]),
    ("m15", "milo", "Band practice playlist",
     "Hey,\n\nAdd two songs to the band playlist when you can. No hurry.\n\nMilo", None, "songs", ["playlist"]),
    ("m16", "omar", "Intramural soccer signup",
     "Hey,\n\nSign up for the intramural soccer team on the rec site {dl}. Games are Thursday nights.\n\nOmar",
     8, "sign up", ["soccer"]),
    ("m17", "tess", "Concert tickets",
     "Hi,\n\nI have two extra tickets for the winter concert if you want them. Just tell me.\n\nTess",
     None, "tickets", ["concert"]),
    ("m18", "hugo", "Demo slides",
     "Yo,\n\nPlease finish your two demo slides {dl}. The pitch is right after.\n\nHugo", 13, "slides", ["pitch"]),
    ("m19", "felix", "Cabin packing list",
     "Hey,\n\nThe packing list for the cabin is in the shared folder. Bring a sleeping bag.\n\nFelix",
     None, None, ["sleeping bag"]),
    ("m20", "kiri", "Thank you",
     "Hi,\n\nThank you for covering my shift last month. It meant a lot.\n\nKiri", None, None, ["covering"]),
    # Meeting asks (computer control X and suggestions W): {mt} is a day and time from MEETINGS.
    ("m21", "milo", "Band practice Thursday",
     "Hey,\n\nAre you free for band practice {mt} in Lincoln Hall 101? Let me know.\n\nMilo",
     None, "band practice", ["lincoln hall"]),
    ("m22", "greta", "Book club meeting",
     "Hi,\n\nCan you meet {mt} to plan the book club? Let me know.\n\nGreta", None, "book club", ["book club"]),
    ("m23", "ivy", "Garden plot",
     "Hello,\n\nCan we meet sometime soon about the garden plot?\n\nIvy", None, "garden plot", ["garden plot"]),
]

# Meeting emails: (weekday, time). The day is the first such weekday at least two days after
# TODAY, so for Sun Nov 15 it is Thu Nov 19 7pm (free on the demo calendar) and Wed Nov 18
# 2pm (clashes with "Lab", 1:30-3:30pm). These have no deadline; checks treat them as optional.
MEETINGS = {"m21": (3, "7pm"), "m22": (2, "2pm")}
MEETING_KEYS = {"m21", "m22", "m23"}


def meeting_phrase(key: str) -> str:
    wd, t = MEETINGS[key]
    d = TODAY + timedelta(days=2)
    d += timedelta(days=(wd - d.weekday()) % 7)
    return f"{d:%A}, {d:%B} {d.day} at {t}"


# ---- extra demo mail (brief DEMO): optional rows, not scored by check ---------------
# Added for the video. Each row is marked "optional": true in truth.json; check() asks no
# questions about them, lets their due rows be extra, and allows them as a sender's sources.
EXTRA_SENDERS = {
    "sam": ("Sam", "Ortiz", "sortiz@example.edu"),
    "phone": ("Northway Mobile", "Billing", "billing@northway.example.com"),
    "rec": ("Campus Rec", "Weekly", "news@rec.example.edu"),
}


def _weekday_after(d: date, wd: int, gap: int = 1) -> date:
    """The first given weekday at least `gap` days after d."""
    x = d + timedelta(days=gap)
    return x + timedelta(days=(wd - x.weekday()) % 7)


def _long(d: date) -> str:
    return f"{d:%A}, {d:%B} {d.day}"


def extra_mail() -> list[tuple]:
    """(key, sender, subject, body, sent offset (days before TODAY), sent hour, due date, ask_kw, facts)."""
    thu = _weekday_after(TODAY, 3, 2)   # Felix's meeting day (free at 3 on the demo calendar)
    tue = _weekday_after(TODAY, 1)      # Nina's meeting day (clashes with CHEM 1583 Lab, Tue 2-4pm)
    lab_due = _weekday_after(TODAY, 3, 2)
    fri = _weekday_after(TODAY, 4, 2)
    wed = _weekday_after(TODAY, 2, 2)
    return [
        ("d01", "felix", "Free Thursday at 3?",
         "Hey,\n\nAre you free Thursday at 3? I want to plan the robotics bake sale with you.\n\nFelix",
         0, 10, None, "bake sale", ["bake sale"]),
        ("d02", "ninav", "Practice our seminar talk",
         "Hi,\n\nCan we meet Tuesday at 2:30 to practice our seminar talk?\n\nNina",
         1, 16, None, "seminar", ["seminar talk"]),
        ("d03", "jonah", "Lab Report 3 template",
         "Hi all,\n\nFor Lab Report 3, please use the template on Canvas and cite at least "
         "three sources. The due date is on the assignment page.\n\nJonah (TA, Kitchen Chemistry)",
         2, 9, None, "template", ["three sources"]),
        ("d04", "ivy", "Garden workday photos",
         f"Hello,\n\nCould you send me your photos from the garden workday by {_long(fri)}? "
         "I'm making the slideshow.\n\nIvy", 3, 18, fri, "photos", ["slideshow"]),
        ("d05", "phone", "Your November phone bill",
         f"Hello,\n\nYour November bill of $48.20 is due {_long(fri)}. Pay it on your account page "
         "to avoid a late fee.\n\nNorthway Mobile", 4, 7, fri, "48.20", ["48.20"]),
        ("d06", "rec", "This week at Campus Rec",
         "Hi everyone,\n\nThe climbing wall reopens Monday, and yoga moves to the small gym this week. "
         "Have a good week!\n\nCampus Rec", 1, 8, None, None, ["climbing wall"]),
        ("d07", "sam", "Graphing calculator",
         f"Hey,\n\nCan you return my graphing calculator by {_long(wed)}? I need it for my problem set.\n\nSam",
         2, 20, wed, "calculator", ["calculator"]),
    ]


# The video's staged set (thinker ruling 2: short lists on screen). Lab report: Lena's format
# mail + Jonah's template mail; tomorrow: Hugo's vote; Tuesday: Tess; Felix's Thursday-at-3
# meeting; the $48.20 bill; Omar's no-deadline ask; the newsletter with no ask.
VIDEO_KEYS = ("m02", "m04", "m05", "m11", "d01", "d03", "d05", "d06")


def build_video() -> list[dict]:
    """The video bank's mail: VIDEO_KEYS out of build(extra=True), every row optional-free."""
    return [m for m in build(extra=True) if m["key"] in VIDEO_KEYS]


def build_extra() -> list[dict]:
    rng = random.Random(SEED + 1)
    out = []
    for key, s, subject, body, back, hour, due, ask_kw, facts in extra_mail():
        first, last, addr = {**SENDERS, **EXTRA_SENDERS}[s]
        sent = TODAY - timedelta(days=back)
        sent_dt = datetime(sent.year, sent.month, sent.day, hour, rng.randint(0, 59))
        name = f"{first} {last}" if s not in ("phone", "rec") else first
        text = (f"From: {name} <{addr}>\nDate: {sent_dt:%a, %d %b %Y %H:%M:%S} -0500\n"
                f"Subject: {subject}\n\n" + body)
        out.append({"key": key, "sender": s, "name": name, "first": first, "address": addr,
                    "sent": sent.isoformat(), "subject": subject,
                    "due": due.isoformat() if due else None, "phrase": None, "ask_kw": ask_kw,
                    "facts": facts, "sent_at": sent_dt.isoformat(timespec="minutes"),
                    "body": body, "text": text, "optional": True})
    return out


def phrase_for(d: date, sent: date, rng: random.Random) -> str:
    """An explicit date, or a bare weekday when that is unambiguous from the sent date."""
    t = rng.choice(["5pm", "noon", "11:59pm", None])
    if rng.random() < 0.6 or not 0 < (d - sent).days <= 6:
        p = f"by {d:%A}, {d:%B} {d.day}"
    else:
        p = f"by {d:%A}"
    return f"{p} at {t}" if t else p


def build(extra: bool = False) -> list[dict]:
    """Brief M's mail (m01-m23); extra=True appends the optional demo rows (d01-...)."""
    rng = random.Random(SEED)
    out = []
    for key, s, subject, body, off, ask_kw, facts in MAIL:
        first, last, addr = SENDERS[s]
        sent = TODAY - timedelta(days=rng.randint(0, 3))
        sent_dt = datetime(sent.year, sent.month, sent.day, rng.randint(8, 21), rng.randint(0, 59))
        due = TODAY + timedelta(days=off) if off is not None else None
        dl = phrase_for(due, sent, rng) if due else ""
        plain = body.format(dl=dl, mt=meeting_phrase(key) if key in MEETINGS else "").replace(" .", ".")
        text = (f"From: {first} {last} <{addr}>\nDate: {sent_dt:%a, %d %b %Y %H:%M:%S} -0500\n"
                f"Subject: {subject}\n\n" + plain)
        out.append({"key": key, "sender": s, "name": f"{first} {last}", "first": first,
                    "address": addr, "sent": sent.isoformat(), "subject": subject,
                    "due": due.isoformat() if due else None, "phrase": dl or None,
                    "ask_kw": ask_kw, "facts": facts, "sent_at": sent_dt.isoformat(timespec="minutes"),
                    "body": plain, "text": text})
    return out + (build_extra() if extra else [])


def write(out_dir: Path, extra: bool = False) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    mails = build(extra)
    for m in mails:
        (out_dir / f"{m['key']}.txt").write_text(m["text"])
    truth = [{k: v for k, v in m.items() if k not in ("text", "body")} for m in mails]
    (out_dir / "truth.json").write_text(json.dumps({"today": TODAY.isoformat(), "mail": truth}, indent=1))
    print(f"wrote {len(mails)} emails from {len({m['sender'] for m in mails})} senders to {out_dir}")


# ---- check ----------------------------------------------------------------

def _subjects_from(a, entries_by_path, kinds=None) -> set[str]:
    """Subjects of the answer's sources; kinds limits them (the due check counts only mail)."""
    return {entries_by_path[p]["subject"] for p in a.sources if p in entries_by_path
            and (kinds is None or entries_by_path[p].get("kind") in kinds)}


def check(out_dir: Path) -> int:
    from bank import store
    from reason import answer

    every = json.loads((out_dir / "truth.json").read_text())["mail"]
    truth = [m for m in every if not m.get("optional")]   # extra demo rows are not scored
    optional = {m["subject"] for m in every if m.get("optional")}
    by_path = {e["path"]: e for e in store.all_entries()}
    rows = []

    def record(kind, q, ok, a, want):
        rows.append((kind, q, ok, a, want))
        print(f"[{'RIGHT' if ok else 'WRONG'}] {kind:<6} {q}\n   want: {want}\n   got ({a.route}, "
              f"{a.seconds}s): {a.text.replace(chr(10), ' | ')[:300]}", flush=True)

    # person: one question per sender (by first name, or full name when shared)
    firsts = [m["first"] for m in truth]
    for s in dict.fromkeys(m["sender"] for m in truth):
        mine = [m for m in truth if m["sender"] == s]
        allowed = {m["subject"] for m in every if m["sender"] == s}  # incl. their extra demo mail
        first, name = mine[0]["first"], mine[0]["name"]
        who = name if firsts.count(first) > 1 and len({m['sender'] for m in truth if m['first'] == first}) > 1 else first
        q = f"What did {who} ask me?"
        a = answer(q, today=TODAY)
        asks = [m["ask_kw"] for m in mine if m["ask_kw"]]
        text = a.text.lower()
        if asks:
            ok = a.route == "person" and any(k in text for k in asks) and \
                 _subjects_from(a, by_path) <= allowed
            want = f"person route, mentions one of {asks}, sources only {name}'s mail"
        else:
            ok = a.route == "person" and any(w in text for w in ("don't say", "didn't ask", "did not ask",
                                                                     "nothing", "no request", "no ask")) \
                and _subjects_from(a, by_path) <= allowed
            want = f"person route, says {name} asked nothing; sources only {name}'s mail"
        record("person", q, ok, a, want)

    # shared first name alone: must not mix the two Ninas' asks as one person's
    a = answer("What did Nina ask me?", today=TODAY)
    got = _subjects_from(a, by_path)
    record("person", "What did Nina ask me?", a.route == "person" and len(got) >= 1, a,
           "person route; two Ninas exist, so any Nina answer is acceptable (reported, not judged)")

    # no-match
    for nm in ("Zelda", "Bartholomew"):
        q = f"What did {nm} ask me?"
        a = answer(q, today=TODAY)
        record("nomatch", q, a.text == f"I have nothing from {nm}.", a, f'"I have nothing from {nm}."')

    # due: each deadline day, plus this week / next week
    def due_check(q, lo, hi):
        a = answer(q, today=TODAY)
        want = {m["subject"] for m in truth if m["due"] and lo <= m["due"] <= hi}
        got = _subjects_from(a, by_path, kinds=("email",))  # Canvas rows (kind="canvas") may be extra
        got -= {m["subject"] for m in truth if m["key"] in MEETING_KEYS}  # a meeting time filed as a deadline is fine
        got -= optional  # extra demo mail may add due rows
        record("due", q, a.route == "due" and got == want, a, sorted(want) or "nothing due")

    for d in sorted({m["due"] for m in truth if m["due"]}):
        dd = date.fromisoformat(d)
        due_check(f"What's due on {dd:%B} {dd.day}?", d, d)
    # Same week rule as reason.route: on Sat/Sun "this week" runs to the coming Sunday.
    mon = TODAY - timedelta(days=TODAY.weekday())
    wk_end = mon + timedelta(days=6 + (7 if TODAY.weekday() >= 5 else 0))
    due_check("What's due this week?", TODAY.isoformat(), wk_end.isoformat())
    nxt = mon + timedelta(days=7)
    due_check("What's due next week?", nxt.isoformat(), (nxt + timedelta(days=6)).isoformat())
    tmr = (TODAY + timedelta(days=1)).isoformat()
    due_check("What's due tomorrow?", tmr, tmr)
    due_check("Anything due November 29?", "2026-11-29", "2026-11-29")

    # bank: fact questions answered from summaries
    facts = [
        ("Where is the review session now?", "barrow", "m03"),
        ("How much is my share for the cabin trip?", "35", "m09"),
        ("What book is on hold for me at the library?", "tidal", "m10"),
        ("What are the team name options for the hackathon?", "night owls", "m11"),
        ("What did the garden club plant this month?", "tulip", "m12"),
        ("What should I bring to the cabin?", "sleeping bag", "m19"),
    ]
    for q, kw, key in facts:
        a = answer(q, today=TODAY)
        subj = next(m["subject"] for m in truth if m["key"] == key)
        ok = a.route == "bank" and kw in a.text.lower() and subj in _subjects_from(a, by_path)
        record("bank", q, ok, a, f'bank route, says "{kw}", source "{subj}"')

    right = sum(1 for r in rows if r[2])
    print(f"\n{right}/{len(rows)} right")
    for kind in ("person", "nomatch", "due", "bank"):
        ks = [r for r in rows if r[0] == kind]
        print(f"  {kind:<7} {sum(r[2] for r in ks)}/{len(ks)}")
    wrong = [r for r in rows if not r[2]]
    if wrong:
        print("\nWRONG:")
        for kind, q, _, a, want in wrong:
            print(f"- {kind}: {q} -> ({a.route}) {a.text.replace(chr(10), ' | ')[:200]}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="scripts/demo/make_test_mail.py")
    ap.add_argument("mode", choices=("write", "check"))
    ap.add_argument("out_dir", type=Path)
    ap.add_argument("--today", type=date.fromisoformat, default=None,
                    help="the day the mail is built and checked for (default 2026-11-14)")
    ap.add_argument("--extra", action="store_true",
                    help="write: also the optional demo emails (d01-d07), marked optional in truth.json")
    ap.add_argument("--offline", action="store_true",
                    help="block the network for this process (localhost stays open for Bonsai)")
    args = ap.parse_args(argv)
    global TODAY
    if args.today:
        TODAY = args.today
    if args.offline:
        from reason.live_check import block_network
        block_network()
    if args.mode == "write":
        write(args.out_dir, args.extra)
        return 0
    return check(args.out_dir)


if __name__ == "__main__":
    raise SystemExit(main())

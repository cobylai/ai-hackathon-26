"""Typed chat loop with push-to-talk: python -m reason [--today YYYY-MM-DD] [--no-voice]

Type a question and press Enter. Press Enter on an empty line to start talking, and
Enter again to stop; the words heard are shown and answered like a typed question.
Ctrl-D (or "quit") exits. If voice can't start, typing still works.
--speak reads each answer aloud with the Mac's `say` (no Source line); talking or a new
question stops it. Follow-ups ("and tomorrow?", "the first one") lean on this run's last
answer only (reason/session.py). The conversation is saved as a chat after every answer
(reason/chats.py, outside the repo), so it shows in the window's chats list; --no-save skips that.
A thin wrapper: answer() does the work.
"""
from __future__ import annotations

import argparse

from . import answer
from .session import Session
from .speak import Speaker
from .speech import start_voice

SESSION = Session()   # this run's conversation, for follow-ups
SPEAKER = None        # a Speaker when --speak
SAVE = True           # save this run's conversation (reason/chats.py); --no-save turns it off


def ask(q: str, today) -> None:
    if SPEAKER:
        SPEAKER.stop()
    try:
        a = answer(q, today=today, session=SESSION)
    except Exception as e:  # keep the loop alive; show what broke
        print(f"muse> Error: {type(e).__name__}: {e}\n")
        return
    print(f"muse> {a.text}\n[{a.route}, {a.seconds:.1f}s]\n")
    if SAVE:
        from . import chats
        try:
            chats.save(SESSION)
        except OSError as e:
            print(f"  (couldn't save this chat: {e})\n")
    if SPEAKER:
        SPEAKER.speak(a.text)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m reason")
    ap.add_argument("--today", help="pretend today is this date (YYYY-MM-DD)")
    ap.add_argument("--no-voice", action="store_true", help="typing only")
    ap.add_argument("--no-save", action="store_true", help="don't save this conversation as a chat")
    ap.add_argument("--speak", action="store_true", help="read answers aloud with the Mac's say")
    args = ap.parse_args(argv)
    global SPEAKER, SAVE
    SPEAKER = Speaker() if args.speak else None
    SAVE = not args.no_save

    voice, why = (None, "turned off") if args.no_voice else start_voice()
    if voice:
        print("Type a question, or press Enter on an empty line to talk (Enter again to stop).")
    else:
        print(f"Voice is unavailable ({why}). Type your questions.")
    try:
        while True:
            try:
                q = input("you> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return 0
            if q.lower() in ("quit", "exit"):
                return 0
            if not q:
                if not voice:
                    continue
                if SPEAKER:
                    SPEAKER.stop()  # talking stops the spoken answer
                try:
                    q = voice.listen(wait_for_stop=lambda: input("  (recording… Enter to stop) ")).strip()
                except Exception as e:
                    print(f"  voice error: {e}\n")
                    continue
                print(f"you (spoken)> {q}")
                if not q:
                    continue
            ask(q, args.today)
    finally:
        if SPEAKER:
            SPEAKER.stop()
        if voice:
            voice.close()


if __name__ == "__main__":
    import applecal
    applecal.warm()  # read Apple Calendar in the background (docs/calendar.md, Speed)
    raise SystemExit(main())

"""CLI: ``uv run python -m harness goto https://example.com`` or ``... app_open TextEdit``."""

from __future__ import annotations

import argparse
import sys

from harness.browser.session import get_session
from harness.registry import TOOLS


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="harness", description="Hidden browser and computer-control tools")
    sub = parser.add_subparsers(dest="command", required=True)

    goto = sub.add_parser("goto", help="open a URL")
    goto.add_argument("url")

    read = sub.add_parser("read", help="read page N of the current text")
    read.add_argument("page", nargs="?", type=int, default=1)

    listed = sub.add_parser("elements", help="number the clickable items")
    listed.add_argument("filter", nargs="?", default=None)

    click = sub.add_parser("click", help="click item N")
    click.add_argument("n", type=int)

    typed = sub.add_parser("type", help="type into item N")
    typed.add_argument("n", type=int)
    typed.add_argument("text")
    typed.add_argument("--enter", action="store_true", help="press Enter after typing")

    sub.add_parser("back", help="go back one page")

    login = sub.add_parser("login", help="sign in once in a visible window")
    login.add_argument("url")

    app_open = sub.add_parser("app_open", help="open a Mac app by name")
    app_open.add_argument("name")
    app_open.add_argument("--token", default="", help="one-time token from a CONFIRM reply")

    file_find = sub.add_parser("file_find", help="find files by name (home folder)")
    file_find.add_argument("query")

    file_open = sub.add_parser("file_open", help="open file N from the last file_find list")
    file_open.add_argument("n", type=int)
    file_open.add_argument("--token", default="")

    ui_list = sub.add_parser("ui", help="number the front window's controls")
    ui_list.add_argument("filter", nargs="?", default="")

    ui_click = sub.add_parser("ui_click", help="click control N from the last ui list")
    ui_click.add_argument("n", type=int)
    ui_click.add_argument("--token", default="")

    ui_type = sub.add_parser("ui_type", help="type text into control N")
    ui_type.add_argument("n", type=int)
    ui_type.add_argument("text")
    ui_type.add_argument("--token", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "login":
        from harness.browser.login import login

        return login(args.url)
    kwargs: dict[str, object] = {}
    if args.command == "goto":
        kwargs = {"url": args.url}
    elif args.command == "read":
        kwargs = {"page": args.page}
    elif args.command == "elements":
        kwargs = {"filter": args.filter}
    elif args.command == "click":
        kwargs = {"n": args.n}
    elif args.command == "type":
        kwargs = {"n": args.n, "text": args.text, "enter": 1 if args.enter else 0}
    elif args.command == "back":
        kwargs = {}
    elif args.command == "app_open":
        kwargs = {"name": args.name, "token": args.token}
    elif args.command == "file_find":
        kwargs = {"query": args.query}
    elif args.command == "file_open":
        kwargs = {"n": args.n, "token": args.token}
    elif args.command == "ui":
        kwargs = {"filter": args.filter}
    elif args.command == "ui_click":
        kwargs = {"n": args.n, "token": args.token}
    elif args.command == "ui_type":
        kwargs = {"n": args.n, "text": args.text, "token": args.token}

    try:
        result = TOOLS[args.command].run(**kwargs)
    finally:
        get_session().stop()

    print(result)
    return 0 if result.startswith("OK") else 1


if __name__ == "__main__":
    sys.exit(main())

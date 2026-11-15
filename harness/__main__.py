"""CLI: ``uv run python -m harness goto https://example.com``."""

from __future__ import annotations

import argparse
import sys

from harness.browser.session import get_session
from harness.registry import TOOLS


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="harness", description="Hidden browser tools")
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

    try:
        result = TOOLS[args.command].run(**kwargs)
    finally:
        get_session().stop()

    print(result)
    return 0 if result.startswith("OK") else 1


if __name__ == "__main__":
    sys.exit(main())

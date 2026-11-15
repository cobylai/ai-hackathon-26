"""Run any registered harness tool from the shell.

    uv run python scripts/run_tool.py --list
    uv run python scripts/run_tool.py goto url=https://example.com
    uv run python scripts/run_tool.py email_search sender=me days=7
    uv run python scripts/run_tool.py email_read n=1

Arguments are ``name=value`` pairs, coerced to the types ``Tool.args`` declares,
so this also checks the registry contract the reasoning layer relies on.
Exit code is 0 when the tool answers ``OK`` and 1 otherwise (2 for usage errors).
Nothing here can send mail: there is no send tool in the registry.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from harness import registry  # noqa: E402


def usage() -> str:
    lines = ["groups:"]
    for group, names in registry.GROUPS.items():
        lines.append(f"  {group or '(none)'}: {', '.join(names) or '-'}")
    lines.append("")
    lines.append("tools:")
    for group, names in registry.GROUPS.items():
        for name in names:
            tool = registry.TOOLS.get(name)
            if tool is None:
                continue
            args = " ".join(f"{key}=<{kind.__name__}>" for key, kind in tool.args.items())
            lines.append(f"  {group:9} {name:18} {tool.desc} [{args}]")
    return "\n".join(lines)


def run(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help", "--list"):
        print(usage())
        return 0 if argv else 2

    name, pairs = argv[0], argv[1:]
    tool = registry.TOOLS.get(name)
    if tool is None:
        print(f"ERR unknown tool {name!r}")
        print(usage())
        return 2

    kwargs: dict[str, object] = {}
    for pair in pairs:
        if "=" not in pair:
            print(f"ERR expected name=value, got {pair!r}")
            return 2
        key, value = pair.split("=", 1)
        if key not in tool.args:
            print(f"ERR {name} takes: {', '.join(tool.args) or '(no arguments)'}")
            return 2
        kwargs[key] = int(value) if tool.args[key] is int else value

    try:
        output = tool.run(**kwargs)
    except TypeError as exc:  # a required argument was left out
        print(f"ERR {name} needs {', '.join(tool.args)} | {exc}")
        return 2

    print(output)
    return 0 if output.startswith("OK") else 1


if __name__ == "__main__":
    sys.exit(run(sys.argv[1:]))

"""Launch args for optional Chromium extensions (uBlock Origin Lite)."""

from __future__ import annotations

from pathlib import Path

from harness import config


def ubol_dir(directory: str | Path | None = None) -> Path:
    return Path(directory) if directory is not None else config.EXTENSIONS_DIR / "ubol"


def launch_args(directory: str | Path | None = None) -> list[str]:
    """Return the two ``--load-extension`` flags when UBOL is on and installed.

    Extensions only load in full Chromium with new headless mode, which is what
    ``Session.start`` uses. Off by default until the headless check passes.
    """
    folder = ubol_dir(directory)
    if not config.USE_UBOL:
        return []
    if not (folder / "manifest.json").is_file():
        return []
    return [
        f"--disable-extensions-except={folder}",
        f"--load-extension={folder}",
    ]

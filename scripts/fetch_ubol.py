"""Download the latest uBlock Origin Lite (Chromium) build into ~/.harness.

Run once after install: ``uv run python scripts/fetch_ubol.py``.
Nothing is written inside the repo; the unpacked extension lives under
``~/.harness/extensions/ubol`` and is only used when ``config.USE_UBOL`` is on.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness import config  # noqa: E402

RELEASE_API = "https://api.github.com/repos/uBlockOrigin/uBOL-home/releases/latest"
ASSET_PREFIX = "uBOLite_"
ASSET_SUFFIX = ".chromium.zip"


def latest_asset() -> tuple[str, str]:
    """Return ``(name, download_url)`` for the newest Chromium zip."""
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        release = client.get(RELEASE_API, headers={"Accept": "application/vnd.github+json"})
        release.raise_for_status()
        for asset in release.json().get("assets", []):
            name = asset.get("name", "")
            if name.startswith(ASSET_PREFIX) and name.endswith(ASSET_SUFFIX):
                return name, asset["browser_download_url"]
    raise SystemExit(f"no {ASSET_PREFIX}*{ASSET_SUFFIX} asset in the latest release")


def _safe_extract(archive: zipfile.ZipFile, target: Path) -> None:
    root = target.resolve()
    for member in archive.infolist():
        destination = (target / member.filename).resolve()
        if root != destination and root not in destination.parents:
            raise SystemExit(f"refusing unsafe zip member: {member.filename}")
    archive.extractall(target)


def main(destination: Path | None = None) -> int:
    folder = destination if destination is not None else config.EXTENSIONS_DIR / "ubol"
    name, url = latest_asset()
    print(f"latest: {name}")

    folder.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=folder.parent) as staging:
        staging_path = Path(staging) / "unpack"
        archive_path = Path(staging) / name
        with httpx.Client(timeout=120, follow_redirects=True) as client:
            with client.stream("GET", url) as response:
                response.raise_for_status()
                with archive_path.open("wb") as handle:
                    for chunk in response.iter_bytes():
                        handle.write(chunk)

        staging_path.mkdir()
        try:
            with zipfile.ZipFile(archive_path) as archive:
                _safe_extract(archive, staging_path)
        except zipfile.BadZipFile as exc:
            raise SystemExit(f"bad zip from {url}: {exc}") from exc

        if not (staging_path / "manifest.json").is_file():
            # Some builds wrap the extension in a top-level folder.
            nested = [
                path.parent
                for path in staging_path.glob("*/manifest.json")
                if path.parent != staging_path
            ]
            if len(nested) != 1:
                raise SystemExit("manifest.json not found in the unpacked extension")
            staging_path = nested[0]

        if folder.exists():
            shutil.rmtree(folder)
        shutil.move(str(staging_path), str(folder))

    manifest = folder / "manifest.json"
    print(f"installed: {manifest} ({sum(1 for _ in folder.rglob('*'))} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

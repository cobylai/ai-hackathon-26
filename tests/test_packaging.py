"""Packaging: the wheel must carry the element script.

`harness/browser/elements.py` reads `elements.js` at import time, and setuptools
ships only .py files unless package data says otherwise. Without that, a wheel
installs cleanly and then fails on `import harness`. These tests guard the
declaration, the file's presence and, when asked, a real wheel.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tomllib
import zipfile
from importlib import resources
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def pyproject() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_package_data_declares_the_element_script():
    data = pyproject()["tool"]["setuptools"]["package-data"]
    assert "*.js" in data["harness.browser"]


def test_only_the_harness_package_is_shipped():
    include = pyproject()["tool"]["setuptools"]["packages"]["find"]["include"]
    assert include == ["harness*"]


def test_element_script_sits_next_to_its_module():
    script = resources.files("harness.browser").joinpath("elements.js")
    assert script.is_file()
    assert "data-hn" in script.read_text(encoding="utf-8")


@pytest.mark.skipif(
    not os.environ.get("HARNESS_BUILD_TEST"),
    reason="set HARNESS_BUILD_TEST=1 to build a wheel (needs network for the build backend)",
)
def test_wheel_contains_the_element_script(tmp_path):
    if shutil.which("uv") is None:
        pytest.skip("uv not on PATH")
    proc = subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(tmp_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, proc.stderr[-500:]
    wheel = next(tmp_path.glob("*.whl"))
    names = zipfile.ZipFile(wheel).namelist()
    assert "harness/browser/elements.js" in names
    assert any(name.startswith("harness/search/loop.py") for name in names)
    assert not any(name.startswith("tests/") for name in names)

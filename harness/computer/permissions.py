"""macOS accessibility permission check (task C2).

The accessibility tree is only readable when the process running the harness
has the Accessibility grant. The user grants it once, to the terminal or app
that runs the harness, under System Settings > Privacy & Security >
Accessibility.
"""

from __future__ import annotations

try:
    from ApplicationServices import AXIsProcessTrusted
except ImportError:  # non-macOS: pyobjc unavailable
    AXIsProcessTrusted = None

NEEDED = (
    "ERR accessibility permission needed: "
    "System Settings > Privacy & Security > Accessibility"
)


def accessibility_ok() -> bool:
    """True when this process may read other apps' accessibility trees."""
    if AXIsProcessTrusted is None:
        return False
    return bool(AXIsProcessTrusted())

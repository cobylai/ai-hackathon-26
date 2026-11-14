"""Numbered controls of the front window, via the macOS accessibility tree.

Per the C1 decision this is a thin pyobjc layer. The walk is split from the
pyobjc fetching so tests can run it on a fake tree:

- ``walk(tree)`` is pure: tree nodes are ``(role, label, children)`` tuples.
- ``_ax_tree(...)`` builds those tuples from a live AXUIElementRef.
- ``list_controls()`` is the tool: status line first, numbered lines, capped.

The last listing is kept in ``_last`` so ui_click / ui_type (task C6) can map
a number back to the control.
"""

from __future__ import annotations

from harness import config
from harness.computer import permissions, policy
from harness.computer.tools import _cap

MAX_DEPTH = 8
MAX_LINES = 40

KEEP_ROLES = {
    "AXButton": "button",
    "AXTextField": "textfield",
    "AXTextArea": "textarea",
    "AXCheckBox": "checkbox",
    "AXRadioButton": "radiobutton",
    "AXMenuItem": "menuitem",
    "AXMenuButton": "menubutton",
    "AXLink": "link",
    "AXTab": "tab",
    "AXPopUpButton": "popupbutton",
    "AXComboBox": "combobox",
}

# Number -> control the model was shown. Elements hold the live AX ref.
_last: list[dict] = []


def walk(tree, depth: int = 0, out: list | None = None) -> list[dict]:
    """Collect labelled, actionable controls from a (role, label, children) tree."""
    if out is None:
        out = []
    if depth > MAX_DEPTH or len(out) >= MAX_LINES:
        return out
    role, label, children, *extra = tree
    element = extra[0] if extra else None
    if role in KEEP_ROLES and label:
        out.append({"kind": KEEP_ROLES[role], "label": label, "element": element})
    for child in children:
        walk(child, depth + 1, out)
        if len(out) >= MAX_LINES:
            break
    return out


def format_lines(controls: list[dict]) -> list[str]:
    return [f'{i}. {c["kind"]} "{c["label"]}"' for i, c in enumerate(controls, 1)]


def apply_filter(controls: list[dict], word: str) -> list[dict]:
    word = word.strip().lower()
    if not word:
        return controls
    return [
        c for c in controls
        if word in c["label"].lower() or word in c["kind"].lower()
    ]


# --- live accessibility tree (pyobjc, macOS only) ----------------------------


def _front_app():
    """(pid, name) of the frontmost app, or None.

    macOS 27 workarounds (C1 findings): NSRunningApplication reports pid -1,
    the system-wide AXFocusedApplication query fails outright, and
    CGWindowList ordering is unreliable across displays and Spaces. So: the
    name comes from NSWorkspace.frontmostApplication, the pid from the window
    list entry with that owner name.
    """
    import AppKit
    import Quartz

    front = AppKit.NSWorkspace.sharedWorkspace().frontmostApplication()
    if front is None:
        return None
    name = str(front.localizedName() or "")
    pid = front.processIdentifier()
    if pid and pid > 0:
        return int(pid), name
    windows = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionAll, Quartz.kCGNullWindowID
    )
    for w in windows:
        if w.get("kCGWindowOwnerName") == name and w.get("kCGWindowOwnerPID"):
            return int(w["kCGWindowOwnerPID"]), name
    return None


def _ax_tree(el, depth: int = 0):
    """Build a (role, label, children, element) tuple tree from an AX element."""
    import ApplicationServices as AX

    if depth > MAX_DEPTH:
        return None
    _, role = AX.AXUIElementCopyAttributeValue(el, AX.kAXRoleAttribute, None)
    label = ""
    for attr in (AX.kAXTitleAttribute, AX.kAXDescriptionAttribute, AX.kAXValueAttribute):
        err, value = AX.AXUIElementCopyAttributeValue(el, attr, None)
        if err == 0 and isinstance(value, str) and value.strip():
            label = " ".join(value.split())[:60]
            break
    _, kids = AX.AXUIElementCopyAttributeValue(el, AX.kAXChildrenAttribute, None)
    children = [t for k in kids or [] if (t := _ax_tree(k, depth + 1))]
    return (str(role or ""), label, children, el)


def _best_window_tree(app):
    """The front app's window whose walk yields the most controls.

    AXWindows[0] can be a floating palette with a nearly empty subtree
    (C1 finding), so every window is walked and the richest wins.
    """
    import ApplicationServices as AX

    err, windows = AX.AXUIElementCopyAttributeValue(app, AX.kAXWindowsAttribute, None)
    if err != 0 or not windows:
        return None, ""
    best_tree, best_title, best_count = None, "", -1
    for win in windows:
        tree = _ax_tree(win)
        count = len(walk(tree)) if tree else 0
        if count > best_count:
            _, title = AX.AXUIElementCopyAttributeValue(win, AX.kAXTitleAttribute, None)
            best_tree, best_title, best_count = tree, str(title or ""), count
    return best_tree, " ".join(best_title.split())[:60]


def list_controls(filter: str = "") -> str:
    """List the front window's controls as numbered lines (the `ui` tool)."""
    global _last
    if policy.stopped():
        return policy.STOPPED_MESSAGE

    if not permissions.accessibility_ok():
        _last = []
        return permissions.NEEDED

    front = _front_app()
    if front is None:
        _last = []
        return "ERR no front window found"
    pid, app_name = front
    verdict = policy.check(app_name, "ui", filter)
    if verdict == policy.DENY:
        _last = []
        return f"ERR not allowed: ui on '{app_name}'"
    if verdict == policy.CONFIRM:
        _last = []
        return f"CONFIRM list controls of '{app_name}'"

    import ApplicationServices as AX

    tree, title = _best_window_tree(AX.AXUIElementCreateApplication(pid))
    controls = walk(tree) if tree else []
    controls = apply_filter(controls, filter)
    _last = controls

    if not controls:
        suffix = f" | filter '{filter}'" if filter.strip() else ""
        return f"OK {app_name} | {title or '(untitled)'} | 0 controls{suffix}"
    header = f"OK {app_name} | {title or '(untitled)'} | {len(controls)} controls"
    return _cap(header + "\n" + "\n".join(format_lines(controls)))

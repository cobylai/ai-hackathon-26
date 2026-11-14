"""Tests for numbered controls on a fake accessibility tree (task C5)."""

from harness.computer import ui

# Fake tree: (role, label, children) — TextEdit-like document window.
FAKE_TREE = (
    "AXWindow", "Untitled", [
        ("AXGroup", "", [
            ("AXButton", "Siri Waveform Orb", []),
        ]),
        ("AXToolBar", "", [
            ("AXCheckBox", "bold", []),
            ("AXCheckBox", "italic", []),
            ("AXPopUpButton", "typeface", []),
            ("AXButton", "", []),  # unlabelled button: dropped
        ]),
        ("AXScrollArea", "", [
            ("AXTextArea", "", []),  # empty document: no label, dropped
            ("AXScrollBar", "", []),  # role not kept
        ]),
        ("AXMenuButton", "document actions", [
            ("AXMenuItem", "Duplicate", []),
            ("AXMenuItem", "Move to Trash", []),
        ]),
        ("AXTab", "Info", []),
        ("AXLink", "help page", []),
        ("AXTextField", "search", []),
    ],
)


def test_walk_keeps_labelled_controls():
    controls = ui.walk(FAKE_TREE)
    lines = ui.format_lines(controls)
    assert lines == [
        '1. button "Siri Waveform Orb"',
        '2. checkbox "bold"',
        '3. checkbox "italic"',
        '4. popupbutton "typeface"',
        '5. menubutton "document actions"',
        '6. menuitem "Duplicate"',
        '7. menuitem "Move to Trash"',
        '8. tab "Info"',
        '9. link "help page"',
        '10. textfield "search"',
    ]


def test_walk_drops_unlabelled_and_unknown_roles():
    controls = ui.walk(FAKE_TREE)
    labels = [c["label"] for c in controls]
    kinds = [c["kind"] for c in controls]
    assert "" not in labels
    assert "scrollbar" not in kinds and "group" not in kinds


def test_walk_depth_limit():
    # a button buried deeper than MAX_DEPTH is not listed
    tree = ("AXButton", "too deep", [])
    for _ in range(ui.MAX_DEPTH + 1):
        tree = ("AXGroup", "", [tree])
    tree = ("AXWindow", "w", [tree, ("AXButton", "shallow", [])])
    labels = [c["label"] for c in ui.walk(tree)]
    assert labels == ["shallow"]


def test_walk_line_cap():
    kids = [("AXButton", f"b{i}", []) for i in range(100)]
    controls = ui.walk(("AXWindow", "w", kids))
    assert len(controls) == ui.MAX_LINES


def test_filter_keeps_matching_lines():
    controls = ui.walk(FAKE_TREE)
    kept = ui.apply_filter(controls, "bold")
    assert ui.format_lines(kept) == ['1. checkbox "bold"']
    kept = ui.apply_filter(controls, "TRASH")
    assert ui.format_lines(kept) == ['1. menuitem "Move to Trash"']
    kept = ui.apply_filter(controls, "menu")
    assert [c["label"] for c in kept] == ["document actions", "Duplicate", "Move to Trash"]
    assert ui.apply_filter(controls, "  ") == controls


def test_filter_matches_kind():
    controls = ui.walk(FAKE_TREE)
    kept = ui.apply_filter(controls, "checkbox")
    assert [c["label"] for c in kept] == ["bold", "italic"]

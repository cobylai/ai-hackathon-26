# dmgbuild settings for Muse.dmg (app/make_dmg.sh passes -D stage=<folder> -D art=<folder>).
import os

stage = defines["stage"]
art = defines["art"]

format = "UDZO"
filesystem = "HFS+"
files = [os.path.join(stage, f) for f in ("Muse.app", "INSTALL.html", "setup.sh")]
symlinks = {"Applications": "/Applications"}
icon = os.path.join(stage, "Muse.app", "Contents", "Resources", "Muse.icns")
hide_extensions = ["Muse.app", "INSTALL.html"]

background = os.path.join(art, "background.tiff")
window_rect = ((200, 140), (660, 428))   # 400 pt of content under the title bar
default_view = "icon-view"
show_status_bar = False
show_tab_view = False
show_toolbar = False
show_pathbar = False
show_sidebar = False
icon_size = 80
text_size = 13
# Centres match the drawn background (app/dmg/art.swift).
icon_locations = {
    "Muse.app": (165, 150),
    "Applications": (495, 150),
    "INSTALL.html": (265, 322),
    "setup.sh": (395, 322),
}

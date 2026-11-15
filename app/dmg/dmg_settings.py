# dmgbuild settings for Flux.dmg (app/make_dmg.sh passes -D stage=<folder> -D art=<folder>).
import os

stage = defines["stage"]
art = defines["art"]

format = "UDZO"
filesystem = "HFS+"
files = [os.path.join(stage, "Flux.app")]
symlinks = {"Applications": "/Applications"}
icon = os.path.join(stage, "Flux.app", "Contents", "Resources", "Flux.icns")
hide_extensions = ["Flux.app"]

background = os.path.join(art, "background.tiff")
window_rect = ((200, 140), (660, 428))   # 400 pt of content under the title bar
default_view = "icon-view"
show_status_bar = False
show_tab_view = False
show_toolbar = False
show_pathbar = False
show_sidebar = False
icon_size = 96
text_size = 13
# Centres match the drawn background (app/dmg/art.swift).
icon_locations = {
    "Flux.app": (165, 175),
    "Applications": (495, 175),
}

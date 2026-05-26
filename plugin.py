"""CartographerPlugin — PinSheet plugin adapter for Cartographer."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

_plugins_parent = str(Path(__file__).parent.parent)
if _plugins_parent not in sys.path:
    sys.path.insert(0, _plugins_parent)

from plugin import PinSheetPlugin


class CartographerPlugin(PinSheetPlugin):
    """Adds course geometry, hole diagrams, and yardage book generation to PinSheet."""

    name = "cartographer"
    version = "1.3.0"

    def __init__(self) -> None:
        super().__init__()
        self._install_fonts()

    @staticmethod
    def _install_fonts() -> None:
        fonts_dir = Path(__file__).parent / "fonts" / "JetBrainsMono"
        target_dir = Path.home() / ".local" / "share" / "fonts" / "pinsheet"
        target_dir.mkdir(parents=True, exist_ok=True)
        needs_cache = False
        for ttf in fonts_dir.glob("*.ttf"):
            dst = target_dir / ttf.name
            if not dst.exists() or dst.stat().st_size != ttf.stat().st_size:
                shutil.copy2(ttf, dst)
                needs_cache = True
        if needs_cache and shutil.which("fc-cache"):
            subprocess.run(["fc-cache", "-f"], check=False)

    def screens(self) -> list:
        from cartographer.screens.hole_view import HoleViewScreen
        from cartographer.screens.course_gallery import CourseGalleryScreen
        from cartographer.screens.geometry_setup import GeometrySetupScreen
        from cartographer.screens.pdf_export import PDFExportScreen
        return [HoleViewScreen, CourseGalleryScreen, GeometrySetupScreen, PDFExportScreen]

    def bindings(self) -> list:
        return [
            ("RoundDetailScreen", "h", "hole_view", "Hole View"),
            ("CourseDetailScreen", "h", "hole_view", "Hole View"),
            ("CourseDetailScreen", "g", "geometry", "Geometry"),
            ("CourseDetailScreen", "p", "pdf_export", "Export PDF"),
        ]

    def css(self) -> str:
        path = Path(__file__).parent / "cartographer.tcss"
        return path.read_text() if path.exists() else ""

    def settings_schema(self) -> dict:
        return {
            "cartographer.yardage_arcs": True,
            "cartographer.yardage_arc_distances": [100, 125, 150, 175, 200],
            "cartographer.green_heightmap": True,
            "cartographer.green_contours": True,
            "cartographer.green_arrows": True,
        }

    def on_course_saved(self, course_name: str, course_data: dict) -> None:
        pass

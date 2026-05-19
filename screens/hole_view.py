# plugins/cartographer/screens/hole_view.py
"""HoleViewScreen — single hole diagram view for PinSheet."""
from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center
from textual.screen import Screen
from textual.widgets import Footer, Header, LoadingIndicator, Static


class HoleViewScreen(Screen):
    """Shows the hole diagram for a single hole of a course."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
    ]

    def __init__(self, course_name: str, hole_number: int, **kwargs):
        super().__init__(**kwargs)
        self._course_name = course_name
        self._hole_number = hole_number

    def compose(self) -> ComposeResult:
        yield Header()
        yield Center(LoadingIndicator(), id="hole-loading")
        yield Center(Static("", id="hole-svg-widget"), id="hole-svg-container")
        yield Footer()

    def on_mount(self) -> None:
        self.title = f"Hole {self._hole_number} — {self._course_name}"
        self.query_one("#hole-svg-container").display = False
        self._render_hole()

    @work(thread=True)
    def _render_hole(self) -> None:
        from cartographer.renderer import render_hole_svg
        from cartographer.data import load_courses_geo

        courses_geo = load_courses_geo()
        if self._course_name not in courses_geo:
            svg = ""
        else:
            svg = render_hole_svg(self._course_name, self._hole_number)

        self.app.call_from_thread(self._display_result, svg)

    def _display_result(self, svg: str) -> None:
        self.query_one("#hole-loading").display = False
        container = self.query_one("#hole-svg-container")
        widget = self.query_one("#hole-svg-widget", Static)

        if not svg:
            widget.update(
                f"No course geometry available for {self._course_name}.\n\n"
                f'Run: python -m cartographer.tagger "{self._course_name}" to add it.'
            )
        else:
            widget.update(f"[Hole diagram: {self._course_name} hole {self._hole_number}]\n\n"
                          f"SVG rendered ({len(svg)} bytes). "
                          f"textual-image display requires cairosvg and textual-image installed.")

        container.display = True

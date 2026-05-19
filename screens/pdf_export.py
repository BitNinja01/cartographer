# plugins/cartographer/screens/pdf_export.py
"""PDF export screen for Cartographer plugin."""
from __future__ import annotations

from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.screen import Screen
from textual.widgets import Static, Button, Select, Checkbox
from textual.binding import Binding


class PDFExportScreen(Screen):
    """Screen for configuring and generating PDF yardage books."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
    ]

    def __init__(self, course_name: str) -> None:
        super().__init__()
        self.course_name = course_name
        self.slot1_mode = "green_grid"
        self.slot2_mode = "stats_panel"
        self.show_calculated_stats = True

    def compose(self) -> ComposeResult:
        """Compose the export screen UI."""
        with Vertical(id="pdf-export-container"):
            yield Static(f"Export PDF: {self.course_name}", id="pdf-export-header")

            with Horizontal(id="pdf-export-controls"):
                with Vertical(id="slot-selectors"):
                    yield Static("Top slot:")
                    yield Select(
                        [
                            ("Green Grid", "green_grid"),
                            ("Stats Panel", "stats_panel"),
                            ("Notes", "notes"),
                        ],
                        value="green_grid",
                        id="slot1-select",
                    )

                    yield Static("Bottom slot:")
                    yield Select(
                        [
                            ("Green Grid", "green_grid"),
                            ("Stats Panel", "stats_panel"),
                            ("Notes", "notes"),
                        ],
                        value="stats_panel",
                        id="slot2-select",
                    )

                yield Checkbox("Show calculated stats", value=True, id="stats-checkbox")

            yield Button("Generate PDF", variant="primary", id="generate-button")
            yield Static("", id="status-widget")

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle slot selector changes."""
        if event.select.id == "slot1-select":
            self.slot1_mode = event.value
        elif event.select.id == "slot2-select":
            self.slot2_mode = event.value

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Handle stats checkbox toggle."""
        if event.checkbox.id == "stats-checkbox":
            self.show_calculated_stats = event.value

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle generate button press."""
        if event.button.id != "generate-button":
            return

        # Validate geometry data exists
        from cartographer.data import load_courses_geo
        courses_geo = load_courses_geo()
        if self.course_name not in courses_geo:
            self.app.push_screen(
                ErrorModal("No geometry data found for this course.\nRun Geometry Setup (g) first.")
            )
            return

        # Validate course data exists
        import sys
        import json
        if getattr(sys, "frozen", False):
            courses_json = Path(sys.executable).parent / "data" / "courses.json"
        else:
            courses_json = Path(__file__).parent.parent.parent.parent / "data" / "courses.json"

        if not courses_json.exists():
            self.app.push_screen(
                ErrorModal("Course data not found in PinSheet.")
            )
            return

        pinsheet_courses = json.loads(courses_json.read_text())
        if self.course_name not in pinsheet_courses:
            self.app.push_screen(
                ErrorModal(f"Course '{self.course_name}' not found in PinSheet data.")
            )
            return

        # Start generation
        self._generate_pdf()

    @work(thread=True)
    def _generate_pdf(self) -> None:
        """Generate PDF in background thread with progress updates."""
        from cartographer.pdf import generate_book
        import sys

        # Determine output directory
        if getattr(sys, "frozen", False):
            data_dir = Path(sys.executable).parent / "data"
        else:
            data_dir = Path(__file__).parent.parent.parent.parent / "data"

        output_dir = data_dir / "plugins" / "cartographer" / "export" / f"{self.course_name}_yardage_book"

        def progress_callback(current: int, total: int) -> None:
            self.app.call_from_thread(self._update_status, f"Generating page {current}/{total}...")

        try:
            generate_book(
                course_name=self.course_name,
                output_dir=output_dir,
                slot1_mode=self.slot1_mode,
                slot2_mode=self.slot2_mode,
                show_calculated_stats=self.show_calculated_stats,
                progress_callback=progress_callback,
            )
            self.app.call_from_thread(self._update_status, f"PDF generated: {output_dir}")
        except Exception as e:
            self.app.call_from_thread(
                self._show_error,
                f"PDF generation failed: {str(e)}"
            )

    def _update_status(self, message: str) -> None:
        """Update status widget from main thread."""
        status = self.query_one("#status-widget", Static)
        status.update(message)

    def _show_error(self, message: str) -> None:
        """Show error modal from main thread."""
        self.app.push_screen(ErrorModal(message))


class ErrorModal(Screen):
    """Simple error modal."""

    def __init__(self, message: str) -> None:
        super().__init__()
        self.message = message

    def compose(self) -> ComposeResult:
        with Vertical(id="error-modal"):
            yield Static(self.message, id="error-message")
            yield Button("OK", variant="primary", id="error-ok")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "error-ok":
            self.app.pop_screen()

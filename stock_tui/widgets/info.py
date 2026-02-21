from textual.widgets import Static, Label, DataTable
from textual.containers import Vertical, ScrollableContainer
from textual.reactive import reactive
from rich.text import Text

class CompanyInfo(Static):
    """A sidebar widget to display company fundamentals and description."""

    data = reactive(None)

    def compose(self):
        with ScrollableContainer(id="info-container"):
            yield Label("", id="company-name")
            yield Label("", id="company-meta")
            yield DataTable(id="fundamentals-table")
            yield Label("Description", id="desc-header")
            yield Label("", id="company-description")

    def on_mount(self):
        table = self.query_one("#fundamentals-table", DataTable)
        table.add_columns("Metric", "Value")
        table.show_header = False
        table.zebra_stripes = True

    def watch_data(self, data):
        if not data:
            return

        self.query_one("#company-name", Label).update(Text(data["name"], style="bold cyan"))

        meta = data["meta"]
        meta_text = f"{meta['sector']} | {meta['industry']} | {meta['country']}"
        self.query_one("#company-meta", Label).update(Text(meta_text, style="italic grey70"))

        table = self.query_one("#fundamentals-table", DataTable)
        table.clear()

        snapshot = data["snapshot"]
        for label, value in snapshot.items():
            table.add_row(label, value)

        self.query_one("#company-description", Label).update(data["description"])

    def update_info(self, info_data):
        self.data = info_data

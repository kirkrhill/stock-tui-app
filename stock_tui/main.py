import os
import logging
import asyncio
import warnings
import yfinance as yf
import pandas as pd
from textual import work
from textual.app import App, ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Header, Footer, Input, Label
from rich.text import Text

from utils import load_config, save_config
from widgets.watchlist import Watchlist
from widgets.chart import StockChart

# Configure logging
logging.basicConfig(filename="stock_tui.log", level=logging.INFO, filemode="w")
for logger_name in ["yfinance", "peewee", "matplotlib", "urllib3", "asyncio"]:
    logging.getLogger(logger_name).setLevel(logging.WARNING)
warnings.filterwarnings("ignore")

class StockTuiApp(App):
    TITLE = "Stock TUI (Alpha)"

    CSS = """
    Screen {
        padding: 0;
        margin: 0;
    }

    #sidebar {
        width: 30;
        height: 100%;
        border-right: solid grey;
        background: $surface;
    }

    #sidebar.hidden {
        display: none;
    }

    #watchlist-header {
        width: 100%;
        text-align: center;
        text-style: bold;
        padding: 1;
        background: $primary;
        color: white;
    }

    #watchlist-list {
        height: 1fr;
    }

    #main-content {
        width: 1fr;
        height: 100%;
    }

    StockChart {
        width: 100%;
        height: 1fr; 
        border: solid green;
        overflow: hidden;
        content-align: left top;
        padding: 0;
        margin: 0;
    }
    
    Input {
        margin: 0 1;
        width: 40;
    }

    #notifications {
        width: 1fr;
        height: 3;
        content-align: left middle;
        padding: 0 1;
        color: $text;
        text-style: italic;
    }

    #top-bar {
        height: auto;
        dock: top;
        background: $surface;
    }
    """

    BINDINGS = [
        ("ctrl+b", "toggle_block", "Block Mode"),
        ("ctrl+h", "toggle_image", "Image Mode"),
        ("ctrl+t", "toggle_debug", "Test Graphics"),
        ("ctrl+w", "toggle_sidebar", "Watchlist"),
        ("ctrl+g", "toggle_show_image", "Hide/Show Image"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield Watchlist(id="sidebar")
            with Vertical(id="main-content"):
                with Horizontal(id="top-bar"):
                    yield Input(placeholder="Enter Ticker (e.g. AAPL, BTC-USD)", id="ticker")
                    yield Label("", id="notifications")
                yield StockChart(id="chart")
        yield Footer()

    def on_mount(self):
        config = load_config()
        self.history = config.get("history", [])
        
        chart = self.query_one("#chart", StockChart)
        chart.update(
            Text(
                "Welcome! Enter a stock symbol above.\n\n"
                "Controls:\n"
                " - ENTER: Fetch data\n"
                " - CTRL+B: Switch to Block (Text) Mode\n"
                " - CTRL+H: Switch to Image (High-Res) Mode\n"
                " - CTRL+T: Test Terminal Graphics Support\n"
                " - CTRL+W: Toggle Watchlist Sidebar\n"
                " - CTRL+G: Toggle High-Res Image Visibility"
            )
        )

    def notify(self, message: str, title: str = "", severity: str = "information", timeout: float = 3.0):
        """Override notify to use our custom notification area and disable popups."""
        try:
            notification_label = self.query_one("#notifications", Label)
            notification_label.update(message)
            if severity == "error":
                notification_label.styles.color = "red"
            elif severity == "warning":
                notification_label.styles.color = "yellow"
            else:
                notification_label.styles.color = "green"

            async def clear_message():
                await asyncio.sleep(timeout)
                if str(notification_label.renderable) == message:
                    notification_label.update("")
            
            asyncio.create_task(clear_message())
        except Exception as e:
            logging.error(f"Notification failed: {e}")

    def action_toggle_sidebar(self):
        sidebar = self.query_one("#sidebar")
        sidebar.toggle_class("hidden")
        self.query_one("#chart").trigger_render()

    def action_toggle_block(self):
        self.query_one("#chart", StockChart).set_mode("block")
        self.notify("Switched to Block Mode")

    def action_toggle_image(self):
        self.query_one("#chart", StockChart).set_mode("image")
        self.notify("Switched to Image Mode")

    def action_toggle_debug(self):
        self.query_one("#chart", StockChart).set_mode("debug")
        self.notify("Running Graphics Test...")

    def action_toggle_show_image(self):
        chart = self.query_one("#chart", StockChart)
        chart.show_image = not chart.show_image
        status = "Shown" if chart.show_image else "Hidden"
        self.notify(f"High-Res Image {status}")

    @work(exclusive=True, thread=True)
    def fetch_stock_data(self, symbol: str):
        input_widget = self.query_one("#ticker", Input)
        if input_widget.value.upper() != symbol.upper():
            self.call_from_thread(setattr, input_widget, "value", symbol)

        chart_widget = self.query_one("#chart", StockChart)
        try:
            self.notify(f"Fetching {symbol}...")
            df = yf.download(symbol, period="6mo", interval="1d", progress=False)
            if df.empty:
                self.notify(f"No data found for '{symbol}'", severity="error")
                return
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)
            required = ["Open", "High", "Low", "Close"]
            if not all(col in df.columns for col in required):
                self.notify(f"Invalid data format for {symbol}", severity="error")
                return
            self.call_from_thread(chart_widget.update_data, df, symbol)
        except Exception as e:
            logging.exception("Data fetch failed")
            self.notify(f"Fetch Error: {e}", severity="error")

    async def on_input_submitted(self, message: Input.Submitted):
        symbol = message.value.strip().upper()
        if symbol:
            config = load_config()
            history = config.get("history", [])
            pinned = config.get("pinned", [])
            if symbol in pinned:
                pass
            else:
                if symbol in history:
                    history.remove(symbol)
                first_pinned_idx = len(history)
                for i, s in enumerate(history):
                    if s in pinned:
                        first_pinned_idx = i
                        break
                history.insert(first_pinned_idx, symbol)
            if len(history) > 100:
                history.pop(0)
            save_config({"history": history})
            try:
                self.query_one("#sidebar", Watchlist).refresh_list()
            except:
                pass
            self.fetch_stock_data(symbol)

    def on_key(self, event) -> None:
        input_widget = self.query_one("#ticker", Input)
        if input_widget.has_focus and event.key in ("up", "down"):
            config = load_config()
            visual_history = list(reversed(config.get("history", [])))
            if not visual_history:
                return
            current_symbol = input_widget.value.strip().upper()
            try:
                current_idx = visual_history.index(current_symbol)
            except ValueError:
                current_idx = -1
            if event.key == "up":
                new_idx = (current_idx - 1) % len(visual_history)
            else:
                new_idx = (current_idx + 1) % len(visual_history)
            new_symbol = visual_history[new_idx]
            input_widget.value = new_symbol
            input_widget.cursor_position = len(new_symbol)
            self.fetch_stock_data(new_symbol)
            event.prevent_default()
            event.stop()
        elif event.key == "ctrl+w":
            self.action_toggle_sidebar()
            event.prevent_default()
            event.stop()
        elif event.key == "ctrl+g":
            self.action_toggle_show_image()
            event.prevent_default()
            event.stop()

    def on_input_changed(self, event: Input.Changed) -> None:
        if " " in event.value:
            input_widget = self.query_one("#ticker", Input)
            input_widget.value = ""

if __name__ == "__main__":
    StockTuiApp().run()

import os
import logging
import asyncio
import threading
import warnings
import yfinance as yf
import pandas as pd
from textual import work
from textual.app import App, ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Header, Footer, Input, Label, TabbedContent, TabPane
from rich.text import Text

from utils import load_config, save_config, fetch_finviz_data
from widgets.watchlist import Watchlist
from widgets.chart import StockChart
from widgets.info import CompanyInfo

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("stock_tui.log", mode="w"),
        logging.StreamHandler()
    ]
)
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
        width: 50;
        height: 100%;
        border-right: solid grey;
        background: $surface;
    }

    #sidebar.hidden {
        display: none;
    }

    /* TabbedContent in sidebar */
    #sidebar TabbedContent {
        height: 100%;
    }

    #sidebar TabPane {
        padding: 0;
    }

    #main-content {
        width: 1fr;
        height: 100%;
    }

    #info-container {
        padding: 1;
        width: 100%;
    }

    #company-name {
        margin-bottom: 1;
    }

    #company-meta {
        margin-bottom: 1;
    }

    #fundamentals-table {
        height: auto;
        max-height: 20;
        margin-bottom: 1;
    }

    #desc-header {
        text-style: bold underline;
        margin-bottom: 1;
    }

    #company-description {
        height: auto;
        width: 100%;
        content-align: left top;
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
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with Vertical(id="sidebar"):
                with TabbedContent():
                    with TabPane("Watchlist", id="tab-watchlist"):
                        yield Watchlist(id="watchlist")
                    with TabPane("Info", id="tab-info"):
                        yield CompanyInfo(id="info")
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
                " - CTRL+T: Test Terminal Graphics Support"
            )
        )


    def notify(self, message: str, title: str = "", severity: str = "information", timeout: float = 3.0):
        """Override notify to use our custom notification area and disable popups."""
        def update_ui():
            try:
                notification_label = self.query_one("#notifications", Label)
                notification_label.update(message)
                # Store the message locally on the widget to check before clearing
                notification_label._current_msg = message

                if severity == "error":
                    notification_label.styles.color = "red"
                elif severity == "warning":
                    notification_label.styles.color = "yellow"
                else:
                    notification_label.styles.color = "green"

                async def clear_message():
                    await asyncio.sleep(timeout)
                    try:
                        # Only clear if it's still the same message
                        if getattr(notification_label, "_current_msg", "") == message:
                            notification_label.update("")
                    except:
                        pass

                asyncio.create_task(clear_message())
            except Exception as e:
                logging.error(f"Notification UI update failed: {e}")

        # Check if we are running in the main thread (event loop thread)
        if self._thread_id == threading.get_ident():
            update_ui()
        else:
            self.call_from_thread(update_ui)


    def action_toggle_block(self):
        self.query_one("#chart", StockChart).set_mode("block")
        self.notify("Switched to Block Mode")

    def action_toggle_image(self):
        self.query_one("#chart", StockChart).set_mode("image")
        self.notify("Switched to Image Mode")

    def action_toggle_debug(self):
        self.query_one("#chart", StockChart).set_mode("debug")
        self.notify("Running Graphics Test...")

    @work(exclusive=True, thread=True)
    def fetch_stock_data(self, symbol: str):
        chart_widget = self.query_one("#chart", StockChart)
        input_widget = self.query_one("#ticker", Input)

        # Sync input value if fetched from watchlist
        if input_widget.value.upper() != symbol.upper():
            self.call_from_thread(setattr, input_widget, "value", symbol)

        try:
            self.notify(f"Fetching {symbol}...")

            # Fetch YFinance data
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

            # Update UI components
            self.call_from_thread(chart_widget.update_data, df, symbol)

            # Start Finviz fetch in another worker so it doesn't block
            self.fetch_extra_info(symbol)

        except Exception as e:
            logging.exception("Data fetch failed")
            self.notify(f"Fetch Error: {e}", severity="error")

    @work(exclusive=True, thread=True)
    def fetch_extra_info(self, symbol: str):
        info_widget = self.query_one("#info", CompanyInfo)
        try:
            finviz_data = fetch_finviz_data(symbol)
            if finviz_data:
                self.call_from_thread(info_widget.update_info, finviz_data)
            else:
                self.notify(f"Finviz data unavailable for {symbol}", severity="warning")
        except Exception as e:
            logging.error(f"Finviz fetch failed: {e}")


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
                self.query_one("#watchlist", Watchlist).refresh_list()
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

    def on_input_changed(self, event: Input.Changed) -> None:
        if " " in event.value:
            input_widget = self.query_one("#ticker", Input)
            input_widget.value = ""

if __name__ == "__main__":
    StockTuiApp().run()

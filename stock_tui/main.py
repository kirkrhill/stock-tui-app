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
from textual.widgets import Header, Footer, Input, Label, TabbedContent, TabPane, Button
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

    .history-button {
        min-width: 6;
        width: 6;
        height: 3;
        margin: 0 1;
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
        height: 3;
        dock: top;
        background: $surface;
    }
    """

    BINDINGS = [
        ("ctrl+b", "toggle_block", "Block Mode"),
        ("ctrl+h", "toggle_image", "Image Mode"),
        ("+", "increase_history", "Increase History"),
        ("-", "decrease_history", "Decrease History"),
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
                    yield Button("+", id="history-increase", classes="history-button")
                    yield Button("-", id="history-decrease", classes="history-button")
                    yield Button("3m", id="timeframe-3m", classes="history-button")
                    yield Button("6m", id="timeframe-6m", classes="history-button")
                    yield Button("1y", id="timeframe-1y", classes="history-button")
                    yield Button("2y", id="timeframe-2y", classes="history-button")
                    yield Label("", id="notifications")
                yield StockChart(id="chart")
        yield Footer()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._thread_id = None

    def on_mount(self):
        self._thread_id = threading.get_ident()
        config = load_config()
        self.history = config.get("history", [])


        chart = self.query_one("#chart", StockChart)
        chart.update(
            Text(
                "Welcome! Enter a stock symbol above.\n\n"
                "Controls:\n"
                " - ENTER: Fetch data\n"
                " - CTRL+B: Switch to Block (Text) Mode\n"
                " - CTRL+H: Switch to Image (High-Res) Mode"
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
        if self._thread_id and self._thread_id == threading.get_ident():
            update_ui()
        else:
            self.call_from_thread(update_ui)


    def action_toggle_block(self):
        # Explicitly clear terminal graphics when moving to block mode
        self.console.file.write("\x1b_Ga=d,d=a,q=2\x1b\\")
        self.console.file.flush()
        self.query_one("#chart", StockChart).set_mode("block")
        self.notify("Switched to Block Mode")

    def action_toggle_image(self):
        # Explicitly clear terminal graphics before moving to image mode
        self.console.file.write("\x1b_Ga=d,d=a,q=2\x1b\\")
        self.console.file.flush()
        self.query_one("#chart", StockChart).set_mode("image")
        self.notify("Switched to Image Mode")

    @work(exclusive=True, thread=True)
    def fetch_stock_data(self, symbol: str, period: str = "2y"):
        chart_widget = self.query_one("#chart", StockChart)
        input_widget = self.query_one("#ticker", Input)

        # Sync input value if fetched from watchlist
        if input_widget.value.upper() != symbol.upper():
            self.call_from_thread(setattr, input_widget, "value", symbol)

        try:
            self.notify(f"Fetching {symbol} ({period})...")

            # Fetch YFinance data
            df = yf.download(symbol, period=period, interval="1d", progress=False)

            if df.empty:
                self.notify(f"No data found for '{symbol}'", severity="error")
                return

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)

            required = ["Open", "High", "Low", "Close"]
            if not all(col in df.columns for col in required):
                self.notify(f"Invalid data format for {symbol}", severity="error")
                return

            # Store the current period on the widget for re-fetch logic
            chart_widget.current_period = period

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


    def get_period_for_days(self, days: int) -> str:
        """Calculate the minimum period needed for a given number of trading days."""
        # 21 trading days per month approx
        if days <= 126: return "6mo"
        if days <= 252: return "1y"
        if days <= 504: return "2y"
        if days <= 1260: return "5y"
        if days <= 2520: return "10y"
        return "max"

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

            # Use current history length to determine period
            chart_widget = self.query_one("#chart", StockChart)
            period = self.get_period_for_days(chart_widget._history_length)
            self.fetch_stock_data(symbol, period=period)

    def on_key(self, event) -> None:
        input_widget = self.query_one("#ticker", Input)

        # History navigation (Up/Down) in ticker
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

            # Use current history length to determine period
            chart_widget = self.query_one("#chart", StockChart)
            period = self.get_period_for_days(chart_widget._history_length)
            self.fetch_stock_data(new_symbol, period=period)
            event.prevent_default()
            event.stop()
            return

        # Button navigation (Left/Right)
        BUTTON_IDS = ["history-increase", "history-decrease", "timeframe-3m", "timeframe-6m", "timeframe-1y", "timeframe-2y"]
        NAV_IDS = ["ticker"] + BUTTON_IDS
        if event.key in ("left", "right"):
            focused = self.focused
            if focused and focused.id in BUTTON_IDS:
                idx = NAV_IDS.index(focused.id)
                if event.key == "right":
                    new_idx = (idx + 1) % len(NAV_IDS)
                else:
                    new_idx = (idx - 1) % len(NAV_IDS)
                self.query_one(f"#{NAV_IDS[new_idx]}").focus()
                event.prevent_default()
                event.stop()

    def action_increase_history(self):
        """Increase chart history length by 10 days, fetching more if needed."""
        try:
            chart_widget = self.query_one("#chart", StockChart)
            if chart_widget.chart_data is not None:
                # Returns True if it reached the data limit
                at_limit = chart_widget.increase_history_length()

                if at_limit:
                    next_p = self.get_period_for_days(chart_widget._history_length + 10)
                    if next_p != getattr(chart_widget, "current_period", ""):
                        self.notify(f"Fetching more data ({next_p})...")
                        # We pre-emptively increment _history_length
                        # so that when update_data is called, it already has the new length.
                        chart_widget._history_length += 10
                        self.fetch_stock_data(chart_widget.symbol, period=next_p)
                    else:
                        self.notify("Max historical data reached", severity="warning")
                else:
                    self.notify(f"History increased to {chart_widget._history_length} days")
            else:
                self.notify("Load a stock first to adjust history", severity="warning")
        except Exception as e:
            logging.error(f"Failed to increase history: {e}")

    def action_decrease_history(self):
        """Decrease chart history length by 10 days."""
        try:
            chart_widget = self.query_one("#chart", StockChart)
            if chart_widget.chart_data is not None:
                chart_widget.decrease_history_length()
                self.notify(f"History decreased to {chart_widget._history_length} days")
            else:
                self.notify("Load a stock first to adjust history", severity="warning")
        except Exception as e:
            logging.error(f"Failed to decrease history: {e}")

    def on_button_pressed(self, event) -> None:
        """Handle button presses for history adjustment."""
        logging.info(f"Button pressed: {event.button.id}")
        if event.button.id == "history-increase":
            self.action_increase_history()
        elif event.button.id == "history-decrease":
            self.action_decrease_history()
        elif event.button.id.startswith("timeframe-"):
            timeframe = event.button.id.split("-")[1]
            mapping = {"3m": 63, "6m": 126, "1y": 252, "2y": 504}
            days = mapping.get(timeframe)
            if days:
                self.action_set_timeframe(days, timeframe)

    def action_set_timeframe(self, days: int, label: str):
        """Instantly set the chart to a specific timeframe (3m, 6m, 1y, 2y)."""
        try:
            chart_widget = self.query_one("#chart", StockChart)
            if chart_widget.chart_data is None:
                self.notify("Load a stock first to adjust timeframe", severity="warning")
                return

            # Check if we have enough data
            if len(chart_widget.chart_data) < days + 10:
                # Trigger a larger fetch if needed
                next_p = self.get_period_for_days(days)
                self.notify(f"Fetching more data for {label} view...")
                # We update the history length requested so it shows after fetch
                chart_widget._history_length = days
                self.fetch_stock_data(chart_widget.symbol, period=next_p)
            else:
                chart_widget.set_history_length(days)
                self.notify(f"Timeframe set to {label} ({days} days)")
        except Exception as e:
            logging.error(f"Failed to set timeframe: {e}")

    def on_input_changed(self, event: Input.Changed) -> None:
        if " " in event.value:
            input_widget = self.query_one("#ticker", Input)
            input_widget.value = ""

if __name__ == "__main__":
    StockTuiApp().run()

import base64
import os
import io
import logging
import asyncio
import time
import matplotlib
# Force non-interactive backend immediately
matplotlib.use("Agg")

import mplfinance as mpf
import pandas as pd
import plotext as plt
from rich.segment import Segment
from rich.text import Text
from rich.console import Group
from textual.widgets import Static
from textual.reactive import reactive

class ZeroWidthSegment(Segment):
    """A segment that has a cell length of 0, used for escape codes."""
    @property
    def cell_length(self):
        return 0

class ImageRenderable:
    """A renderable that emits a graphics protocol sequence and reserves space."""
    def __init__(
        self,
        protocol_code: str,
        height: int,
        caption: str = "",
    ):
        self.protocol_code = protocol_code
        self.height = height
        self.caption = caption

    def __rich_console__(self, console, options):
        # We don't clear here to avoid flickering during Textual's frequent repaints
        # The terminal protocol with a=T and a specific ID handles replacement.

        # 1. Emit the escape sequence
        yield ZeroWidthSegment(self.protocol_code)


        if self.caption:
            yield Segment(f" {self.caption}\n")
            start = 1
        else:
            start = 0

        # 2. Emit newlines to reserve space
        for i in range(start, self.height):
            if i < self.height - 1:
                yield Segment("\n")
            else:
                yield Segment(" ")

class ClearGraphics:
    """A simple renderable that clears all terminal images."""
    def __rich_console__(self, console, options):
        yield ZeroWidthSegment("\x1b_Ga=d,d=a,q=2\x1b\\")

class StockChart(Static):
    """
    A widget to display the stock chart.
    Supports both text (block) and image (Kitty/iTerm) rendering.
    """
    symbol = reactive("")
    render_mode = reactive("image")

    def __init__(self, **kwargs):
        self.chart_data = None
        self._temp_file = None
        self._last_shm = None
        super().__init__(**kwargs)

    def on_mount(self):
        if self.chart_data is not None:
            self.trigger_render()

    def get_chart_height(self):
        if self.content_size.height > 0:
            return self.content_size.height
        return 28

    def on_resize(self, event):
        self.trigger_render()

    def update_data(self, df, symbol):
        self.chart_data = df
        self.symbol = symbol
        # Explicitly trigger render
        self.trigger_render()

    def set_mode(self, mode):
        self.render_mode = mode

    def trigger_render(self):
        # We don't clear the console directly here to avoid race conditions with Textual
        # The replacement will happen through the ID 'i=1' in the graphics protocol
        self.update(Text("Rendering...", style="italic grey50"))
        self.run_worker(self.generate_render(), exclusive=True)

    def watch_symbol(self, symbol):
        self.trigger_render()

    def watch_render_mode(self, mode):
        self.trigger_render()

    async def generate_render(self):
        try:
            if self.render_mode == "block":
                if self.chart_data is None:
                    new_renderable = Text("Enter a stock ticker to see the chart.")
                else:
                    ansi_text = await asyncio.to_thread(self._get_block_ansi)
                    new_renderable = Text.from_ansi(ansi_text)

                # Always clear graphics when in block mode
                self.update(Group(ClearGraphics(), new_renderable))
            else:
                if self.chart_data is None:
                    # Clear graphics when no data is loaded
                    self.update(Group(ClearGraphics(), Text("No data loaded. Enter a ticker first.")))
                else:
                    self.app.notify(f"Generating image for {self.symbol}...")
                    new_renderable = await asyncio.to_thread(self._get_image_renderable)
                    self.update(new_renderable)
        except Exception as e:
            logging.exception("Render failed")
            self.update(Text(f"Render failed: {e}"))

    def _get_block_ansi(self):
        plt.clear_figure()
        plt.theme("dark")
        # plotext.candlestick expects: dates, {Open, High, Low, Close}
        subset = self.chart_data.tail(60)
        dates = subset.index.strftime("%d/%m/%Y").tolist()
        plt.date_form("d/m/Y")
        plt.candlestick(dates, {
            "Open": subset["Open"].tolist(),
            "High": subset["High"].tolist(),
            "Low": subset["Low"].tolist(),
            "Close": subset["Close"].tolist(),
        })
        plt.title(f"{self.symbol} - Daily (Last 60 Days)")
        plt.plotsize(100, self.get_chart_height())
        return plt.build()

    def _get_image_renderable(self):
        mc = mpf.make_marketcolors(up="#26a69a", down="#ef5350", edge="inherit", wick="inherit", volume="in")
        s = mpf.make_mpf_style(marketcolors=mc, base_mpf_style="nightclouds", gridstyle=":")
        try:
            df = self.chart_data
            if df is None: return Text("No data available.")
            char_width = self.content_size.width
            char_height = self.content_size.height
            if char_width == 0: char_width = 80
            if char_height == 0: char_height = 24
            width = (char_width * 0.12)
            height = (char_height * 0.25)
            x_limit = (0, len(df))

            # Create image in memory instead of saving to file
            img_buffer = io.BytesIO()
            mpf.plot(df, type="candle", style=s, volume=True, savefig=dict(fname=img_buffer, format="png"), figsize=(width, height), tight_layout=True, xlim=x_limit)
            img_buffer.seek(0)

            # Log for debugging
            # logging.debug(f"Generated image buffer size: {len(img_buffer.getvalue())}")

            return self._create_image_renderable(img_buffer, caption=f"GRAPHIC: {self.symbol} ({char_width}x{char_height})", width=char_width, height=char_height)
        except Exception as e:
            logging.error(f"Image generation failed: {e}")
            import traceback
            traceback.print_exc()
            return Text(f"Error generating image: {e}")

    def _create_image_renderable(self, img_buffer, caption="", width=None, height=None):
        # Using t=f (local file) but storing it in /dev/shm for memory performance
        img_data = img_buffer.getvalue()

        # 1. Create a unique name for the temporary file in shared memory
        shm_name = f"stock_tui_chart_{int(time.time() * 1000)}.png"
        shm_path = f"/dev/shm/{shm_name}"

        try:
            # 2. Write the data to /dev/shm
            with open(shm_path, "wb") as f:
                f.write(img_data)

            # 3. Base64 encode the full path for t=f
            b64_path = base64.b64encode(shm_path.encode("ascii")).decode("ascii")

            # Record this for cleanup fallback
            self._last_shm_path = shm_path
        except Exception as e:
            logging.error(f"Failed to write to /dev/shm: {e}")
            return Text(f"Image Storage Error: {e}")

        reserve_height = self.get_chart_height()
        display_c = width if width else ""
        display_r = height if height else ""

        # a=T: Transmit and display
        # f=100: PNG
        # t=f: Local file
        # Use a unique ID for each new image to avoid race conditions with replacement
        img_id = int(time.time() * 1000) % 10000 + 1
        code = f"\x1b_Gf=100,a=T,t=f,i={img_id},q=1,c={display_c},r={display_r};{b64_path}\x1b\\"

        # Log the escape sequence for debugging
        visible_code = code.replace("\x1b", "\\x1b")
        logging.info(f"Kitty Escape Sequence: {visible_code}")

        return ImageRenderable(code, reserve_height, caption=caption)

    def on_unmount(self):
        # Cleanup any lingering shared memory files
        if hasattr(self, "_last_shm_path") and self._last_shm_path:
            try:
                if os.path.exists(self._last_shm_path):
                    os.remove(self._last_shm_path)
            except Exception as e:
                logging.error(f"Cleanup failed: {e}")

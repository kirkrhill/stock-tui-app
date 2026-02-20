import base64
import os
import logging
import asyncio
import matplotlib
# Force non-interactive backend immediately
matplotlib.use("Agg")

import mplfinance as mpf
import pandas as pd
import plotext as plt
from rich.segment import Segment
from rich.text import Text
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
        clear_code: str = "",
    ):
        self.protocol_code = protocol_code
        self.height = height
        self.caption = caption
        self.clear_code = clear_code

    def __rich_console__(self, console, options):
        if self.clear_code:
            yield ZeroWidthSegment(self.clear_code)
        yield ZeroWidthSegment(self.protocol_code)
        if self.caption:
            yield Segment(f" {self.caption}\n")
            start = 1
        else:
            start = 0
        for i in range(start, self.height):
            if i < self.height - 1:
                yield Segment("\n")
            else:
                yield Segment(" ")

class StockChart(Static):
    """
    A widget to display the stock chart.
    Supports both text (block) and image (Kitty/iTerm) rendering.
    """
    show_image = reactive(True)
    symbol = reactive("")
    render_mode = reactive("image")

    def __init__(self, **kwargs):
        self.chart_data = None
        self._temp_file = None
        super().__init__(**kwargs)

    def get_chart_height(self):
        if self.content_size.height > 0:
            return self.content_size.height
        return 28

    def on_resize(self, event):
        self.trigger_render()

    def update_data(self, df, symbol):
        self.chart_data = df
        self.symbol = symbol

    def set_mode(self, mode):
        self.render_mode = mode

    def trigger_render(self):
        self.update(Text("Rendering...", style="italic grey50"))
        self.run_worker(self.generate_render(), exclusive=True)

    def watch_symbol(self, symbol):
        self.trigger_render()

    def watch_render_mode(self, mode):
        self.trigger_render()

    def watch_show_image(self, show):
        self.trigger_render()

    async def generate_render(self):
        try:
            if self.render_mode == "block":
                if self.chart_data is None:
                    new_renderable = Text("Enter a stock ticker to see the chart.")
                else:
                    ansi_text = await asyncio.to_thread(self._get_block_ansi)
                    new_renderable = Text.from_ansi(ansi_text)
            elif self.render_mode == "debug":
                new_renderable = await asyncio.to_thread(self._get_debug_renderable)
            else:
                if self.chart_data is None:
                    new_renderable = Text("No data loaded. Enter a ticker first.")
                else:
                    new_renderable = await asyncio.to_thread(self._get_image_renderable)
            self.update(new_renderable)
        except Exception as e:
            logging.exception("Render failed")
            self.update(Text(f"Render failed: {e}"))

    def _get_block_ansi(self):
        plt.clear_figure()
        plt.theme("dark")
        subset = self.chart_data.tail(60)
        dates = subset.index.strftime("%d/%m/%Y").tolist()
        plt.date_form("d/m/Y")
        plt.candlestick(dates, subset.to_dict("list"))
        plt.title(f"{self.symbol} - Daily (Last 60 Days)")
        plt.plotsize(100, self.get_chart_height())
        return plt.build()

    def _get_debug_renderable(self):
        path = os.path.abspath("stock_tui/test_image.png")
        if not os.path.exists(path):
            path = os.path.abspath("test_image.png")
        if os.path.exists(path):
            return self._create_image_renderable(path, caption="DEBUG: 100x100 WHITE SQUARE")
        return Text("Debug image (test_image.png) not found.")

    def _get_image_renderable(self):
        path = os.path.abspath("stock_tui/current_chart.png")
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
            mpf.plot(df, type="candle", style=s, volume=True, savefig=dict(fname=path, format="png"), figsize=(width, height), tight_layout=True, xlim=x_limit)
            return self._create_image_renderable(path, caption=f"GRAPHIC: {self.symbol} ({char_width}x{char_height})", width=char_width, height=char_height)
        except Exception as e:
            logging.error(f"Image generation failed: {e}")
            return Text(f"Error generating image: {e}")

    def _create_image_renderable(self, path, caption="", width=None, height=None):
        abs_path = os.path.abspath(path)
        b64_path = base64.b64encode(abs_path.encode("utf-8")).decode("ascii")
        term_program = os.environ.get("TERM_PROGRAM", "")
        if "kitty" in os.environ.get("TERM", "").lower(): term_program = "kitty"
        protocol = os.environ.get("GRAPHICS_PROTOCOL", "").lower()
        reserve_height = self.get_chart_height()
        clear_code = ""
        if "iTerm" in term_program or protocol == "iterm":
            with open(abs_path, "rb") as f:
                b64_content = base64.b64encode(f.read()).decode("ascii")
            code = f"\x1b]1337;File=inline=1;width=auto;height=auto:{b64_content}\a"
            return ImageRenderable(code, reserve_height, caption=caption)
        else:
            clear_code = "\x1b_Ga=d,d=a,q=2\x1b\\"
            display_c = width if width else ""
            display_r = height if height else ""
            if not self.show_image:
                return ImageRenderable("", reserve_height, caption=caption + " (IMAGE HIDDEN)", clear_code=clear_code)
            code = f"\x1b_Gf=100,a=T,t=f,i=1,q=2,c={display_c},r={display_r};{b64_path}\x1b\\"
            return ImageRenderable(code, reserve_height, caption=caption, clear_code=clear_code)

    def on_unmount(self):
        if self._temp_file and os.path.exists(self._temp_file):
            try: os.remove(self._temp_file)
            except: pass

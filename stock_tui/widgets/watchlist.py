from textual import events
from textual.widgets import Static, ListView, ListItem, Label
from utils import load_config, save_config

class Watchlist(Static):
    """A widget to display and manage the stock ticker history."""

    def compose(self):
        yield Label("WATCHLIST", id="watchlist-header")
        yield ListView(id="watchlist-list")

    def on_mount(self):
        self.refresh_list()

    def refresh_list(self):
        config = load_config()
        history = config.get("history", [])
        pinned = config.get("pinned", [])

        # Update header with count
        header = self.query_one("#watchlist-header", Label)
        header.update(f"WATCHLIST ({len(history)})")

        list_view = self.query_one("#watchlist-list", ListView)
        list_view.clear()

        # history is the canonical order, we just visually show pinned items
        # Let's ensure items are drawn from newest/top to oldest/bottom
        for symbol in reversed(history):
            is_pinned = symbol in pinned
            # Use fixed width padding for the symbol to ensure pins line up vertically
            label_text = f"{symbol:<10} 📌" if is_pinned else symbol
            label = Label(label_text)
            if is_pinned:
                label.styles.color = "cyan"
                label.styles.text_style = "bold"

            item = ListItem(label)
            item.ticker_symbol = symbol
            item.is_pinned = is_pinned
            list_view.append(item)

    def on_list_view_selected(self, message: ListView.Selected):
        if message.item:
            symbol = getattr(message.item, "ticker_symbol", "")
            if symbol:
                self.app.fetch_stock_data(symbol)

    def on_key(self, event: events.Key) -> None:
        list_view = self.query_one("#watchlist-list", ListView)
        if not list_view.has_focus:
            return

        if (event.key == "d" or event.key == "delete") and list_view.index is not None:
            index = list_view.index
            if 0 <= index < len(list_view.children):
                item = list_view.children[index]
                symbol = getattr(item, "ticker_symbol", "")
                if symbol:
                    config = load_config()
                    history = config.get("history", [])
                    if symbol in history:
                        history.remove(symbol)
                        save_config({"history": history})
                        self.refresh_list()
                        # Keep index if possible
                        list_view.index = min(index, len(list_view.children) - 1)
                event.prevent_default()

        elif event.key == "K":  # Shift+Up
            index = list_view.index
            if index is not None and index > 0:
                config = load_config()
                history = config.get("history", [])
                # history is reversed in the UI
                hist_idx = len(history) - 1 - index
                if 0 <= hist_idx < len(history) - 1:
                    history[hist_idx], history[hist_idx + 1] = (
                        history[hist_idx + 1],
                        history[hist_idx],
                    )
                    save_config({"history": history})
                    self.refresh_list()
                    list_view.index = index - 1
                event.prevent_default()

        elif event.key == "J":  # Shift+Down
            index = list_view.index
            if index is not None and index < len(list_view.children) - 1:
                config = load_config()
                history = config.get("history", [])
                hist_idx = len(history) - 1 - index
                if 1 <= hist_idx < len(history):
                    history[hist_idx], history[hist_idx - 1] = (
                        history[hist_idx - 1],
                        history[hist_idx],
                    )
                    save_config({"history": history})
                    self.refresh_list()
                    list_view.index = index + 1
                event.prevent_default()

        elif event.key == "p":
            index = list_view.index
            if index is not None and 0 <= index < len(list_view.children):
                item = list_view.children[index]
                symbol = getattr(item, "ticker_symbol", "")
                if symbol:
                    config = load_config()
                    history = config.get("history", [])
                    pinned = config.get("pinned", [])

                    if symbol in pinned:
                        # Unpin
                        pinned.remove(symbol)
                        # Move to top of unpinned section
                        if symbol in history:
                            history.remove(symbol)

                        first_pinned_idx = 0
                        for i, s in enumerate(history):
                            if s in pinned:
                                first_pinned_idx = i
                                break
                        else:
                            first_pinned_idx = len(history)

                        history.insert(first_pinned_idx, symbol)
                    else:
                        # Pin
                        pinned.append(symbol)
                        if symbol in history:
                            history.remove(symbol)

                        first_pinned_idx = len(history)
                        for i, s in enumerate(history):
                            if s in pinned:
                                first_pinned_idx = i
                                break
                        history.insert(first_pinned_idx, symbol)

                    save_config({"history": history, "pinned": pinned})
                    self.refresh_list()
                    # Keep index if possible
                    list_view.index = index
                event.prevent_default()

        elif event.key in "123456789":
            target_index = int(event.key) - 1
            current_index = list_view.index
            if current_index is not None:
                config = load_config()
                history = config.get("history", [])
                if target_index < len(history) and current_index != target_index:
                    # history is reversed in UI
                    symbol = history.pop(len(history) - 1 - current_index)
                    history.insert(len(history) - target_index, symbol)
                    save_config({"history": history})
                    self.refresh_list()
                    list_view.index = target_index
                event.prevent_default()

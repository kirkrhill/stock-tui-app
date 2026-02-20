# Stock TUI (Alpha)

A Python-based Terminal User Interface (TUI) application for viewing live stock market charts. This application features a unique dual-rendering system that supports both traditional text-based "block" charts and high-resolution graphical charts using the Kitty Graphics Protocol.

## Key Features

- **Live Data**: Fetches real-time stock data from Yahoo Finance via the `yfinance` library.
- **Persistent Watchlist**: A dedicated sidebar tracks your search history and allows you to build a curated list of favorite stocks.
- **Smart Pinning**: Pin important tickers to the top of your list with a single keypress. Pinned items are visually highlighted (📌) and kept in your preferred order.
- **Adaptive High-Res Mode**: Graphical charts automatically scale to match the size of your terminal window and respond instantly to window resizing.
- **Inline Notifications**: Clutter-free status and error messages appear directly in the top bar, color-coded for visibility.
- **Dual-Mode Rendering**:
  - **Image Mode (Default)**: Uses `mplfinance` to generate high-resolution PNG charts displayed directly in the terminal using the **Kitty Graphics Protocol** or **iTerm2 Inline Image Protocol**.
  - **Block Mode**: Uses `plotext` to render candlestick charts using Braille and block characters, compatible with all modern terminal emulators.
- **Multithreaded Architecture**: Data fetching and chart rendering occur in background threads to ensure a smooth, lag-free UI experience.

## Prerequisites

- **Python 3.10+**
- **Compatible Terminal** (for Image Mode):
  - [Kitty](https://sw.kovidgoyal.net/kitty/) (Recommended)
  - [Ghostty](https://ghostty.org/)
  - [WezTerm](https://wezfurlong.org/wezterm/)
  - [iTerm2](https://iterm2.com/) (Requires `GRAPHICS_PROTOCOL=iterm`)

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/stock-tui.git
   cd stock-tui
   ```
2. Set up the virtual environment and install dependencies:
   ```bash
   # This matches the structure expected by the run script
   python3 -m venv stock_tui/venv
   source stock_tui/venv/bin/activate
   pip install -r requirements.txt
   ```

## Usage

Launch the application using the provided wrapper script:
```bash
./run.sh
```

### Global Controls
- **Enter Ticker**: Type a symbol (e.g., `AAPL`, `BTC-USD`) and press **Enter**. New searches appear at the top of the unpinned list.
- **Smart Cycle**: Use **Up** and **Down** arrow keys while in the input box to cycle through tickers in the exact order shown in your Watchlist.
- **`Ctrl+W`**: Toggle the **Watchlist** sidebar visibility.
- **`Ctrl+G`**: Toggle **Image Visibility**. Temporarily hide the chart overlay to interact with the TUI underneath without shifting the layout.
- **`Ctrl+B`**: Switch to **Block Mode** (Standard text chart).
- **`Ctrl+H`**: Switch to **Image Mode** (High-resolution chart).
- **`Ctrl+T`**: Run **Graphics Test** to verify terminal protocol support.
- **`Spacebar`**: Quickly clear the ticker input box.

### Watchlist Management (Focus Sidebar)
*Navigate the list using arrow keys, then use these shortcuts:*
- **`Enter`**: Load the chart for the selected ticker.
- **`p`**: **Pin / Unpin** the selected ticker. Pinned items move to the top section.
- **`1-9`**: Move the selected ticker to that specific position in the list.
- **`Shift+K` / `Shift+J`**: Manually move the selected ticker Up or Down.
- **`d` or `Delete`**: Remove the selected ticker from your history.

## Technical Details

### Modular Architecture
The application is organized into specialized modules for better maintainability:
- `main.py`: Application entry point and layout coordination.
- `utils.py`: Configuration persistence and shared utilities.
- `widgets/chart.py`: High-resolution and text-based rendering logic.
- `widgets/watchlist.py`: Sidebar management and history synchronization.

### Dynamic Scaling
Image Mode uses a sophisticated scaling algorithm that converts terminal cell dimensions into physical inch ratios for `matplotlib`. This ensures that the generated PNG always fits perfectly within its green border container regardless of your font size or window dimensions.

### Kitty Graphics Protocol
The app utilizes the **file-based transmission** method. It generates charts as local temporary files and instructs the terminal to render them via base64-encoded path sequences. This is significantly more stable than sending raw binary data over the TTY and prevents "ghosting" or "doubling" artifacts common in other TUI graphics implementations.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

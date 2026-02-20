#!/bin/bash
# Force Kitty TERM to encourage graphics support
export TERM=xterm-kitty

# Activate virtual environment
source stock_tui/venv/bin/activate

# Run the app
python stock_tui/main.py

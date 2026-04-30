#!/usr/bin/env python3
"""Web server launcher for the Champion Draft Assist Tool."""

import sys
import os

# Load .env.local before importing app so RIOT_API_KEY is available
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '.env.local'))
    load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
except ImportError:
    pass

sys.path.insert(0, os.path.dirname(__file__))

from src.interface.web_app import run_web_app

if __name__ == '__main__':
    # When frozen by PyInstaller sys.argv may contain unexpected flags — ignore them
    try:
        port = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 5001
    except (IndexError, ValueError):
        port = 5001
    key = os.getenv('RIOT_API_KEY')
    print(f"Draft Advisor -> http://127.0.0.1:{port}")
    print(f"Data source: {'Riot API (live)' if key else 'mock data (set RIOT_API_KEY to use live)'}")
    frozen = getattr(sys, 'frozen', False)
    try:
        run_web_app(host='127.0.0.1', port=port, debug=not frozen)
    except KeyboardInterrupt:
        print("\nServer stopped.")

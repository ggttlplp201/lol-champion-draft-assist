#!/usr/bin/env python3
"""
Web server launcher for the Champion Draft Assist Tool.

This script starts the Flask web application.
"""

import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.interface.web_app import run_web_app

if __name__ == '__main__':
    import sys
    port = 5001 if len(sys.argv) == 1 else int(sys.argv[1])
    
    print("🎯 Starting Champion Draft Advisor Web Interface...")
    print(f"📍 Open your browser to: http://127.0.0.1:{port}")
    print("🛑 Press Ctrl+C to stop the server")
    print()
    
    try:
        run_web_app(host='127.0.0.1', port=port, debug=True)
    except KeyboardInterrupt:
        print("\n👋 Server stopped. Thanks for using Draft Advisor!")
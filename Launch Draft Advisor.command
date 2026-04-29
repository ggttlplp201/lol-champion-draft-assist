#!/bin/bash
# Double-click this file to start Draft Advisor in your browser.
DIR="$(cd "$(dirname "$0")" && pwd)"

# Start Flask server using the venv
"$DIR/venv/bin/python" "$DIR/web_server.py" &
SERVER_PID=$!

# Wait until the server is accepting connections
for i in $(seq 1 20); do
  curl -s "http://127.0.0.1:5001/" > /dev/null 2>&1 && break
  sleep 0.5
done

# Open in the default browser
open "http://127.0.0.1:5001/"

echo ""
echo "Draft Advisor is running at http://127.0.0.1:5001"
echo "Close this window to stop the server."
wait $SERVER_PID

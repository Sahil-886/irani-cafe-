#!/usr/bin/env bash
set -e

echo "Starting Irani Café Management System..."

if command -v python3 >/dev/null 2>&1; then
    python3 app.py
elif command -v python >/dev/null 2>&1; then
    python app.py
else
    echo ""
    echo "[ERROR] Python 3 could not be found on this system."
    echo "Please install Python 3.8 or newer."
    echo ""
    exit 1
fi
